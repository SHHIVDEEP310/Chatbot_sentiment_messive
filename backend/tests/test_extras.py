from fastapi.testclient import TestClient

from app.main import app


def test_control_chars_stripped_before_storage(authed_client):
    resp = authed_client.post("/api/predict", json={"text": "great\x00 day\x07"})
    assert resp.status_code == 200
    assert resp.json()["input_text"] == "great day"


def test_html_is_stored_verbatim_not_executed(authed_client):
    # Output encoding is the frontend's job (textContent); storage keeps text as-is.
    resp = authed_client.post("/api/predict", json={"text": "<b>good</b>"})
    assert resp.status_code == 200
    assert resp.json()["input_text"] == "<b>good</b>"


def test_emoji_passes_through_untouched(authed_client):
    resp = authed_client.post("/api/predict", json={"text": "🙂👍"})
    assert resp.status_code == 200
    assert resp.json()["input_text"] == "🙂👍"


def test_batch_with_non_string_items_rejected(authed_client):
    resp = authed_client.post("/api/predict/batch", json={"texts": [123, None]})
    assert resp.status_code == 422


def test_batch_results_are_per_item_and_ordered(authed_client):
    texts = ["good one", "bad one"]
    body = authed_client.post("/api/predict/batch", json={"texts": texts}).json()
    assert [r["input_text"] for r in body["results"]] == texts
    assert body["results"][0]["predicted_label"] != body["results"][1]["predicted_label"]


def test_delete_keeps_account_and_login_works(authed_client):
    authed_client.post("/api/predict", json={"text": "good"})
    authed_client.delete("/api/user/data")
    authed_client.post("/api/auth/logout")
    resp = authed_client.post(
        "/api/auth/login", json={"email": "testuser@example.com", "password": "strongpassword123"}
    )
    assert resp.status_code == 200


def test_delete_only_affects_current_user(client):
    client.post("/api/auth/register", json={"email": "alice1@example.com", "password": "password123"})
    client.post("/api/predict", json={"text": "good"})
    client.post("/api/auth/logout")

    client.post("/api/auth/register", json={"email": "bob123@example.com", "password": "password123"})
    client.post("/api/predict", json={"text": "bad"})
    client.delete("/api/user/data")
    client.post("/api/auth/logout")

    client.post("/api/auth/login", json={"email": "alice1@example.com", "password": "password123"})
    assert len(client.get("/api/history").json()["items"]) == 1




def test_overlong_password_rejected(client):
    resp = client.post("/api/auth/register", json={"email": "longpw@example.com", "password": "é" * 50})
    assert resp.status_code == 422


def test_mcp_stub_is_not_implemented(client):
    assert client.get("/api/mcp").status_code == 501


def test_model_unavailable_returns_503(authed_client):
    class Down:
        def is_ready(self):
            return False

    original = app.state.ml_service
    app.state.ml_service = Down()
    try:
        resp = authed_client.post("/api/predict", json={"text": "hello"})
        assert resp.status_code == 503
    finally:
        app.state.ml_service = original


def test_inference_failure_returns_500_not_crash(authed_client):
    from app.ml_service import InferenceError

    class Broken:
        def is_ready(self):
            return True

        def predict_batch(self, texts):
            raise InferenceError("boom")

    original = app.state.ml_service
    app.state.ml_service = Broken()
    try:
        resp = authed_client.post("/api/predict", json={"text": "hello"})
        assert resp.status_code == 500
        # server still healthy afterwards
        assert authed_client.get("/api/health").status_code == 200
    finally:
        app.state.ml_service = original
