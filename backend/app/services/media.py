"""
Turns an uploaded photo or short video into text so the sentiment model
(which only reads text + emoji) can analyse it.

Pipeline:  file -> extract context (text) -> sentiment model -> result

- Image: OCR (Tesseract) on the picture.
- Video: a few frames sampled evenly across the clip, OCR on each, with
  repeated lines removed. Audio/speech is NOT transcribed.

Heavy imports (cv2, PIL, pytesseract) are lazy so the rest of the app and
the test-suite don't need them unless media is actually uploaded.
"""
import os
import re
import tempfile
from typing import List

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}

_MAX_PIXELS = 25_000_000  # decompression-bomb guard
_WORDISH = re.compile(r"\w", re.UNICODE)


class MediaError(ValueError):
    """The upload is unusable (bad file, too long, no readable text) -> 422."""


class MediaUnavailableError(RuntimeError):
    """Server-side dependency missing (e.g. Tesseract not installed) -> 503."""


def _ocr(pil_image, lang: str) -> str:
    try:
        import pytesseract
        from PIL import ImageOps
    except ImportError as exc:
        raise MediaUnavailableError(
            f"Media libraries not installed: {exc}. Run `pip install -r requirements.txt`."
        ) from exc

    img = ImageOps.exif_transpose(pil_image).convert("L")
    # Tesseract does poorly on small text; upscale small images.
    if max(img.size) < 1000:
        img = img.resize((img.width * 2, img.height * 2))
    try:
        return pytesseract.image_to_string(img, lang=lang)
    except pytesseract.TesseractNotFoundError as exc:
        raise MediaUnavailableError(
            "Tesseract OCR is not installed on the server (apt install tesseract-ocr)."
        ) from exc
    except pytesseract.TesseractError as exc:
        raise MediaError(f"Could not read text from the media: {exc}") from exc


def _clean_lines(raw: str) -> List[str]:
    lines = []
    for line in raw.splitlines():
        line = " ".join(line.split())
        # drop OCR noise such as "|" or "_ ." — keep lines with real characters
        if len(_WORDISH.findall(line)) >= 2:
            lines.append(line)
    return lines


def extract_text_from_image(data: bytes, lang: str = "eng") -> str:
    try:
        from PIL import Image
        import io

        probe = Image.open(io.BytesIO(data))
        probe.verify()  # raises on corrupt/non-image data
        img = Image.open(io.BytesIO(data))
        if img.width * img.height > _MAX_PIXELS:
            raise MediaError("Image resolution is too large.")
        img.load()
    except MediaError:
        raise
    except ImportError as exc:
        raise MediaUnavailableError(f"Pillow is not installed: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - any decode failure = bad upload
        raise MediaError("That file is not a readable image.") from exc

    text = "\n".join(_clean_lines(_ocr(img, lang)))
    if not text:
        raise MediaError(
            "No readable text was found in this image. Try a clearer screenshot "
            "or photo that contains text."
        )
    return text


def extract_text_from_video(
    data: bytes,
    suffix: str,
    lang: str = "eng",
    max_seconds: int = 30,
    samples: int = 6,
) -> str:
    try:
        import cv2
        from PIL import Image
    except ImportError as exc:
        raise MediaUnavailableError(f"Video libraries not installed: {exc}") from exc

    path = None
    cap = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".mp4") as tmp:
            tmp.write(data)
            path = tmp.name

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise MediaError("That file is not a readable video.")

        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if fps <= 0 or frame_count <= 0:
            raise MediaError("Could not read the video's length or frames.")
        if frame_count / fps > max_seconds:
            raise MediaError(f"Video is too long. Maximum is {max_seconds} seconds.")

        n = max(1, min(samples, frame_count))
        positions = sorted({int(i * (frame_count - 1) / max(1, n - 1)) for i in range(n)})

        seen, collected = set(), []
        for pos in positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ok, frame = cap.read()
            if not ok:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            for line in _clean_lines(_ocr(Image.fromarray(rgb), lang)):
                key = line.lower()
                if key not in seen:
                    seen.add(key)
                    collected.append(line)
    finally:
        if cap is not None:
            cap.release()
        if path and os.path.exists(path):
            os.remove(path)

    text = "\n".join(collected)
    if not text:
        raise MediaError(
            "No readable on-screen text was found in this video. "
            "Speech/audio is not analysed."
        )
    return text
