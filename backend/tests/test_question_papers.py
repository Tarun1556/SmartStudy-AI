"""Question paper upload, processing, topic mapping, historical analysis,
priority scoring, and RAG/search/study-guide integration.

Follows the same conventions as the rest of this suite: SQLite test DB via
conftest fixtures, LLM_PROVIDER defaults to "mock" so nothing here depends on
a live LLM call, and background jobs are driven synchronously via
process_question_paper_job(job_id) the same way test_job_reliability.py and
test_lectures.py drive process_lecture_job(job_id) — FastAPI's BackgroundTasks
don't reliably fire under TestClient.
"""
import io
import time

import pytest
from reportlab.pdfgen import canvas


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_pdf_bytes(lines):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
        if y < 50:
            c.showPage()
            y = 800
    c.save()
    return buf.getvalue()


SAMPLE_PAPER_LINES = [
    "SECTION A",
    "1. Explain the Bankers Algorithm for deadlock avoidance. [10 marks]",
    "2. Compare FCFS and Round Robin scheduling algorithms. [10 marks]",
    "SECTION B",
    "3(a) What is paging in memory management? [5 marks]",
    "3(b) What is segmentation in memory management? [5 marks]",
]


def _upload_paper(client, auth_headers, course_id, pdf_bytes, **fields):
    data = {"title": fields.pop("title", "Semester End Examination")}
    # Form fields must be omitted (not sent as the literal string "None") when
    # unset, so Optional[...] = Form(None) actually resolves to None server-side.
    data.update({k: v for k, v in fields.items() if v is not None})
    return client.post(
        f"/api/courses/{course_id}/question-papers/upload",
        headers=auth_headers,
        data=data,
        files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
    )


def _process_qp_job(db, job_id):
    """Drive the job synchronously, but only if it isn't already done.

    This TestClient setup actually runs FastAPI's BackgroundTasks inline
    during client.post(...) (unlike the assumption in some of the older
    lecture tests' comments), so the upload call above may have already
    completed the job before this is ever called. Re-running an already-
    completed job would double up its DB writes (e.g. duplicate
    QuestionPaperQuestion rows), so this checks first — mirroring the
    poll-then-conditionally-run pattern in test_lectures.py.
    """
    from app.tasks.question_paper_processing import process_question_paper_job
    from app.models import QuestionPaperProcessingJob
    db.expire_all()
    job = db.query(QuestionPaperProcessingJob).filter(QuestionPaperProcessingJob.id == job_id).first()
    if job and job.status not in ("completed", "failed"):
        process_question_paper_job(job_id)
        db.expire_all()


def _seed_topic(db, course_id, name, description):
    from app.models import Topic
    from app.services.embeddings import get_embedding_provider
    emb = get_embedding_provider().embed_texts([f"{name} {description}"])[0]
    t = Topic(
        course_id=course_id,
        name=name,
        canonical_name=name,
        description=description,
        coverage_score=0.6,
        lecture_count=2,
        evidence_count=3,
        embedding=emb,
    )
    db.add(t)
    db.flush()
    return t


# ---------------------------------------------------------------------------
# 1. Upload
# ---------------------------------------------------------------------------

def test_upload_creates_pending_paper_and_queued_job(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    pdf = _make_pdf_bytes(SAMPLE_PAPER_LINES)
    res = _upload_paper(client, auth_headers, cid, pdf, academic_year=2025, semester="Semester 1", exam_type="Final")
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["question_paper_id"] and body["job_id"]

    from app.models import QuestionPaper, QuestionPaperProcessingJob
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == body["question_paper_id"]).first()
    # This TestClient setup runs BackgroundTasks inline during client.post(),
    # so by the time the response returns the job may already have finished
    # (unlike production behind uvicorn, where the 202 response is sent before
    # the background job runs). Assert the upload created valid records with a
    # real status, not a specific transient one this harness doesn't produce.
    assert paper.status in ("pending", "processing", "processed", "error")
    assert paper.academic_year == 2025
    job = db.query(QuestionPaperProcessingJob).filter(QuestionPaperProcessingJob.id == body["job_id"]).first()
    assert job.status in ("queued", "processing", "completed", "failed")


