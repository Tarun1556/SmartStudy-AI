from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.api.deps import get_current_user, get_current_user_optional
from app.models import (
    User, Course, Lecture, Topic, ProcessingJob, StudyGuide
)
from app.schemas import (
    DashboardStats, CourseStats, TopicRead, ProcessingJobRead,
    CourseRead
)

router = APIRouter()


@router.get("", response_model=DashboardStats)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        courses = db.query(Course).filter(Course.user_id == 0).all()
    else:
        courses = db.query(Course).filter(Course.user_id == current_user.id).all()

    course_ids = [c.id for c in courses]
    total_courses = len(courses)

    total_lectures = db.query(func.count(Lecture.id)).filter(Lecture.course_id.in_(course_ids or [-1])).scalar() or 0
    total_topics = db.query(func.count(Topic.id)).filter(Topic.course_id.in_(course_ids or [-1])).scalar() or 0
    total_jobs = 0
    if course_ids:
        total_jobs = (
            db.query(func.count(ProcessingJob.id))
            .join(Lecture, Lecture.id == ProcessingJob.lecture_id)
            .filter(Lecture.course_id.in_(course_ids))
            .filter(ProcessingJob.status.in_(["queued", "processing"]))
            .scalar() or 0
        )

    frequent = []
    if course_ids:
        frequent = (
            db.query(Topic)
            .filter(Topic.course_id.in_(course_ids))
            .order_by(Topic.coverage_score.desc(), Topic.lecture_count.desc())
            .limit(10)
            .all()
        )

    recent_jobs = []
    if course_ids:
        recent_jobs = (
            db.query(ProcessingJob)
            .join(Lecture, Lecture.id == ProcessingJob.lecture_id)
            .filter(Lecture.course_id.in_(course_ids))
            .order_by(ProcessingJob.updated_at.desc())
            .limit(10)
            .all()
        )

    course_stats = []
    for c in courses:
        lc = db.query(func.count(Lecture.id)).filter(Lecture.course_id == c.id).scalar() or 0
        tc = db.query(func.count(Topic.id)).filter(Topic.course_id == c.id).scalar() or 0
        course_stats.append(CourseStats(
            id=c.id, name=c.name, color=c.color,
            lecture_count=lc, topic_count=tc, last_updated=c.updated_at,
        ))

    return DashboardStats(
        total_courses=total_courses,
        total_lectures=total_lectures,
        total_topics=total_topics,
        processing_jobs=total_jobs,
        frequently_covered=[TopicRead.model_validate(t) for t in frequent],
        recent_jobs=[ProcessingJobRead.model_validate(j) for j in recent_jobs],
        course_stats=course_stats,
    )
