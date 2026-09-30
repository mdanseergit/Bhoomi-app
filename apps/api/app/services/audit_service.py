"""
Centralized audit logging (PRODUCT SPEC sections 32-33). Every sensitive
operation across the platform must call `record` so there is a single,
consistent, privacy-safe audit trail.
"""
import hashlib

from sqlalchemy.orm import Session

from app.models.governance import AuditLog


def hash_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


def record(
    db: Session,
    *,
    user_id: str | None,
    action: str,
    resource: str,
    resource_id: str | None = None,
    ip: str | None = None,
    result: str = "success",
    metadata: dict | None = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        ip_hash=hash_ip(ip),
        result=result,
        metadata_json=metadata or {},
    )
    db.add(entry)
    db.commit()
