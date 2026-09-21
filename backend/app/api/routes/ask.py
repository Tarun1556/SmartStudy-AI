import logging
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User, Course, ChatSession, ChatMessage
from app.schemas import AskRequest, AskResponse, Citation, ChatSessionRead, ChatMessageRead
from app.services.search import search_hybrid
from app.services.llm import get_llm_provider
from app.services.question_papers.analysis import compute_topic_exam_stats

router = APIRouter()
logger = logging.getLogger("studyapp.rag")

# Deliberately simple keyword heuristic rather than a separate intent
# classifier — matches spec's "kept deliberately simple" guidance. False
# positives just mean the exam-evidence block is included when it didn't
# need to be, which is harmless (it's still grounded, factual context).
_EXAM_INTENT_KEYWORDS = (
    "exam", "semester exam", "study first", "prioritize", "priority",
    "most important topic", "what should i study", "study guide",
)


def _is_exam_intent(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in _EXAM_INTENT_KEYWORDS)


def _exam_evidence_chunk(db: Session, course_id: int):
    """A synthetic context chunk carrying historical question-paper evidence,
    phrased entirely in evidence-based language ("appeared in X of Y papers")
    with no predictive claims. It's passed into llm.answer_question() the
    same way a real lecture chunk is — every provider already reads
    `content`/`snippet` generically, so this needs no LLMProvider changes.
    Returns None when the course has no processed question papers, so
    behavior for courses that never use this feature is unchanged."""
    stats = [s for s in compute_topic_exam_stats(db, course_id) if s["total_papers_analyzed"] > 0]
    if not stats:
        return None
    lines = []
    for s in stats[:8]:
        lines.append(
            f"- {s['topic_name']}: appeared in {s['papers_appeared_in']} of "
            f"{s['total_papers_analyzed']} analyzed question papers, across "
            f"{s['years_appeared_in']} academic year(s); lecture coverage "
            f"{s['lecture_coverage']:.2f}; recent trend: {s['recent_trend']}; "
            f"historical priority: {s['priority_label']}."
        )
    content = (
        "Historical question-paper evidence (factual counts from the "
        "student's own uploaded past papers — describe this as historical "
        "frequency, never as a guarantee about the next exam):\n" + "\n".join(lines)
    )
    return {
        "lecture_id": None,
        "lecture_title": "Historical Exam Pattern Analysis",
        "lecture_number": None,
        "content": content,
        "snippet": content[:300],
        "start_time": None,
    }


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


@router.post("", response_model=AskResponse)
def ask_question(
    req: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_course_owner(db, req.course_id, current_user)

    session_id = req.session_id
    if session_id:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session or session.course_id != req.course_id:
            session_id = None

    if not session_id:
        title = req.question[:60] + ("…" if len(req.question) > 60 else "")
        session = ChatSession(course_id=req.course_id, title=title)
        db.add(session)
        db.flush()
        session_id = session.id
    else:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

    user_msg = ChatMessage(session_id=session_id, role="user", content=req.question)
    db.add(user_msg)

    t_retrieval = time.perf_counter()
    retrieved = search_hybrid(db, req.course_id, req.question, mode="hybrid", limit=8)
    retrieval_ms = (time.perf_counter() - t_retrieval) * 1000
    context_chunks = []
    for r in retrieved:
        # search_hybrid already resolved lecture_title/lecture_number in a single
        # batched query; re-querying Lecture per chunk here would be an N+1.
        context_chunks.append({
            "lecture_id": r.get("lecture_id"),
            "lecture_title": r.get("lecture_title") or "Unknown",
            "lecture_number": r.get("lecture_number") or r.get("metadata", {}).get("lecture_number"),
            "content": r.get("content", r.get("snippet", "")),
            "snippet": r.get("snippet", ""),
            "start_time": r.get("metadata", {}).get("start_time") if isinstance(r.get("metadata"), dict) else None,
        })

    if _is_exam_intent(req.question):
        exam_chunk = _exam_evidence_chunk(db, req.course_id)
        if exam_chunk:
            context_chunks.insert(0, exam_chunk)

    t_llm = time.perf_counter()
    llm = get_llm_provider()
    answer_data = llm.answer_question(req.question, context_chunks)
    llm_ms = (time.perf_counter() - t_llm) * 1000
    logger.info(
        "ask course=%s chunks=%d retrieval_ms=%.1f llm_ms=%.1f total_ms=%.1f",
        req.course_id, len(context_chunks), retrieval_ms, llm_ms, retrieval_ms + llm_ms,
    )

    answer = answer_data.get("answer", "")
    citations_raw = answer_data.get("citations", []) or []
    found = bool(answer_data.get("found_in_material", True)) and bool(citations_raw or "could not find" not in answer.lower())

    citations = []
    seen_lectures = set()
    for c in citations_raw[:6]:
        lid = c.get("lecture_id")
        # The Citation schema's lecture_id is a required int (it always points
        # at a real Lecture for the frontend's "open full lecture" link) — the
        # synthetic exam-evidence chunk above has lecture_id=None by design
        # (it isn't a lecture), so a citation of it is surfaced in the answer
        # text only, never as a Citation object. This also guards the
        # pre-existing case of the LLM citing with a missing lecture_id.
        if lid is None:
            continue
        if lid in seen_lectures:
            continue
        seen_lectures.add(lid)
        citations.append(Citation(
            lecture_id=lid,
            lecture_title=c.get("lecture_title", "Unknown"),
            lecture_number=c.get("lecture_number"),
            snippet=c.get("snippet", "")[:300],
            start_time=c.get("start_time"),
        ))

    citations_dict = [
        {
            "lecture_id": c.lecture_id,
            "lecture_title": c.lecture_title,
            "lecture_number": c.lecture_number,
            "snippet": c.snippet,
            "start_time": c.start_time,
        }
        for c in citations
    ]

    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=answer,
        citations=citations_dict,
    )
    db.add(assistant_msg)
    db.commit()

    return AskResponse(
        answer=answer,
        citations=citations,
        session_id=session_id,
        found_in_material=found,
    )


@router.get("/sessions/{course_id}", response_model=list[ChatSessionRead])
def list_sessions(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_course_owner(db, course_id, current_user)
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.course_id == course_id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return sessions


@router.get("/session/{session_id}", response_model=ChatSessionRead)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _check_course_owner(db, session.course_id, current_user)
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.id).all()
    session.messages = messages
    return session
