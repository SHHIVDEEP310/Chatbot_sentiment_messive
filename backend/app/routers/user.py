from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import get_current_user
from app.services import storage

router = APIRouter(prefix="/api/user", tags=["user"])


@router.delete("/data", status_code=status.HTTP_200_OK)
def delete_my_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Wipes only this user's history. The account and credentials stay."""
    return {"deleted": storage.delete_user_history(db, current_user)}
