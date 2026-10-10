def test_register_and_me(client):
    resp = client.post(
        "/api/auth/register", json={"email": "alice@example.com", "password": "password123"}
    )
    assert resp.status_code == 201
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_email_is_normalised_to_lowercase(client):
    client.post("/api/auth/register", json={"email": "  Alice@Example.COM ", "password": "password123"})
    assert client.get("/api/auth/me").json()["email"] == "alice@example.com"


def test_duplicate_email_rejected(client):
    client.post("/api/auth/register", json={"email": "bob@example.com", "password": "password123"})
    resp = client.post(
        "/api/auth/register", json={"email": "BOB@example.com", "password": "password123"}
    )
    assert resp.status_code == 409


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={"email": "carol@example.com", "password": "password123"})
    resp = client.post(
        "/api/auth/login", json={"email": "carol@example.com", "password": "wrongpass"}
    )
    assert resp.status_code == 401


def test_logout_clears_session(client):
    client.post("/api/auth/register", json={"email": "dave@example.com", "password": "password123"})
    client.post("/api/auth/logout")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_invalid_emails_rejected_on_register_and_login(client):
    for bad in ["plain", "a@b", "a b@example.com", "@example.com", "a@.com", "a@example..com", ""]:
        r1 = client.post("/api/auth/register", json={"email": bad, "password": "password123"})
        r2 = client.post("/api/auth/login", json={"email": bad, "password": "password123"})
        assert r1.status_code == 422, bad
        assert r2.status_code == 422, bad
