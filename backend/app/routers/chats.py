"""
Chat list + read-only sharing.

- GET  /api/chats                  the user's stored chats (newest first)
- POST /api/chats/{chat_id}/share  create/reuse an unguessable share token
- GET  /api/shared/{token}         PUBLIC read-only view of that chat
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import (
    ChatListResponse,
    ChatSummary,
    ShareResponse,
    SharedChatResponse,
    SharedItem,
    normalize_chat_id,
)
from app.security import get_current_user
from app.services import storage

router = APIRouter(prefix="/api", tags=["chats"])


@router.get("/chats", response_model=ChatListResponse)
def list_chats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ChatListResponse(
        items=[ChatSummary(**c) for c in storage.list_chats(db, current_user)]
    )


@router.post("/chats/{chat_id}/share", response_model=ShareResponse)
def share_chat(
    chat_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        chat_id = normalize_chat_id(chat_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not storage.chat_exists(db, current_user, chat_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nothing to share yet - send a message first.",
        )
    return ShareResponse(token=storage.get_or_create_share(db, current_user, chat_id))


@router.get("/shared/{token}", response_model=SharedChatResponse)
def get_shared(token: str, db: Session = Depends(get_db)):
    data = storage.get_shared_chat(db, token)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shared chat not found."
        )
    return SharedChatResponse(
        title=data["title"], items=[SharedItem(**i) for i in data["items"]]
    )
