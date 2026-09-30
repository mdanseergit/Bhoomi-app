from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationService:
    def create(self, db: Session, *, user_id: str, type_: str, title: str, message: str, severity: str = "info") -> Notification:
        n = Notification(user_id=user_id, type=type_, title=title, message=message, severity=severity)
        db.add(n)
        db.commit()
        db.refresh(n)
        return n

    def mark_read(self, db: Session, *, notification: Notification) -> Notification:
        from datetime import datetime, timezone

        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
        return notification
