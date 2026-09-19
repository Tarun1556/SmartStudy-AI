from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User, Course, Topic, TopicMention, Lecture
from app.schemas import (
    TopicRead, TopicMentionRead, TopicTimeline, TopicDetail,
    TopicTimelineEvent, EvidenceSnippet, KnowledgeMap
)
from app.services.topics import get_topic_timeline, get_knowledge_map

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


def _check_topic_course(db, topic_id, user):
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    _check_course_owner(db, topic.course_id, user)
    return topic


@router.get("/courses/{course_id}/topics", response_model=List[TopicRead])
def list_course_topics(
    course_id: int,
    min_coverage: float = 0.0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_course_owner(db, course_id, current_user)
    topics = (
        db.query(Topic)
        .filter(Topic.course_id == course_id, Topic.coverage_score >= min_coverage)
        .order_by(Topic.coverage_score.desc(), Topic.lecture_count.desc())
        .limit(limit)
        .all()
    )
    return topics


@router.get("/topics/{topic_id}", response_model=TopicDetail)
def get_topic_detail(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = _check_topic_course(db, topic_id, current_user)

    mentions = (
        db.query(TopicMention)
        .filter(TopicMention.topic_id == topic_id)
        .order_by(TopicMention.id.desc())
        .limit(30)
        .all()
    )
    evidence = []
    for m in mentions:
        lecture = db.query(Lecture).filter(Lecture.id == m.lecture_id).first()
        evidence.append(EvidenceSnippet(
            lecture_id=m.lecture_id,
            lecture_title=lecture.title if lecture else "Unknown",
            lecture_number=lecture.lecture_number if lecture else None,
            context=m.context,
            start_time=m.start_time,
            source_type=m.source_type,
        ))

    related_raw = topic.related_topics if isinstance(topic.related_topics, list) else []
    related_ids = [r.get("id") for r in related_raw if isinstance(r, dict) and r.get("id")]
    related_topics = db.query(Topic).filter(Topic.id.in_(related_ids)).all() if related_ids else []

    return TopicDetail(
        topic=TopicRead.model_validate(topic),
        evidence=evidence,
        related=[TopicRead.model_validate(t) for t in related_topics],
    )


@router.get("/topics/{topic_id}/timeline", response_model=TopicTimeline)
def get_topic_timeline_route(
    topic_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    topic = _check_topic_course(db, topic_id, current_user)
    events_raw = get_topic_timeline(db, topic_id)
    events = [TopicTimelineEvent(**e) for e in events_raw]
    return TopicTimeline(topic_id=topic.id, topic_name=topic.canonical_name, events=events)


@router.get("/topics/{topic_id}/evidence", response_model=List[TopicMentionRead])
def get_topic_evidence(
    topic_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_topic_course(db, topic_id, current_user)
    mentions = (
        db.query(TopicMention)
        .filter(TopicMention.topic_id == topic_id)
        .order_by(TopicMention.confidence.desc())
        .limit(limit)
        .all()
    )
    result = []
    for m in mentions:
        lecture = db.query(Lecture).filter(Lecture.id == m.lecture_id).first()
        read = TopicMentionRead.model_validate(m)
        if lecture:
            read.lecture_title = lecture.title
            read.lecture_number = lecture.lecture_number
        result.append(read)
    return result


@router.get("/courses/{course_id}/knowledge-map", response_model=KnowledgeMap)
def get_course_knowledge_map(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_course_owner(db, course_id, current_user)
    data = get_knowledge_map(db, course_id)
    return KnowledgeMap(**data)
