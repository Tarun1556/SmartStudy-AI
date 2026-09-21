"""Read-only topic matching for exam questions.

Reuses the same embedding-cosine-similarity mechanism as
app.services.topics.find_or_create_topic, but never creates a new Topic —
question papers should link to topics that already exist from lecture
coverage, not mint new ones. Uses a separate, lower threshold than
TOPIC_SIMILARITY_THRESHOLD (which governs stricter topic-label-to-topic-label
dedup) because matching a full question sentence against a short topic
name/description scores lower even for a correct match.
"""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import Topic
from app.services.embeddings import cosine_similarity
from app.core.config import get_settings

settings = get_settings()


def match_topic_for_text(
    db: Session,
    course_id: int,
    text: str,
    question_embedding: Optional[List[float]] = None,
    existing_topics: Optional[List[Topic]] = None,
    threshold: Optional[float] = None,
) -> Tuple[Optional[Topic], float]:
    """Return the best-matching course Topic for `text` and its confidence.

    Returns (None, 0.0) when nothing clears the threshold — an uncertain
    mapping is left unmapped rather than forced onto the nearest topic.
    """
    if not text or not text.strip():
        return None, 0.0

    if existing_topics is None:
        existing_topics = db.query(Topic).filter(Topic.course_id == course_id).all()
    embedded_topics = [t for t in existing_topics if t.embedding is not None]
    if not embedded_topics:
        return None, 0.0

    if question_embedding is None:
        from app.services.embeddings import get_embedding_provider
        try:
            question_embedding = get_embedding_provider().embed_texts([text])[0]
        except Exception:
            return None, 0.0

    thresh = threshold if threshold is not None else settings.EXAM_TOPIC_MATCH_THRESHOLD

    best_topic: Optional[Topic] = None
    best_score = 0.0
    for t in embedded_topics:
        sim = cosine_similarity(question_embedding, t.embedding)
        if sim > best_score:
            best_score = sim
            best_topic = t

    if best_topic is not None and best_score >= thresh:
        return best_topic, round(best_score, 4)
    return None, 0.0
