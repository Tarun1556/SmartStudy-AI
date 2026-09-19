from typing import List, Dict
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import (
    User, Course, Topic, TopicMention, Quiz, QuizQuestion, QuizAttempt, Lecture
)
from app.schemas import (
    QuizGenerateRequest, QuizRead, QuizQuestionRead, QuizSubmitRequest, QuizAttemptRead
)
from app.services.llm import get_llm_provider

router = APIRouter()


def _check_course_owner(db, course_id, user):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if user.is_demo:
        if course.user_id != 0:
            raise HTTPException(status_code=403, detail="Not authorized")
        return course
    if course.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return course


@router.post("/generate", response_model=QuizRead)
def generate_quiz(
    req: QuizGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    _check_course_owner(db, req.course_id, current_user)

    content = []
    topics_q = db.query(Topic).filter(Topic.course_id == req.course_id)
    if req.topic_ids:
        topics_q = topics_q.filter(Topic.id.in_(req.topic_ids))
    topics = topics_q.order_by(Topic.coverage_score.desc()).limit(30).all()

    # Single batched query instead of one TopicMention query per topic (was up
    # to 30 round trips for a 30-topic quiz); group and take top-3 per topic
    # in Python since the whole batch is already bounded and in memory.
    topic_ids = [t.id for t in topics]
    mentions_by_topic: Dict[int, List[TopicMention]] = defaultdict(list)
    if topic_ids:
        all_mentions = (
            db.query(TopicMention)
            .filter(TopicMention.topic_id.in_(topic_ids))
            .order_by(TopicMention.confidence.desc())
            .all()
        )
        for m in all_mentions:
            mentions_by_topic[m.topic_id].append(m)

    for t in topics:
        for m in mentions_by_topic.get(t.id, [])[:3]:
            content.append({
                "topic_id": t.id,
                "term": t.canonical_name,
                "lecture_id": m.lecture_id,
                "content": m.context[:500],
                "definition": t.description or "",
            })

    if not content:
        raise HTTPException(status_code=400, detail="No content available to generate quiz. Upload some lectures first.")

    llm = get_llm_provider()
    questions = llm.generate_quiz_questions(content, req.num_questions, req.quiz_type)

    quiz_type_val = req.quiz_type or "mcq"
    course = db.query(Course).filter(Course.id == req.course_id).first()
    title = f"{course.name} — Practice Quiz" if course else "Practice Quiz"

    quiz = Quiz(
        course_id=req.course_id,
        title=title,
        quiz_type=quiz_type_val,
        topic_filter={"topic_ids": req.topic_ids} if req.topic_ids else None,
    )
    db.add(quiz)
    db.flush()

    for q in questions:
        options = q.get("options") or []
        db.add(QuizQuestion(
            quiz_id=quiz.id,
            question_type=q.get("question_type", quiz_type_val),
            question_text=q.get("question_text", "Question"),
            options=options if isinstance(options, list) else None,
            correct_answer=q.get("correct_answer", ""),
            explanation=q.get("explanation"),
            source_lecture_id=q.get("source_lecture_id"),
            source_topic_id=q.get("source_topic_id"),
            source_context=q.get("source_context"),
        ))

    db.commit()
    db.refresh(quiz)
    return QuizRead.model_validate(quiz)


@router.get("/{quiz_id}", response_model=QuizRead)
def get_quiz(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    _check_course_owner(db, quiz.course_id, current_user)
    return QuizRead.model_validate(quiz)


@router.post("/{quiz_id}/attempts", response_model=QuizAttemptRead, status_code=201)
def submit_quiz_attempt(
    quiz_id: int,
    req: QuizSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    _check_course_owner(db, quiz.course_id, current_user)

    questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz_id).all()
    if not questions:
        raise HTTPException(status_code=400, detail="Quiz has no questions")

    # Grade server-side from the stored correct_answer rather than trusting a
    # client-submitted score, so the persisted result is authoritative.
    score = 0
    for q in questions:
        picked_idx = req.answers.get(q.id)
        options = q.options if isinstance(q.options, list) else []
        if picked_idx is not None and 0 <= picked_idx < len(options):
            if options[picked_idx] == q.correct_answer:
                score += 1

    attempt = QuizAttempt(
        quiz_id=quiz_id,
        user_id=current_user.id,
        answers={str(k): v for k, v in req.answers.items()},
        score=score,
        total_questions=len(questions),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return QuizAttemptRead.model_validate(attempt)


@router.get("/{quiz_id}/attempts", response_model=List[QuizAttemptRead])
def list_quiz_attempts(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    _check_course_owner(db, quiz.course_id, current_user)
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.quiz_id == quiz_id, QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.completed_at.desc())
        .all()
    )
    return attempts


@router.get("/list/{course_id}", response_model=list[QuizRead])
def list_quizzes(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_course_owner(db, course_id, current_user)
    quizzes = (
        db.query(Quiz)
        .filter(Quiz.course_id == course_id)
        .order_by(Quiz.generated_at.desc())
        .all()
    )
    return quizzes
