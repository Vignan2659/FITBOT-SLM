from tests.conftest import register


def test_conversation_crud(client, auth):
    h = auth["headers"]
    c = client.post("/conversations", json={"title": "Leg day ideas"}, headers=h)
    assert c.status_code == 201
    cid = c.json()["id"]
    assert any(x["id"] == cid for x in client.get("/conversations", headers=h).json())
    d = client.get(f"/conversations/{cid}", headers=h)
    assert d.status_code == 200 and d.json()["title"] == "Leg day ideas" and d.json()["messages"] == []
    assert client.delete(f"/conversations/{cid}", headers=h).status_code == 204
    assert client.get(f"/conversations/{cid}", headers=h).status_code == 404


def test_conversations_are_private(client, auth):
    h1 = auth["headers"]
    _, _, token2 = register(client, name="Other")
    h2 = {"Authorization": f"Bearer {token2}"}
    cid = client.post("/conversations", json={}, headers=h1).json()["id"]
    client.post("/chat", json={"message": "How much sleep do I need?", "conversation_id": cid}, headers=h1)
    # user 2 can neither see, read, delete nor post into user 1's conversation
    assert all(x["id"] != cid for x in client.get("/conversations", headers=h2).json())
    assert client.get(f"/conversations/{cid}", headers=h2).status_code == 404
    assert client.delete(f"/conversations/{cid}", headers=h2).status_code == 404
    assert client.post("/chat", json={"message": "hi", "conversation_id": cid}, headers=h2).status_code == 404
    assert client.get(f"/conversations/{cid}", headers=h1).status_code == 200


def test_conversation_requires_auth(client):
    assert client.get("/conversations").status_code == 401
    assert client.post("/conversations", json={}).status_code == 401
    assert client.post("/chat", json={"message": "hello"}).status_code == 401


def test_delete_cascades_messages(client, auth):
    from sqlalchemy import func, select
    from app.db.database import SessionLocal
    from app.db.models import Message
    h = auth["headers"]
    r = client.post("/chat", json={"message": "What should I eat after a workout?"}, headers=h).json()
    cid = r["conversation_id"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Message).where(Message.conversation_id == cid)) == 2
    client.delete(f"/conversations/{cid}", headers=h)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Message).where(Message.conversation_id == cid)) == 0
