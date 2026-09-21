from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models import Course, Topic, Lecture, StudyGuide, LectureNote
from app.services.llm import get_llm_provider
from app.services.topics import recalculate_topic_stats
from app.services.question_papers.analysis import compute_topic_exam_stats


def generate_study_guide(db: Session, course_id: int) -> StudyGuide:
    recalculate_topic_stats(db, course_id)
    topics = db.query(Topic).filter(Topic.course_id == course_id).all()
    lectures = (
        db.query(Lecture)
        .filter(Lecture.course_id == course_id)
        .order_by(Lecture.lecture_number.is_(None), Lecture.lecture_number, Lecture.id)
        .all()
    )

    topic_dicts = []
    for t in topics:
        lecture_ids = [m.lecture_id for m in t.mentions]
        topic_dicts.append({
            "id": t.id,
            "name": t.name,
            "canonical_name": t.canonical_name,
            "description": t.description,
            "coverage_score": t.coverage_score,
            "lecture_count": t.lecture_count,
            "evidence_count": t.evidence_count,
            "lecture_ids": list(set(lecture_ids)),
        })

    lecture_dicts = []
    for l in lectures:
        note = db.query(LectureNote).filter(LectureNote.lecture_id == l.id).first()
        lecture_dicts.append({
            "id": l.id,
            "title": l.title,
            "lecture_number": l.lecture_number,
            "lecture_date": l.lecture_date.isoformat() if l.lecture_date else None,
            "overview": note.overview if note else "",
        })

    # Historical question-paper evidence, keyed by topic_id. Computed fresh
    # from stored QuestionPaper/QuestionPaperQuestion rows (see
    # services/question_papers/analysis.py) — empty for courses that have
    # never uploaded a question paper, in which case no exam_priority block
    # is stamped and the study guide behaves exactly as it did before this
    # feature existed.
    exam_stats_by_topic = {s["topic_id"]: s for s in compute_topic_exam_stats(db, course_id)}

    llm = get_llm_provider()
    content = llm.generate_study_guide(topic_dicts, lecture_dicts)
    content = _reconcile_topic_stats(content, topic_dicts, exam_stats_by_topic)

    course = db.query(Course).filter(Course.id == course_id).first()
    course_name = course.name if course else "Course"

    latest = db.query(StudyGuide).filter(StudyGuide.course_id == course_id).order_by(StudyGuide.version.desc()).first()
    next_version = (latest.version + 1) if latest else 1

    sg = StudyGuide(
        course_id=course_id,
        version=next_version,
        title=f"{course_name} — Study Guide v{next_version}",
        content=content,
        top_topics=content.get("top_topics"),
    )
    db.add(sg)
    db.commit()
    db.refresh(sg)
    return sg


def _reconcile_topic_stats(
    content: Dict[str, Any],
    topic_dicts: List[Dict[str, Any]],
    exam_stats_by_topic: Dict[int, Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Overwrite the LLM-echoed coverage_score/lecture_count/evidence_count with the
    authoritative, DB-computed values. These are factual statistics, not prose the
    LLM should be trusted to retype accurately into JSON — an LLM call can silently
    drop or alter a number, which would otherwise show a coverage stat that disagrees
    with what /topics reports for the same topic (e.g. "Appears in 1 lecture" here vs
    2 mentions actually recorded). Only the LLM-authored summary text is kept as-is.

    exam_stats_by_topic (see services/question_papers/analysis.py) is stamped on the
    same way: every number under entry["exam_priority"] traces back to a stored count,
    never to something the LLM said. When the course has no processed question papers
    yet, no exam_priority key is added at all and ranking is unchanged from before this
    feature existed — this is what keeps existing courses' study guides behaving
    exactly as they did previously.
    """
    exam_stats_by_topic = exam_stats_by_topic or {}
    has_exam_data = any(s.get("total_papers_analyzed", 0) > 0 for s in exam_stats_by_topic.values())

    by_id = {t["id"]: t for t in topic_dicts}
    top_topics = content.get("top_topics") if isinstance(content, dict) else None
    if not isinstance(top_topics, list):
        return content

    reconciled = []
    for entry in top_topics:
        if not isinstance(entry, dict):
            continue
        tid = entry.get("topic_id", entry.get("id"))
        truth = by_id.get(tid)
        if truth:
            entry["topic_id"] = tid
            entry["coverage_score"] = truth["coverage_score"]
            entry["lecture_count"] = truth["lecture_count"]
            entry["evidence_count"] = truth["evidence_count"]
        if has_exam_data and tid in exam_stats_by_topic:
            s = exam_stats_by_topic[tid]
            entry["exam_priority"] = {
                "priority_score": s["priority_score"],
                "priority_label": s["priority_label"],
                "papers_appeared_in": s["papers_appeared_in"],
                "total_papers_analyzed": s["total_papers_analyzed"],
                "years_appeared_in": s["years_appeared_in"],
                "recent_trend": s["recent_trend"],
                "evidence": s["evidence"],
            }
        reconciled.append(entry)

    sort_key = (
        (lambda e: e.get("exam_priority", {}).get("priority_score", 0))
        if has_exam_data else
        (lambda e: e.get("coverage_score", 0))
    )
    reconciled.sort(key=sort_key, reverse=True)
    content["top_topics"] = reconciled[:15]
    return content
