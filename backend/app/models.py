"""
ORM models: users, submissions, results.

A Submission is what the user sent; a Result is what the model returned
for it (1:1). "Delete my data" removes a user's submissions + results and
never touches the User row (account/credentials).
"""
import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Login identifier. Stored lower-cased (see schemas.normalize_email).
    email = Column(String(254), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utcnow)

    submissions = relationship("Submission", back_populates="user")


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Items sent together share a batch_id (single items get their own).
    batch_id = Column(String(36), nullable=False, index=True)
    # A chat = everything sent from one "New chat" session. The frontend
    # starts a fresh chat_id on every visit; old chats stay stored.
    chat_id = Column(String(64), nullable=False, index=True)
    # "text" | "image" | "video". For image/video, input_text holds the
    # text extracted from the media (the file itself is never stored).
    source_type = Column(String(16), nullable=False, default="text")
    source_name = Column(String(120), nullable=True)
    input_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, index=True)

    user = relationship("User", back_populates="submissions")
    result = relationship(
        "Result",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True)
    submission_id = Column(
        Integer, ForeignKey("submissions.id"), nullable=False, unique=True, index=True
    )
    predicted_label = Column(String(64), nullable=False)
    # label -> probability, e.g. {"positive": 0.81, "negative": 0.11, ...}
    scores = Column(JSON, nullable=False)
    insight = Column(Text, nullable=True)

    submission = relationship("Submission", back_populates="result")


class ChatShare(Base):
    """Unguessable token that exposes one chat read-only at /api/shared/{token}."""

    __tablename__ = "chat_shares"

    token = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    chat_id = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)
