from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import User, Course
from app.schemas import SearchResponse, SearchResult
from app.services.search import search_hybrid

router = APIRouter()


def _check_course_owner(db, course_id, user):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if user.is_demo:
        if course.user_id != 0:
            raise HTTPException(status_code=403, detail="Not authorized")
    elif course.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return course


@router.get("", response_model=SearchResponse)
def search_endpoint(
    q: str = Query(..., min_length=1),
    course_id: Optional[int] = None,
    mode: str = Query("hybrid", pattern="^(keyword|semantic|meaning|hybrid)$"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if course_id:
        _check_course_owner(db, course_id, current_user)
    else:
        if not current_user.is_demo:
            owned_courses = [c.id for c in db.query(Course.id).filter(Course.user_id == current_user.id).all()]
        else:
            owned_courses = [c.id for c in db.query(Course.id).filter(Course.user_id == 0).all()]
        if not owned_courses:
            return SearchResponse(query=q, search_mode=mode, results=[], total=0)
        from app.models import SearchDocument
        results_raw = []
        for cid in owned_courses:
            per = search_hybrid(db, cid, q, mode=mode, limit=limit)
            results_raw.extend(per)
        results_raw.sort(key=lambda r: r["relevance_score"], reverse=True)
        results_raw = results_raw[:limit]
        results = [
            SearchResult(
                document_id=r["document_id"],
                doc_type=r["doc_type"],
                lecture_id=r["lecture_id"],
                lecture_title=r["lecture_title"],
                title=r["title"],
                snippet=r["snippet"],
                relevance_score=r["relevance_score"],
                source_reference=r["source_reference"],
            )
            for r in results_raw
        ]
        return SearchResponse(query=q, search_mode=mode, results=results, total=len(results))

    results_raw = search_hybrid(db, course_id, q, mode=mode, limit=limit)
    results = [
        SearchResult(
            document_id=r["document_id"],
            doc_type=r["doc_type"],
            lecture_id=r["lecture_id"],
            lecture_title=r["lecture_title"],
            title=r["title"],
            snippet=r["snippet"],
            relevance_score=r["relevance_score"],
            source_reference=r["source_reference"],
        )
        for r in results_raw
    ]
    return SearchResponse(query=q, search_mode=mode, results=results, total=len(results))
