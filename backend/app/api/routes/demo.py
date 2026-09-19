from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db.session import get_db
from app.models import Course, User
from app.schemas import CourseRead, Token
from app.core.security import create_access_token
from app.core.config import get_settings

settings = get_settings()

router = APIRouter()


def _get_demo_course(db: Session) -> Course:
    course = db.query(Course).filter(Course.user_id == 0).first()
    if not course:
        raise HTTPException(status_code=404, detail="Demo content not ready. Please try again later.")
    return course


@router.get("/token", response_model=Token)
def get_demo_token(db: Session = Depends(get_db)):
    course = _get_demo_course(db)
    token = create_access_token(subject=0, expires_delta=timedelta(days=1))
    return Token(access_token=token)


@router.get("/course", response_model=CourseRead)
def get_demo_course_route(db: Session = Depends(get_db)):
    course = _get_demo_course(db)
    return CourseRead.model_validate(course)
