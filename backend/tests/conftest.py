import os
import sys
import uuid
from pathlib import Path
from typing import Generator

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-prod-0000000000")
os.environ.setdefault("STORAGE_DIR", str(BACKEND_ROOT / "tests" / "_storage_tmp"))
os.environ.setdefault("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024))

_TEST_DB = os.environ.get("TEST_DATABASE_URL")
_TEST_USE_SQLITE = _TEST_DB is None

if _TEST_USE_SQLITE:
    _db_file = BACKEND_ROOT / "tests" / f"_test_{uuid.uuid4().hex}.db"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{_db_file}")
else:
    os.environ.setdefault("DATABASE_URL", _TEST_DB)


from sqlalchemy import create_engine, event, Column, LargeBinary, String
from sqlalchemy.orm import sessionmaker, Session

from app.db.session import Base, get_db
from app.core.config import get_settings
from app.core.security import create_access_token, get_password_hash
from fastapi.testclient import TestClient


def _monkey_patch_vector_for_sqlite():
    """On SQLite, pgvector Vector type is unavailable; map to LargeBinary/BLOB so tables can create."""
    import sys
    from types import ModuleType
    try:
        from pgvector.sqlalchemy import Vector as _RealVector  # noqa: F401
        _have_pgvector = True
    except Exception:
        _have_pgvector = False
        class _FakeVecType(String):
            """In tests without pgvector, use JSON instead of raw Vector for list[float] payloads."""
            python_type = list
            def __init__(self, *args, **kwargs):
                super().__init__(length=None)
        _fake_pg = ModuleType("pgvector")
        _fake_pg_sql = ModuleType("pgvector.sqlalchemy")
        _fake_pg_sql.Vector = _FakeVecType
        _fake_pg.sqlalchemy = _fake_pg_sql
        sys.modules["pgvector"] = _fake_pg
        sys.modules["pgvector.sqlalchemy"] = _fake_pg_sql

    import app.models as _models
    if _TEST_USE_SQLITE or not _have_pgvector:
        from sqlalchemy import JSON as _JSON
        for cls in vars(_models).values():
            if not isinstance(cls, type):
                continue
            if not hasattr(cls, "__table__"):
                continue
            for col in list(cls.__table__.columns):
                tname = type(col.type).__name__.lower()
                if "vector" in tname or "fakevec" in tname:
                    col.type = _JSON()


_monkey_patch_vector_for_sqlite()


@pytest.fixture(scope="session")
def _test_db_path():
    if _TEST_USE_SQLITE:
        yield BACKEND_ROOT / "tests" / "_storage_tmp"
    else:
        yield None


@pytest.fixture(scope="session")
def _db_engine():
    settings = get_settings()
    if _TEST_USE_SQLITE:
        engine = create_engine(settings.DATABASE_URL, future=True, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _enable_fk(dbapi_connection, connection_record):
            try:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
            except Exception:
                pass
    else:
        engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
        try:
            with engine.begin() as conn:
                from sqlalchemy import text
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        except Exception:
            pass
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session")
def _db_session_factory(_db_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=_db_engine, future=True)


@pytest.fixture
def db(_db_session_factory) -> Generator[Session, None, None]:
    session: Session = _db_session_factory()
    try:
        yield session
    finally:
        for tbl in reversed(Base.metadata.sorted_tables):
            try:
                session.execute(tbl.delete())
            except Exception:
                pass
        session.commit()
        session.close()


@pytest.fixture
def app():
    from app.main import app as _app
    return _app


@pytest.fixture
def client(app, db) -> Generator[TestClient, None, None]:
    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def user(db):
    from app.models import User
    u = User(
        email="alice@example.com",
        full_name="Alice Test",
        hashed_password=get_password_hash("password123"),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def user2(db):
    from app.models import User
    u = User(
        email="bob@example.com",
        full_name="Bob Stranger",
        hashed_password=get_password_hash("qwerty987"),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def auth_headers(user):
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_u2(user2):
    token = create_access_token(subject=str(user2.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def demo_headers():
    from app.core.config import get_settings
    settings = get_settings()
    token = create_access_token(subject=str(settings.DEMO_USER_ID))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seed_course(client, auth_headers):
    res = client.post("/api/courses", json={
        "name": "Data Structures & Algorithms",
        "description": "Semester-long DSA overview.",
        "color": "#6366f1",
    }, headers=auth_headers)
    assert res.status_code == 201 or res.status_code == 200
    return res.json()
