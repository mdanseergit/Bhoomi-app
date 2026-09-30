from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.advisory import Advisory, ReviewStatus
from app.models.user import Role, User
from app.repositories.farm_repository import FarmRepository
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/advisories", tags=["advisories"])
farm_repo = FarmRepository()
notification_service = NotificationService()


def _out(a: Advisory) -> dict:
    return {
        "id": str(a.id),
        "farm_id": str(a.farm_id),
        "type": a.type.value,
        "severity": a.severity.value,
        "title": a.title,
        "summary": a.summary,
        "actions": a.actions,
        "evidence": a.evidence,
        "source_references": a.source_references,
        "confidence": a.confidence,
        "generated_by": a.generated_by,
        "review_status": a.review_status.value,
        "created_at": a.created_at.isoformat(),
    }


@router.get("")
def list_advisories(farm_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Advisory)
    if farm_id:
        farm = farm_repo.get(db, farm_id)
        if not farm:
            raise NotFoundError("Farm not found.")
        if user.role == Role.FARMER and str(farm.user_id) != str(user.id):
            raise ForbiddenError("You do not have access to this farm's advisories.")
        query = query.filter(Advisory.farm_id == farm.id)
    elif user.role == Role.FARMER:
        farm_ids = [f.id for f in farm_repo.list_for_user(db, str(user.id))]
        query = query.filter(Advisory.farm_id.in_(farm_ids))
    advisories = query.order_by(Advisory.created_at.desc()).limit(100).all()
    return [_out(a) for a in advisories]


@router.post("/{advisory_id}/review")
def review_advisory(
    advisory_id: str,
    approve: bool,
    user: User = Depends(require_roles(Role.AGRONOMIST, Role.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
):
    advisory = db.get(Advisory, advisory_id)
    if not advisory:
        raise NotFoundError("Advisory not found.")
    advisory.review_status = ReviewStatus.APPROVED if approve else ReviewStatus.REJECTED
    db.commit()
    db.refresh(advisory)

    farm = farm_repo.get(db, str(advisory.farm_id))
    if farm and str(farm.user_id) != str(user.id):
        outcome = "approved" if approve else "rejected"
        notification_service.create(
            db,
            user_id=str(farm.user_id),
            type_="advisory_review",
            title=f"Advisory {outcome}: {advisory.title}",
            message=(
                f"An agronomist {outcome} the advisory \"{advisory.title}\" for your farm "
                f"{farm.name}."
            ),
            severity="info" if approve else "warning",
        )

    return _out(advisory)
