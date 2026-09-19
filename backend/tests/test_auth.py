def test_register_happy_path(client):
    res = client.post("/api/auth/register", json={
        "email": "new@example.com",
        "password": "strongpass123",
        "full_name": "New User",
    })
    assert res.status_code in (200, 201)
    body = res.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "new@example.com"


def test_register_duplicate_email(client, user):
    res = client.post("/api/auth/register", json={
        "email": user.email,
        "password": "whatever",
    })
    assert res.status_code >= 400


def test_login_ok(client, user):
    res = client.post("/api/auth/login", json={
        "email": "alice@example.com",
        "password": "password123",
    })
    assert res.status_code == 200
    tok = res.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200
    assert me.json()["id"] == user.id


def test_login_wrong_password(client, user):
    res = client.post("/api/auth/login", json={
        "email": "alice@example.com",
        "password": "wrong",
    })
    assert res.status_code >= 400


def test_me_unauthorized(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_demo_token_and_me(client, demo_headers):
    me = client.get("/api/auth/me", headers=demo_headers)
    assert me.status_code == 200
    assert me.json()["is_demo"] is True


def test_demo_is_read_only_mutations_blocked(client, demo_headers, seed_course):
    res = client.post("/api/courses", json={"name": "nope"}, headers=demo_headers)
    assert res.status_code == 403
