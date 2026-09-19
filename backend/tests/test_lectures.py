import time

TRANSCRIPT = """Welcome everyone. Today we introduce Binary Search Trees, or BST for short.
A Binary Search Tree is a tree data structure where each node has at most two children.
The left child is always less than the parent, and the right child is greater.
This ordering makes search very efficient with logarithmic time complexity in the average case.
For example, to find a value we compare it to the root and go left or right.
Time Complexity for search in a balanced BST is Big O of log n.
In the worst case a skewed BST degrades to a linked list with O(n) search.
We also visit nodes using traversal methods: in-order, pre-order, and post-order.
In-order traversal of a BST visits nodes in ascending sorted order.
Binary Search Trees are related to the broader Tree data structure category."""


def test_create_lecture_and_process_via_pasted_transcript(client, auth_headers, seed_course, db):
    from app.models import Lecture, LectureNote, Topic, ProcessingJob
    cid = seed_course["id"]
    res = client.post("/api/lectures", headers=auth_headers, json={
        "course_id": cid,
        "title": "Lecture 4: Binary Search Trees",
        "lecture_number": 4,
        "description": "Intro to BST",
        "transcript_text": TRANSCRIPT,
    })
    assert res.status_code in (200, 201)
    lecture_id = res.json()["id"]

    # Poll status up to ~30 seconds (processing is BackgroundTasks via TestClient sync test env
    # -> runs in-process synchronously via the dependency injection thread if executed)
    # Note: TestClient synchronous mode may not trigger background tasks; we manually ensure processing completed
    # by re-running the job synchronously if not yet done.
    job_id = None
    for _ in range(20):
        status = client.get(f"/api/lectures/{lecture_id}/status", headers=auth_headers)
        if status.status_code == 200:
            job = status.json()
            job_id = job.get("id")
            if job["status"] in ("completed", "failed"):
                break
        time.sleep(0.5)

    if job_id:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job and job.status != "completed":
            from app.tasks.processing import process_lecture_job
            process_lecture_job(job_id)

    status = client.get(f"/api/lectures/{lecture_id}/status", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["status"] == "completed", status.json().get("error_message")

    notes = client.get(f"/api/lectures/{lecture_id}/notes", headers=auth_headers)
    assert notes.status_code == 200
    n = notes.json()
    assert "overview" in n

    topics = client.get(f"/api/courses/{cid}/topics", headers=auth_headers)
    assert topics.status_code == 200
    tl = topics.json()
    assert len(tl) >= 2


def test_lecture_list_filters_by_course(client, auth_headers, seed_course):
    cid = seed_course["id"]
    c2 = client.post("/api/courses", json={"name": "Other"}, headers=auth_headers).json()
    client.post("/api/lectures", headers=auth_headers, json={
        "course_id": cid,
        "title": "L1",
        "transcript_text": "Hello from L1. Topic: Sorting algorithms and Big O.",
    })
    client.post("/api/lectures", headers=auth_headers, json={
        "course_id": c2["id"],
        "title": "Other L",
        "transcript_text": "Unrelated content here.",
    })
    time.sleep(1.0)
    from app.tasks.processing import process_lecture_job
    from app.models import ProcessingJob
    from app.db.session import SessionLocal
    s = SessionLocal()
    try:
        for j in s.query(ProcessingJob).all():
            try:
                process_lecture_job(j.id)
            except Exception:
                pass
    finally:
        s.close()

    lst = client.get("/api/lectures", headers=auth_headers, params={"course_id": cid})
    assert lst.status_code == 200
    titles = [l["title"] for l in lst.json()]
    assert "L1" in titles
    assert "Other L" not in titles
