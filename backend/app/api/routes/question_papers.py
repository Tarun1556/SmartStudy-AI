from typing import List, Optional
from fastapi import (
    APIRouter, Depends, HTTPException, status, UploadFile, File,
    Form, BackgroundTasks,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import (
    User, Course, QuestionPaper, QuestionPaperProcessingJob, QuestionPaperQuestion,
)
from app.schemas import (
    QuestionPaperRead, QuestionPaperListResponse, QuestionPaperUploadResponse,
    QuestionPaperProcessingJobRead, QuestionPaperQuestionRead,
    ExamInsightsResponse,
)
from app.services.ingestion.storage import get_storage_provider
from app.services.question_papers.analysis import compute_topic_exam_stats, exam_insights_summary
from app.tasks.question_paper_processing import process_question_paper_job
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


def _check_question_paper_owner(db, paper: QuestionPaper, user) -> None:
    course = db.query(Course).filter(Course.id == paper.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if user.is_demo:
        if course.user_id != 0:
            raise HTTPException(status_code=403, detail="Not authorized")
        return
    if course.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")


def _get_paper_or_404(db, paper_id: int) -> QuestionPaper:
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Question paper not found")
    return paper


def _with_latest_job(db, paper: QuestionPaper) -> QuestionPaperRead:
    read = QuestionPaperRead.model_validate(paper)
    jobs = sorted(paper.processing_jobs, key=lambda j: j.id, reverse=True)
    if jobs:
        read.latest_job = QuestionPaperProcessingJobRead.model_validate(jobs[0])
    read.question_count = len(paper.questions)
    return read


@router.get("/courses/{course_id}/question-papers", response_model=QuestionPaperListResponse)
def list_question_papers(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_course_owner(db, course_id, current_user)
    papers = (
        db.query(QuestionPaper)
        .filter(QuestionPaper.course_id == course_id)
        .order_by(QuestionPaper.academic_year.is_(None), QuestionPaper.academic_year.desc(), QuestionPaper.created_at.desc())
        .all()
    )
    summary = exam_insights_summary(db, course_id)
    return QuestionPaperListResponse(
        papers=[_with_latest_job(db, p) for p in papers],
        papers_analyzed=summary["papers_analyzed"],
        topics_identified=summary["topics_identified"],
    )


@router.post(
    "/courses/{course_id}/question-papers/upload",
    response_model=QuestionPaperUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_question_paper(
    course_id: int,
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    academic_year: Optional[int] = Form(None),
    semester: Optional[str] = Form(None),
    exam_type: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    _check_course_owner(db, course_id, current_user)

    filename = file.filename or "question_paper.pdf"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF question papers are supported.")

    data_bytes = await file.read()
    size = len(data_bytes)
    if size == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if size > settings.max_upload_bytes:
        raise HTTPException(status_code=400, detail=f"File too large. Max {settings.MAX_UPLOAD_SIZE_MB}MB")

    paper = QuestionPaper(
        course_id=course_id,
        title=title,
        academic_year=academic_year,
        semester=semester,
        exam_type=exam_type,
        original_filename=filename,
        file_path="",
        file_size=size,
        mime_type=file.content_type or "application/pdf",
        status="pending",
    )
    db.add(paper)
    db.flush()

    storage = get_storage_provider()
    rel_path = storage.save(
        f"user_{current_user.id}/course_{course_id}/qpaper_{paper.id}", filename, data_bytes,
    )
    paper.file_path = rel_path

    job = QuestionPaperProcessingJob(
        question_paper_id=paper.id,
        job_type="question_paper_analysis",
        status="queued",
        current_step="Awaiting processing",
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(paper)
    db.refresh(job)

    background_tasks.add_task(process_question_paper_job, job.id)

    return QuestionPaperUploadResponse(
        question_paper_id=paper.id,
        job_id=job.id,
        message="Upload received. Processing started.",
    )


@router.get("/question-papers/{paper_id}", response_model=QuestionPaperRead)
def get_question_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = _get_paper_or_404(db, paper_id)
    _check_question_paper_owner(db, paper, current_user)
    return _with_latest_job(db, paper)


@router.get("/question-papers/{paper_id}/status", response_model=QuestionPaperProcessingJobRead)
def get_question_paper_status(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = _get_paper_or_404(db, paper_id)
    _check_question_paper_owner(db, paper, current_user)
    jobs = sorted(paper.processing_jobs, key=lambda j: j.id, reverse=True)
    if not jobs:
        raise HTTPException(status_code=404, detail="No processing job found")
    return QuestionPaperProcessingJobRead.model_validate(jobs[0])


@router.post(
    "/question-papers/{paper_id}/retry",
    response_model=QuestionPaperProcessingJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_question_paper_processing(
    paper_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    paper = _get_paper_or_404(db, paper_id)
    _check_question_paper_owner(db, paper, current_user)

    jobs = sorted(paper.processing_jobs, key=lambda j: j.id, reverse=True)
    latest = jobs[0] if jobs else None
    if latest and latest.status in ("queued", "processing"):
        raise HTTPException(status_code=409, detail="Processing is already in progress for this question paper")

    job = QuestionPaperProcessingJob(
        question_paper_id=paper.id,
        job_type="question_paper_analysis",
        status="queued",
        current_step="Awaiting processing",
        progress=0,
    )
    db.add(job)
    paper.status = "pending"
    db.commit()
    db.refresh(job)

    background_tasks.add_task(process_question_paper_job, job.id)
    return QuestionPaperProcessingJobRead.model_validate(job)


@router.get("/question-papers/{paper_id}/download")
def download_question_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = _get_paper_or_404(db, paper_id)
    _check_question_paper_owner(db, paper, current_user)

    storage = get_storage_provider()
    if not paper.file_path or not storage.exists(paper.file_path):
        raise HTTPException(status_code=404, detail="Original file is no longer available")

    # file_path is always the server-generated relative path recorded at
    # upload time (LocalStorageProvider._safe() + a uuid prefix) — never a
    # client-supplied path, so there's no path-traversal surface here.
    data = storage.load(paper.file_path)
    safe_name = paper.original_filename.replace('"', "'").replace("\r", "").replace("\n", "")
    return Response(
        content=data,
        media_type=paper.mime_type or "application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get("/question-papers/{paper_id}/questions", response_model=List[QuestionPaperQuestionRead])
def list_question_paper_questions(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    paper = _get_paper_or_404(db, paper_id)
    _check_question_paper_owner(db, paper, current_user)
    questions = (
        db.query(QuestionPaperQuestion)
        .filter(QuestionPaperQuestion.question_paper_id == paper_id)
        .order_by(QuestionPaperQuestion.id)
        .all()
    )
    from app.models import Topic
    topic_ids = {q.topic_id for q in questions if q.topic_id}
    topics_by_id = {t.id: t for t in db.query(Topic).filter(Topic.id.in_(topic_ids)).all()} if topic_ids else {}

    result = []
    for q in questions:
        read = QuestionPaperQuestionRead.model_validate(q)
        if q.topic_id and q.topic_id in topics_by_id:
            read.topic_name = topics_by_id[q.topic_id].canonical_name
        result.append(read)
    return result


@router.delete("/question-papers/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.is_demo:
        raise HTTPException(status_code=403, detail="Demo mode is read-only")
    paper = _get_paper_or_404(db, paper_id)
    _check_question_paper_owner(db, paper, current_user)

    storage = get_storage_provider()
    if paper.file_path and storage.exists(paper.file_path):
        try:
            storage.delete(paper.file_path)
        except Exception:
            pass

    # Clean up this paper's indexed SearchDocument rows. Filtered in Python
    # rather than a DB-specific JSON-path operator so this works identically
    # on Postgres and the SQLite test database.
    from app.models import SearchDocument
    candidates = (
        db.query(SearchDocument)
        .filter(SearchDocument.course_id == paper.course_id, SearchDocument.doc_type == "question")
        .all()
    )
    for doc in candidates:
        meta = doc.doc_metadata or {}
        if isinstance(meta, dict) and meta.get("question_paper_id") == paper_id:
            db.delete(doc)

    db.delete(paper)
    db.commit()
    return None


@router.get("/courses/{course_id}/exam-insights", response_model=ExamInsightsResponse)
def get_exam_insights(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_course_owner(db, course_id, current_user)
    stats = compute_topic_exam_stats(db, course_id)
    summary = exam_insights_summary(db, course_id, stats=stats)
    return ExamInsightsResponse(
        course_id=course_id,
        papers_analyzed=summary["papers_analyzed"],
        topics_identified=summary["topics_identified"],
        has_historical_patterns=summary["has_historical_patterns"],
        topics=stats,
    )
