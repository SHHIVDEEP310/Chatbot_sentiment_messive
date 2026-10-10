import io

import pytest
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------- chats

def test_new_chat_id_is_separate_from_old_chat(authed_client):
    authed_client.post("/api/predict", json={"text": "great day", "chat_id": "chat-aaaaaaaa"})
    authed_client.post("/api/predict", json={"text": "bad day", "chat_id": "chat-bbbbbbbb"})

    chats = authed_client.get("/api/chats").json()["items"]
    assert {c["chat_id"] for c in chats} == {"chat-aaaaaaaa", "chat-bbbbbbbb"}
    assert chats[0]["chat_id"] == "chat-bbbbbbbb"  # newest first

    one = authed_client.get("/api/history", params={"chat_id": "chat-aaaaaaaa"}).json()["items"]
    assert [i["input_text"] for i in one] == ["great day"]
    # unfiltered history still returns everything (nothing is deleted)
    assert len(authed_client.get("/api/history").json()["items"]) == 2


def test_chat_title_and_count(authed_client):
    authed_client.post(
        "/api/predict/batch",
        json={"texts": ["love it", "hate it"], "chat_id": "chat-cccccccc"},
    )
    chat = authed_client.get("/api/chats").json()["items"][0]
    assert chat["title"] == "love it"
    assert chat["count"] == 2


def test_invalid_chat_id_rejected(authed_client):
    r = authed_client.post("/api/predict", json={"text": "good", "chat_id": "bad id!"})
    assert r.status_code == 422


def test_chats_are_per_user(client):
    client.post("/api/auth/register", json={"email": "u1@example.com", "password": "password123"})
    client.post("/api/predict", json={"text": "good", "chat_id": "chat-11111111"})
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"email": "u2@example.com", "password": "password123"})
    assert client.get("/api/chats").json()["items"] == []


# ---------------------------------------------------------------- share

def test_share_roundtrip_is_public_and_read_only(client):
    client.post("/api/auth/register", json={"email": "s@example.com", "password": "password123"})
    client.post("/api/predict", json={"text": "great stuff", "chat_id": "chat-share001"})
    token = client.post("/api/chats/chat-share001/share").json()["token"]
    # same token reused on a second call
    assert client.post("/api/chats/chat-share001/share").json()["token"] == token

    client.post("/api/auth/logout")  # anonymous viewer
    body = client.get(f"/api/shared/{token}").json()
    assert body["title"] == "great stuff"
    assert body["items"][0]["predicted_label"] == "positive"
    assert "id" not in body["items"][0] and "chat_id" not in body["items"][0]


def test_share_empty_or_foreign_chat_404(client):
    client.post("/api/auth/register", json={"email": "a@example.com", "password": "password123"})
    client.post("/api/predict", json={"text": "good", "chat_id": "chat-owner001"})
    client.post("/api/auth/logout")
    client.post("/api/auth/register", json={"email": "b@example.com", "password": "password123"})
    assert client.post("/api/chats/chat-owner001/share").status_code == 404
    assert client.get("/api/shared/not-a-token").status_code == 404


def test_delete_my_data_revokes_share_links(authed_client):
    authed_client.post("/api/predict", json={"text": "good", "chat_id": "chat-revoke01"})
    token = authed_client.post("/api/chats/chat-revoke01/share").json()["token"]
    authed_client.delete("/api/user/data")
    assert authed_client.get(f"/api/shared/{token}").status_code == 404


def test_share_requires_login(client):
    assert client.post("/api/chats/chat-whatever1/share").status_code == 401


# ---------------------------------------------------------------- media

def _png_with_text(text="I love this great product", size=(900, 200)) -> bytes:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 60), text, fill="black", font=ImageFont.load_default(size=48))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def test_image_ocr_then_sentiment(authed_client):
    r = authed_client.post(
        "/api/predict/media",
        files={"file": ("shot.png", _png_with_text(), "image/png")},
        data={"chat_id": "chat-media001"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_type"] == "image" and body["source_name"] == "shot.png"
    assert "love" in body["input_text"].lower()
    assert body["predicted_label"] == "positive"
    # stored in the chat's history with media info preserved
    item = authed_client.get("/api/history", params={"chat_id": "chat-media001"}).json()["items"][0]
    assert item["source_type"] == "image"


def test_image_without_text_is_422(authed_client):
    blank = Image.new("RGB", (400, 200), "white")
    buf = io.BytesIO(); blank.save(buf, "PNG")
    r = authed_client.post("/api/predict/media", files={"file": ("blank.png", buf.getvalue(), "image/png")})
    assert r.status_code == 422
    assert "No readable text" in r.json()["detail"]


def test_corrupt_image_is_422(authed_client):
    r = authed_client.post("/api/predict/media", files={"file": ("x.png", b"not an image", "image/png")})
    assert r.status_code == 422


def test_unsupported_type_is_415(authed_client):
    r = authed_client.post("/api/predict/media", files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 415


def test_oversized_image_is_413(authed_client, monkeypatch):
    from app.routers import predict

    monkeypatch.setattr(predict.settings, "MAX_IMAGE_BYTES", 1000)
    r = authed_client.post("/api/predict/media", files={"file": ("big.png", _png_with_text(), "image/png")})
    assert r.status_code == 413


def test_media_requires_login(client):
    r = client.post("/api/predict/media", files={"file": ("a.png", _png_with_text(), "image/png")})
    assert r.status_code == 401


def _make_video(path, text, seconds=2, fps=10):
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    frame_img = Image.open(io.BytesIO(_png_with_text(text, (640, 240)))).convert("RGB")
    frame = cv2.cvtColor(np.array(frame_img), cv2.COLOR_RGB2BGR)
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 240))
    for _ in range(seconds * fps):
        out.write(frame)
    out.release()


def test_video_frames_ocr_then_sentiment(authed_client, tmp_path):
    vid = tmp_path / "clip.mp4"
    _make_video(vid, "I hate this terrible service")
    r = authed_client.post(
        "/api/predict/media", files={"file": ("clip.mp4", vid.read_bytes(), "video/mp4")}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source_type"] == "video"
    assert "terrible" in body["input_text"].lower()
    assert body["predicted_label"] == "negative"
    # same on-screen line across frames must not be repeated
    assert body["input_text"].lower().count("terrible") == 1


def test_video_too_long_is_422(authed_client, tmp_path, monkeypatch):
    from app.routers import predict

    monkeypatch.setattr(predict.settings, "MAX_VIDEO_SECONDS", 1)
    vid = tmp_path / "long.mp4"
    _make_video(vid, "good good good", seconds=3)
    r = authed_client.post(
        "/api/predict/media", files={"file": ("long.mp4", vid.read_bytes(), "video/mp4")}
    )
    assert r.status_code == 422
    assert "too long" in r.json()["detail"].lower()