def test_upload_rejects_non_pdf_and_empty_file(client, auth_headers, seed_course):
    cid = seed_course["id"]
    res = client.post(
        f"/api/courses/{cid}/question-papers/upload",
        headers=auth_headers,
        data={"title": "Not a PDF"},
        files={"file": ("paper.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 400

    res2 = client.post(
        f"/api/courses/{cid}/question-papers/upload",
        headers=auth_headers,
        data={"title": "Empty"},
        files={"file": ("paper.pdf", b"", "application/pdf")},
    )
    assert res2.status_code == 400


def test_upload_blocked_for_demo_user(client, demo_headers, db):
    from app.models import Course
    course = db.query(Course).filter(Course.user_id == 0).first()
    if not course:
        pytest.skip("No demo course seeded in this test DB")
    pdf = _make_pdf_bytes(SAMPLE_PAPER_LINES)
    res = _upload_paper(client, demo_headers, course.id, pdf)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 2. Ownership + 12. Download authorization
# ---------------------------------------------------------------------------

def test_ownership_blocks_other_user(client, auth_headers, auth_headers_u2, seed_course, db):
    cid = seed_course["id"]
    pdf = _make_pdf_bytes(SAMPLE_PAPER_LINES)
    paper_id = _upload_paper(client, auth_headers, cid, pdf).json()["question_paper_id"]

    assert client.get(f"/api/question-papers/{paper_id}", headers=auth_headers_u2).status_code == 403
    assert client.get(f"/api/question-papers/{paper_id}/download", headers=auth_headers_u2).status_code == 403
    assert client.get(f"/api/question-papers/{paper_id}/questions", headers=auth_headers_u2).status_code == 403
    assert client.post(f"/api/question-papers/{paper_id}/retry", headers=auth_headers_u2).status_code in (403, 409)
    assert client.delete(f"/api/question-papers/{paper_id}", headers=auth_headers_u2).status_code == 403


def test_download_unauthenticated_401(client, auth_headers, seed_course):
    cid = seed_course["id"]
    pdf = _make_pdf_bytes(SAMPLE_PAPER_LINES)
    paper_id = _upload_paper(client, auth_headers, cid, pdf).json()["question_paper_id"]
    res = client.get(f"/api/question-papers/{paper_id}/download")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# 3. PDF preservation / download
# ---------------------------------------------------------------------------

def test_download_preserves_original_bytes(client, auth_headers, seed_course):
    cid = seed_course["id"]
    pdf = _make_pdf_bytes(SAMPLE_PAPER_LINES)
    res = _upload_paper(client, auth_headers, cid, pdf, title="2025 Finals")
    paper_id = res.json()["question_paper_id"]

    dl = client.get(f"/api/question-papers/{paper_id}/download", headers=auth_headers)
    assert dl.status_code == 200
    assert dl.content == pdf
    assert "paper.pdf" in dl.headers.get("content-disposition", "")


# ---------------------------------------------------------------------------
# 4. Question extraction + 3. structure preserved even on unusual formatting
# ---------------------------------------------------------------------------

def test_processing_extracts_questions_preserving_text(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    pdf = _make_pdf_bytes(SAMPLE_PAPER_LINES)
    res = _upload_paper(client, auth_headers, cid, pdf)
    job_id = res.json()["job_id"]
    _process_qp_job(db, job_id)

    status = client.get(f"/api/question-papers/{res.json()['question_paper_id']}/status", headers=auth_headers)
    assert status.json()["status"] == "completed", status.json().get("error_message")

    questions = client.get(f"/api/question-papers/{res.json()['question_paper_id']}/questions", headers=auth_headers).json()
    assert len(questions) >= 4
    numbers = {q["question_number"] for q in questions}
    assert "1" in numbers
    assert any("Banker" in q["question_text"] or "bankers" in q["question_text"].lower() for q in questions)
    marks = {q["question_number"]: q["marks"] for q in questions}
    assert marks.get("1") == 10


def test_unusual_formatting_falls_back_to_single_preserved_block(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    pdf = _make_pdf_bytes(["This paper has no recognizable question numbering", "just free-form prose across lines."])
    res = _upload_paper(client, auth_headers, cid, pdf)
    _process_qp_job(db, res.json()["job_id"])

    paper_id = res.json()["question_paper_id"]
    status = client.get(f"/api/question-papers/{paper_id}/status", headers=auth_headers).json()
    assert status["status"] == "completed"
    questions = client.get(f"/api/question-papers/{paper_id}/questions", headers=auth_headers).json()
    assert len(questions) == 1
    assert "free-form prose" in questions[0]["question_text"]


# ---------------------------------------------------------------------------
# 5. Topic mapping (matched + no identifiable topic)
# ---------------------------------------------------------------------------

def test_topic_mapping_matches_known_topic_and_leaves_unrelated_unmapped(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    _seed_topic(
        db, cid, "Deadlocks",
        "Deadlock prevention, avoidance and detection including the Bankers Algorithm for safe resource allocation",
    )
    db.commit()

    pdf = _make_pdf_bytes([
        "1. Explain the Bankers Algorithm for deadlock avoidance in operating systems. [10 marks]",
        "2. What is the capital of France and how does tourism affect its economy? [5 marks]",
    ])
    res = _upload_paper(client, auth_headers, cid, pdf)
    _process_qp_job(db, res.json()["job_id"])

    paper_id = res.json()["question_paper_id"]
    questions = client.get(f"/api/question-papers/{paper_id}/questions", headers=auth_headers).json()
    by_num = {q["question_number"]: q for q in questions}

    assert by_num["1"]["topic_id"] is not None
    assert by_num["1"]["topic_name"] == "Deadlocks"
    assert by_num["1"]["topic_match_confidence"] > 0

    # Not everything must map — an unrelated question is left uncertain
    # rather than being forced onto the nearest available topic.
    assert by_num["2"]["topic_id"] is None


# ---------------------------------------------------------------------------
# 6. Embeddings / similar-question detection
# ---------------------------------------------------------------------------

def test_embeddings_persisted_and_near_duplicate_questions_score_high(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    text = "Explain the Bankers Algorithm for deadlock avoidance in operating systems."
    pdf1 = _make_pdf_bytes([f"1. {text} [10 marks]"])
    pdf2 = _make_pdf_bytes([f"1. {text} [10 marks]"])

    r1 = _upload_paper(client, auth_headers, cid, pdf1, title="2023 Finals", academic_year=2023)
    r2 = _upload_paper(client, auth_headers, cid, pdf2, title="2024 Finals", academic_year=2024)
    _process_qp_job(db, r1.json()["job_id"])
    _process_qp_job(db, r2.json()["job_id"])

    from app.models import QuestionPaperQuestion
    from app.services.embeddings import cosine_similarity
    qs = db.query(QuestionPaperQuestion).all()
    assert len(qs) == 2
    assert all(q.embedding is not None for q in qs)
    sim = cosine_similarity(qs[0].embedding, qs[1].embedding)
    assert sim > 0.9  # near-identical text should score very high


# ---------------------------------------------------------------------------
# 7 + 8 + 10. Frequency / year recurrence / recent trend + 9. priority scoring
# ---------------------------------------------------------------------------

def _upload_and_process(client, auth_headers, db, cid, question_line, title, academic_year=None):
    pdf = _make_pdf_bytes([f"1. {question_line} [10 marks]"])
    res = _upload_paper(client, auth_headers, cid, pdf, title=title, academic_year=academic_year)
    _process_qp_job(db, res.json()["job_id"])
    return res.json()["question_paper_id"]


def test_topic_frequency_and_year_recurrence(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    _seed_topic(
        db, cid, "Deadlocks",
        "Deadlock prevention, avoidance and detection including the Bankers Algorithm for safe resource allocation",
    )
    db.commit()

    q = "Explain the Bankers Algorithm for deadlock avoidance in operating systems."
    _upload_and_process(client, auth_headers, db, cid, q, "2022 Finals", 2022)
    _upload_and_process(client, auth_headers, db, cid, q, "2023 Finals", 2023)
    # Third paper has no academic_year on record — must not crash or skew the count.
    _upload_and_process(client, auth_headers, db, cid, "Unrelated question about something else entirely.", "Undated Finals", None)

    insights = client.get(f"/api/courses/{cid}/exam-insights", headers=auth_headers).json()
    assert insights["papers_analyzed"] == 3
    deadlocks = next(t for t in insights["topics"] if t["topic_name"] == "Deadlocks")
    assert deadlocks["papers_appeared_in"] == 2
    assert deadlocks["total_papers_analyzed"] == 3
    assert abs(deadlocks["frequency_score"] - (2 / 3)) < 1e-3  # API value is rounded to 4dp
    assert deadlocks["years_appeared_in"] == 2
    assert deadlocks["total_years_analyzed"] == 2  # the undated paper doesn't count toward the denominator either
    assert 0.0 <= deadlocks["priority_score"] <= 1.0
    assert deadlocks["priority_label"] in ("high", "medium", "lower_historical_frequency")
    assert len(deadlocks["evidence"]["papers"]) == 2


def test_only_one_previous_paper(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    _seed_topic(db, cid, "Deadlocks", "Deadlock prevention and the Bankers Algorithm")
    db.commit()
    _upload_and_process(
        client, auth_headers, db, cid,
        "Explain the Bankers Algorithm for deadlock avoidance.", "Only Paper", 2025,
    )
    insights = client.get(f"/api/courses/{cid}/exam-insights", headers=auth_headers).json()
    assert insights["papers_analyzed"] == 1
    deadlocks = next(t for t in insights["topics"] if t["topic_name"] == "Deadlocks")
    assert deadlocks["papers_appeared_in"] == 1
    assert deadlocks["recent_trend"] == "insufficient_data"


def test_no_question_papers_uploaded_gives_empty_state(client, auth_headers, seed_course):
    cid = seed_course["id"]
    res = client.get(f"/api/courses/{cid}/question-papers", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["papers"] == []
    assert body["papers_analyzed"] == 0

    insights = client.get(f"/api/courses/{cid}/exam-insights", headers=auth_headers).json()
    assert insights["papers_analyzed"] == 0
    assert insights["has_historical_patterns"] is False


def test_priority_scoring_formula_is_a_documented_weighted_sum():
    from app.services.question_papers.analysis import (
        WEIGHT_LECTURE_COVERAGE, WEIGHT_FREQUENCY, WEIGHT_YEAR_RECURRENCE,
        WEIGHT_RECENT_TREND, WEIGHT_MARKS, _priority_label,
        HIGH_PRIORITY_THRESHOLD, MEDIUM_PRIORITY_THRESHOLD,
    )
    assert abs(
        (WEIGHT_LECTURE_COVERAGE + WEIGHT_FREQUENCY + WEIGHT_YEAR_RECURRENCE
         + WEIGHT_RECENT_TREND + WEIGHT_MARKS) - 1.0
    ) < 1e-9
    assert _priority_label(HIGH_PRIORITY_THRESHOLD) == "high"
    assert _priority_label(MEDIUM_PRIORITY_THRESHOLD) == "medium"
    assert _priority_label(0.0) == "lower_historical_frequency"


def test_recent_trend_increasing_and_decreasing(db):
    from app.services.question_papers.analysis import _trend_for_topic
    older = {1, 2}
    newer = {3, 4}
    # Appears in both newer papers, neither older paper -> increasing.
    assert _trend_for_topic({3, 4}, older, newer) == "increasing"
    # Appears in both older papers, neither newer -> decreasing.
    assert _trend_for_topic({1, 2}, older, newer) == "decreasing"
    # Equal share on both sides -> stable.
    assert _trend_for_topic({1, 3}, older, newer) == "stable"
    # No older papers at all -> not enough history to compare.
    assert _trend_for_topic({3}, set(), newer) == "insufficient_data"


# ---------------------------------------------------------------------------
# 11. Study guide integration
# ---------------------------------------------------------------------------

def test_study_guide_integration_exam_priority_block(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    _seed_topic(db, cid, "Deadlocks", "Deadlock prevention and the Bankers Algorithm")
    db.commit()
    _upload_and_process(
        client, auth_headers, db, cid,
        "Explain the Bankers Algorithm for deadlock avoidance.", "2025 Finals", 2025,
    )

    sg = client.post(f"/api/courses/{cid}/study-guide/regenerate", headers=auth_headers)
    assert sg.status_code == 200, sg.text
    top_topics = sg.json()["top_topics"]
    deadlocks_entry = next((t for t in top_topics if t.get("name") == "Deadlocks"), None)
    assert deadlocks_entry is not None
    assert "exam_priority" in deadlocks_entry
    assert deadlocks_entry["exam_priority"]["papers_appeared_in"] == 1
    assert deadlocks_entry["exam_priority"]["total_papers_analyzed"] == 1


def test_study_guide_unchanged_when_no_question_papers(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    _seed_topic(db, cid, "Deadlocks", "Deadlock prevention and the Bankers Algorithm")
    db.commit()
    sg = client.post(f"/api/courses/{cid}/study-guide/regenerate", headers=auth_headers)
    assert sg.status_code == 200
    top_topics = sg.json()["top_topics"]
    for t in top_topics:
        assert "exam_priority" not in t


# ---------------------------------------------------------------------------
# 13 + 14. Failed processing / retry
# ---------------------------------------------------------------------------

def test_failed_processing_on_empty_and_malformed_pdf(client, auth_headers, seed_course, db):
    cid = seed_course["id"]

    # A syntactically well-formed PDF with zero drawn text -> no extractable text.
    empty_pdf = _make_pdf_bytes([])
    res = _upload_paper(client, auth_headers, cid, empty_pdf, title="Empty")
    _process_qp_job(db, res.json()["job_id"])
    status = client.get(f"/api/question-papers/{res.json()['question_paper_id']}/status", headers=auth_headers).json()
    assert status["status"] == "failed"
    assert status["error_message"]

    from app.models import QuestionPaper
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == res.json()["question_paper_id"]).first()
    assert paper.status == "error"
    # Original file must still be there — failure doesn't destroy the upload.
    dl = client.get(f"/api/question-papers/{paper.id}/download", headers=auth_headers)
    assert dl.status_code == 200

    # Malformed/non-PDF bytes given a .pdf name — extract_pdf_text swallows the
    # fitz error and returns "", hitting the same empty-text failure path.
    res2 = _upload_paper(client, auth_headers, cid, b"not a real pdf file", title="Malformed")
    _process_qp_job(db, res2.json()["job_id"])
    status2 = client.get(f"/api/question-papers/{res2.json()['question_paper_id']}/status", headers=auth_headers).json()
    assert status2["status"] == "failed"


def test_retry_flow(client, auth_headers, auth_headers_u2, demo_headers, seed_course, db):
    cid = seed_course["id"]
    empty_pdf = _make_pdf_bytes([])
    res = _upload_paper(client, auth_headers, cid, empty_pdf)
    paper_id = res.json()["question_paper_id"]
    _process_qp_job(db, res.json()["job_id"])
    status = client.get(f"/api/question-papers/{paper_id}/status", headers=auth_headers).json()
    assert status["status"] == "failed"

    # blocked for a non-owner
    assert client.post(f"/api/question-papers/{paper_id}/retry", headers=auth_headers_u2).status_code == 403

    # retry re-queues and can complete once given real content
    from app.models import QuestionPaper
    paper = db.query(QuestionPaper).filter(QuestionPaper.id == paper_id).first()
    from app.services.ingestion.storage import get_storage_provider
    storage = get_storage_provider()
    storage.delete(paper.file_path) if storage.exists(paper.file_path) else None
    real_pdf = _make_pdf_bytes(SAMPLE_PAPER_LINES)
    new_rel = storage.save(f"user_1/course_{cid}/qpaper_{paper_id}", "paper.pdf", real_pdf)
    paper.file_path = new_rel
    db.commit()

    retry_res = client.post(f"/api/question-papers/{paper_id}/retry", headers=auth_headers)
    assert retry_res.status_code == 202
    new_job_id = retry_res.json()["id"]
    _process_qp_job(db, new_job_id)
    status2 = client.get(f"/api/question-papers/{paper_id}/status", headers=auth_headers).json()
    assert status2["status"] == "completed", status2.get("error_message")

    # blocked while a job is already in-flight
    from app.models import QuestionPaperProcessingJob
    inflight = QuestionPaperProcessingJob(question_paper_id=paper_id, status="processing")
    db.add(inflight)
    db.commit()
    assert client.post(f"/api/question-papers/{paper_id}/retry", headers=auth_headers).status_code == 409


def test_retry_blocked_for_demo_user(client, demo_headers, db):
    from app.models import Course, QuestionPaper
    course = db.query(Course).filter(Course.user_id == 0).first()
    if not course:
        pytest.skip("No demo course seeded in this test DB")
    paper = db.query(QuestionPaper).filter(QuestionPaper.course_id == course.id).first()
    if not paper:
        pytest.skip("No demo question paper seeded in this test DB")
    res = client.post(f"/api/question-papers/{paper.id}/retry", headers=demo_headers)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 15. Search integration
# ---------------------------------------------------------------------------

def test_search_integration_finds_question(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    pdf = _make_pdf_bytes(["1. Explain the Bankers Algorithm for deadlock avoidance. [10 marks]"])
    res = _upload_paper(client, auth_headers, cid, pdf, title="2025 Finals")
    _process_qp_job(db, res.json()["job_id"])

    search = client.get("/api/search", headers=auth_headers, params={"q": "Bankers Algorithm", "course_id": cid})
    assert search.status_code == 200
    results = search.json()["results"]
    assert any(r["doc_type"] == "question" for r in results)


# ---------------------------------------------------------------------------
# 16. RAG (Ask) integration
# ---------------------------------------------------------------------------

def test_ask_rag_graceful_with_zero_papers(client, auth_headers, seed_course):
    cid = seed_course["id"]
    res = client.post("/api/ask", json={
        "course_id": cid, "question": "What should I prioritize for my exam?",
    }, headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "answer" in body
    assert isinstance(body["citations"], list)


def test_ask_rag_with_exam_evidence_present(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    _seed_topic(db, cid, "Deadlocks", "Deadlock prevention and the Bankers Algorithm")
    db.commit()
    _upload_and_process(
        client, auth_headers, db, cid,
        "Explain the Bankers Algorithm for deadlock avoidance.", "2025 Finals", 2025,
    )

    res = client.post("/api/ask", json={
        "course_id": cid, "question": "What are the most important topics to prioritize for my exam?",
    }, headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "answer" in body
    assert isinstance(body["citations"], list)
    # every returned citation must reference a real lecture (schema requires
    # a non-null lecture_id) — the synthetic exam-evidence chunk must never
    # surface as a citation object even though it's in context_chunks.
    for c in body["citations"]:
        assert c["lecture_id"] is not None
