"""
Cooperation network workflow (PRODUCT SPEC sections 27, 30-31):

    State A -> publish model -> validation -> registry -> State B requests
    -> State A approves -> metadata transfer -> State B registers local
    version -> evaluation -> local deployment
"""
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.models.cooperation import ModelRegistryEntry, ModelRequest, StateNode
from app.services import audit_service

VALID_STATUSES = {"draft", "pending_review", "published", "requested", "approved", "rejected", "deprecated"}


class CooperationService:
    def publish_model(self, db: Session, *, publisher_state_node: StateNode, payload: dict, user_id: str) -> ModelRegistryEntry:
        if not payload.get("name") or not payload.get("model_type"):
            raise ValidationFailedError("Model name and model_type are required.")
        model = ModelRegistryEntry(
            name=payload["name"],
            description=payload.get("description", ""),
            publisher_state_node_id=publisher_state_node.id,
            version=payload.get("version", "v1.0"),
            model_type=payload["model_type"],
            crop=payload.get("crop", "general"),
            supported_regions=payload.get("supported_regions", [publisher_state_node.state]),
            accuracy=payload.get("accuracy"),
            training_dataset_description=payload.get("training_dataset_description", ""),
            license=payload.get("license", "BHOOMI Cooperative License"),
            visibility="state_only",
            status="pending_review",
            is_demo=payload.get("is_demo", False),
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        audit_service.record(db, user_id=user_id, action="MODEL_PUBLISHED", resource="model_registry", resource_id=str(model.id))
        return model

    def approve_publication(self, db: Session, *, model: ModelRegistryEntry, user_id: str) -> ModelRegistryEntry:
        if model.status != "pending_review":
            raise ConflictError("Only models pending review can be approved for publication.")
        model.status = "published"
        model.visibility = "shared"
        db.commit()
        db.refresh(model)
        audit_service.record(db, user_id=user_id, action="MODEL_APPROVED_FOR_PUBLICATION", resource="model_registry", resource_id=str(model.id))
        return model

    def request_model(self, db: Session, *, model: ModelRegistryEntry, requesting_state_node: StateNode, justification: str, user_id: str) -> ModelRequest:
        if model.visibility != "shared" or model.status != "published":
            raise ValidationFailedError("This model has not been published for cross-state sharing yet.")
        existing = (
            db.query(ModelRequest)
            .filter(ModelRequest.model_id == model.id, ModelRequest.requesting_state_node_id == requesting_state_node.id, ModelRequest.status == "requested")
            .first()
        )
        if existing:
            raise ConflictError("A pending request for this model from this state already exists.")
        req = ModelRequest(
            model_id=model.id,
            requesting_state_node_id=requesting_state_node.id,
            status="requested",
            justification=justification,
        )
        db.add(req)
        db.commit()
        db.refresh(req)
        audit_service.record(db, user_id=user_id, action="MODEL_REQUESTED", resource="model_request", resource_id=str(req.id))
        return req

    def decide_request(self, db: Session, *, request: ModelRequest, approve: bool, user_id: str) -> ModelRequest:
        if request.status != "requested":
            raise ConflictError("This request has already been decided.")
        request.status = "approved" if approve else "rejected"
        request.decided_by_user_id = user_id
        db.commit()
        db.refresh(request)
        audit_service.record(
            db,
            user_id=user_id,
            action="MODEL_REQUEST_APPROVED" if approve else "MODEL_REQUEST_REJECTED",
            resource="model_request",
            resource_id=str(request.id),
        )
        return request
