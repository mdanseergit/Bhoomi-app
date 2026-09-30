from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])
notification_service = NotificationService()


@router.get("")
def list_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notifications = (
        db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50).all()
    )
    return [
        {
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "severity": n.severity,
            "read_at": n.read_at.isoformat() if n.read_at else None,
            "created_at": n.created_at.isoformat(),
        }
        for n in notifications
    ]


@router.post("/{notification_id}/read")
def mark_read(notification_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if not n:
        raise NotFoundError("Notification not found.")
    if str(n.user_id) != str(user.id):
        raise ForbiddenError("You cannot modify another user's notifications.")
    n = notification_service.mark_read(db, notification=n)
    return {"id": str(n.id), "read_at": n.read_at.isoformat()}
