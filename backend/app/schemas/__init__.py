from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRead(UserBase):
    id: int
    is_demo: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CourseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = "#4f46e5"


class CourseCreate(CourseBase):
    pass


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = None


class CourseRead(CourseBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class CourseStats(BaseModel):
    id: int
    name: str
    color: str
    lecture_count: int
    topic_count: int
    last_updated: datetime


class LectureAssetRead(BaseModel):
    id: int
    asset_type: str
    file_name: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class TranscriptSegmentRead(BaseModel):
    id: int
    segment_index: int
    text: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    source_type: str
    model_config = ConfigDict(from_attributes=True)


class LectureBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    lecture_number: Optional[int] = None
    lecture_date: Optional[datetime] = None
    description: Optional[str] = None


class LectureCreate(LectureBase):
    course_id: int
    transcript_text: Optional[str] = None


class LectureUpdate(BaseModel):
    title: Optional[str] = None
    lecture_number: Optional[int] = None
    lecture_date: Optional[datetime] = None
    description: Optional[str] = None


class ProcessingJobRead(BaseModel):
    id: int
    lecture_id: int
    job_type: str
    status: str
    current_step: Optional[str] = None
    progress: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class LectureRead(LectureBase):
    id: int
    course_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    assets: List[LectureAssetRead] = []
    latest_job: Optional[ProcessingJobRead] = None
    model_config = ConfigDict(from_attributes=True)


class LectureNoteRead(BaseModel):
    id: int
    lecture_id: int
    title: Optional[str] = None
    overview: Optional[str] = None
    headings: Optional[Any] = None
    key_ideas: Optional[Any] = None
    definitions: Optional[Any] = None
    examples: Optional[Any] = None
    relationships: Optional[Any] = None
    source_references: Optional[Any] = None
    model_config = ConfigDict(from_attributes=True)


class UploadResponse(BaseModel):
    lecture_id: int
    job_id: int
    message: str


class TopicBase(BaseModel):
    name: str
    canonical_name: str
    description: Optional[str] = None


class TopicRead(TopicBase):
    id: int
    course_id: int
    coverage_score: float
    lecture_count: int
    evidence_count: int
    aliases: Optional[Any] = None
    related_topics: Optional[Any] = None
    model_config = ConfigDict(from_attributes=True)


class TopicMentionRead(BaseModel):
    id: int
    topic_id: int
    lecture_id: int
    context: str
    start_time: Optional[float] = None
    source_type: str
    confidence: float
    lecture_title: Optional[str] = None
    lecture_number: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class TopicTimelineEvent(BaseModel):
    lecture_id: int
    lecture_number: Optional[int]
    lecture_title: str
    event_type: str
    context: str
    evidence_count: int


class TopicTimeline(BaseModel):
    topic_id: int
    topic_name: str
    events: List[TopicTimelineEvent]


class EvidenceSnippet(BaseModel):
    lecture_id: int
    lecture_title: str
    lecture_number: Optional[int]
    context: str
    start_time: Optional[float] = None
    source_type: str


class TopicDetail(BaseModel):
    topic: TopicRead
    evidence: List[EvidenceSnippet]
    related: List[TopicRead]


class StudyGuideTopic(BaseModel):
    topic_id: int
    name: str
    coverage_score: float
    lecture_count: int
    evidence_count: int
    summary: Optional[str] = None
    lectures: List[Dict[str, Any]] = []


class StudyGuideRead(BaseModel):
    id: int
    course_id: int
    version: int
    title: str
    content: Any
    top_topics: Optional[Any] = None
    generated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SearchResult(BaseModel):
    document_id: int
    doc_type: str
    lecture_id: Optional[int] = None
    lecture_title: Optional[str] = None
    title: str
    snippet: str
    relevance_score: float
    source_reference: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    search_mode: str
    results: List[SearchResult]
    total: int


class AskRequest(BaseModel):
    course_id: int
    question: str
    session_id: Optional[int] = None


class Citation(BaseModel):
    lecture_id: int
    lecture_title: str
    lecture_number: Optional[int] = None
    snippet: str
    start_time: Optional[float] = None


class AskResponse(BaseModel):
    answer: str
    citations: List[Citation] = []
    session_id: int
    found_in_material: bool = True


class QuizQuestionRead(BaseModel):
    id: int
    question_type: str
    question_text: str
    options: Optional[Any] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    source_lecture_id: Optional[int] = None
    source_context: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class QuizRead(BaseModel):
    id: int
    course_id: int
    title: str
    quiz_type: str
    generated_at: datetime
    questions: List[QuizQuestionRead] = []
    model_config = ConfigDict(from_attributes=True)


class QuizGenerateRequest(BaseModel):
    course_id: int
    topic_ids: Optional[List[int]] = None
    num_questions: int = Field(default=10, ge=1, le=50)
    quiz_type: str = "mcq"


class QuizSubmitRequest(BaseModel):
    answers: Dict[int, int] = Field(..., description="question_id -> selected option index")


class QuizAttemptRead(BaseModel):
    id: int
    quiz_id: int
    score: int
    total_questions: int
    answers: Optional[Any] = None
    completed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ChatMessageRead(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    citations: Optional[Any] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ChatSessionRead(BaseModel):
    id: int
    course_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageRead] = []
    model_config = ConfigDict(from_attributes=True)


class KnowledgeMapNode(BaseModel):
    id: int
    label: str
    size: float
    coverage_score: float
    lecture_count: int


class KnowledgeMapEdge(BaseModel):
    source: int
    target: int
    weight: float


class KnowledgeMap(BaseModel):
    nodes: List[KnowledgeMapNode]
    edges: List[KnowledgeMapEdge]


class DashboardStats(BaseModel):
    total_courses: int
    total_lectures: int
    total_topics: int
    processing_jobs: int
    frequently_covered: List[TopicRead]
    recent_jobs: List[ProcessingJobRead]
    course_stats: List[CourseStats]


class CoverageEntry(BaseModel):
    lecture_number: Optional[int]
    lecture_title: str
    lecture_date: Optional[datetime]
    mentions: int
    first_seen: bool
    depth: str
