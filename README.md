# 📚 StudyAI — The Lecture Knowledge System

**Turn a semester of scattered lectures into one living, queryable knowledge base — with topic tracking, coverage scoring, grounded Q&A, and auto-generated study guides & quizzes.**

<p align="left">
  <img alt="FastAPI" src="https://img.shields.io/badge/backend-FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/frontend-React%2018%20%2B%20TS-61DAFB?logo=react&logoColor=black">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/db-PostgreSQL%20%2B%20pgvector-336791?logo=postgresql&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/deploy-Docker%20Compose-2496ED?logo=docker&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-blue">
</p>

---

## What is this?

StudyAI ingests everything a course throws at a student — PDF slides, PPTX decks, recorded audio, plain notes — and converts it into **structured, cited study material** that accumulates and improves *across the whole course*, not just per file.

Upload lecture 1, then lecture 2, then lecture 12: StudyAI transcribes/extracts the content, writes structured notes, extracts key concepts, and **merges those concepts into one persistent knowledge graph per course** — so "BST" from week 2 and "Binary Search Tree" from week 9 become the *same* tracked topic, with a coverage score and a timeline of where it was introduced, revisited, and expanded.

On top of that knowledge base, StudyAI generates:

- **Grounded Q&A** — ask a question, get an answer synthesized strictly from your own uploaded material, with citations back to the exact lecture and timestamp/snippet.
- **Semantic search** — vector search across every note, transcript, and definition in a course.
- **Auto-compiled study guides** — a ranked, semester-long summary built from topic coverage, not a single document.
- **Practice quizzes** — MCQs generated from your material, each traceable to its source lecture/topic.
- **Knowledge maps & topic timelines** — a visual graph of how concepts relate and evolve lecture-to-lecture.

---

## Table of contents

