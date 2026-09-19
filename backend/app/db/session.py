import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("studyapp.db")

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from pgvector.sqlalchemy import Vector
    from app.db.base import Base
    from app import models

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(bind=engine)

    if engine.dialect.name == "postgresql":
        _ensure_vector_indexes()


def _ensure_vector_indexes():
    """Index the pgvector columns used for similarity search.

    Without this, search_hybrid's semantic branch and topic-merging similarity
    queries fall back to a sequential scan even when they use the native
    `<=>` operator. HNSW is used (rather than IVFFlat) because it needs no
    `lists` parameter tuned to row count and works correctly from an empty
    table, which matters for a demo app that starts with no data.
    Wrapped defensively: an older pgvector extension without HNSW support
    (<0.5) should not prevent the app from starting.
    """
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_search_documents_embedding_hnsw "
        "ON search_documents USING hnsw (embedding vector_cosine_ops)",
        "CREATE INDEX IF NOT EXISTS ix_topics_embedding_hnsw "
        "ON topics USING hnsw (embedding vector_cosine_ops)",
    ]
    for stmt in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception as e:
            logger.warning("Could not create vector index (%s): %s", stmt.split(" ")[5], e)
