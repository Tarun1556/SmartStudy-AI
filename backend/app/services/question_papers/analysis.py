"""Historical question-paper analysis: frequency, year recurrence, recent
trend, and an explainable topic-priority score.

Everything here is computed fresh from stored QuestionPaper/
QuestionPaperQuestion rows on each call (no persisted cache table — see
QUESTION_PAPER_FEATURE_PLAN.md §2 for why). At the scale of a handful of
papers per course this is cheap, and it avoids an entire class of
cache-staleness bugs a persisted stats table would introduce.

Every number this module produces traces back to a stored count — nothing is
phrased as a prediction. See the priority formula docstring below.
"""
from collections import defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import QuestionPaper, QuestionPaperQuestion, Topic

HIGH_PRIORITY_THRESHOLD = 0.6
MEDIUM_PRIORITY_THRESHOLD = 0.35

# Weights sum to 1.0 so priority_score stays in [0, 1]. Documented here rather
# than left as unexplained magic numbers — see QUESTION_PAPER_FEATURE_PLAN.md §6.
WEIGHT_LECTURE_COVERAGE = 0.30
WEIGHT_FREQUENCY = 0.30
WEIGHT_YEAR_RECURRENCE = 0.15
WEIGHT_RECENT_TREND = 0.10
WEIGHT_MARKS = 0.15


def _priority_label(score: float) -> str:
    if score >= HIGH_PRIORITY_THRESHOLD:
        return "high"
    if score >= MEDIUM_PRIORITY_THRESHOLD:
        return "medium"
    return "lower_historical_frequency"


def _trend_for_topic(
    topic_paper_ids: set,
    older_paper_ids: set,
    newer_paper_ids: set,
) -> str:
    if not older_paper_ids or not newer_paper_ids:
        return "insufficient_data"
    older_share = len(topic_paper_ids & older_paper_ids) / len(older_paper_ids)
    newer_share = len(topic_paper_ids & newer_paper_ids) / len(newer_paper_ids)
    if newer_share > older_share:
        return "increasing"
    if newer_share < older_share:
        return "decreasing"
    return "stable"


_TREND_SCORE = {
    "increasing": 1.0,
    "stable": 0.5,
    "decreasing": 0.0,
    "insufficient_data": 0.0,
}


