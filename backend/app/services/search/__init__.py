from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, and_

from app.models import SearchDocument, Course, Lecture, Topic, TopicMention
from app.services.embeddings import get_embedding_provider, cosine_similarity
from app.core.config import get_settings

settings = get_settings()


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

    results_map: Dict[int, Dict[str, Any]] = {}

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
            kw_score = 1.0 - (i * 0.05)
            if d.id in results_map:
                results_map[d.id]["score"] += kw_score * 0.5
            else:
                results_map[d.id] = _to_result(d, kw_score * 0.5, query)

    if mode in ("semantic", "meaning", "hybrid"):
        try:
            prov = get_embedding_provider()
            q_emb = prov.embed_texts([query])[0]
            docs = db.query(SearchDocument).filter(
                SearchDocument.course_id == course_id,
                SearchDocument.embedding.isnot(None),
            ).limit(200).all()

            scored = []
            for d in docs:
                sim = cosine_similarity(q_emb, d.embedding) if d.embedding is not None else 0.0
                scored.append((d, sim))
            scored.sort(key=lambda x: x[1], reverse=True)

            for d, sim in scored[:limit]:
                sem_score = sim
                if d.id in results_map:
                    results_map[d.id]["score"] += sem_score * 0.7
                    results_map[d.id]["relevance_score"] = round(results_map[d.id]["score"], 4)
                else:
                    results_map[d.id] = _to_result(d, sem_score * 0.7, query)
        except Exception:
            pass

    if mode not in ("keyword", "semantic", "meaning", "hybrid"):
        docs = (
            db.query(SearchDocument)
            .filter(SearchDocument.course_id == course_id)
            .filter(SearchDocument.content.ilike(f"%{query}%"))
            .limit(limit)
            .all()
        )
        for d in docs:
            results_map[d.id] = _to_result(d, 0.5, query)

    sorted_results = sorted(results_map.values(), key=lambda r: r["relevance_score"], reverse=True)
    return sorted_results[:limit]


def _to_result(d: SearchDocument, score: float, query: str = "") -> Dict[str, Any]:
    lecture_title = None
    lecture = None
    if d.lecture_id:
        lecture = db_get_lecture(d.lecture_id)
        if lecture:
            lecture_title = lecture.title

    snippet = d.snippet or d.content[:300]
    if query:
        snippet = highlight_snippet(d.content, query)

    return {
        "document_id": d.id,
        "doc_type": d.doc_type,
        "lecture_id": d.lecture_id,
        "lecture_title": lecture_title,
        "title": d.title,
        "snippet": snippet,
        "relevance_score": round(score, 4),
        "source_reference": f"Lecture {getattr(lecture, 'lecture_number', '?') if lecture else '?'}" if lecture else "",
        "content": d.content,
        "metadata": d.doc_metadata or {},
        "_score_raw": score,
    }


_lecture_cache: Dict[int, Any] = {}


def db_get_lecture(lecture_id: int):
    if lecture_id in _lecture_cache:
        return _lecture_cache[lecture_id]
    from app.db.session import SessionLocal
    try:
        db2 = SessionLocal()
        l = db2.query(Lecture).filter(Lecture.id == lecture_id).first()
        _lecture_cache[lecture_id] = l
        return l
    finally:
        try:
            db2.close()
        except Exception:
            pass


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
