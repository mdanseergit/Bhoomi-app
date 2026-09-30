from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.cooperation import ModelRegistryEntry, ModelRequest, StateDataset, StateNode
from app.models.user import User

router = APIRouter(prefix="/cooperation", tags=["cooperation"])


@router.get("/summary")
def cooperation_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    nodes = db.query(StateNode).all()
    shared_models = db.query(ModelRegistryEntry).filter(ModelRegistryEntry.visibility == "shared").count()
    shared_schemas = db.query(StateDataset).filter(StateDataset.visibility == "shared").count()
    pending_requests = db.query(ModelRequest).filter(ModelRequest.status == "requested").count()
    return {
        "nodes": [
            {"state": n.state, "status": n.status, "is_demo": n.is_demo, "last_sync": n.updated_at.isoformat()}
            for n in nodes
        ],
        "shared_models": shared_models,
        "shared_schemas": shared_schemas,
        "model_requests": pending_requests,
    }