def compute_topic_exam_stats(db: Session, course_id: int) -> List[Dict[str, Any]]:
    """One stat entry per course Topic (even topics with zero exam evidence,
    so callers — study guide reconciliation, exam-insights — can always find
    an entry for a topic they already know about, defaulting gracefully to
    "no historical exam data yet" rather than a missing key)."""
    topics = db.query(Topic).filter(Topic.course_id == course_id).all()
    if not topics:
        return []

    papers = (
        db.query(QuestionPaper)
        .filter(QuestionPaper.course_id == course_id, QuestionPaper.status == "processed")
        .all()
    )
    total_papers_analyzed = len(papers)
    papers_by_id = {p.id: p for p in papers}
    all_years = sorted({p.academic_year for p in papers if p.academic_year is not None})
    total_years_analyzed = len(all_years)

    # Split papers into an "older" and "newer" half by academic year for the
    # recent-trend comparison. The middle year (odd count) leans into the
    # newer half so a genuinely recent uptick isn't diluted into "stable".
    older_years = set(all_years[: len(all_years) // 2])
    newer_years = set(all_years[len(all_years) // 2:])
    older_paper_ids = {p.id for p in papers if p.academic_year in older_years}
    newer_paper_ids = {p.id for p in papers if p.academic_year in newer_years}

    questions = (
        db.query(QuestionPaperQuestion)
        .filter(
            QuestionPaperQuestion.topic_id.isnot(None),
            QuestionPaperQuestion.question_paper_id.in_(papers_by_id.keys()),
        )
        .all()
    ) if papers_by_id else []

    by_topic: Dict[int, List[QuestionPaperQuestion]] = defaultdict(list)
    for q in questions:
        by_topic[q.topic_id].append(q)

    course_avg_marks: Dict[int, float] = {}
    for tid, qs in by_topic.items():
        marks = [q.marks for q in qs if q.marks is not None]
        if marks:
            course_avg_marks[tid] = sum(marks) / len(marks)
    max_avg_marks = max(course_avg_marks.values(), default=0.0)

    stats: List[Dict[str, Any]] = []
    for topic in topics:
        qs = by_topic.get(topic.id, [])
        topic_paper_ids = {q.question_paper_id for q in qs}
        topic_years = {
            papers_by_id[pid].academic_year
            for pid in topic_paper_ids
            if papers_by_id.get(pid) and papers_by_id[pid].academic_year is not None
        }
        marks_values = [q.marks for q in qs if q.marks is not None]
        avg_marks = (sum(marks_values) / len(marks_values)) if marks_values else None

        frequency_score = (len(topic_paper_ids) / total_papers_analyzed) if total_papers_analyzed else 0.0
        year_recurrence_score = min(1.0, len(topic_years) / total_years_analyzed) if total_years_analyzed else 0.0
        trend = (
            _trend_for_topic(topic_paper_ids, older_paper_ids, newer_paper_ids)
            if total_years_analyzed >= 2 else "insufficient_data"
        )
        recent_trend_score = _TREND_SCORE[trend]
        marks_weight_score = (course_avg_marks.get(topic.id, 0.0) / max_avg_marks) if max_avg_marks else 0.0
        lecture_coverage = topic.coverage_score or 0.0

        priority_score = round(
            WEIGHT_LECTURE_COVERAGE * lecture_coverage
            + WEIGHT_FREQUENCY * frequency_score
            + WEIGHT_YEAR_RECURRENCE * year_recurrence_score
            + WEIGHT_RECENT_TREND * recent_trend_score
            + WEIGHT_MARKS * marks_weight_score,
            4,
        )

        paper_refs = [
            {
                "id": pid,
                "title": papers_by_id[pid].title,
                "academic_year": papers_by_id[pid].academic_year,
            }
            for pid in sorted(topic_paper_ids, key=lambda pid: papers_by_id[pid].academic_year or 0)
            if papers_by_id.get(pid)
        ]

        stats.append({
            "topic_id": topic.id,
            "topic_name": topic.canonical_name,
            "papers_appeared_in": len(topic_paper_ids),
            "total_papers_analyzed": total_papers_analyzed,
            "years_appeared_in": len(topic_years),
            "total_years_analyzed": total_years_analyzed,
            "question_count": len(qs),
            "total_marks": int(sum(marks_values)) if marks_values else None,
            "avg_marks": round(avg_marks, 1) if avg_marks is not None else None,
            "recent_trend": trend,
            "lecture_coverage": round(lecture_coverage, 4),
            "frequency_score": round(frequency_score, 4),
            "priority_score": priority_score,
            "priority_label": _priority_label(priority_score),
            "evidence": {
                "components": {
                    "lecture_coverage": round(lecture_coverage, 4),
                    "frequency_score": round(frequency_score, 4),
                    "year_recurrence_score": round(year_recurrence_score, 4),
                    "recent_trend_score": recent_trend_score,
                    "marks_weight_score": round(marks_weight_score, 4),
                },
                "papers": paper_refs,
            },
        })

    stats.sort(key=lambda s: s["priority_score"], reverse=True)
    return stats


def exam_insights_summary(db: Session, course_id: int, stats: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if stats is None:
        stats = compute_topic_exam_stats(db, course_id)
    total_papers_analyzed = stats[0]["total_papers_analyzed"] if stats else (
        db.query(QuestionPaper)
        .filter(QuestionPaper.course_id == course_id, QuestionPaper.status == "processed")
        .count()
    )
    topics_with_evidence = [s for s in stats if s["papers_appeared_in"] > 0]
    return {
        "papers_analyzed": total_papers_analyzed,
        "topics_identified": len(topics_with_evidence),
        "has_historical_patterns": total_papers_analyzed > 0 and len(topics_with_evidence) > 0,
    }
