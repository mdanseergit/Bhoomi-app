from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.advisory import Advisory
from app.models.cooperation import ModelRegistryEntry, StateNode
from app.models.disease import DiseaseScan
from app.models.farm import Farm
from app.models.governance import AuditLog
from app.models.system import AIUsage
from app.models.user import Role, User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", dependencies=[Depends(require_roles(Role.PLATFORM_ADMIN))])
def admin_overview(db: Session = Depends(get_db)):
    return {
        "users": db.query(func.count(User.id)).scalar(),
        "farms": db.query(func.count(Farm.id)).scalar(),
        "states": db.query(func.count(StateNode.id)).scalar(),
        "models": db.query(func.count(ModelRegistryEntry.id)).scalar(),
        "advisories": db.query(func.count(Advisory.id)).scalar(),
        "disease_scans": db.query(func.count(DiseaseScan.id)).scalar(),
    }


@router.get("/users", dependencies=[Depends(require_roles(Role.PLATFORM_ADMIN))])
def list_users(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).limit(200).all()
    return [
        {"id": str(u.id), "full_name": u.full_name, "email": u.email, "role": u.role.value, "state": u.state, "is_active": u.is_active}
        for u in users
    ]


@router.get("/audit-logs", dependencies=[Depends(require_roles(Role.PLATFORM_ADMIN))])
def list_audit_logs(db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return [
        {
            "id": str(l.id),
            "user_id": str(l.user_id) if l.user_id else None,
            "action": l.action,
            "resource": l.resource,
            "resource_id": l.resource_id,
            "result": l.result,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


@router.get("/ai-usage", dependencies=[Depends(require_roles(Role.PLATFORM_ADMIN))])
def ai_usage(db: Session = Depends(get_db)):
    rows = db.query(AIUsage).order_by(AIUsage.created_at.desc()).limit(200).all()
    totals = db.query(AIUsage.provider, func.count(AIUsage.id)).group_by(AIUsage.provider).all()
    return {
        "recent": [
            {"provider": r.provider, "model": r.model, "request_type": r.request_type, "status": r.status, "latency_ms": r.latency_ms, "created_at": r.created_at.isoformat()}
            for r in rows
        ],
        "totals_by_provider": {p: c for p, c in totals},
    }
