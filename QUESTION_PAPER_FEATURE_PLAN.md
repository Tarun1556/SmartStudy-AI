# Question Paper Analysis — Feature Plan

Extends StudyAI so it also ingests previous semester/year question papers and
combines them with existing lecture coverage to produce an **evidence-based**
exam-priority signal. This document is the plan required before implementation
starts. It is grounded in a full read of the current codebase (backend +
frontend), not assumptions.

---

## 1. Existing Architecture (as found)

**Backend**: FastAPI + SQLAlchemy 2.0 + Postgres/pgvector, `backend/app/`.

- **Models** (`app/models/__init__.py`, single file, ~290 lines): `User →
  Course → {Lecture, Topic, StudyGuide, SearchDocument, Quiz, ChatSession}`.
  `Lecture → {LectureAsset, TranscriptSegment, LectureNote, TopicMention,
  ProcessingJob, SearchDocument}`. All PKs are plain autoincrement `Integer`.
  No enum columns — status fields are free-text `String`. Ownership is never
  stored directly on a child row; it's always resolved by walking up the FK
  chain to `Course.user_id`.
- **Migrations**: `alembic` is in `requirements.txt` but **not actually wired
  up** (no `alembic/` dir, no `alembic.ini`). Schema is created by
  `init_db()` (`app/db/session.py:26`) via `Base.metadata.create_all()` at
  FastAPI startup. This only creates *missing* tables — it does not alter
  existing ones. **Implication: new work must ship as new tables, not new
  columns on existing tables**, or a real migration step would be needed
  where none exists today.
- **Auth/ownership**: JWT bearer (`app/api/deps.py`), plus a special
  `DEMO_USER_ID=0` that maps to an in-memory read-only demo user. There is no
  shared ownership dependency — every route file defines its own local
  `_check_course_owner`/`_check_lecture_owner` helper (same logic, duplicated
  ~7×). New routes should follow this same duplicated-helper convention for
  consistency, not introduce a new pattern.
