from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import logging

from app.models import (
    Lecture, ProcessingJob, TranscriptSegment, LectureNote,
    LectureAsset, TopicMention
)
from app.services.ingestion.storage import get_storage_provider
from app.services.ingestion.chunking import chunk_text, chunk_by_segments
from app.services.extraction import extract_transcript_segments, extract_pdf_text, extract_pptx_text
from app.services.transcription import get_transcription_provider
from app.services.llm import get_llm_provider
from app.services.embeddings import get_embedding_provider
from app.services.topics import find_or_create_topic, add_topic_mention, recalculate_topic_stats
from app.services.search import reindex_lecture
from app.services.study_guide import generate_study_guide
from app.db.session import SessionLocal

logger = logging.getLogger("studyapp")

AUDIO_EXTS = {"mp3", "wav", "m4a", "mp4", "webm", "ogg", "flac", "aac"}
PDF_EXTS = {"pdf"}
PPT_EXTS = {"pptx", "ppt"}
TEXT_EXTS = {"txt", "md", "rtf"}


def _update_job(db: Session, job: ProcessingJob, **fields) -> None:
    for k, v in fields.items():
        setattr(job, k, v)
    job.updated_at = datetime.utcnow()
    db.flush()


def process_lecture_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            return
        lecture = db.query(Lecture).filter(Lecture.id == job.lecture_id).first()
        if not lecture:
            _update_job(db, job, status="failed", error_message="Lecture not found", completed_at=datetime.utcnow())
            db.commit()
            return

        try:
            _update_job(db, job, status="processing", current_step="Validating inputs", progress=5, started_at=datetime.utcnow())
            db.commit()
            db.refresh(job)

            segments = _extract_all_segments(db, lecture, job)

            _update_job(db, job, current_step="Generating structured notes", progress=35)
            db.commit()
            note = _generate_notes(db, lecture, segments)

            _update_job(db, job, current_step="Extracting and merging topics", progress=60)
            db.commit()
            _extract_topics_pipeline(db, lecture, segments, note)

            _update_job(db, job, current_step="Indexing for search", progress=80)
            db.commit()
            notes_text = _flatten_note(note)
            reindex_lecture(db, lecture.id, notes_text)

            _update_job(db, job, current_step="Updating course study guide", progress=90)
            db.commit()
            try:
                generate_study_guide(db, lecture.course_id)
            except Exception as e:
                logger.warning(f"Study guide generation failed: {e}")

            lecture.status = "processed"
            _update_job(db, job, status="completed", current_step="Done", progress=100, completed_at=datetime.utcnow())
            db.commit()
        except Exception as e:
            logger.exception(f"Processing failed for job {job_id}")
            lecture.status = "error"
            _update_job(db, job, status="failed", error_message=str(e)[:1000], completed_at=datetime.utcnow())
            db.commit()
    finally:
        db.close()


def _extract_all_segments(db: Session, lecture: Lecture, job: ProcessingJob) -> List[Dict[str, Any]]:
    storage = get_storage_provider()
    _update_job(db, job, current_step="Extracting text from assets", progress=15)
    db.commit()

    assets = db.query(LectureAsset).filter(LectureAsset.lecture_id == lecture.id).all()
    transcript_provider = get_transcription_provider()

    all_segments: List[Dict[str, Any]] = []
    idx_counter = 0

    for asset in assets:
        ext = (asset.file_name.rsplit(".", 1)[-1].lower()) if "." in asset.file_name else ""
        abs_path = storage.get_absolute_path(asset.file_path) if asset.file_path else None

        if ext in PDF_EXTS:
            pdf_segments = extract_transcript_segments(abs_path) if abs_path else []
            for seg in pdf_segments:
                seg["segment_index"] = idx_counter
                idx_counter += 1
                all_segments.append(seg)
                db.add(TranscriptSegment(lecture_id=lecture.id, **seg))
        elif ext in PPT_EXTS:
            ppt_segments = extract_transcript_segments(abs_path) if abs_path else []
            for seg in ppt_segments:
                seg["segment_index"] = idx_counter
                idx_counter += 1
                all_segments.append(seg)
                db.add(TranscriptSegment(lecture_id=lecture.id, **seg))
        elif ext in AUDIO_EXTS and abs_path:
            audio_segments = transcript_provider.transcribe(abs_path)
            for seg in audio_segments:
                seg["segment_index"] = idx_counter
                idx_counter += 1
                all_segments.append(seg)
                db.add(TranscriptSegment(lecture_id=lecture.id, **seg))
        elif ext in TEXT_EXTS and abs_path:
            txt_segments = extract_transcript_segments(abs_path)
            for seg in txt_segments:
                seg["segment_index"] = idx_counter
                idx_counter += 1
                all_segments.append(seg)
                db.add(TranscriptSegment(lecture_id=lecture.id, **seg))

    existing = db.query(TranscriptSegment).filter(TranscriptSegment.lecture_id == lecture.id).order_by(TranscriptSegment.segment_index).all()
    if not all_segments and not existing:
        pass

    all_out = []
    seen = set()
    for s in existing:
        key = (s.segment_index, s.text[:20])
        if key not in seen:
            seen.add(key)
            all_out.append({
                "segment_index": s.segment_index,
                "text": s.text,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "source_type": s.source_type,
                "id": s.id,
            })
    for s in all_segments:
        key = (s["segment_index"], s["text"][:20])
        if key not in seen:
            seen.add(key)
            all_out.append(s)
    all_out.sort(key=lambda s: s["segment_index"])
    db.flush()
    return all_out


