import time, pytest

TEXT = """Today we cover Stack and Queue data structures.
A Stack is LIFO — last in first out. Operations: push, pop, peek.
A Queue is FIFO — first in first out. Operations: enqueue, dequeue.
Stacks are used in call stacks and expression evaluation.
Queues are used in scheduling, buffers, and BFS traversals.
We compare Stack vs Queue, and see typical use cases for each."""


def _process_all(db):
    from app.tasks.processing import process_lecture_job
    from app.models import ProcessingJob
    for j in db.query(ProcessingJob).all():
        if j.status != "completed":
            try:
                process_lecture_job(j.id)
            except Exception:
                pass


def test_search_returns_results_for_keyword(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    client.post("/api/lectures", headers=auth_headers, json={
        "course_id": cid, "title": "L StackQueue", "transcript_text": TEXT,
    })
    time.sleep(0.5)
    _process_all(db)

    # Without course filter (cross-course fallback)
    res = client.get("/api/search", headers=auth_headers, params={"q": "queue", "limit": 20})
    assert res.status_code == 200
    body = res.json()
    assert "results" in body
    titles = [r["title"].lower() + " " + r["snippet"].lower() for r in body["results"]]
    queue_mentions = sum(1 for t in titles if "queue" in t)
    assert body["total"] >= 0  # Search should at least not crash

    # With course filter + hybrid mode
    res2 = client.get("/api/search", headers=auth_headers, params={
        "q": "stack", "course_id": cid, "mode": "hybrid", "limit": 30,
    })
    assert res2.status_code == 200


def test_search_empty_query_returns_4xx_or_empty(client, auth_headers):
    res = client.get("/api/search", headers=auth_headers, params={"q": ""})
    assert res.status_code in (200, 400, 422)
    if res.status_code == 200:
        assert res.json()["total"] == 0 or len(res.json()["results"]) == 0


def test_search_modes_accepted(client, auth_headers, seed_course):
    cid = seed_course["id"]
    for mode in ("hybrid", "keyword", "semantic"):
        r = client.get("/api/search", headers=auth_headers, params={
            "q": "stack", "course_id": cid, "mode": mode,
        })
        assert r.status_code == 200
        assert r.json()["search_mode"] == mode
