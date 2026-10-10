import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.ml_service import InferenceError, ModelNotLoadedError
from app.models import User
from app.schemas import (
    HistoryItem,
    HistoryResponse,
    PredictBatchRequest,
    PredictBatchResponse,
    PredictionResult,
    PredictRequest,
)
from app.security import get_current_user
from app.schemas import normalize_chat_id
from app.services import media, storage

router = APIRouter(prefix="/api", tags=["prediction"])
settings = get_settings()


def _get_ml_service(request: Request):
    ml_service = getattr(request.app.state, "ml_service", None)
    if ml_service is None or not ml_service.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sentiment model is not loaded yet. Please try again shortly.",
        )
    return ml_service


def _check_lengths(texts: list[str]) -> None:
    if any(len(t) > settings.MAX_INPUT_LENGTH for t in texts):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Each input must be at most {settings.MAX_INPUT_LENGTH} characters",
        )


async def _infer(ml_service, texts: list[str]) -> list[dict]:
    """Run blocking model inference off the event loop."""
    try:
        return await run_in_threadpool(ml_service.predict_batch, texts)
    except (ModelNotLoadedError, InferenceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed: {exc}",
        ) from exc


@router.post("/predict", response_model=PredictionResult)
async def predict(
    payload: PredictRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_lengths([payload.text])
    ml_service = _get_ml_service(request)
    scores_list = await _infer(ml_service, [payload.text])
    results = await run_in_threadpool(
        storage.save_batch, db, current_user, [payload.text], scores_list, payload.chat_id
    )
    return results[0]


@router.post("/predict/batch", response_model=PredictBatchResponse)
async def predict_batch(
    payload: PredictBatchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    texts = payload.texts
    if len(texts) > settings.MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Batch exceeds max size of {settings.MAX_BATCH_SIZE} items",
        )
    _check_lengths(texts)
    ml_service = _get_ml_service(request)
    scores_list = await _infer(ml_service, texts)
    results = await run_in_threadpool(
        storage.save_batch, db, current_user, texts, scores_list, payload.chat_id
    )
    return PredictBatchResponse(results=results)


def _safe_filename(name: Optional[str]) -> str:
    name = os.path.basename(name or "upload")
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return (name or "upload")[:120]


@router.post("/predict/media", response_model=PredictionResult)
async def predict_media(
    request: Request,
    file: UploadFile = File(...),
    chat_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """photo/short video -> extract text context -> sentiment model -> result."""
    try:
        chat_id = normalize_chat_id(chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    ctype = (file.content_type or "").lower()
    if ctype in media.IMAGE_TYPES:
        kind, limit = "image", settings.MAX_IMAGE_BYTES
    elif ctype in media.VIDEO_TYPES:
        kind, limit = "video", settings.MAX_VIDEO_BYTES
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only photos (JPG, PNG, WEBP, GIF) and short videos (MP4, WEBM, MOV) are supported.",
        )

    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max {limit // (1024 * 1024)} MB for a {kind}.",
        )
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")

    name = _safe_filename(file.filename)
    ml_service = _get_ml_service(request)

    try:
        if kind == "image":
            text = await run_in_threadpool(
                media.extract_text_from_image, data, settings.OCR_LANG
            )
        else:
            text = await run_in_threadpool(
                media.extract_text_from_video,
                data,
                os.path.splitext(name)[1].lower(),
                settings.OCR_LANG,
                settings.MAX_VIDEO_SECONDS,
                settings.VIDEO_FRAME_SAMPLES,
            )
    except media.MediaError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except media.MediaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    text = text[: settings.MAX_INPUT_LENGTH]
    scores_list = await _infer(ml_service, [text])
    results = await run_in_threadpool(
        storage.save_batch, db, current_user, [text], scores_list, chat_id, kind, name
    )
    return results[0]


@router.get("/history", response_model=HistoryResponse)
def history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 100,
    chat_id: Optional[str] = None,
):
    items = storage.list_history(db, current_user, limit, chat_id)
    return HistoryResponse(items=[HistoryItem(**i) for i in items])
