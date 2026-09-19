import logging
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, and_

from app.models import SearchDocument, Course, Lecture, Topic, TopicMention
from app.services.embeddings import get_embedding_provider, cosine_similarity
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("studyapp.search")


def index_document(
    db: Session,
    course_id: int,
    doc_type: str,
    title: str,
    content: str,
    lecture_id: Optional[int] = None,
    doc_metadata: Optional[Dict[str, Any]] = None,
    embed: bool = True,
) -> SearchDocument:
    snippet = content[:500]
    doc = SearchDocument(
        course_id=course_id,
        lecture_id=lecture_id,
        doc_type=doc_type,
        title=title[:500],
        content=content,
        snippet=snippet,
        doc_metadata=doc_metadata or {},
    )
    db.add(doc)
    db.flush()

    if embed:
        try:
            prov = get_embedding_provider()
            text_for_emb = f"{title} {content[:2000]}"
            embs = prov.embed_texts([text_for_emb])
            doc.embedding = embs[0]
        except Exception:
            pass

    return doc


def reindex_lecture(db: Session, lecture_id: int, notes_content: str = "") -> None:
    from app.models import Lecture, LectureNote, TranscriptSegment
    lecture = db.query(Lecture).filter(Lecture.id == lecture_id).first()
    if not lecture:
        return

    db.query(SearchDocument).filter(SearchDocument.lecture_id == lecture_id).delete()
    db.flush()

    note = db.query(LectureNote).filter(LectureNote.lecture_id == lecture_id).first()
    if note:
        notes_text = notes_content or _note_to_text(note)
        if notes_text:
            index_document(
                db, lecture.course_id, "notes",
                title=f"Notes: {lecture.title}",
                content=notes_text,
                lecture_id=lecture_id,
                doc_metadata={"lecture_id": lecture_id, "type": "notes"},
            )

    segments = db.query(TranscriptSegment).filter(TranscriptSegment.lecture_id == lecture_id).all()
    for seg in segments:
        index_document(
            db, lecture.course_id, "segment",
            title=f"{lecture.title} — seg {seg.segment_index}",
            content=seg.text,
            lecture_id=lecture_id,
            doc_metadata={"segment_index": seg.segment_index, "start_time": seg.start_time, "source_type": seg.source_type},
        )

    topics = (
        db.query(Topic)
        .join(Topic.mentions)
        .filter(Topic.course_id == lecture.course_id, TopicMention.lecture_id == lecture_id)
        .all()
    )
    for t in topics:
        index_document(
            db, lecture.course_id, "topic",
            title=f"Topic: {t.canonical_name}",
            content=f"{t.canonical_name}. {t.description or ''}",
            lecture_id=lecture_id,
            doc_metadata={"topic_id": t.id, "type": "topic"},
        )


def _note_to_text(note) -> str:
    parts = []
    if note.title:
        parts.append(note.title)
    if note.overview:
        parts.append(note.overview)
    ki = note.key_ideas if isinstance(note.key_ideas, list) else []
    for k in ki:
        if isinstance(k, dict):
            parts.append(k.get("idea", ""))
        elif isinstance(k, str):
            parts.append(k)
    dfs = note.definitions if isinstance(note.definitions, list) else []
    for d in dfs:
        if isinstance(d, dict):
            parts.append(f"{d.get('term','')}: {d.get('definition','')}")
    return "\n".join(p for p in parts if p)


def _is_postgres(db: Session) -> bool:
    return db.bind is not None and db.bind.dialect.name == "postgresql"


def _semantic_candidates(db: Session, course_id: int, q_emb: List[float], limit: int) -> List[tuple]:
    """Return (SearchDocument, similarity) pairs for the query embedding.

    On Postgres this runs the similarity search inside the database using
    pgvector's cosine-distance operator (indexed via the HNSW index created in
    init_db) instead of pulling every candidate row into Python. SQLite (used
    in tests, where the Vector column is monkey-patched to JSON) falls back to
    the original in-process scoring loop over a bounded candidate set.
    """
    if _is_postgres(db):
        try:
            distance = SearchDocument.embedding.cosine_distance(q_emb)
            rows = (
                db.query(SearchDocument, distance.label("distance"))
                .filter(SearchDocument.course_id == course_id, SearchDocument.embedding.isnot(None))
                .order_by(distance)
                .limit(limit)
                .all()
            )
            return [(d, max(0.0, 1.0 - dist)) for d, dist in rows]
        except Exception:
            logger.warning("pgvector similarity query failed, falling back to Python scoring", exc_info=True)

    docs = db.query(SearchDocument).filter(
        SearchDocument.course_id == course_id,
        SearchDocument.embedding.isnot(None),
    ).limit(200).all()
    scored = [(d, cosine_similarity(q_emb, d.embedding) if d.embedding is not None else 0.0) for d in docs]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


