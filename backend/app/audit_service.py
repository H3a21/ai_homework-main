"""Append-only persistence for security and data-change audit events."""

from dataclasses import dataclass
import logging

from app.database import AsyncSession
from app.models import AuditLog


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuditEvent:
    request_id: str
    user_id: int | None
    action: str
    resource_type: str
    resource_id: int | None
    old_value: dict | None
    new_value: dict | None
    ip_address: str | None
    user_agent: str | None
    outcome: str
    method: str
    path: str
    status_code: int


async def persist_audit_event(event: AuditEvent) -> bool:
    try:
        async with AsyncSession() as db:
            db.add(AuditLog(**event.__dict__))
            await db.commit()
        return True
    except Exception:
        logger.warning(
            "audit_persistence_failed",
            extra={
                "request_id": event.request_id,
                "action": event.action,
                "status_code": event.status_code,
            },
            exc_info=True,
        )
        return False
