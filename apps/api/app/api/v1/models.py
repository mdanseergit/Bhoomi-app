from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.cooperation import ModelRegistryEntry, ModelRequest, StateNode
from app.models.user import Role, User
from app.services.cooperation_service import CooperationService
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/models", tags=["models"])
cooperation_service = CooperationService()
notification_service = NotificationService()


def _model_out(m: ModelRegistryEntry) -> dict:
    return {
        "id": str(m.id),
        "name": m.name,
        "description": m.description,
        "publisher_state_node_id": str(m.publisher_state_node_id),
        "version": m.version,
        "model_type": m.model_type,
        "crop": m.crop,
        "supported_regions": m.supported_regions,
        "accuracy": m.accuracy,
        "training_dataset_description": m.training_dataset_description,
        "license": m.license,
        "visibility": m.visibility,
        "status": m.status,
        "is_demo": m.is_demo,
        "created_at": m.created_at.isoformat(),
    }


@router.get("")
def list_models(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    models = db.query(ModelRegistryEntry).order_by(ModelRegistryEntry.created_at.desc()).all()
    return [_model_out(m) for m in models]


@router.post("", dependencies=[])
def publish_model(
    payload: dict = Body(...),
    user: User = Depends(require_roles(Role.STATE_ADMIN, Role.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
):
    node = db.query(StateNode).filter(StateNode.state == user.state).first() if user.state else None
    if not node:
        raise NotFoundError("No state node is associated with this account. Set a state in your profile first.")
    model = cooperation_service.publish_model(db, publisher_state_node=node, payload=payload, user_id=str(user.id))
    return _model_out(model)


@router.post("/{model_id}/publish")
def approve_publication(
    model_id: str,
    user: User = Depends(require_roles(Role.STATE_ADMIN, Role.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
):
    model = db.get(ModelRegistryEntry, model_id)
    if not model:
        raise NotFoundError("Model not found.")
    model = cooperation_service.approve_publication(db, model=model, user_id=str(user.id))
    return _model_out(model)


@router.post("/{model_id}/request")
def request_model(
    model_id: str,
    payload: dict = Body(default={}),
    user: User = Depends(require_roles(Role.STATE_ADMIN, Role.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
):
    model = db.get(ModelRegistryEntry, model_id)
    if not model:
        raise NotFoundError("Model not found.")
    node = db.query(StateNode).filter(StateNode.state == user.state).first() if user.state else None
    if not node:
        raise NotFoundError("No state node is associated with this account.")
    req = cooperation_service.request_model(db, model=model, requesting_state_node=node, justification=payload.get("justification", ""), user_id=str(user.id))
    return {"id": str(req.id), "status": req.status, "model_id": str(req.model_id), "requesting_state_node_id": str(req.requesting_state_node_id)}


@router.post("/{model_id}/approve")
def approve_request(
    model_id: str,
    payload: dict = Body(...),
    user: User = Depends(require_roles(Role.STATE_ADMIN, Role.PLATFORM_ADMIN)),
    db: Session = Depends(get_db),
):
    request_id = payload.get("request_id")
    approve = payload.get("approve", True)
    request_row = db.get(ModelRequest, request_id) if request_id else None
    if not request_row or str(request_row.model_id) != model_id:
        raise NotFoundError("Model request not found.")
    node = db.get(StateNode, request_row.requesting_state_node_id)
    model = db.get(ModelRegistryEntry, request_row.model_id)
    request_row = cooperation_service.decide_request(db, request=request_row, approve=approve, user_id=str(user.id))

    if node and model:
        outcome = "approved" if approve else "rejected"
        for recipient in (
            db.query(User)
            .filter(User.role == Role.STATE_ADMIN, User.state == node.state, User.is_active.is_(True))
            .all()
        ):
            if str(recipient.id) == str(user.id):
                continue
            notification_service.create(
                db,
                user_id=str(recipient.id),
                type_="model_request",
                title=f"Model request {outcome}: {model.name}",
                message=(
                    f"Your request for the shared model \"{model.name}\" from {node.display_name} "
                    f"was {outcome} by the reviewing administration."
                ),
                severity="info" if approve else "warning",
            )

    return {"id": str(request_row.id), "status": request_row.status}


@router.get("/requests")
def list_requests(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    requests = db.query(ModelRequest).order_by(ModelRequest.created_at.desc()).all()
    return [
        {
            "id": str(r.id),
            "model_id": str(r.model_id),
            "requesting_state_node_id": str(r.requesting_state_node_id),
            "status": r.status,
            "justification": r.justification,
            "created_at": r.created_at.isoformat(),
        }
        for r in requests
    ]
