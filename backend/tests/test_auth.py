from tests.conftest import register


def test_register_returns_token_and_user(client):
    r = client.post("/auth/register", json={"name": "Alex", "email": "alex.reg@example.com", "password": "strongpass1"})
    assert r.status_code == 201
    body = r.json()
    assert body["access_token"] and body["token_type"] == "bearer"
    assert body["user"]["email"] == "alex.reg@example.com"
    assert "password" not in str(body).lower().replace("password_hash", "")


def test_register_duplicate_email_rejected(client):
    payload = {"name": "Dup", "email": "dup@example.com", "password": "strongpass1"}
    assert client.post("/auth/register", json=payload).status_code == 201
    r = client.post("/auth/register", json={**payload, "email": "DUP@example.com"})
    assert r.status_code == 409


def test_register_validation(client):
    assert client.post("/auth/register", json={"name": "x", "email": "bad", "password": "longenough"}).status_code == 422
    assert client.post("/auth/register", json={"name": "x", "email": "s@example.com", "password": "short"}).status_code == 422


def test_password_is_hashed_in_db(client):
    from sqlalchemy import select
    from app.db.database import SessionLocal
    from app.db.models import User
    email, password, _ = register(client)
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        assert u.password_hash != password and u.password_hash.startswith("$2")


def test_login_success_and_failure(client, auth):
    ok = client.post("/auth/login", json={"email": auth["email"], "password": auth["password"]})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post("/auth/login", json={"email": auth["email"], "password": "wrong-password"})
    assert bad.status_code == 401
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever1"})
    assert unknown.status_code == 401


def test_me_requires_auth(client, auth):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    r = client.get("/auth/me", headers=auth["headers"])
    assert r.status_code == 200 and r.json()["email"] == auth["email"]


def test_logout_revokes_token(client, auth):
    assert client.post("/auth/logout", headers=auth["headers"]).status_code == 200
    assert client.get("/auth/me", headers=auth["headers"]).status_code == 401
    assert client.get("/conversations", headers=auth["headers"]).status_code == 401
    # logging in again issues a new, valid token
    new = client.post("/auth/login", json={"email": auth["email"], "password": auth["password"]}).json()["access_token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {new}"}).status_code == 200


def test_profile_update(client, auth):
    h = auth["headers"]
    body = {"age": 28, "height_cm": 175, "weight_kg": 72, "fitness_level": "beginner", "goal": "weight_loss",
            "dietary_preference": "vegetarian", "equipment": ["dumbbells"], "location": "home"}
    r = client.put("/auth/profile", json=body, headers=h)
    assert r.status_code == 200 and r.json()["goal"] == "weight_loss"
    assert client.get("/auth/profile", headers=h).json()["equipment"] == ["dumbbells"]
    assert client.get("/auth/me", headers=h).json()["profile"]["fitness_level"] == "beginner"
    assert client.put("/auth/profile", json={"fitness_level": "superhuman"}, headers=h).status_code == 422