- **Upload → async processing**: `POST /api/lectures/upload` (multipart) →
  creates `Lecture` (status="pending") → saves file via
  `services/ingestion/storage.py`'s `StorageProvider` → creates `LectureAsset`
  → creates `ProcessingJob` (status="queued") → commits → returns 202
  immediately → `background_tasks.add_task(process_lecture_job, job.id)`
  (FastAPI's in-process `BackgroundTasks`, **no Celery/Redis**). Startup
  `sweep_stale_jobs()` force-fails any job still queued/processing after a
  restart (BackgroundTasks work isn't durable), and `POST
  /lectures/{id}/retry` re-queues a failed job.
- **File storage**: `LocalStorageProvider` (only implementation; S3 settings
  exist but are unused) writes under `backend/storage/user_{id}/course_{id}/
  lecture_{id}/{uuid8}_{sanitized_filename}` and returns that relative path,
  stored in `LectureAsset.file_path`. **No download endpoint exists yet for
  any uploaded file** — only the *generated* study-guide PDF is streamed back
  today (`services/pdf` — ReportLab generation, not extraction).
- **Text extraction**: `services/extraction/extract_pdf_text()` uses PyMuPDF
  (`fitz`), flattens all pages into one string, no OCR (silently returns `""`
  on scanned/image-only pages). `_text_to_segments()` is a generic
  sentence-boundary chunker — not question-aware.
- **Embeddings**: `services/embeddings` — `SentenceTransformerProvider`
  (384-dim, `all-MiniLM-L6-v2`) or `MockEmbeddingProvider` (deterministic
  hash-based, used in tests / when the real model isn't installed). **384 is
  hard-baked** into `Vector(384)` columns on `Topic.embedding` and
  `SearchDocument.embedding`.
- **Search**: `services/search.search_hybrid()` — keyword (Postgres
  `tsvector`/`ILIKE` fallback) + semantic (`pgvector` `.cosine_distance()`,
  HNSW index) blended, scoped by `course_id`, generic over `SearchDocument
  .doc_type`. `index_document(db, course_id, doc_type, title, content, ...)`
  is the reusable indexer.
- **Topics**: per-course `Topic` rows with `coverage_score`/`lecture_count`/
  `evidence_count`, linked to lectures via `TopicMention`.
  `find_or_create_topic()` (`services/topics`) does exact/alias match, then
  **embedding cosine-similarity dedup** against `TOPIC_SIMILARITY_THRESHOLD`
  (0.85) before creating a new topic. `recalculate_topic_stats()` recomputes
  `coverage_score` after each lecture is processed.
- **Study guide**: `services/study_guide.generate_study_guide()` — recomputes
  topic stats, asks the LLM for prose (`llm.generate_study_guide`), then
  **overwrites the LLM's echoed numbers with DB-authoritative ones**
  (`_reconcile_topic_stats`) — the LLM is trusted for wording only, never for
  arithmetic. Stored as a new versioned `StudyGuide` row.
- **LLM abstraction**: `services/llm` — `LLMProvider` ABC with
  Mock/OpenAI/Anthropic/Gemini implementations, all built on shared
  `_chat_json_object`/`_chat_json_array`/`_chat_text` helpers with retry,
  JSON-repair, and a **guaranteed Mock fallback on any failure** (LLM issues
  degrade gracefully, never hard-fail the pipeline). `LLM_PROVIDER` defaults
  to `"mock"`.
- **RAG ask**: `POST /api/ask` — `search_hybrid()` for retrieval,
  `llm.answer_question()` for generation, stores `ChatSession`/`ChatMessage`
  with citations.
- **Tests**: pytest, SQLite for the default test DB (with `pgvector.Vector`
  monkey-patched to JSON so vector columns still work without Postgres),
  fixtures in `conftest.py` (`db`, `client`, `user`/`user2`, `auth_headers`,
  `demo_headers`, `seed_course`). LLM provider defaults to Mock in tests
  already, so nothing needs extra mocking for that.

**Frontend**: React + TypeScript + Vite, `frontend/src/`.

- Flat routing in `App.tsx`: course-scoped full pages already exist at
  `/courses/:id/study-guide`, plus `/ask/:courseId`, `/quiz/:courseId`,
  `/lectures/:id`. `CourseDetail.tsx` (`/courses/:id`) has an in-page `Tabs`
  system (lectures/topics/map/timeline, client-state only, not URL-synced)
  **plus** header buttons linking out to the full-page features (Study
  Guide/Ask/Practice).
- `lib/api/hooks.ts` is a single flat file of React Query hooks, one per
  endpoint, with established idioms for: list/detail queries, mutations with
  `invalidateQueries`, multipart upload (`useUploadLecture`), status polling
  (`useLectureStatus` — `refetchInterval` that stops once terminal), and
  ad-hoc blob download (`api.get(url, {responseType:"blob"})` in
  `StudyGuide.tsx`, not a hook).
- `types/index.ts` has no question-paper/exam-insight types yet.
- Reusable UI: `Badge`/`Card`/`Progress`/`Dialog`/`Tabs` (all in
  `components/ui`), `EmptyState`/`Spinner`/`InputError`
  (`components/common/helpers.tsx`), a recurring "status → colored outline
  Badge" map-lookup pattern (`StatusBadge` in both `CourseDetail.tsx` and
  `LectureDetail.tsx`), and a recurring "gradient hero stat card" style used
  by both `StudyGuide.tsx` and `QuizPage.tsx`. `recharts` is an installed but
  **unused** dependency — the codebase's actual convention for
  frequency/coverage visuals is hand-rolled `Progress` bars, not a charting
  library.

---

## 2. Database Changes

Three new tables only. **No existing table is altered** — this matters
because `create_all()` cannot add columns to a table that already exists, and
there's no Alembic to write a real migration with. Adding new tables is safe
and automatic (next backend restart creates them); adding columns to
`Lecture`/`ProcessingJob`/`Topic` would silently do nothing on any database
that already has those tables.

### `QuestionPaper`
Mirrors `Lecture`'s shape/conventions.

| column | type | notes |
|---|---|---|
| id | PK | |
| course_id | FK courses.id, CASCADE, indexed | |
| title | String(500) | e.g. "2025 Semester End Examination" |
| academic_year | Integer, nullable | e.g. 2025 |
| semester | String(100), nullable | e.g. "Semester 1", free text |
| exam_type | String(100), nullable | e.g. "Final", "Midterm", "Quiz" |
| original_filename | String(500) | |
| file_path | String(1000) | relative path from `StorageProvider.save()`, same convention as `LectureAsset.file_path` |
| file_size | BigInteger, nullable | |
| mime_type | String(200), nullable | |
| status | String(50), default `"pending"` | pending / processing / processed / error — mirrors `Lecture.status` |
| created_at / updated_at | DateTime | |

Relationship: `Course.question_papers` (cascade delete-orphan) — added to the
existing `Course` class; this is a Python-level relationship, not a table
change, so it's safe.

### `QuestionPaperProcessingJob`
A **parallel** table to `ProcessingJob` (same shape), rather than adding a
nullable `question_paper_id` column to `ProcessingJob`. Reason: `ProcessingJob
.lecture_id` is `NOT NULL`; making it nullable or adding a second polymorphic
FK is exactly the kind of existing-table change `create_all()` can't apply
retroactively. A parallel table keeps the existing lecture pipeline
byte-for-byte untouched.

| column | type | notes |
|---|---|---|
| id | PK | |
| question_paper_id | FK question_papers.id, CASCADE, indexed | |
| job_type | String(100), default `"question_paper_analysis"` | |
| status | String(50), default `"queued"` | queued / processing / completed / failed |
| current_step | String(200), nullable | |
| progress | Integer, default 0 | |
| error_message | Text, nullable | |
| started_at / completed_at | DateTime, nullable | |
| created_at / updated_at | DateTime | |

`sweep_stale_jobs()` (currently only sweeps `ProcessingJob`) gets one
additional, additive query over this table — the existing lecture-sweep query
is untouched.

### `QuestionPaperQuestion`
The structured, per-question output of parsing.

| column | type | notes |
|---|---|---|
| id | PK | |
| question_paper_id | FK question_papers.id, CASCADE, indexed | |
| question_number | String(50), nullable | e.g. "1(a)", "Q3" — best-effort |
| section | String(100), nullable | e.g. "Section A" — best-effort |
| question_text | Text, **not null** | original extracted text — always preserved even if structuring is uncertain |
| marks | Integer, nullable | best-effort |
| unit | String(200), nullable | best-effort, if a unit/module label is detectable |
| topic_id | FK topics.id, **SET NULL**, nullable, indexed | matched course topic, or NULL if unmatched/uncertain |
| topic_match_confidence | Float, nullable | cosine-similarity score backing `topic_id`; UI uses this to label a mapping as certain vs. uncertain rather than pretending exactness |
| normalized_topic | String(500), nullable | LLM-suggested topic label, kept even when no confident `topic_id` match exists, so nothing is silently dropped |
| embedding | `Vector(384)`, nullable | same dimension as `Topic`/`SearchDocument`, same embedding provider |
| created_at | DateTime | |

No stats/aggregate table is added. Historical-frequency, year-recurrence,
trend and priority numbers (spec §7–§9) are **computed on demand** from
`QuestionPaper` + `QuestionPaperQuestion` via a pure service function (§6
below), the same on-demand-view pattern already used by
`get_topic_timeline()`/`get_knowledge_map()`. Given the realistic scale (a
handful of question papers and tens of topics per course), this is cheap, and
it avoids a whole class of cache-staleness bugs a persisted stats table would
introduce. If profiling ever shows this is too slow at scale, a follow-up can
add a cache table — not needed for correctness now.

A `HNSW` index on `QuestionPaperQuestion.embedding` is added (mirroring the
existing guarded `_ensure_vector_indexes()` pattern) to support
similar-question-across-years comparisons directly, in addition to the
already-indexed `SearchDocument.embedding` used for the main search/RAG path.

---

## 3. Backend Changes

New modules, following existing file layout:

- `app/services/question_papers/extraction.py` — question-boundary-aware
  text segmentation (new; `services/extraction`'s existing
  `_text_to_segments` is sentence-based and unsuitable here).
- `app/services/question_papers/matching.py` — `match_topic_for_text(db,
  course_id, text, existing_topics=None, threshold=...) -> (Topic | None,
  float)`. Factored out of the matching *mechanism* already inside
  `services/topics.find_or_create_topic()` (embed → cosine similarity → best
  match), but **read-only**: it never creates a new `Topic`. Uses a separate,
  lower threshold (`EXAM_TOPIC_MATCH_THRESHOLD`, new config default `0.45`)
  than `TOPIC_SIMILARITY_THRESHOLD` (0.85), because that existing threshold
  governs *topic-name-to-topic-name* dedup (two short labels), a much
  stricter comparison than *question-sentence-to-topic-name* matching, which
  scores lower even for correct matches.
- `app/services/question_papers/analysis.py` — `compute_topic_exam_stats(db,
  course_id) -> list[TopicExamStat]` (§6) and the priority-score formula
  (§7).
- `app/tasks/question_paper_processing.py` — `process_question_paper_job
  (job_id)`, mirroring `process_lecture_job`'s structure exactly (own
  `SessionLocal()`, phase-by-phase `current_step`/`progress` updates, single
  outer `try/except` with a generic user-safe failure message + full
  traceback via `logger.exception`).
- `app/api/routes/question_papers.py` — new router, mounted with prefix
  `/api` (matching `topics.py`/`study_guide.py`'s mounting style so course-
  scoped paths read as `/api/courses/{id}/question-papers`).
- `app/services/llm/__init__.py` — add one new abstract method,
  `parse_question_paper(raw_text: str) -> list[dict]`, implemented in every
  existing provider (Mock/OpenAI/Anthropic/Gemini) using the same
  `_chat_json_array` helper the other structured-extraction methods already
  use. `MockProvider`'s implementation is a deterministic regex-based parser
  (not a canned fixture) so it exercises real logic and keeps tests
  independent of a live LLM.
- `app/services/study_guide/__init__.py` — `generate_study_guide()` gains an
  additional, optional data source (§5). Falls back to identical
  lecture-only behavior when a course has zero question papers.
- `app/api/routes/ask.py` — light, additive augmentation for exam-focused
  questions (§6).
- `app/core/config.py` — add `EXAM_TOPIC_MATCH_THRESHOLD: float = 0.45`.
- `app/tasks/processing.py` — extend `sweep_stale_jobs()` with one additional
  query over `QuestionPaperProcessingJob` (additive, existing query for
  `ProcessingJob` unchanged).

### New API endpoints

All require `get_current_user`; ownership is checked with the same
locally-duplicated `_check_course_owner`/new `_check_question_paper_owner`
helper pattern already used by every other route file. Mutating endpoints
(`upload`, `delete`, `retry`) are blocked for the demo user
(`is_demo → 403`), matching every existing mutating route.

| method | path | purpose |
|---|---|---|
| GET | `/api/courses/{course_id}/question-papers` | list papers for a course (+ small aggregate: analyzed count, topics identified) |
| POST | `/api/courses/{course_id}/question-papers/upload` | multipart upload; creates `QuestionPaper` + `QuestionPaperProcessingJob`, returns 202 immediately, queues background processing |
| GET | `/api/question-papers/{id}` | paper detail + processing status |
| GET | `/api/question-papers/{id}/status` | latest `QuestionPaperProcessingJob` (mirrors `GET /lectures/{id}/status`) |
| POST | `/api/question-papers/{id}/retry` | re-queue a failed job (409 if already in progress, mirrors lecture retry) |
| GET | `/api/question-papers/{id}/download` | stream the original file; path is always resolved from the DB-stored `file_path`, never from client input |
| GET | `/api/question-papers/{id}/questions` | list parsed `QuestionPaperQuestion` rows |
| DELETE | `/api/question-papers/{id}` | delete paper (cascades to questions; file removed via storage provider) |
| GET | `/api/courses/{course_id}/exam-insights` | computed per-topic historical stats + priority + evidence (§6/§7) |

`GET /api/courses/{id}/stats` gains one new optional field,
`question_paper_count` — additive, does not break any existing consumer of
that schema.

---

## 4. Frontend Changes

Per the existing routing convention (`/courses/:id/study-guide` already
exists as a full page linked from `CourseDetail`'s header, alongside
`/ask/:courseId` and `/quiz/:courseId`), Question Papers and Exam Insights
are implemented as **two new full pages**, linked the same way, rather than
squeezed into `CourseDetail`'s existing `Tabs`:

- `pages/QuestionPapers.tsx` → route `/courses/:id/question-papers`
- `pages/ExamInsights.tsx` → route `/courses/:id/exam-insights`

New types in `types/index.ts`: `QuestionPaper`, `QuestionPaperQuestion`,
`ExamTopicInsight`, `ExamInsightsResponse` (snake_case fields matching the
backend JSON, same convention as every existing type).

New hooks in `lib/api/hooks.ts` (same file — matches existing "one flat
file" convention): `useQuestionPapers`, `useUploadQuestionPaper` (multipart,
mirrors `useUploadLecture`), `useQuestionPaperStatus` (polling, mirrors
`useLectureStatus`), `useDeleteQuestionPaper`, `useQuestionPaperQuestions`,
`useExamInsights`.

**QuestionPapers.tsx**:
- Upload form reusing `Upload.tsx`'s dropzone JSX/`FormData` pattern, scoped
  to the current course (`course_id` from the route, not a `<select>`);
  fields: title (defaults from filename), academic year, semester, exam type.
- List of papers as cards, following the lecture-card layout already in
  `CourseDetail.tsx`'s lectures tab: title, year/semester/exam-type badges,
  upload date, `StatusBadge` (same map-lookup pattern as
  `LectureStatusBadge`), View / Download (blob-download pattern copied from
  `StudyGuide.tsx`) / Delete actions.
- Empty state via the existing `EmptyState` component: "No previous question
  papers uploaded yet." + upload call-to-action — appears automatically for
  every existing course since the list query just returns `[]`.
- Summary line: "Analyzed: N question papers", "Topics identified: N".
- `isDemo` gate on upload/delete, exactly like `Upload.tsx`/`StudyGuide.tsx`.

**ExamInsights.tsx**:
- Gradient "hero" summary card, reusing the existing
  `from-primary/10 via-card to-neon-cyan/5` style already used by
  `StudyGuide.tsx`'s `OverviewSummary` and `QuizPage.tsx`'s `ScoreCard`.
- Per-topic rows sorted by priority score: name, frequency badge (e.g. "4/5
  papers"), a `Progress`-bar frequency visualization (matching the existing
  coverage-bar visual language rather than introducing the unused `recharts`
  dependency), a new `priorityBadge`/`priorityLabel` helper in
  `lib/utils/index.ts` mirroring the existing `coverageBadge`/
  `coverageLabel`, and a simple ↑/→/↓ recent-trend indicator.
- "Why this topic matters" — a `Dialog` per topic listing the evidence
  bullets straight from the API's `evidence` object (appearances, years,
  lecture coverage, marks), mirroring `Ask.tsx`'s citation-dialog pattern.
  This directly answers spec's explainability requirement — every bullet is
  a stored number, not a phrase invented at render time.
- Empty state when no processed papers exist yet, pointing at the Question
  Papers page.

**CourseDetail.tsx**: two new header buttons ("Question Papers", "Exam
Insights") added next to the existing Study Guide / Ask Notes / Practice
buttons.

**Search.tsx**: extend the existing `doc_type → badge label` map-lookup to
include `"question" → "Question Paper"` — the only change needed, because
`search_hybrid` is already generic over `doc_type` and needs no backend
change to surface question results.

**App.tsx**: two new routes, wrapped in the same `RequireAuth`/`AppLayout`
as every other course-scoped page.

---

## 5. Processing Pipeline

```
POST /api/courses/{id}/question-papers/upload  (multipart)
    │
    ├─ create QuestionPaper (status="pending")
    ├─ save original PDF via existing StorageProvider
    │     path: user_{uid}/course_{cid}/qpaper_{qid}/{uuid8}_{filename}
    ├─ create QuestionPaperProcessingJob (status="queued")
    ├─ commit, return 202 immediately  { question_paper_id, job_id, message }
    └─ background_tasks.add_task(process_question_paper_job, job.id)

process_question_paper_job(job_id)          [same phase/commit shape as
                                              process_lecture_job]
    │
    ├─ [10%] extract_pdf_text()  (existing services/extraction, PyMuPDF)
    │         empty result → fail job with a clear, honest message
    │         ("Could not extract text — this may be a scanned/image-only
    │         PDF; OCR isn't supported.") — file stays saved, retry allowed.
    │
    ├─ [30%] regex-based structural segmentation into raw question blocks
    │         (section headers, "Q\d+"/"\d+\."/"\(\w\)" numbering, marks
    │         patterns like "[10 marks]"). Robust to unknown formats: if no
    │         structure is detected, the whole extracted text becomes one
    │         preserved block rather than being discarded.
    │
    ├─ [50%] llm.parse_question_paper() normalizes/cleans each block into
    │         {question_number, question_text, marks, section}. If the LLM
    │         result is empty or fails validation, fall back to the raw
    │         regex blocks directly — the original question text is never
    │         silently dropped in favor of a guess.
    │
    ├─ [65%] batch-embed all question texts in one embed_texts() call
    │         (not one call per question — avoids the N+1-style pattern
    │         already flagged elsewhere in this codebase)
    │
    ├─ [80%] match_topic_for_text() per question using the precomputed
    │         embeddings; store topic_id + confidence, or leave topic_id
    │         NULL when below threshold (uncertain mapping is preserved as
    │         uncertain, never forced)
    │
    ├─ persist QuestionPaperQuestion rows (bulk insert)
    │
    ├─ [90%] index_document(doc_type="question", ...) per question — reuses
    │         the existing search indexer as-is, so results are
    │         automatically retrievable by /api/search and /api/ask
    │
    └─ [100%] QuestionPaper.status="processed"; job.status="completed"

    on any exception at any phase:
        job.status="failed", error_message=<safe generic message>
        QuestionPaper.status="error"
        full traceback → logger.exception (never sent to client)
        retryable via POST /question-papers/{id}/retry (mirrors lecture retry,
        409 if a job is already in flight)
```

`sweep_stale_jobs()` (startup) additionally sweeps orphaned
`QuestionPaperProcessingJob` rows the same way it already sweeps
`ProcessingJob` rows.

---

## 6. AI / RAG Changes

- **Topic mapping** reuses the embedding mechanism already proven in
  `find_or_create_topic()`, in a new read-only variant
  (`match_topic_for_text`) that never mints new topics from exam content —
  it only links to topics that already exist from lecture coverage, per the
  "do not create duplicate topics unnecessarily" constraint. Confidence is
  always stored, so the UI can visibly distinguish a confident match from an
  uncertain one instead of presenting every mapping as exact.

- **Historical analysis** (`compute_topic_exam_stats`) — pure aggregation
  over `QuestionPaperQuestion` joined to `QuestionPaper`, grouped by
  `topic_id`, computed fresh on each request:
  - `papers_appeared_in` / `total_papers_analyzed` → **frequency_score**
  - distinct `academic_year` count → **years_appeared_in** (papers with no
    year recorded are excluded from this specific count, not from the
    dataset as a whole)
  - `question_count`, `total_marks` (sum where `marks` is not null; absence
    of marks data never breaks the aggregation)
  - **recent_trend**: papers are split into an older half and a newer half
    by `academic_year`; `"increasing"` if the topic's share of papers is
    higher in the newer half, `"decreasing"` if lower, `"stable"` if equal,
    `"insufficient_data"` if fewer than 2 distinct years are available. This
    is a plain, documented comparison — not a forecast.

- **Priority score** — explicit, documented, weighted sum of five 0–1
  components (weights sum to 1.0, so the result is 0–1):

  ```
  priority_score =
        0.30 × lecture_coverage        (Topic.coverage_score, already computed)
      + 0.30 × frequency_score         (papers_appeared_in / total_papers_analyzed)
      + 0.15 × year_recurrence_score   (min(years_appeared_in / total_years_analyzed, 1.0))
      + 0.10 × recent_trend_score      (1.0 increasing / 0.5 stable / 0.0 decreasing or insufficient_data)
      + 0.15 × marks_weight_score      (topic's avg marks ÷ max avg marks across the course's topics; 0 if no marks data)
  ```

  Labels: `>= 0.6` → **High**, `>= 0.35` → **Medium**, below that →
  **"Lower historical frequency"** (matching the spec's own example wording,
  which deliberately avoids sounding dismissive). Every component value and
  its raw inputs (counts, years, marks) are returned in the API response's
  `evidence` object, so the UI's "why is this prioritized" bullets are read
  directly from stored numbers — nothing is phrased by an LLM at render
  time, and nothing is an unexplained magic number.

- **Study guide** (`generate_study_guide`) gains `compute_topic_exam_stats`
  as a second, optional input alongside the existing lecture/topic data.
  `_reconcile_topic_stats` (which already overwrites LLM-echoed numbers with
  DB-authoritative ones for lecture coverage) is extended to do the same for
  exam numbers — the LLM only supplies the prose distinguishing "learned
  from lectures" vs. "historically important for exams"; every number in
  that prose is stamped from `compute_topic_exam_stats`. With zero question
  papers uploaded, this input is empty and the study guide behaves exactly
  as it does today — required for existing courses to keep working
  unchanged.

- **Search** needs no backend change: `search_hybrid` is already generic
  over `SearchDocument.doc_type`, and question papers are indexed with
  `doc_type="question"` through the same `index_document()` call lectures
  already use.

- **Ask/RAG** (`POST /api/ask`) needs no structural change for retrieval
  (indexed questions are picked up by the existing `search_hybrid` call
  automatically). For exam-focused questions specifically (light keyword
  heuristic on the question text — "exam", "prioritize", "study first", etc.
  — kept deliberately simple rather than a new intent classifier), the route
  additionally fetches the top of `compute_topic_exam_stats` and passes it
  into an extended `llm.answer_question(question, context_chunks,
  exam_context=...)`. The system prompt for this path explicitly instructs
  the model to phrase output as historical evidence ("appeared in 4 of 5
  analyzed papers", "high historical coverage") and explicitly forbids
  predictive claims ("will appear", "guaranteed") — enforcing the spec's
  "evidence, not prediction" constraint at the prompt level, on top of the
  fact that every number available to the model is already
  evidence-derived, not invented.

---

## 7. Testing Strategy

New file `backend/tests/test_question_papers.py`, using the existing
`conftest.py` fixtures (`db`, `client`, `user`/`user2`, `auth_headers`,
`auth_headers_u2`, `demo_headers`, `seed_course`) — no new test
infrastructure needed. `LLM_PROVIDER` already defaults to `"mock"` in this
test environment, and `MockProvider.parse_question_paper` is a real
deterministic regex-based implementation (not a canned fixture), so tests
exercise genuine parsing logic without any live Gemini/OpenAI/Anthropic
calls, per the explicit "don't depend on live LLM calls" requirement.

Planned cases (mapped to the spec's required list):

1. Upload → 202, `QuestionPaper(status="pending")` +
   `QuestionPaperProcessingJob(status="queued")` created.
2. Ownership — `user2` gets 403 on another user's paper (get/download/delete/retry).
3. PDF preservation — downloaded bytes match the uploaded bytes exactly;
   correct filename in `Content-Disposition`.
4. Question extraction — run `process_question_paper_job` synchronously
   (same pattern `test_job_reliability.py` already uses for
   `process_lecture_job`) against a small multi-question fixture text;
   assert `QuestionPaperQuestion` rows with question numbers/text preserved.
5. Topic mapping — a question matching an existing course `Topic`'s
   canonical name/description gets `topic_id` + confidence set; an unrelated
   question is left `topic_id=None` (uncertain is preserved, not forced).
6. Similar-question detection — embeddings are non-null after processing;
   near-duplicate question text across two papers scores high via the
   existing `cosine_similarity` helper.
7. Topic frequency — 3 papers, topic present in 2 → `frequency_score ≈
   0.667`.
8. Year recurrence — papers across 3 distinct years computed correctly;
   a paper with no `academic_year` doesn't break or skew the count.
9. Priority scoring — direct unit test of the scoring function against known
   component inputs (isolated from the DB, fast).
10. Historical trend — engineered fixtures for `increasing`/`decreasing`/
    `insufficient_data` (single-year case).
11. Study guide integration — after processing lectures + papers,
    `top_topics` include an `exam_priority` block with correct
    `papers_appeared_in`.
12. Download authorization — 401 unauthenticated, 403 wrong owner, 200 for
    the owner.
13. Failed processing — an empty/malformed PDF fixture ends with
    `status="failed"`, a safe message, `QuestionPaper.status="error"`, and
    the original file still present (not deleted).
14. Retry — failed → retry → 202 → can complete; blocked (409) while a job
    is already in flight; blocked (403) for the demo user; ownership-checked
    (403 for a non-owner) — mirrors `test_job_reliability.py` exactly.
15. Search integration — after processing, `/api/search` returns a
    `doc_type="question"` hit for a keyword drawn from an uploaded question.
16. RAG integration — `/api/ask` doesn't crash with zero papers uploaded
    (graceful empty case) and returns a normal response shape with papers
    present; assertions are on response shape/fields, not exact Mock
    wording, to avoid brittle tests.

Edge cases folded into the above: empty/malformed PDF (13), unusual/no
structure detected (4's fallback path), question with no identifiable topic
(5), missing academic year (8), missing marks (marks aggregation is
null-safe by construction), only one previous paper (7/10 with
`total_papers_analyzed=1`), duplicate paper upload (two uploads with
identical title both succeed as independent records — no de-duplication is
implemented, since two genuinely different exam sittings can share a title),
no question papers uploaded at all (11 and the exam-insights endpoint return
an explicit empty/zero state, never an error).

Scanned/image-only PDFs: covered as an explicit **failure-path** test (13's
variant) with a clear user-facing message, not as a supported case — see
Limitations (§9). OCR is not implemented; claiming otherwise would violate
the "don't claim unimplemented functionality" constraint.

---

## 8. Backward-Compatibility Considerations

- **No existing table is altered.** Only three new tables
  (`QuestionPaper`, `QuestionPaperProcessingJob`, `QuestionPaperQuestion`)
  plus a few additive, safely-defaulted changes: one new relationship
  attribute on `Course`, one new optional field on the `CourseStats`
  response, one new optional parameter on `LLMProvider.answer_question`/
  `generate_study_guide` (both default to the current behavior when omitted).
- **No existing code path changes behavior.** The lecture upload/processing
  pipeline, `ProcessingJob`, `sweep_stale_jobs`'s existing query, and the
  existing study-guide generation for lecture-only courses are untouched;
  question-paper support is additive alongside them, not a refactor of them.
- **Schema application**: since there's no Alembic wired up in this repo,
  the three new tables are created automatically the next time the backend
  starts (`init_db()` → `create_all()`), exactly like every other table in
  this project today — no manual migration step exists to run, because none
  exists for the current schema either. This is flagged here explicitly:
  it's a pre-existing characteristic of the codebase, not something newly
  introduced by this feature.
- **Existing courses** automatically show a "Question Papers" page with the
  standard "No previous question papers uploaded yet." empty state (the list
  query simply returns `[]` — no special-casing needed), and their Study
  Guide / Ask behavior is unchanged until the user actually uploads a paper.
- **No data is destroyed.** Deleting a `QuestionPaper` only cascades to its
  own `QuestionPaperQuestion`/`QuestionPaperProcessingJob` rows and its own
  stored file; it cannot touch lecture data, and nothing about this feature
  deletes or rewrites existing rows in any pre-existing table.

---

## 9. Known Limitations (stated up front, not discovered after the fact)

- **No OCR.** Scanned/image-only question papers will fail extraction with a
  clear message, same limitation the existing lecture PDF pipeline already
  has (`services/extraction.extract_pdf_text` silently returns empty text
  for image-only pages today).
- **Topic mapping is similarity-based, not guaranteed-correct.** Confidence
  is always shown; low-confidence matches are surfaced as uncertain, not
  hidden or forced.
- **Priority scoring is evidence-based, not predictive**, by design — this
  is a hard constraint from the spec and is enforced in both the API
  response wording and the RAG system prompt, not just in UI copy.
- **On-demand stats computation** trades a small amount of per-request
  aggregation cost for correctness/simplicity (no cache invalidation to get
  wrong). Fine at the expected scale (a handful of papers/course); would need
  revisiting only if that assumption changes materially.

---

## 10. Implementation Phases

Matches the spec's ordering; each phase ends with the relevant tests run and
a check that nothing existing regressed before moving on.

1. DB models (`QuestionPaper`, `QuestionPaperProcessingJob`,
   `QuestionPaperQuestion`) + `Course.question_papers` relationship.
2. Upload endpoint + secure PDF storage + download endpoint.
3. Background job scaffold (`process_question_paper_job`, sweep extension,
   retry endpoint) with extraction wired in.
4. Question parsing/normalization (regex segmentation + `llm
   .parse_question_paper` + Mock implementation).
5. Topic mapping (`match_topic_for_text`).
6. Historical frequency/trend analysis (`compute_topic_exam_stats`).
7. Priority scoring formula + `/exam-insights` endpoint.
8. Question Papers UI (page, hooks, types).
9. Exam Insights UI (page, hooks, types).
10. Study Guide integration (`generate_study_guide` + `_reconcile_topic_stats`
    extension).
11. Search integration (frontend badge only) + Ask/RAG integration
    (`answer_question` exam_context param).
12. Tests (`test_question_papers.py`, covering §7 in full).
13. Performance pass (batch embedding calls, grouped SQL aggregation, HNSW
    index on the new embedding column).
14. README/documentation update.
