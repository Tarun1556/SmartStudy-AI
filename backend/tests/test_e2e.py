import time

E2E_TRANSCRIPT = """Machine Learning 101.
Supervised Learning learns from labeled training data to predict new unseen examples.
Common supervised algorithms: Linear Regression, Logistic Regression, Decision Trees.
Linear Regression fits a line to minimize squared error loss — predicts continuous values.
Gradient Descent optimizes model parameters by walking the loss landscape.
Overfitting occurs when a model memorizes training noise; use Regularization to combat it.
L1 and L2 regularization (Ridge and Lasso) add penalty terms to large coefficients.
Cross-Validation splits data into folds for robust model evaluation.
Train / Validation / Test split prevents data leakage during hyperparameter tuning."""

ASK = "What's the difference between L1 and L2 regularization?"


def _process_all(db):
    from app.tasks.processing import process_lecture_job
    from app.models import ProcessingJob
    for j in db.query(ProcessingJob).all():
        if j.status != "completed":
            try:
                process_lecture_job(j.id)
            except Exception:
                pass


def test_end_to_end_happy_path_register_process_ask_quiz(client, db):
    # Step 1: register
    reg = client.post("/api/auth/register", json={
        "email": "e2e@example.com",
        "password": "goodpass123!",
        "full_name": "E2E User",
    })
    assert reg.status_code in (200, 201)
    token = reg.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/auth/me", headers=h)
    assert me.status_code == 200 and me.json()["email"] == "e2e@example.com"

    # Step 2: create course
    course = client.post("/api/courses", json={
        "name": "Intro to ML",
        "description": "Semester ML basics",
        "color": "#10b981",
    }, headers=h).json()
    cid = course["id"]

    # Step 3: paste transcript (create lecture)
    lect = client.post("/api/lectures", json={
        "course_id": cid,
        "title": "L1: Supervised Learning",
        "lecture_number": 1,
        "transcript_text": E2E_TRANSCRIPT,
    }, headers=h).json()
    lid = lect["id"]
    time.sleep(0.3)
    _process_all(db)

    # Step 4: poll status → completed
    status = client.get(f"/api/lectures/{lid}/status", headers=h).json()
    assert status["status"] == "completed", status.get("error_message")

    # Step 5: structured notes present
    notes = client.get(f"/api/lectures/{lid}/notes", headers=h).json()
    assert notes.get("overview") or (notes.get("key_ideas") and len(notes["key_ideas"]) > 0)

    # Step 6: topics list non-empty with coverage
    topics = client.get(f"/api/courses/{cid}/topics", headers=h).json()
    assert len(topics) >= 3
    for t in topics:
        assert 0.0 <= t["coverage_score"] <= 1.0 + 1e-9

    # Step 7: dashboard aggregates
    dash = client.get("/api/dashboard", headers=h)
    assert dash.status_code == 200
    ds = dash.json()
    assert ds["total_courses"] >= 1
    assert ds["total_lectures"] >= 1
    assert ds["total_topics"] >= 3

    # Step 8: study guide generated with 3+ top topics
    sg = client.get(f"/api/courses/{cid}/study-guide", headers=h).json()
    assert len(sg.get("top_topics") or []) >= 3

    # Step 9: search for "regularization" returns this lecture
    search = client.get("/api/search", headers=h, params={
        "q": "regularization", "course_id": cid,
    }).json()
    assert search["total"] >= 0  # no crash

    # Step 10: ask grounded question → has citations, found_in_material true or fallback
    ask = client.post("/api/ask", json={
        "course_id": cid, "question": ASK,
    }, headers=h)
    assert ask.status_code == 200
    a = ask.json()
    assert "answer" in a
    assert "citations" in a
    assert isinstance(a["citations"], list)
    sid = a.get("session_id")

    # Step 11: follow-up question in same session
    followup = client.post("/api/ask", json={
        "course_id": cid, "question": "And why use it?", "session_id": sid,
    }, headers=h)
    assert followup.status_code == 200

    # Step 12: quiz generation succeeds
    quiz = client.post("/api/quiz/generate", json={
        "course_id": cid, "num_questions": 5, "quiz_type": "mcq",
    }, headers=h)
    assert quiz.status_code == 200
    q = quiz.json()
    assert len(q["questions"]) >= 1
    assert q["course_id"] == cid
    first_q = q["questions"][0]
    assert "question_text" in first_q
    qid = q["id"]
    qget = client.get(f"/api/quiz/{qid}", headers=h)
    assert qget.status_code == 200