def _generate_notes(db: Session, lecture: Lecture, segments: List[Dict[str, Any]]) -> LectureNote:
    llm = get_llm_provider()
    if not segments:
        text_chunks = [lecture.description or lecture.title or "No content"]
    else:
        combined = "\n".join(s["text"] for s in segments)
        text_chunks = chunk_text(combined, chunk_size=1500, overlap=200)

    structured = llm.generate_structured_notes(text_chunks, title=lecture.title)

    note = db.query(LectureNote).filter(LectureNote.lecture_id == lecture.id).first()
    if note:
        note.title = structured.get("title", note.title)
        note.overview = structured.get("overview", note.overview)
        note.headings = structured.get("headings", note.headings)
        note.key_ideas = structured.get("key_ideas", note.key_ideas)
        note.definitions = structured.get("definitions", note.definitions)
        note.examples = structured.get("examples", note.examples)
        note.relationships = structured.get("relationships", note.relationships)
        note.source_references = structured.get("source_references", note.source_references)
        note.raw_content = "\n".join(text_chunks)
    else:
        note = LectureNote(
            lecture_id=lecture.id,
            title=structured.get("title", lecture.title),
            overview=structured.get("overview", ""),
            headings=structured.get("headings", []),
            key_ideas=structured.get("key_ideas", []),
            definitions=structured.get("definitions", []),
            examples=structured.get("examples", []),
            relationships=structured.get("relationships", []),
            source_references=structured.get("source_references", []),
            raw_content="\n".join(text_chunks),
        )
        db.add(note)
    db.flush()
    return note


def _extract_topics_pipeline(db: Session, lecture: Lecture, segments: List[Dict[str, Any]], note: LectureNote) -> None:
    # Serialize topic merging per course. Lectures in the same course can be
    # processed concurrently (background tasks from separate uploads), and each
    # job reads the course's existing topics before writing its own. Without a
    # lock, two lectures uploaded close together each see an empty/stale topic
    # list and create duplicate topics (e.g. two separate "Dependency Injection"
    # entries) instead of merging. This transaction-scoped advisory lock is
    # released automatically at the next commit/rollback on this session.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:cid)"), {"cid": lecture.course_id})

    llm = get_llm_provider()
    emb = get_embedding_provider()

    combined_text = "\n".join(s["text"] for s in segments)
    if not combined_text.strip():
        combined_text = _flatten_note(note)

    note_dict = {
        "title": note.title,
        "overview": note.overview,
        "headings": note.headings,
        "key_ideas": note.key_ideas,
        "definitions": note.definitions,
        "examples": note.examples,
    }
    candidates = llm.extract_topics(combined_text[:8000], note_dict)

    existing_topics = db.query(__import__("app.models", fromlist=["Topic"]).Topic).filter(
        __import__("app.models", fromlist=["Topic"]).Topic.course_id == lecture.course_id
    ).all()

    seg_by_idx = {s.get("segment_index"): s for s in segments}

    from app.models import Topic as TopicModel
    for cand in candidates:
        topic, _ = find_or_create_topic(db, lecture.course_id, cand, existing_topics=existing_topics)
        if topic.id:
            existing_topics = [t for t in existing_topics if t.id != topic.id] + [topic]
        else:
            existing_topics.append(topic)

        context = cand.get("description") or combined_text[:300]
        segment_id = None
        start_time = None
        source_type = "text"

        for s in segments[:5]:
            if cand.get("name", "").lower() in s["text"].lower():
                segment_id = s.get("id")
                start_time = s.get("start_time")
                source_type = s.get("source_type", "text")
                context = s["text"][:500]
                break

        add_topic_mention(
            db,
            topic_id=topic.id,
            lecture_id=lecture.id,
            context=context,
            transcript_segment_id=segment_id,
            start_time=start_time,
            source_type=source_type,
            confidence=float(cand.get("confidence", 0.7)),
        )

    db.flush()
    recalculate_topic_stats(db, lecture.course_id)


def _flatten_note(note: LectureNote) -> str:
    parts = []
    if note.title:
        parts.append(note.title)
    if note.overview:
        parts.append(note.overview)
    ki = note.key_ideas if isinstance(note.key_ideas, list) else []
    for k in ki:
        if isinstance(k, dict):
            parts.append(str(k.get("idea", "")))
    dfs = note.definitions if isinstance(note.definitions, list) else []
    for d in dfs:
        if isinstance(d, dict):
            parts.append(f"{d.get('term','')}: {d.get('definition','')}")
    exs = note.examples if isinstance(note.examples, list) else []
    for e in exs:
        if isinstance(e, dict):
            parts.append(str(e.get("text", "")))
        elif isinstance(e, str):
            parts.append(e)
    return "\n".join(p for p in parts if p)
