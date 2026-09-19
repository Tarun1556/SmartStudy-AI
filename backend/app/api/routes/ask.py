from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import (
    User, Course, SearchDocument, ChatSession, ChatMessage, Lecture
)
from app.schemas import AskRequest, AskResponse, Citation, ChatSessionRead, ChatMessageRead
from app.services.search import search_hybrid
from app.services.llm import get_llm_provider

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


@router.post("", response_model=AskResponse)
def ask_question(
    req: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_course_owner(db, req.course_id, current_user)

    session_id = req.session_id
    if session_id:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if not session or session.course_id != req.course_id:
            session_id = None

    if not session_id:
        title = req.question[:60] + ("…" if len(req.question) > 60 else "")
        session = ChatSession(course_id=req.course_id, title=title)
        db.add(session)
        db.flush()
        session_id = session.id
    else:
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()

    user_msg = ChatMessage(session_id=session_id, role="user", content=req.question)
    db.add(user_msg)

    retrieved = search_hybrid(db, req.course_id, req.question, mode="hybrid", limit=8)
    context_chunks = []
    for r in retrieved:
        lecture = db.query(Lecture).filter(Lecture.id == r.get("lecture_id")).first() if r.get("lecture_id") else None
        context_chunks.append({
            "lecture_id": r.get("lecture_id"),
            "lecture_title": lecture.title if lecture else r.get("lecture_title", "Unknown"),
            "lecture_number": lecture.lecture_number if lecture else r.get("metadata", {}).get("lecture_number"),
            "content": r.get("content", r.get("snippet", "")),
            "snippet": r.get("snippet", ""),
            "start_time": r.get("metadata", {}).get("start_time") if isinstance(r.get("metadata"), dict) else None,
        })

    llm = get_llm_provider()
    answer_data = llm.answer_question(req.question, context_chunks)

    answer = answer_data.get("answer", "")
    citations_raw = answer_data.get("citations", []) or []
    found = bool(answer_data.get("found_in_material", True)) and bool(citations_raw or "could not find" not in answer.lower())

    citations = []
    seen_lectures = set()
    for c in citations_raw[:6]:
        lid = c.get("lecture_id")
        if lid in seen_lectures:
            continue
        seen_lectures.add(lid)
        citations.append(Citation(
            lecture_id=lid,
            lecture_title=c.get("lecture_title", "Unknown"),
            lecture_number=c.get("lecture_number"),
            snippet=c.get("snippet", "")[:300],
            start_time=c.get("start_time"),
        ))

    citations_dict = [
        {
            "lecture_id": c.lecture_id,
            "lecture_title": c.lecture_title,
            "lecture_number": c.lecture_number,
            "snippet": c.snippet,
            "start_time": c.start_time,
        }
        for c in citations
    ]

    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=answer,
        citations=citations_dict,
    )
    db.add(assistant_msg)
    db.commit()

    return AskResponse(
        answer=answer,
        citations=citations,
        session_id=session_id,
        found_in_material=found,
    )


@router.get("/sessions/{course_id}", response_model=list[ChatSessionRead])
def list_sessions(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_course_owner(db, course_id, current_user)
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.course_id == course_id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return sessions


@router.get("/session/{session_id}", response_model=ChatSessionRead)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _check_course_owner(db, session.course_id, current_user)
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.id).all()
    session.messages = messages
    return session
