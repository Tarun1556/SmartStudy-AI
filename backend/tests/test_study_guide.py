import time

T1 = """Sorting algorithms. Insertion Sort, Bubble Sort, Merge Sort, Quick Sort.
Time Complexity: Merge Sort is O(n log n) worst case. Quick Sort average O(n log n).
Big O notation describes asymptotic upper bounds.
We compare running time and stability of each algorithm."""

T2 = """Graph algorithms: Breadth First Search (BFS), Depth First Search (DFS).
Shortest paths: Dijkstra's Algorithm works on graphs with non-negative weights.
Time Complexity matters here too — BFS runs in O(V+E) with an adjacency list."""


def _process_all(db):
    from app.tasks.processing import process_lecture_job
    from app.models import ProcessingJob
    for j in db.query(ProcessingJob).all():
        if j.status != "completed":
            try:
                process_lecture_job(j.id)
            except Exception:
                pass


def test_study_guide_generate_and_pdf_endpoint(client, auth_headers, seed_course, db):
    cid = seed_course["id"]
    client.post("/api/lectures", headers=auth_headers, json={
        "course_id": cid, "title": "Sorting L", "lecture_number": 1, "transcript_text": T1,
    })
    client.post("/api/lectures", headers=auth_headers, json={
        "course_id": cid, "title": "Graphs L", "lecture_number": 2, "transcript_text": T2,
    })
    time.sleep(0.5)
    _process_all(db)

    res = client.get(f"/api/courses/{cid}/study-guide", headers=auth_headers)
    assert res.status_code == 200
    sg = res.json()
    assert sg["course_id"] == cid
    assert "version" in sg
    top = sg.get("top_topics") or []
    # Should have at least 3 topics across 2 lectures
    assert len(top) >= 3, f"Topics: {[(t['name'], t['lecture_count']) for t in top]}"
    # At least one topic should span both lectures (Time Complexity / Big O) — coverage > 0.5
    high_coverage = [t for t in top if t["coverage_score"] >= 0.5]
    assert len(high_coverage) >= 1, f"No high coverage topics: {[(t['name'], t['coverage_score']) for t in top]}"

    regen = client.post(f"/api/courses/{cid}/study-guide/regenerate", headers=auth_headers)
    assert regen.status_code == 200
    new_sg = regen.json()
    assert new_sg["version"] >= sg["version"]

    pdf = client.get(f"/api/courses/{cid}/study-guide/pdf", headers=auth_headers)
    assert pdf.status_code == 200
    assert len(pdf.content) >= 500
    assert pdf.headers.get("content-type", "").lower().startswith("application/pdf")
