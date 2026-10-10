"""
Pydantic schemas for request validation and response serialization.
"""
import datetime
import re
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.services.sanitize import sanitize_text

# Pragmatic email check: local@domain.tld, no spaces, at least one dot in
# the domain. Format validity only — we don't send mail to verify existence.
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
_CHAT_ID_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not _EMAIL_RE.match(value):
        raise ValueError("enter a valid email address, e.g. name@example.com")
    return value


def normalize_chat_id(value: Optional[str]) -> str:
    """Return a safe chat id; generate one if the client didn't send any."""
    if value is None or not value.strip():
        return str(uuid.uuid4())
    value = value.strip()
    if not _CHAT_ID_RE.match(value):
        raise ValueError("invalid chat_id")
    return value


# ---------- Auth ----------

class UserCreate(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        return normalize_email(v)

    @field_validator("password")
    @classmethod
    def password_bcrypt_limit(cls, v: str) -> str:
        # bcrypt only uses the first 72 bytes; reject rather than silently truncate.
        if len(v.encode("utf-8")) > 72:
            raise ValueError("password must be at most 72 bytes")
        return v


class UserLogin(BaseModel):
    email: str = Field(..., max_length=254)
    password: str

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        return normalize_email(v)


class UserOut(BaseModel):
    id: int
    email: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


# ---------- Prediction ----------

class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1)
    chat_id: Optional[str] = Field(default=None, validate_default=True)

    @field_validator("text")
    @classmethod
    def clean_and_require_content(cls, v: str) -> str:
        v = sanitize_text(v)
        if not v:
            raise ValueError("text must not be empty or whitespace-only")
        return v

    @field_validator("chat_id")
    @classmethod
    def chat_id_valid(cls, v: Optional[str]) -> str:
        return normalize_chat_id(v)


class PredictBatchRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1)
    chat_id: Optional[str] = Field(default=None, validate_default=True)

    @field_validator("texts")
    @classmethod
    def entries_not_blank(cls, v: List[str]) -> List[str]:
        cleaned = [c for c in (sanitize_text(t) for t in v) if c]
        if not cleaned:
            raise ValueError("batch must contain at least one non-empty entry")
        return cleaned

    @field_validator("chat_id")
    @classmethod
    def chat_id_valid(cls, v: Optional[str]) -> str:
        return normalize_chat_id(v)


class PredictionResult(BaseModel):
    input_text: str
    predicted_label: str
    scores: Dict[str, float]
    insight: str
    submission_id: int
    chat_id: str
    source_type: str = "text"
    source_name: Optional[str] = None
    created_at: datetime.datetime


class PredictBatchResponse(BaseModel):
    results: List[PredictionResult]


class HistoryItem(BaseModel):
    id: int
    input_text: str
    predicted_label: str
    scores: Dict[str, float]
    insight: Optional[str]
    batch_id: str
    chat_id: str
    source_type: str = "text"
    source_name: Optional[str] = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    items: List[HistoryItem]


# ---------- Chats / sharing ----------

class ChatSummary(BaseModel):
    chat_id: str
    title: str
    count: int
    last_at: datetime.datetime


class ChatListResponse(BaseModel):
    items: List[ChatSummary]


class ShareResponse(BaseModel):
    token: str


class SharedItem(BaseModel):
    """Public, read-only view of one entry (no internal ids)."""

    input_text: str
    predicted_label: str
    scores: Dict[str, float]
    insight: Optional[str]
    batch_id: str
    source_type: str = "text"
    source_name: Optional[str] = None
    created_at: datetime.datetime


class SharedChatResponse(BaseModel):
    title: str
    items: List[SharedItem]
