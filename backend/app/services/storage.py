"""
Persistence layer for submissions/results. Routers call these helpers and
never build queries themselves.
"""
import secrets
import uuid
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ml_service import build_insight, friendly_label, friendly_scores, top_label
from app.models import ChatShare, Result, Submission, User


def save_batch(
    db: Session,
    user: User,
    texts: List[str],
    scores_list: List[Dict[str, float]],
    chat_id: str,
    source_type: str = "text",
    source_name: Optional[str] = None,
) -> List[dict]:
    """Persist each item as its own submission+result (no merging/averaging)."""
    batch_id = str(uuid.uuid4())
    out: List[dict] = []
    for text, scores in zip(texts, scores_list):
        label = top_label(scores)
        insight = build_insight(label, scores)

        submission = Submission(
            user_id=user.id,
            batch_id=batch_id,
            chat_id=chat_id,
            source_type=source_type,
            source_name=source_name,
            input_text=text,
        )
        submission.result = Result(
            predicted_label=label, scores=scores, insight=insight
        )
        db.add(submission)
        db.flush()  # assigns ids/created_at without ending the transaction

        out.append(
            {
                "input_text": text,
                "predicted_label": label,
                "scores": scores,
                "insight": insight,
                "submission_id": submission.id,
                "chat_id": chat_id,
                "source_type": source_type,
                "source_name": source_name,
                "created_at": submission.created_at,
            }
        )
    db.commit()
    return out


def _history_row(s: Submission, r: Result) -> dict:
    return {
        "id": s.id,
        "input_text": s.input_text,
        "predicted_label": friendly_label(r.predicted_label),
        "scores": friendly_scores(r.scores),
        "insight": r.insight,
        "batch_id": s.batch_id,
        "chat_id": s.chat_id,
        "source_type": s.source_type or "text",
        "source_name": s.source_name,
        "created_at": s.created_at,
    }


def list_history(
    db: Session, user: User, limit: int = 100, chat_id: Optional[str] = None
) -> List[dict]:
    q = (
        db.query(Submission, Result)
        .join(Result, Result.submission_id == Submission.id)
        .filter(Submission.user_id == user.id)
    )
    if chat_id:
        q = q.filter(Submission.chat_id == chat_id)
    rows = (
        q.order_by(Submission.created_at.asc(), Submission.id.asc())
        .limit(min(limit, 500))
        .all()
    )
    return [_history_row(s, r) for s, r in rows]


def _chat_title(first: Submission) -> str:
    base = first.source_name if first.source_type != "text" and first.source_name else first.input_text
    base = " ".join(base.split())
    prefix = {"image": "[image] ", "video": "[video] "}.get(first.source_type, "")
    title = prefix + base
    return title if len(title) <= 48 else title[:47] + "…"


def list_chats(db: Session, user: User, limit: int = 30) -> List[dict]:
    """Most recently active chats first; title = first message of the chat."""
    agg = (
        db.query(
            Submission.chat_id.label("chat_id"),
            func.min(Submission.id).label("first_id"),
            func.max(Submission.created_at).label("last_at"),
            func.count(Submission.id).label("n"),
        )
        .filter(Submission.user_id == user.id)
        .group_by(Submission.chat_id)
        .subquery()
    )
    rows = (
        db.query(agg.c.chat_id, agg.c.last_at, agg.c.n, Submission)
        .join(Submission, Submission.id == agg.c.first_id)
        .order_by(agg.c.last_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [
        {"chat_id": cid, "title": _chat_title(first), "count": n, "last_at": last_at}
        for cid, last_at, n, first in rows
    ]


def chat_exists(db: Session, user: User, chat_id: str) -> bool:
    return (
        db.query(Submission.id)
        .filter(Submission.user_id == user.id, Submission.chat_id == chat_id)
        .first()
        is not None
    )


def get_or_create_share(db: Session, user: User, chat_id: str) -> str:
    existing = (
        db.query(ChatShare)
        .filter(ChatShare.user_id == user.id, ChatShare.chat_id == chat_id)
        .first()
    )
    if existing:
        return existing.token
    share = ChatShare(
        token=secrets.token_urlsafe(18), user_id=user.id, chat_id=chat_id
    )
    db.add(share)
    db.commit()
    return share.token


def get_shared_chat(db: Session, token: str) -> Optional[dict]:
    share = db.query(ChatShare).filter(ChatShare.token == token).first()
    if share is None:
        return None
    rows = (
        db.query(Submission, Result)
        .join(Result, Result.submission_id == Submission.id)
        .filter(
            Submission.user_id == share.user_id,
            Submission.chat_id == share.chat_id,
        )
        .order_by(Submission.created_at.asc(), Submission.id.asc())
        .limit(500)
        .all()
    )
    if not rows:
        return None
    items = [_history_row(s, r) for s, r in rows]
    for it in items:
        it.pop("id")
        it.pop("chat_id")
    return {"title": _chat_title(rows[0][0]), "items": items}


def delete_user_history(db: Session, user: User) -> int:
    """Delete this user's results + submissions (and share links) only.
    The account row is untouched."""
    ids = select(Submission.id).where(Submission.user_id == user.id)
    db.query(Result).filter(Result.submission_id.in_(ids)).delete(
        synchronize_session=False
    )
    db.query(ChatShare).filter(ChatShare.user_id == user.id).delete(
        synchronize_session=False
    )
    deleted = (
        db.query(Submission)
        .filter(Submission.user_id == user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
