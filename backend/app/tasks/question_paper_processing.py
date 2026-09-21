"""Background processing for uploaded question papers.

Mirrors app.tasks.processing.process_lecture_job's shape deliberately: its own
SessionLocal(), phase-by-phase current_step/progress updates with a commit
after each, and a single outer try/except that stores a generic user-safe
message on the job while the real exception goes to logger.exception only.
"""
from datetime import datetime
import logging
import time
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import QuestionPaper, QuestionPaperProcessingJob, QuestionPaperQuestion, Topic
from app.services.ingestion.storage import get_storage_provider
from app.services.extraction import extract_pdf_text
from app.services.question_papers.extraction import segment_question_paper
from app.services.question_papers.matching import match_topic_for_text
from app.services.embeddings import get_embedding_provider
from app.services.llm import get_llm_provider
from app.services.search import index_document

logger = logging.getLogger("studyapp")

GENERIC_FAILURE_MESSAGE = "Question paper processing failed. Please retry."
EMPTY_TEXT_MESSAGE = (
    "Could not extract any text from this PDF. It may be a scanned/image-only "
    "document — OCR isn't supported yet. The original file is still saved; "
    "you can delete it or try a text-based PDF instead."
)
NO_QUESTIONS_MESSAGE = (
    "Text was extracted, but no question content could be identified in it. "
    "The original file is still saved and can be retried."
)


class _KnownProcessingError(Exception):
    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


def _update_job(db: Session, job: QuestionPaperProcessingJob, **fields) -> None:
    for k, v in fields.items():
        setattr(job, k, v)
    job.updated_at = datetime.utcnow()
    db.flush()


def process_question_paper_job(job_id: int) -> None:
    db = SessionLocal()
    job_started = time.perf_counter()
    try:
        job = db.query(QuestionPaperProcessingJob).filter(QuestionPaperProcessingJob.id == job_id).first()
        if not job:
            return
        paper = db.query(QuestionPaper).filter(QuestionPaper.id == job.question_paper_id).first()
        if not paper:
            _update_job(db, job, status="failed", error_message="Question paper not found", completed_at=datetime.utcnow())
            db.commit()
            return

        try:
            _update_job(db, job, status="processing", current_step="Extracting text", progress=10, started_at=datetime.utcnow())
            db.commit()

            storage = get_storage_provider()
            abs_path = storage.get_absolute_path(paper.file_path)
            raw_text = extract_pdf_text(abs_path)
            if not raw_text or not raw_text.strip():
                raise _KnownProcessingError(EMPTY_TEXT_MESSAGE)

            _update_job(db, job, current_step="Identifying questions", progress=30)
            db.commit()
            regex_blocks = segment_question_paper(raw_text)
            if not regex_blocks:
                raise _KnownProcessingError(NO_QUESTIONS_MESSAGE)

            _update_job(db, job, current_step="Parsing questions (AI)", progress=50)
            db.commit()
            llm = get_llm_provider()
            parsed = llm.parse_question_paper(raw_text, regex_blocks)
            # Never silently drop the original text: if the LLM's output shape
            # doesn't line up with the input blocks, fall back to the raw
            # regex segmentation rather than guessing.
            if not isinstance(parsed, list) or len(parsed) != len(regex_blocks):
                parsed = regex_blocks

            _update_job(db, job, current_step="Generating embeddings", progress=65)
            db.commit()
            emb_provider = get_embedding_provider()
            texts = [str(p.get("question_text", "")) for p in parsed]
            embeddings: List[List[float]] = emb_provider.embed_texts(texts) if texts else []

            _update_job(db, job, current_step="Mapping to topics", progress=80)
            db.commit()
            existing_topics = db.query(Topic).filter(Topic.course_id == paper.course_id).all()

            created: List[tuple] = []
            for p, emb in zip(parsed, embeddings):
                question_text = str(p.get("question_text", "")).strip()
                if not question_text:
                    continue
                topic, confidence = match_topic_for_text(
                    db, paper.course_id, question_text,
                    question_embedding=emb, existing_topics=existing_topics,
                )
                q = QuestionPaperQuestion(
                    question_paper_id=paper.id,
                    question_number=p.get("question_number"),
                    section=p.get("section"),
                    question_text=question_text,
                    marks=p.get("marks"),
                    topic_id=topic.id if topic else None,
                    topic_match_confidence=confidence if topic else None,
                    normalized_topic=topic.canonical_name if topic else None,
                    embedding=emb,
                )
                db.add(q)
                created.append((q, p))
            db.flush()

            _update_job(db, job, current_step="Indexing for search", progress=90)
            db.commit()
            for q, p in created:
                label = f"Q{p.get('question_number')}" if p.get("question_number") else "Question"
                index_document(
                    db, paper.course_id, doc_type="question",
                    title=f"{paper.title} — {label}",
                    content=q.question_text,
                    lecture_id=None,
                    doc_metadata={
                        "question_paper_id": paper.id,
                        "paper_title": paper.title,
                        "academic_year": paper.academic_year,
                        "question_number": p.get("question_number"),
                        "marks": p.get("marks"),
                    },
                )

            paper.status = "processed"
            _update_job(db, job, status="completed", current_step="Done", progress=100, completed_at=datetime.utcnow())
            logger.info(
                "question_paper_job=%s completed questions=%d total_duration_ms=%.1f",
                job_id, len(created), (time.perf_counter() - job_started) * 1000,
            )
            db.commit()
        except _KnownProcessingError as e:
            logger.warning("question_paper_job=%s failed: %s", job_id, e.user_message)
            paper.status = "error"
            _update_job(db, job, status="failed", error_message=e.user_message, completed_at=datetime.utcnow())
            db.commit()
        except Exception:
            logger.exception(
                "question_paper_job=%s failed after total_duration_ms=%.1f",
                job_id, (time.perf_counter() - job_started) * 1000,
            )
            paper.status = "error"
            _update_job(db, job, status="failed", error_message=GENERIC_FAILURE_MESSAGE, completed_at=datetime.utcnow())
            db.commit()
    finally:
        db.close()


STALE_JOB_MESSAGE = "Processing was interrupted by a server restart. Please retry."


def sweep_stale_question_paper_jobs() -> int:
    """Startup sweep for QuestionPaperProcessingJob, mirroring
    app.tasks.processing.sweep_stale_jobs for the lecture pipeline. Kept as a
    separate function (rather than editing that one to be polymorphic) so the
    existing lecture sweep query is untouched."""
    db = SessionLocal()
    try:
        stale = (
            db.query(QuestionPaperProcessingJob)
            .filter(QuestionPaperProcessingJob.status.in_(["queued", "processing"]))
            .all()
        )
        for job in stale:
            job.status = "failed"
            job.error_message = STALE_JOB_MESSAGE
            job.completed_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            paper = db.query(QuestionPaper).filter(QuestionPaper.id == job.question_paper_id).first()
            if paper and paper.status != "processed":
                paper.status = "error"
        db.commit()
        return len(stale)
    finally:
        db.close()
