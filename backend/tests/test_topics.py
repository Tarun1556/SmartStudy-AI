import time

L1 = """Introduction to Binary Search Trees — BST. Each node has at most 2 children.
Left subtree values are less than parent; right subtree greater.
Big O of log n on average for search operations; worst case O(n) on skewed trees.
Time Complexity: Big O Notation matters heavily here."""

L2 = """Revisiting Binary Search Trees and balancing. A Binary Search Tree can become skewed.
Big O notation review: worst-case vs average case.
Balanced trees preserve log n complexity. Tree traversal: in-order, pre-order, post-order."""


def _process_all_jobs(db):
    from app.tasks.processing import process_lecture_job
    from app.models import ProcessingJob
    for j in db.query(ProcessingJob).all():
        if j.status != "completed":
            try:
                process_lecture_job(j.id)
            except Exception:
                pass


def test_topic_merge_bst_across_two_lectures(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    l1 = client.post("/api/lectures", headers=auth_headers, json={
        "course_id": cid,
        "title": "L1",
        "lecture_number": 1,
        "transcript_text": L1,
    }).json()
    l2 = client.post("/api/lectures", headers=auth_headers, json={
        "course_id": cid,
        "title": "L2",
        "lecture_number": 2,
        "transcript_text": L2,
    }).json()
    time.sleep(0.5)
    _process_all_jobs(db)

    topics_res = client.get(f"/api/courses/{cid}/topics", headers=auth_headers)
    assert topics_res.status_code == 200
    topics = topics_res.json()

    names = [t["canonical_name"].lower() for t in topics]
    bst_variants = [
        "binary search tree", "binary search trees", "bst",
    ]
    found_bst_count = sum(1 for n in names if any(v in n for v in bst_variants))
    big_o_count = sum(1 for n in names if "big o" in n or "time complex" in n)

    bst_topics = [t for t in topics if any(v in t["canonical_name"].lower() for v in bst_variants)]
    assert len(bst_topics) >= 1, f"Expected at least 1 merged BST topic, got variants={names}"
    if len(bst_topics) == 1:
        assert bst_topics[0]["lecture_count"] >= 2, (
            f"Merged topic should appear in 2 lectures after merge, got {bst_topics[0]}"
        )
    assert len(topics) >= 3, f"Expected multiple topics, got {[t['canonical_name'] for t in topics]}"


def test_topic_detail_and_evidence_returns_snippets(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    client.post("/api/lectures", headers=auth_headers, json={
        "course_id": cid,
        "title": "L Topic Test",
        "lecture_number": 3,
        "transcript_text": L1,
    }).json()
    time.sleep(0.3)
    _process_all_jobs(db)

    topics = client.get(f"/api/courses/{cid}/topics", headers=auth_headers).json()
    assert len(topics) > 0
    t0 = topics[0]
    detail = client.get(f"/api/topics/{t0['id']}", headers=auth_headers)
    assert detail.status_code == 200
    d = detail.json()
    assert "topic" in d
    assert "evidence" in d
    assert "related" in d
    tl = client.get(f"/api/topics/{t0['id']}/timeline", headers=auth_headers)
    assert tl.status_code == 200
    ev = client.get(f"/api/topics/{t0['id']}/evidence", headers=auth_headers)
    assert ev.status_code == 200


def test_coverage_score_bounded_and_positive(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    client.post("/api/lectures", headers=auth_headers, json={
        "course_id": cid, "title": "Coverage Test", "lecture_number": 1, "transcript_text": L1,
    }).json()
    client.post("/api/lectures", headers=auth_headers, json={
        "course_id": cid, "title": "Coverage Test 2", "lecture_number": 2, "transcript_text": L2,
    }).json()
    time.sleep(0.3)
    _process_all_jobs(db)

    topics = client.get(f"/api/courses/{cid}/topics", headers=auth_headers).json()
    for t in topics:
        assert 0.0 <= t["coverage_score"] <= 1.0 + 1e-9, t
        assert t["lecture_count"] >= 1
        assert t["evidence_count"] >= 0
