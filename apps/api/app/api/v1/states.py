from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.models.cooperation import ModelRegistryEntry, StateDataset, StateNode
from app.models.user import User

router = APIRouter(prefix="/states", tags=["states"])


def _node_out(n: StateNode) -> dict:
    return {
        "id": str(n.id),
        "state": n.state,
        "node_id": n.node_id,
        "display_name": n.display_name,
        "status": n.status,
        "data_policy": n.data_policy,
        "available_models": n.available_models,
        "supported_crops": n.supported_crops,
        "is_demo": n.is_demo,
        "last_sync": n.updated_at.isoformat(),
    }


@router.get("")
def list_states(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    nodes = db.query(StateNode).order_by(StateNode.state.asc()).all()
    return [_node_out(n) for n in nodes]


@router.get("/{state_id}")
def get_state(state_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    node = db.get(StateNode, state_id)
    if not node:
        raise NotFoundError("State node not found.")
    datasets = db.query(StateDataset).filter(StateDataset.state_node_id == node.id).all()
    pending_requests = 0
    from app.models.cooperation import ModelRequest

    pending_requests = (
        db.query(ModelRequest)
        .join(ModelRegistryEntry, ModelRequest.model_id == ModelRegistryEntry.id)
        .filter(ModelRegistryEntry.publisher_state_node_id == node.id, ModelRequest.status == "requested")
        .count()
    )
    return {
        **_node_out(node),
        "shared_datasets": [{"id": str(d.id), "name": d.name, "schema_version": d.schema_version, "record_count": d.record_count, "visibility": d.visibility} for d in datasets],
        "pending_requests": pending_requests,
    }


@router.get("/{state_id}/models")
def list_state_models(state_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    node = db.get(StateNode, state_id)
    if not node:
        raise NotFoundError("State node not found.")
    models = db.query(ModelRegistryEntry).filter(ModelRegistryEntry.publisher_state_node_id == node.id).all()
    return [
        {
            "id": str(m.id),
            "name": m.name,
            "version": m.version,
            "model_type": m.model_type,
            "crop": m.crop,
            "status": m.status,
            "visibility": m.visibility,
            "accuracy": m.accuracy,
            "is_demo": m.is_demo,
        }
        for m in models
    ]