def search_hybrid(
    db: Session,
    course_id: int,
    query: str,
    mode: str = "hybrid",
    limit: int = 20,
) -> List[Dict[str, Any]]:
    query = query.strip()
    if not query:
        return []

    t0 = time.perf_counter()
    # doc.id -> {"doc": SearchDocument, "score": float}
    scored_docs: Dict[int, Dict[str, Any]] = {}

    if mode in ("keyword", "hybrid"):
        try:
            docs = (
                db.query(SearchDocument)
                .filter(
                    SearchDocument.course_id == course_id,
                    text("to_tsvector('english', content) @@ plainto_tsquery('english', :q)")
                )
                .params(q=query)
                .limit(limit)
                .all()
            )
        except Exception:
            safe = f"%{query}%"
            docs = (
                db.query(SearchDocument)
                .filter(SearchDocument.course_id == course_id)
                .filter(
                    (SearchDocument.content.ilike(safe))
                    | (SearchDocument.title.ilike(safe))
                )
                .limit(limit)
                .all()
            )
        for i, d in enumerate(docs):
            kw_score = (1.0 - (i * 0.05)) * 0.5
            if d.id in scored_docs:
                scored_docs[d.id]["score"] += kw_score
            else:
                scored_docs[d.id] = {"doc": d, "score": kw_score}

    if mode in ("semantic", "meaning", "hybrid"):
        try:
            prov = get_embedding_provider()
            q_emb = prov.embed_texts([query])[0]
            for d, sim in _semantic_candidates(db, course_id, q_emb, limit):
                sem_score = sim * 0.7
                if d.id in scored_docs:
                    scored_docs[d.id]["score"] += sem_score
                else:
                    scored_docs[d.id] = {"doc": d, "score": sem_score}
        except Exception:
            logger.warning("Semantic search branch failed", exc_info=True)

    if mode not in ("keyword", "semantic", "meaning", "hybrid"):
        docs = (
            db.query(SearchDocument)
            .filter(SearchDocument.course_id == course_id)
            .filter(SearchDocument.content.ilike(f"%{query}%"))
            .limit(limit)
            .all()
        )
        for d in docs:
            scored_docs[d.id] = {"doc": d, "score": 0.5}

    top = sorted(scored_docs.values(), key=lambda r: r["score"], reverse=True)[:limit]

    # Batch-fetch the lectures needed for just the final result set (one query)
    # instead of one query per document, and without the previous unbounded,
    # never-invalidated module-level cache.
    lecture_ids = {e["doc"].lecture_id for e in top if e["doc"].lecture_id}
    lectures_by_id: Dict[int, Lecture] = {}
    if lecture_ids:
        for l in db.query(Lecture).filter(Lecture.id.in_(lecture_ids)).all():
            lectures_by_id[l.id] = l

    results = [_to_result(e["doc"], e["score"], query, lectures_by_id.get(e["doc"].lecture_id)) for e in top]
    logger.info(
        "search_hybrid course=%s mode=%s results=%d duration_ms=%.1f",
        course_id, mode, len(results), (time.perf_counter() - t0) * 1000,
    )
    return results


def _to_result(d: SearchDocument, score: float, query: str, lecture: Optional[Lecture]) -> Dict[str, Any]:
    snippet = d.snippet or d.content[:300]
    if query:
        snippet = highlight_snippet(d.content, query)

    return {
        "document_id": d.id,
        "doc_type": d.doc_type,
        "lecture_id": d.lecture_id,
        "lecture_title": lecture.title if lecture else None,
        "lecture_number": lecture.lecture_number if lecture else None,
        "title": d.title,
        "snippet": snippet,
        "relevance_score": round(score, 4),
        "source_reference": f"Lecture {lecture.lecture_number}" if lecture and lecture.lecture_number else (f"Lecture {lecture.id}" if lecture else ""),
        "content": d.content,
        "metadata": d.doc_metadata or {},
        "_score_raw": score,
    }


def highlight_snippet(text: str, query: str, window: int = 100) -> str:
    if not text or not query:
        return text[:300]
    lower = text.lower()
    q = query.lower()
    idx = lower.find(q)
    if idx == -1:
        return text[:300]
    start = max(0, idx - window)
    end = min(len(text), idx + len(query) + window)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet
