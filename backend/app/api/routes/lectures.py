from typing import List, Optional
from fastapi import (
    APIRouter, Depends, HTTPException, status, UploadFile, File,
    Form, BackgroundTasks
)
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import (
    User, Course, Lecture, LectureAsset, ProcessingJob,
    TranscriptSegment, LectureNote
)
from app.schemas import (
    LectureCreate, LectureRead, LectureUpdate, LectureNoteRead,
    UploadResponse, ProcessingJobRead
)
from app.services.ingestion.storage import get_storage_provider
from app.tasks.processing import process_lecture_job
from app.core.config import get_settings

settings = get_settings()

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


def _check_lecture_owner(db, lecture, user):
    course = db.query(Course).filter(Course.id == lecture.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if user.is_demo:
        if course.user_id != 0:
            raise HTTPException(status_code=403, detail="Not authorized")
        return
    if course.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")


@router.get("", response_model=List[LectureRead])
def list_lectures(
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Lecture)
    if course_id:
        _check_course_owner(db, course_id, current_user)
        q = q.filter(Lecture.course_id == course_id)
    elif not current_user.is_demo:
        q = q.join(Course).filter(Course.user_id == current_user.id)
    else:
        q = q.join(Course).filter(Course.user_id == 0)
    lectures = q.order_by(Lecture.lecture_number.is_(None), Lecture.lecture_number, Lecture.id.desc()).all()

    result = []
    for l in lectures:
        read = LectureRead.model_validate(l)
        jobs = sorted(l.processing_jobs, key=lambda j: j.id, reverse=True)
        if jobs:
            read.latest_job = ProcessingJobRead.model_validate(jobs[0])
        result.append(read)
    return result


@router.post("", response_model=LectureRead, status_code=status.HTTP_201_CREATED)
def create_lecture(
    data: LectureCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    _check_course_owner(db, data.course_id, current_user)

    lecture = Lecture(
        course_id=data.course_id,
        title=data.title,
        lecture_number=data.lecture_number,
        lecture_date=data.lecture_date,
        description=data.description,
        status="pending",
    )
    db.add(lecture)
    db.flush()

    if data.transcript_text:
        from app.services.ingestion.chunking import chunk_text
        chunks = chunk_text(data.transcript_text, 400, 80)
        for i, ch in enumerate(chunks):
            db.add(TranscriptSegment(
                lecture_id=lecture.id,
                segment_index=i,
                text=ch,
                start_time=None,
                end_time=None,
                source_type="pasted",
            ))

    job = ProcessingJob(
        lecture_id=lecture.id,
        job_type="full_processing",
        status="queued",
        current_step="Awaiting processing",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(lecture)
    db.refresh(job)

    if background_tasks:
        background_tasks.add_task(process_lecture_job, job.id)

    read = LectureRead.model_validate(lecture)
    read.latest_job = ProcessingJobRead.model_validate(job)
    return read


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_lecture(
    background_tasks: BackgroundTasks,
    course_id: int = Form(...),
    title: str = Form(...),
    lecture_number: Optional[int] = Form(None),
    lecture_date: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    transcript_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    _check_course_owner(db, course_id, current_user)

    lecture = Lecture(
        course_id=course_id,
        title=title,
        lecture_number=lecture_number,
        lecture_date=datetime.fromisoformat(lecture_date.replace("Z", "+00:00")) if lecture_date else None,
        description=description,
        status="pending",
    )
    db.add(lecture)
    db.flush()

    storage = get_storage_provider()
    asset = None
    if file:
        size = 0
        data_bytes = await file.read()
        size = len(data_bytes)
        if size > settings.max_upload_bytes:
            raise HTTPException(status_code=400, detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB")

        rel = storage.save(f"user_{current_user.id}/course_{course_id}/lecture_{lecture.id}", file.filename or "upload", data_bytes)
        ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
        asset = LectureAsset(
            lecture_id=lecture.id,
            asset_type=ext or "file",
            file_name=file.filename or "upload",
            file_path=rel,
            file_size=size,
            mime_type=file.content_type,
        )
        db.add(asset)

    if transcript_text:
        from app.services.ingestion.chunking import chunk_text
        chunks = chunk_text(transcript_text, 400, 80)
        for i, ch in enumerate(chunks):
            db.add(TranscriptSegment(
                lecture_id=lecture.id,
                segment_index=i,
                text=ch,
                start_time=None,
                end_time=None,
                source_type="pasted",
            ))

    job = ProcessingJob(
        lecture_id=lecture.id,
        job_type="full_processing",
        status="queued",
        current_step="Awaiting processing",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(lecture)
    db.refresh(job)

    background_tasks.add_task(process_lecture_job, job.id)

    return UploadResponse(
        lecture_id=lecture.id,
        job_id=job.id,
        message="Upload received. Processing started.",
    )


@router.get("/{lecture_id}", response_model=LectureRead)
def get_lecture(
    lecture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    _check_lecture_owner(db, lecture, current_user)
    read = LectureRead.model_validate(lecture)
    jobs = sorted(lecture.processing_jobs, key=lambda j: j.id, reverse=True)
    if jobs:
        read.latest_job = ProcessingJobRead.model_validate(jobs[0])
    return read


@router.put("/{lecture_id}", response_model=LectureRead)
def update_lecture(
    lecture_id: int,
    data: LectureUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    _check_lecture_owner(db, lecture, current_user)

    for field in ("title", "lecture_number", "lecture_date", "description"):
        val = getattr(data, field)
        if val is not None:
            setattr(lecture, field, val)
    db.commit()
    db.refresh(lecture)
    return LectureRead.model_validate(lecture)


@router.get("/{lecture_id}/status", response_model=ProcessingJobRead)
def get_lecture_status(
    lecture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    _check_lecture_owner(db, lecture, current_user)
    jobs = sorted(lecture.processing_jobs, key=lambda j: j.id, reverse=True)
    if not jobs:
        raise HTTPException(status_code=404, detail="No processing job found")
    return ProcessingJobRead.model_validate(jobs[0])


@router.post("/{lecture_id}/retry", response_model=ProcessingJobRead, status_code=status.HTTP_202_ACCEPTED)
def retry_lecture_processing(
    lecture_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-queue processing for a lecture whose latest job failed.

    Matches the "allow retry, do not leave stuck in PROCESSING" requirement:
    a failed job (including one failed by the startup stale-job sweep after a
    server restart) is not a dead end — the user can retry from here instead
    of re-uploading.
    """
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    _check_lecture_owner(db, lecture, current_user)

    jobs = sorted(lecture.processing_jobs, key=lambda j: j.id, reverse=True)
    latest = jobs[0] if jobs else None
    if latest and latest.status in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="Processing is already in progress for this lecture")

    job = ProcessingJob(
        lecture_id=lecture.id,
        job_type="full_processing",
        status="queued",
        current_step="Awaiting processing",
        progress=0,
    )
    db.add(job)
    lecture.status = "pending"
    db.commit()
    db.refresh(job)

    background_tasks.add_task(process_lecture_job, job.id)
    return ProcessingJobRead.model_validate(job)


@router.get("/{lecture_id}/notes", response_model=LectureNoteRead)
def get_lecture_notes(
    lecture_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found")
    _check_lecture_owner(db, lecture, current_user)
    note = db.query(LectureNote).filter(LectureNote.lecture_id == lecture_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="No notes generated yet")
    return LectureNoteRead.model_validate(note)
