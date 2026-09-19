from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User, Course, Lecture, Topic, ProcessingJob, StudyGuide
from app.schemas import (
    CourseCreate, CourseUpdate, CourseRead, CourseStats,
    DashboardStats, TopicRead, ProcessingJobRead
)
from app.services.topics import recalculate_topic_stats

router = APIRouter()


def _check_ownership(obj, user: User, field: str = "user_id"):
    if user.is_demo:
        return
    if getattr(obj, field) != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")


@router.get("", response_model=List[CourseRead])
def list_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Course)
    if not current_user.is_demo:
        query = query.filter(Course.user_id == current_user.id)
    else:
        query = query.filter(Course.user_id == 0)
    courses = query.order_by(Course.updated_at.desc()).all()
    return courses


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(
    course_in: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")

    course = Course(
        user_id=current_user.id,
        name=course_in.name,
        description=course_in.description,
        color=course_in.color or "#4f46e5",
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/{course_id}", response_model=CourseRead)
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    _check_ownership(course, current_user)
    return course


@router.put("/{course_id}", response_model=CourseRead)
def update_course(
    course_id: int,
    course_in: CourseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    _check_ownership(course, current_user)

    if course_in.name is not None:
        course.name = course_in.name
    if course_in.description is not None:
        course.description = course_in.description
    if course_in.color is not None:
        course.color = course_in.color
    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    _check_ownership(course, current_user)
    db.delete(course)
    db.commit()
    return None


@router.get("/{course_id}/stats", response_model=CourseStats)
def get_course_stats(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    _check_ownership(course, current_user)
    lecture_count = db.query(Lecture).filter(Lecture.course_id == course_id).count()
    topic_count = db.query(Topic).filter(Topic.course_id == course_id).count()
    return CourseStats(
        id=course.id,
        name=course.name,
        color=course.color,
        lecture_count=lecture_count,
        topic_count=topic_count,
        last_updated=course.updated_at,
    )
