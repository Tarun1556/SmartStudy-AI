from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean,
    Float, JSON, BigInteger, Enum, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.session import Base
import enum


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    courses: Mapped[List["Course"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(7), default="#4f46e5", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="courses")
    lectures: Mapped[List["Lecture"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    topics: Mapped[List["Topic"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    study_guides: Mapped[List["StudyGuide"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    search_documents: Mapped[List["SearchDocument"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    quizzes: Mapped[List["Quiz"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    chat_sessions: Mapped[List["ChatSession"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    question_papers: Mapped[List["QuestionPaper"]] = relationship(back_populates="course", cascade="all, delete-orphan")


class Lecture(Base):
    __tablename__ = "lectures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    lecture_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lecture_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="lectures")
    assets: Mapped[List["LectureAsset"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    transcript_segments: Mapped[List["TranscriptSegment"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    notes: Mapped[Optional["LectureNote"]] = relationship(back_populates="lecture", uselist=False, cascade="all, delete-orphan")
    topic_mentions: Mapped[List["TopicMention"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    processing_jobs: Mapped[List["ProcessingJob"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")
    search_documents: Mapped[List["SearchDocument"]] = relationship(back_populates="lecture", cascade="all, delete-orphan")


class LectureAsset(Base):
    __tablename__ = "lecture_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lecture_id: Mapped[int] = mapped_column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    lecture: Mapped["Lecture"] = relationship(back_populates="assets")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lecture_id: Mapped[int] = mapped_column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    current_step: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    lecture: Mapped["Lecture"] = relationship(back_populates="processing_jobs")


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lecture_id: Mapped[int] = mapped_column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    end_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="transcript", nullable=False)

    lecture: Mapped["Lecture"] = relationship(back_populates="transcript_segments")

    __table_args__ = (
        Index("ix_transcript_segments_lecture_idx", "lecture_id", "segment_index"),
    )


class LectureNote(Base):
    __tablename__ = "lecture_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lecture_id: Mapped[int] = mapped_column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    overview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    headings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    key_ideas: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    definitions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    examples: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    relationships: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source_references: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    lecture: Mapped["Lecture"] = relationship(back_populates="notes")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    coverage_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    lecture_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(384), nullable=True)
    aliases: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    related_topics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="topics")
    mentions: Mapped[List["TopicMention"]] = relationship(back_populates="topic", cascade="all, delete-orphan")


class TopicMention(Base):
    __tablename__ = "topic_mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    topic_id: Mapped[int] = mapped_column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True)
    lecture_id: Mapped[int] = mapped_column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=False, index=True)
    transcript_segment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("transcript_segments.id", ondelete="SET NULL"), nullable=True)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="text", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    topic: Mapped["Topic"] = relationship(back_populates="mentions")
    lecture: Mapped["Lecture"] = relationship(back_populates="topic_mentions")

    __table_args__ = (
        Index("ix_topic_mentions_topic_lecture", "topic_id", "lecture_id"),
    )


class StudyGuide(Base):
    __tablename__ = "study_guides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    top_topics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="study_guides")


class SearchDocument(Base):
    __tablename__ = "search_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    lecture_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("lectures.id", ondelete="CASCADE"), nullable=True, index=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    snippet: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(384), nullable=True)
    doc_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="search_documents")
    lecture: Mapped["Lecture"] = relationship(back_populates="search_documents")


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    quiz_type: Mapped[str] = mapped_column(String(50), default="mcq", nullable=False)
    topic_filter: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="quizzes")
    questions: Mapped[List["QuizQuestion"]] = relationship(back_populates="quiz", cascade="all, delete-orphan")
    attempts: Mapped[List["QuizAttempt"]] = relationship(back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    quiz_id: Mapped[int] = mapped_column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    question_type: Mapped[str] = mapped_column(String(50), default="mcq", nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_lecture_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("lectures.id", ondelete="SET NULL"), nullable=True)
    source_topic_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    source_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    quiz: Mapped["Quiz"] = relationship(back_populates="questions")


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    quiz_id: Mapped[int] = mapped_column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    answers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    quiz: Mapped["Quiz"] = relationship(back_populates="attempts")

    __table_args__ = (
        Index("ix_quiz_attempts_quiz_user", "quiz_id", "user_id"),
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), default="New Session", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="chat_sessions")
    messages: Mapped[List["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class QuestionPaper(Base):
    """A previous semester/year exam paper uploaded for historical analysis.

    Deliberately mirrors Lecture's shape (status/timestamps/ownership-via-
    course) rather than introducing a new convention. Processing is tracked
    by a parallel QuestionPaperProcessingJob table instead of reusing
    ProcessingJob, because ProcessingJob.lecture_id is NOT NULL and
    create_all() cannot retrofit a schema change onto an existing table.
    """
    __tablename__ = "question_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    academic_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    semester: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    exam_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    course: Mapped["Course"] = relationship(back_populates="question_papers")
    questions: Mapped[List["QuestionPaperQuestion"]] = relationship(back_populates="question_paper", cascade="all, delete-orphan")
    processing_jobs: Mapped[List["QuestionPaperProcessingJob"]] = relationship(back_populates="question_paper", cascade="all, delete-orphan")


class QuestionPaperProcessingJob(Base):
    __tablename__ = "question_paper_processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_paper_id: Mapped[int] = mapped_column(Integer, ForeignKey("question_papers.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(100), default="question_paper_analysis", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    current_step: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    question_paper: Mapped["QuestionPaper"] = relationship(back_populates="processing_jobs")


class QuestionPaperQuestion(Base):
    __tablename__ = "question_paper_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_paper_id: Mapped[int] = mapped_column(Integer, ForeignKey("question_papers.id", ondelete="CASCADE"), nullable=False, index=True)
    question_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    section: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    marks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    topic_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True)
    topic_match_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    normalized_topic: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    question_paper: Mapped["QuestionPaper"] = relationship(back_populates="questions")
    topic: Mapped[Optional["Topic"]] = relationship()

    __table_args__ = (
        Index("ix_question_paper_questions_paper_topic", "question_paper_id", "topic_id"),
    )
