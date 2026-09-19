from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User, Course, StudyGuide
from app.schemas import StudyGuideRead
from app.services.study_guide import generate_study_guide
from app.services.pdf import build_study_guide_pdf

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


@router.get("/courses/{course_id}/study-guide", response_model=StudyGuideRead)
def get_study_guide(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_course_owner(db, course_id, current_user)
    latest = (
        db.query(StudyGuide)
        .filter(StudyGuide.course_id == course_id)
        .order_by(StudyGuide.version.desc())
        .first()
    )
    if latest:
        return StudyGuideRead.model_validate(latest)
    if current_user.is_demo:
        sg = generate_study_guide(db, course_id)
        return StudyGuideRead.model_validate(sg)
    raise HTTPException(status_code=404, detail="No study guide yet. Regenerate to create one.")


@router.post("/courses/{course_id}/study-guide/regenerate", response_model=StudyGuideRead)
def regenerate_study_guide(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    _check_course_owner(db, course_id, current_user)
    sg = generate_study_guide(db, course_id)
    return StudyGuideRead.model_validate(sg)


@router.get("/courses/{course_id}/study-guide/pdf")
def get_study_guide_pdf(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course = _check_course_owner(db, course_id, current_user)
    latest = (
        db.query(StudyGuide)
        .filter(StudyGuide.course_id == course_id)
        .order_by(StudyGuide.version.desc())
        .first()
    )
    if not latest:
        latest = generate_study_guide(db, course_id)
    content = latest.content if isinstance(latest.content, dict) else {}
    pdf_bytes = build_study_guide_pdf(latest.title, content, course_name=course.name)
    filename = f"study_guide_course_{course_id}_v{latest.version}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )
