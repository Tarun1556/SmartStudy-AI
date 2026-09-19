from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from collections import defaultdict
import re

from app.models import Topic, TopicMention, Course, Lecture
from app.services.embeddings import get_embedding_provider, cosine_similarity
from app.core.config import get_settings

settings = get_settings()


def _normalize(name: str) -> str:
    return re.sub(r'[^\w\s]', '', name.lower()).strip()


def find_or_create_topic(
    db: Session,
    course_id: int,
    candidate: Dict[str, Any],
    existing_topics: Optional[List[Topic]] = None,
) -> Tuple[Topic, bool]:
    if existing_topics is None:
        existing_topics = db.query(Topic).filter(Topic.course_id == course_id).all()

    cand_name = candidate.get("name", "").strip()
    cand_normalized = _normalize(cand_name).rstrip("s")
    cand_aliases = set(cand_normalized)
    for a in candidate.get("aliases", []) or []:
        cand_aliases.add(_normalize(str(a)).rstrip("s"))

    emb_provider = get_embedding_provider()
    threshold = settings.TOPIC_SIMILARITY_THRESHOLD

    best_match: Optional[Topic] = None
    best_score = 0.0

    cand_text = cand_name + " " + candidate.get("description", "")
    cand_emb = None

    for t in existing_topics:
        t_normalized = _normalize(t.canonical_name).rstrip("s")
        if t_normalized == cand_normalized or cand_normalized == t_normalized:
            return t, False

        aliases = t.aliases if isinstance(t.aliases, list) else []
        for a in aliases:
            if _normalize(str(a)).rstrip("s") == cand_normalized:
                return t, False

        if t.embedding is not None and cand_emb is None:
            try:
                cand_emb = emb_provider.embed_texts([cand_text])[0]
            except Exception:
                cand_emb = None

        if t.embedding is not None and cand_emb is not None:
            sim = cosine_similarity(cand_emb, t.embedding)
            if sim >= threshold and sim > best_score:
                best_score = sim
                best_match = t

    if best_match is not None:
        return best_match, False

    canonical = cand_name or "Unnamed Topic"
    aliases_list = [cand_name] + [a for a in candidate.get("aliases", []) if a != cand_name]

    topic = Topic(
        course_id=course_id,
        name=cand_name,
        canonical_name=canonical,
        description=candidate.get("description", ""),
        aliases=aliases_list,
        coverage_score=0.0,
        lecture_count=0,
        evidence_count=0,
    )
    db.add(topic)
    db.flush()

    try:
        texts = [canonical + " " + (candidate.get("description", "") or "")]
        embs = emb_provider.embed_texts(texts)
        topic.embedding = embs[0]
    except Exception:
        pass

    return topic, True


def add_topic_mention(
    db: Session,
    topic_id: int,
    lecture_id: int,
    context: str,
    transcript_segment_id: Optional[int] = None,
    start_time: Optional[float] = None,
    source_type: str = "text",
    confidence: float = 1.0,
) -> TopicMention:
    mention = TopicMention(
        topic_id=topic_id,
        lecture_id=lecture_id,
        transcript_segment_id=transcript_segment_id,
        context=context[:1000],
        start_time=start_time,
        source_type=source_type,
        confidence=confidence,
    )
    db.add(mention)
    return mention


def recalculate_topic_stats(db: Session, course_id: int) -> None:
    topics = db.query(Topic).filter(Topic.course_id == course_id).all()
    for t in topics:
        mentions = db.query(TopicMention).filter(TopicMention.topic_id == t.id).all()
        lecture_ids = set(m.lecture_id for m in mentions)
        source_types = set(m.source_type for m in mentions)

        lecture_count = len(lecture_ids)
        evidence_count = len(mentions)
        src_count = len(source_types)

        lectures = db.query(Lecture).filter(Lecture.course_id == course_id).all()
        total_lectures = max(1, len(lectures))

        lecture_span = lecture_count / total_lectures
        evidence_norm = min(1.0, evidence_count / max(5, total_lectures * 3))
        source_norm = min(1.0, src_count / 3.0)

        score = (
            0.5 * lecture_span
            + 0.35 * evidence_norm
            + 0.15 * source_norm
        )

        t.lecture_count = lecture_count
        t.evidence_count = evidence_count
        t.coverage_score = round(min(1.0, score), 4)

        related = find_related_topics(db, t, limit=5)
        t.related_topics = [
            {"id": r.id, "name": r.canonical_name, "score": s}
            for r, s in related if r.id != t.id
        ]

    db.flush()


def find_related_topics(db: Session, topic: Topic, limit: int = 5) -> List[Tuple[Topic, float]]:
    if topic.embedding is None:
        return []
    others = (
        db.query(Topic)
        .filter(Topic.course_id == topic.course_id, Topic.id != topic.id, Topic.embedding.isnot(None))
        .all()
    )
    scored = []
    for o in others:
        sim = cosine_similarity(topic.embedding, o.embedding)
        if sim >= 0.5:
            scored.append((o, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


def get_topic_timeline(db: Session, topic_id: int) -> List[Dict[str, Any]]:
    mentions = (
        db.query(TopicMention)
        .filter(TopicMention.topic_id == topic_id)
        .order_by(TopicMention.id)
        .all()
    )
    by_lecture: Dict[int, List[TopicMention]] = defaultdict(list)
    for m in mentions:
        by_lecture[m.lecture_id].append(m)

    events = []
    first = True
    lecture_ids_sorted = sorted(by_lecture.keys())
    for lid in lecture_ids_sorted:
        lecture = db.query(Lecture).filter(Lecture.id == lid).first()
        if not lecture:
            continue
        ms = by_lecture[lid]
        depth = "Introduced" if first else "Revisited"
        if len(ms) >= 3:
            depth = "Expanded" if not first else depth
        if first:
            first = False
        events.append({
            "lecture_id": lecture.id,
            "lecture_number": lecture.lecture_number,
            "lecture_title": lecture.title,
            "lecture_date": lecture.lecture_date,
            "event_type": depth,
            "context": ms[0].context[:300],
            "evidence_count": len(ms),
        })
    return events


def get_knowledge_map(db: Session, course_id: int) -> Dict[str, Any]:
    topics = db.query(Topic).filter(Topic.course_id == course_id).order_by(Topic.coverage_score.desc()).limit(60).all()
    nodes = []
    max_score = max((t.coverage_score for t in topics), default=1.0) or 1.0
    for t in topics:
        nodes.append({
            "id": t.id,
            "label": t.canonical_name,
            "size": 4 + 16 * (t.coverage_score / max_score),
            "coverage_score": t.coverage_score,
            "lecture_count": t.lecture_count,
        })

    edges = []
    for i, t in enumerate(topics):
        related = t.related_topics if isinstance(t.related_topics, list) else []
        seen_pairs = set()
        for rel in related[:4]:
            other_id = rel.get("id")
            weight = rel.get("score", 0.5)
            if other_id and any(n["id"] == other_id for n in nodes):
                pair = (min(t.id, other_id), max(t.id, other_id))
                if pair not in seen_pairs and weight >= 0.5:
                    seen_pairs.add(pair)
                    edges.append({
                        "source": t.id,
                        "target": other_id,
                        "weight": float(weight),
                    })
    return {"nodes": nodes, "edges": edges}