- [Architecture](#architecture)
- [Data model](#data-model)
- [How a lecture becomes a knowledge graph (workflow)](#how-a-lecture-becomes-a-knowledge-graph-workflow)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Environment variables](#environment-variables)
- [API surface](#api-surface)
- [Testing](#testing)
- [Performance & reliability](#performance--reliability)
- [Design decisions](#design-decisions)
- [How this is different from NotebookLM & similar tools](#how-this-is-different-from-notebooklm--similar-tools)

---

## Architecture

A standard 3-tier app, but the backend is built around a **background ingestion pipeline** rather than synchronous request/response — uploads return immediately and processing happens as a tracked job.

```mermaid
flowchart TB
    subgraph Client["🖥️ Frontend — React + TypeScript"]
        UI["Pages: Dashboard · Courses · Upload · LectureDetail<br/>StudyGuide · Search · Ask · Quiz"]
        RQ["TanStack Query + Axios client"]
        Charts["Knowledge Map & Topic Timeline (Recharts)"]
        UI --> RQ
        UI --> Charts
    end

    subgraph API["⚙️ Backend — FastAPI"]
        Auth["Auth routes<br/>JWT (bcrypt + python-jose)"]
        Courses["Courses / Lectures / Topics /<br/>Search / Ask / Quiz / Study Guide / Dashboard"]
        Pipeline["Background processing pipeline<br/>(ProcessingJob state machine)"]
    end

    subgraph Services["🧩 Domain services"]
        Extract["Extraction<br/>PyMuPDF · python-pptx"]
        Transcribe["Transcription<br/>faster-whisper"]
        LLM["LLM Provider<br/>(pluggable: OpenAI · Anthropic · Gemini · Mock)"]
        Embed["Embedding Provider<br/>(sentence-transformers · Mock)"]
        Topics["Topic engine<br/>merge · score · relate"]
        Search["Search indexer"]
        StudyGuide["Study guide compiler"]
    end

    subgraph Data["🗄️ Storage"]
        PG[("PostgreSQL 16 + pgvector<br/>relational data + embeddings")]
        FS[("File storage<br/>local disk / S3-compatible")]
    end

    RQ <-->|REST / JSON, Bearer JWT| API
    Courses --> Pipeline
    Pipeline --> Extract
    Pipeline --> Transcribe
    Pipeline --> LLM
    Pipeline --> Embed
    Pipeline --> Topics
    Pipeline --> Search
    Pipeline --> StudyGuide
    Topics -->|cosine similarity on 384-d vectors| Embed
    API --> PG
    Pipeline --> FS
    Search --> PG
    Topics --> PG
```

**Key design choice:** all AI calls go through a `LLMProvider` / `EmbeddingProvider` abstraction (`app/services/llm`, `app/services/embeddings`). If no API key is configured, the app **automatically falls back to a deterministic Mock provider** — so the entire pipeline (extraction → notes → topics → quizzes) runs and is demo-able with zero external dependencies or cost, and swapping in OpenAI/Anthropic/Gemini is a single environment variable.

---

## Data model

Everything is scoped under a `User → Course → Lecture` hierarchy. Topics and search documents live at the **course** level so they aggregate knowledge across every lecture uploaded to that course.

```mermaid
erDiagram
    USER ||--o{ COURSE : owns
    COURSE ||--o{ LECTURE : contains
    COURSE ||--o{ TOPIC : "tracks (cross-lecture)"
    COURSE ||--o{ STUDY_GUIDE : "compiles from"
    COURSE ||--o{ SEARCH_DOCUMENT : indexes
    COURSE ||--o{ QUIZ : generates
    COURSE ||--o{ CHAT_SESSION : hosts

    LECTURE ||--o{ LECTURE_ASSET : "has files"
    LECTURE ||--o{ PROCESSING_JOB : "tracked by"
    LECTURE ||--o{ TRANSCRIPT_SEGMENT : "split into"
    LECTURE ||--|| LECTURE_NOTE : "summarized as"
    LECTURE ||--o{ TOPIC_MENTION : "mentions"
    LECTURE ||--o{ SEARCH_DOCUMENT : indexes

    TOPIC ||--o{ TOPIC_MENTION : "evidenced by"
    TRANSCRIPT_SEGMENT ||--o{ TOPIC_MENTION : "source of"

    QUIZ ||--o{ QUIZ_QUESTION : contains
    QUIZ ||--o{ QUIZ_ATTEMPT : "attempted via"
    USER ||--o{ QUIZ_ATTEMPT : submits

    CHAT_SESSION ||--o{ CHAT_MESSAGE : contains

    USER {
        int id PK
        string email
        string hashed_password
        bool is_demo
    }
    COURSE {
        int id PK
        int user_id FK
        string name
        string color
    }
    LECTURE {
        int id PK
        int course_id FK
        string title
        int lecture_number
        string status "pending|processing|processed|error"
    }
    LECTURE_ASSET {
        int id PK
        int lecture_id FK
        string asset_type
        string file_path
    }
    PROCESSING_JOB {
        int id PK
        int lecture_id FK
        string status
        string current_step
        int progress
    }
    TRANSCRIPT_SEGMENT {
        int id PK
        int lecture_id FK
        int segment_index
        text text
        float start_time
    }
    LECTURE_NOTE {
        int id PK
        int lecture_id FK
        text overview
        json headings
        json key_ideas
        json definitions
        json examples
    }
    TOPIC {
        int id PK
        int course_id FK
        string canonical_name
        float coverage_score
        int lecture_count
        vector embedding "384-d"
        json related_topics
    }
    TOPIC_MENTION {
        int id PK
        int topic_id FK
        int lecture_id FK
        text context
        float confidence
    }
    STUDY_GUIDE {
        int id PK
        int course_id FK
        int version
        json content
        json top_topics
    }
    SEARCH_DOCUMENT {
        int id PK
        int course_id FK
        int lecture_id FK
        text content
        vector embedding "384-d"
    }
    QUIZ {
        int id PK
        int course_id FK
        string quiz_type
    }
    QUIZ_QUESTION {
        int id PK
        int quiz_id FK
        text question_text
        json options
        string correct_answer
    }
    QUIZ_ATTEMPT {
        int id PK
        int quiz_id FK
        int user_id FK
        int score
    }
    CHAT_SESSION {
        int id PK
        int course_id FK
        string title
    }
    CHAT_MESSAGE {
        int id PK
        int session_id FK
        string role
        text content
        json citations
    }
```

---

## How a lecture becomes a knowledge graph (workflow)

Uploading is **fire-and-forget**: the API accepts the file, creates a `ProcessingJob`, and returns `202 Accepted` immediately. The frontend polls job status and shows live progress while the pipeline runs in the background.

```mermaid
sequenceDiagram
    autonumber
    participant U as User (browser)
    participant API as FastAPI
    participant Job as ProcessingJob
    participant Ext as Extraction / Transcription
    participant LLM as LLM Provider
    participant Emb as Embedding Provider
    participant DB as PostgreSQL (pgvector)

    U->>API: POST /api/lectures/upload (PDF / PPTX / audio / text)
    API->>Job: create job (status=queued)
    API-->>U: 202 Accepted + job id
    API->>Job: run in background

    Job->>Ext: extract text (PyMuPDF/python-pptx) or transcribe (faster-whisper)
    Ext-->>Job: transcript segments (text, timestamps)

    Job->>LLM: generate_structured_notes(segments)
    LLM-->>Job: overview, headings, key ideas, definitions, examples

    Job->>LLM: extract_topics(text, notes)
    LLM-->>Job: candidate topics [{name, aliases, confidence}]

    loop for each candidate topic
        Job->>DB: fetch course's existing topics
        Job->>Emb: embed candidate + existing topic text
        Emb-->>Job: 384-d vectors
        Job->>Job: cosine similarity match (name/alias exact OR ≥ threshold)
        alt match found
            Job->>DB: attach TopicMention to existing Topic
        else no match
            Job->>DB: create new Topic + embedding
        end
    end

    Job->>DB: recalculate coverage_score, lecture_count, related_topics
    Job->>Emb: embed notes for semantic search
    Job->>DB: upsert SearchDocument rows
    Job->>LLM: regenerate course Study Guide (ranked by coverage)
    Job->>Job: status=completed, progress=100

    U->>API: GET /api/lectures/{id}/status (polling)
    API-->>U: progress %, current_step
    U->>API: GET /api/lectures/{id}/notes
    API-->>U: structured notes, ready to read
```

A **PostgreSQL advisory lock** (`pg_advisory_xact_lock` on `course_id`) guards the topic-merge step, so uploading multiple lectures for the same course concurrently can't create duplicate topics from a race condition.

---

## Tech stack

| Layer | Choices |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Radix UI primitives, TanStack Query, React Router 7, Recharts, React Hook Form + Zod |
| **Backend** | FastAPI, SQLAlchemy 2.0 (typed `Mapped[]` models), Pydantic v2, Alembic migrations |
| **Auth** | JWT (`python-jose`) + `passlib`/`bcrypt` password hashing |
| **Database** | PostgreSQL 16 with the `pgvector` extension for embedding storage & similarity search |
| **Content extraction** | PyMuPDF (PDF), `python-pptx` (slides), `faster-whisper` (audio transcription) |
| **AI / ML** | Pluggable LLM providers — OpenAI, Anthropic (Claude), Google Gemini, or a deterministic Mock provider; `sentence-transformers` (`all-MiniLM-L6-v2`, 384-d) for embeddings, with a hash-based Mock embedding fallback |
| **PDF export** | ReportLab (study guide → downloadable PDF) |
| **Infra** | Docker Compose (Postgres + backend + frontend), Dockerfiles per service |
| **Testing** | pytest, pytest-asyncio, pytest-cov |

---

## Project structure

```
Ideathon/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, router registration, CORS
│   │   ├── core/                   # settings, security (JWT/hashing), logging
│   │   ├── db/                     # SQLAlchemy session/engine, Base
│   │   ├── models/                 # ORM models (single module, see ER diagram)
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   ├── api/routes/             # auth, courses, lectures, topics, search,
│   │   │                           #   ask, quiz, study_guide, dashboard, demo
│   │   ├── services/
│   │   │   ├── extraction/         # PDF / PPTX text extraction
│   │   │   ├── transcription/      # faster-whisper audio → segments
│   │   │   ├── ingestion/          # chunking, storage abstraction (local/S3)
│   │   │   ├── llm/                # LLMProvider: OpenAI/Anthropic/Gemini/Mock
│   │   │   ├── embeddings/         # EmbeddingProvider: sentence-transformers/Mock
│   │   │   ├── topics/             # topic merge, coverage scoring, knowledge map
│   │   │   ├── search/             # semantic search indexing/query
│   │   │   └── study_guide/        # cross-course study guide compilation
│   │   └── tasks/                  # background job runner, demo data seeding
│   └── tests/                      # pytest suite (auth, courses, lectures, search, ...)
├── frontend/
│   └── src/
│       ├── pages/                  # Dashboard, Courses, Upload, Ask, Search, Quiz, ...
│       ├── components/
│       │   ├── charts/             # KnowledgeMapView, TopicTimelineView
│       │   ├── ui/                 # Radix-based design system primitives
│       │   └── layout/             # AppLayout (nav shell)
│       ├── features/auth/          # AuthContext (JWT session)
│       └── lib/api/                # Axios client + TanStack Query hooks
└── docker-compose.yml              # postgres (pgvector) + backend + frontend
```

---

## Getting started

### Option A — Docker Compose (recommended)

```bash
git clone <this-repo-url>
cd Ideathon
cp .env.example .env      # fill in an LLM key, or leave LLM_PROVIDER=mock for a no-key demo
docker compose up --build
```

- Frontend → http://localhost:5173
- Backend API → http://localhost:8000 (health check at `/api/health`)
- Postgres (pgvector) → localhost:5432

The backend seeds demo content on startup (`ensure_demo_seeded`), so there's data to explore immediately — no manual upload required to try the UI.

### Option B — Run services locally

**Backend**
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # or `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
# requires a running Postgres with the pgvector extension enabled
uvicorn app.main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

---

## Environment variables

Set these in `.env` (see `.env.example`):

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Postgres connection string | `postgresql+psycopg://postgres:postgres@postgres:5432/studyapp` |
| `JWT_SECRET_KEY` | Signing key for auth tokens | *(change in production)* |
| `LLM_PROVIDER` | `openai` \| `anthropic` \| `gemini` \| `mock` | `mock` |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` | Key for the chosen provider | *(empty)* |
| `EMBEDDING_PROVIDER` | `sentence_transformers` \| `mock` | `sentence_transformers` |
| `SENTENCE_TRANSFORMERS_MODEL` | Embedding model name | `all-MiniLM-L6-v2` |
| `TOPIC_SIMILARITY_THRESHOLD` | Cosine similarity cutoff for merging topics | `0.85` |
| `STORAGE_PROVIDER` | `local` \| `s3` | `local` |
| `MAX_UPLOAD_SIZE_MB` | Max lecture file size | `100` |

> Without a real LLM key, the app runs entirely on `MockProvider` — deterministic, keyword/heuristic-based notes and answers. It's enough to demo the full pipeline, but for genuinely synthesized notes, grounded answers, and quiz quality, set one real provider key.

---

## API surface

All routes are prefixed `/api` and (except `/auth/*`, `/demo/*`, `/health`) require a `Bearer` JWT.

| Area | Endpoints |
|---|---|
| **Auth** | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| **Courses** | `GET/POST /courses`, `GET/PUT/DELETE /courses/{id}`, `GET /courses/{id}/stats` |
| **Lectures** | `GET/POST /lectures`, `POST /lectures/upload`, `GET /lectures/{id}`, `GET /lectures/{id}/status`, `GET /lectures/{id}/notes`, `POST /lectures/{id}/retry` |
| **Topics** | `GET /courses/{id}/topics`, `GET /topics/{id}`, `GET /topics/{id}/timeline`, `GET /topics/{id}/evidence`, `GET /courses/{id}/knowledge-map` |
| **Search** | `GET /search?q=...` — semantic vector search across a course |
| **Ask** | `POST /ask` — grounded Q&A with citations, `GET /ask/sessions/{course_id}`, `GET /ask/session/{id}` |
| **Quiz** | `POST /quiz/generate`, `GET /quiz/{id}`, `POST /quiz/{id}/attempts`, `GET /quiz/{id}/attempts`, `GET /quiz/list/{course_id}` |
| **Study Guide** | `GET /courses/{id}/study-guide`, `POST /courses/{id}/study-guide/regenerate`, `GET /courses/{id}/study-guide/pdf` |
| **Dashboard** | `GET /dashboard` — aggregated stats for the signed-in user |
| **Demo** | `GET /demo/token`, `GET /demo/course` — instant guest access to seeded content |

---

## Testing

```bash
cd backend
pytest --cov=app
```

Covers auth, courses, lectures (upload → processing → notes), topics, search, a full end-to-end flow (`test_e2e.py`), retrieval building blocks (`test_embeddings_and_chunking.py`: cosine similarity edge cases, deterministic embeddings, chunking), and background-job reliability (`test_job_reliability.py`: stale-job sweep, retry endpoint, ownership/state checks). Tests run against SQLite by default (the `pgvector.Vector` column type is swapped for `JSON` at collection time in `conftest.py`), so no Postgres instance is required to run the suite — `search_hybrid`'s Postgres-only ANN branch is skipped in favor of its in-process fallback, and both paths are exercised by the same tests. Set `TEST_DATABASE_URL` to run against a real Postgres/pgvector instance instead.

---

## Performance & reliability

This section documents what was actually profiled and changed, not a wishlist — see [`PERFORMANCE_PLAN.md`](./PERFORMANCE_PLAN.md) for the full bottleneck table this was worked from.

**Retrieval (RAG core).** `search_hybrid`'s semantic branch used to pull up to 200 `SearchDocument` rows (full text + embedding) per query and score them with a Python loop — pgvector was installed but never actually used for the nearest-neighbor search. It now runs the similarity search inside Postgres with pgvector's `<=>` cosine-distance operator (`ORDER BY embedding <=> :q LIMIT k`), backed by an `HNSW` index created in `init_db()` on both `search_documents.embedding` and `topics.embedding`. HNSW was chosen over IVFFlat because it needs no `lists` parameter tuned to row count and behaves correctly from an empty table — relevant for a demo app that starts with zero rows. The SQLite test path (and any non-Postgres deployment) keeps the original in-process scoring loop as a fallback, so behavior is identical either way — only the Postgres path is now indexed.

**N+1 queries removed.**
- `POST /api/ask` re-queried `Lecture` once per retrieved chunk (up to 8 extra round trips per question) even though `search_hybrid` had already resolved it — now reuses the batched result.
- `search_hybrid` had a module-level, never-invalidated `_lecture_cache` global dict that opened a **second** DB session per uncached lecture. Removed in favor of one `WHERE id IN (...)` batch query per search call, using the session already passed in.
- `quiz.generate_quiz` queried `TopicMention` once per topic (up to 30 round trips for a 30-topic quiz) — now one batched query, grouped in Python.
- `topics.get_topic_detail`, `topics.get_topic_evidence`, and `services.topics.get_topic_timeline` each queried `Lecture` once per mention/lecture in a loop — now batch-fetched.
- `services.topics.recalculate_topic_stats` re-ran an identical "all lectures in this course" query and a `find_related_topics` topic-embedding scan **once per topic** — both are now fetched once and reused across the loop.

**Background job reliability.** Processing runs via FastAPI `BackgroundTasks` in-process (see [Design decisions](#design-decisions) for why not Celery/Redis). If the process restarted mid-job, the `ProcessingJob` row was orphaned at `status="processing"` forever with no way to retry. On startup, a sweep now marks any job still `queued`/`processing` as `failed` with a clear, retryable message (nothing can legitimately still be running the instant the process starts, so this is always safe), and `POST /api/lectures/{id}/retry` re-queues a failed job. The raw exception text that used to be stored on a failed job (and returned to the client via `ProcessingJobRead`) is now replaced with a generic "Document processing failed. Please retry." message; the real exception and traceback still go to the server log via `logger.exception`.

**Frontend UX bug fix.** The post-upload "Processing started" dialog's live progress bar never actually polled — `useLectureStatus(created?.job_id ? null : null, 1500)` in `Upload.tsx` always evaluated the ternary to `null`, so the query was permanently disabled and the dialog sat frozen at 0% for the entire processing duration even though the backend was actively working. Fixed to pass the real lecture id. A **Retry** button was also added to the failed-processing card in `LectureDetail.tsx`, wired to the new retry endpoint.

**Observability.** Added a lightweight ASGI timing middleware (`app/main.py`) that logs `method path -> status (duration_ms)` for every request and sets an `X-Response-Time-Ms` response header — enough to compute P95s from the log without adding a monitoring stack. The RAG path (`ask.py`) logs `retrieval_ms` / `llm_ms` / `total_ms` per question, `search_hybrid` logs its own duration, and the background job (`processing.py`) logs a duration per pipeline phase (extract → notes → topics → reindex → study guide) plus a total, so a slow upload can be diagnosed from the log alone.

**Error handling.** A catch-all exception handler on `app` now guarantees an unhandled exception returns `{"detail": "Internal error, please retry."}` instead of ever risking a raw traceback reaching the client, while still logging the full exception server-side. `HTTPException` responses (404/403/400/etc.) are unaffected.

**What wasn't changed, and why** — see [Design decisions](#design-decisions) below.

---

## Design decisions

**Why PostgreSQL + pgvector?** One database for both relational data (users, courses, topic graphs, quiz results) and vector similarity search, instead of running a separate vector store alongside Postgres. At this app's scale (a course's worth of lecture content, not a web-scale corpus), pgvector's `HNSW`/`IVFFlat` indexes are more than sufficient, and keeping embeddings in the same table as the content they describe means a single transaction can insert a `SearchDocument` and its embedding together — no dual-write consistency problem between two systems.

**Why direct RAG instead of LangChain?** `app/services/llm` and `app/services/search` implement retrieval and generation directly (raw HTTP calls to OpenAI/Anthropic/Gemini behind a small `LLMProvider` interface, SQLAlchemy + pgvector for retrieval). For three providers and one retrieval path, that's less code and fewer moving parts to debug than a framework layer would add, and it's what made it straightforward to add a fully offline deterministic `MockProvider`/`MockEmbeddingProvider` fallback — the whole pipeline runs and is demoable with zero API keys, which is harder to guarantee through a heavier abstraction.

**Why background processing (and not Celery/Redis)?** Lecture processing (extraction/transcription → LLM notes → topic extraction/merge → embedding → reindexing → study guide regen) can take anywhere from seconds to a couple of minutes, so `POST /lectures/upload` returns `202 Accepted` immediately with a `ProcessingJob` id and the work runs via FastAPI `BackgroundTasks`. A broker (Celery/Redis) would add real value for multi-worker horizontal scaling, but at this project's scale the actual reliability gap was stale-job recovery and retry, not a missing queue — so that's what got built (see above) instead of a broker this app doesn't otherwise need.

**How API latency was reduced?** Mainly by removing N+1 query patterns (see above) and moving vector similarity search from a Python loop into an indexed Postgres query — both reduce round trips and data transferred rather than adding caching layers. The embedding provider, LLM provider, and settings are already cached as process-level singletons (`get_embedding_provider`, `get_llm_provider`, `get_settings` via `lru_cache`), which was the existing, correct caching strategy; per-answer LLM response caching was deliberately *not* added since question text is user-specific and often unique, and caching it risks staleness for negligible hit rate.

**How failed jobs are handled?** A job's `ProcessingJob.status` moves through `queued → processing → completed | failed`. On failure — whether from an exception during processing or a startup sweep finding an orphaned job — the row is marked `failed` with a clean, user-safe message; it is never left stuck in `processing`. `POST /lectures/{id}/retry` creates a fresh `ProcessingJob` and re-runs the pipeline, rejecting the call with `409` if a job is already in flight so retries can't race a running job.

---

## How this is different from NotebookLM & similar tools

Tools like Google's NotebookLM, ChatPDF, or generic "chat with your PDF" apps are excellent at **one thing**: let you drop in some documents and ask questions grounded in them, inside a single notebook/session. StudyAI is built around a different unit of work — **an entire course, over an entire semester** — and that changes the architecture, not just the UI.

| | NotebookLM / "chat with PDF" tools | StudyAI |
|---|---|---|
| **Unit of knowledge** | A notebook / a document set, largely siloed per session | A **course**: every lecture you upload over weeks/months contributes to one growing knowledge base |
| **Concept tracking** | None — no persistent notion of "topics" across documents | A **deduplicated topic graph**: concepts are extracted, embedded, and merged across lectures (e.g. "BST" and "Binary Search Tree" become one tracked `Topic`) using cosine similarity, not just keyword match |
| **Coverage insight** | Not available | Each topic gets a computed **coverage score** (lecture span × evidence × source diversity) so you can see what's central to the course vs. mentioned once |
| **Temporal view** | Not available | A **topic timeline** per concept — "Introduced" → "Revisited" → "Expanded" — showing exactly which lectures built on it and when |
| **Visualization** | Not available | An interactive **knowledge map** (graph of topics + weighted relatedness edges) generated from real course content |
| **Assessment** | Not available | **Auto-generated quizzes** (MCQs) sourced strictly from your own material, with every question traceable to a lecture/topic, plus attempt history and scoring |
| **Deliverable output** | Chat transcript / summary | An auto-compiled, **ranked, exportable study guide** (PDF) recomputed after every new lecture, not a single static summary |
| **Input types** | Mostly documents | PDF, PPTX, plain text, **and lecture audio** (via `faster-whisper` transcription with timestamps) |
| **Grounding/citations** | Citations to a chunk of a document | Citations back to a specific **lecture, timestamp, and snippet**, because content is modeled at the lecture/segment level from the start |
| **Model flexibility** | Fixed to the vendor's model | Pluggable `LLMProvider` — OpenAI, Anthropic, Gemini, or a fully offline deterministic mock — swappable via one environment variable, so the whole pipeline (notes, topics, quizzes) is provider-agnostic |
| **Ownership model** | Notebook-centric, ephemeral | Full relational data model (users → courses → lectures → topics → quizzes → chat sessions) designed to be queried, exported, and built on |

In short: NotebookLM answers questions about documents you gave it *right now*. StudyAI builds and maintains a **structured map of what you've actually learned across a whole course**, and turns that map into study guides, quizzes, and grounded answers — closer to a personal course-knowledge system than a document chatbot.

---

## License

MIT
