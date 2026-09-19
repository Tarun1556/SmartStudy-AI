def test_create_and_list_course(client, auth_headers):
    res = client.post("/api/courses", json={
        "name": "Algorithms",
        "description": "Basics",
        "color": "#6366f1",
    }, headers=auth_headers)
    assert res.status_code in (200, 201)
    cid = res.json()["id"]
    assert res.json()["name"] == "Algorithms"

    lst = client.get("/api/courses", headers=auth_headers)
    assert lst.status_code == 200
    ids = [c["id"] for c in lst.json()]
    assert cid in ids


def test_get_course_detail(client, auth_headers, seed_course):
    cid = seed_course["id"]
    res = client.get(f"/api/courses/{cid}", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["id"] == cid


def test_update_course(client, auth_headers, seed_course):
    cid = seed_course["id"]
    res = client.put(f"/api/courses/{cid}", json={
        "name": "New Name",
        "color": "#0ea5e9",
    }, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "New Name"


def test_delete_course(client, auth_headers, seed_course):
    cid = seed_course["id"]
    res = client.delete(f"/api/courses/{cid}", headers=auth_headers)
    assert res.status_code in (200, 204)
    res2 = client.get(f"/api/courses/{cid}", headers=auth_headers)
    assert res2.status_code == 404


def test_course_isolation_other_user_blocked(client, auth_headers_u2, seed_course):
    cid = seed_course["id"]
    res = client.get(f"/api/courses/{cid}", headers=auth_headers_u2)
    assert res.status_code in (403, 404)


def test_course_stats_available(client, auth_headers, seed_course):
    cid = seed_course["id"]
    res = client.get(f"/api/courses/{cid}/stats", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "lecture_count" in body
    assert "topic_count" in body
