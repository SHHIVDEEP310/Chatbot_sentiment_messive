def test_predict_valid_input(authed_client):
    resp = authed_client.post("/api/predict", json={"text": "I love this product"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["predicted_label"] == "positive"
    assert "scores" in body and "insight" in body
    assert abs(sum(body["scores"].values()) - 1.0) < 1e-3


def test_predict_empty_input_rejected(authed_client):
    resp = authed_client.post("/api/predict", json={"text": ""})
    assert resp.status_code == 422


def test_predict_whitespace_only_rejected(authed_client):
    resp = authed_client.post("/api/predict", json={"text": "   "})
    assert resp.status_code == 422


def test_predict_malformed_payload_rejected(authed_client):
    # missing required "text" field
    resp = authed_client.post("/api/predict", json={"not_text": "hello"})
    assert resp.status_code == 422


def test_predict_requires_auth(client):
    resp = client.post("/api/predict", json={"text": "hello"})
    assert resp.status_code == 401


def test_predict_batch_valid_input(authed_client):
    resp = authed_client.post(
        "/api/predict/batch",
        json={"texts": ["I love this", "this is terrible", "it is a table"]},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 3
    labels = [r["predicted_label"] for r in results]
    assert labels == ["positive", "negative", "neutral"]


def test_predict_batch_empty_list_rejected(authed_client):
    resp = authed_client.post("/api/predict/batch", json={"texts": []})
    assert resp.status_code == 422


def test_predict_batch_all_blank_entries_rejected(authed_client):
    resp = authed_client.post("/api/predict/batch", json={"texts": ["", "   "]})
    assert resp.status_code == 422


def test_predict_batch_exceeds_max_size(authed_client):
    resp = authed_client.post(
        "/api/predict/batch", json={"texts": ["hi"] * 100}
    )
    assert resp.status_code == 422


def test_history_reflects_predictions(authed_client):
    authed_client.post("/api/predict", json={"text": "great day"})
    resp = authed_client.get("/api/history")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


def test_delete_my_data(authed_client):
    authed_client.post("/api/predict", json={"text": "great day"})
    resp = authed_client.delete("/api/user/data")
    assert resp.status_code == 200
    assert resp.json()["deleted"] == 1

    history_resp = authed_client.get("/api/history")
    assert history_resp.json()["items"] == []
