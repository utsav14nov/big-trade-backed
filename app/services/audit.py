"""Append-only audit trail for every mutation of financial data."""
import uuid
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditLog


async def log_action(
    db: AsyncSession,
    user_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: str | None,
    request: Request | None = None,
    detail: dict | None = None,
):
    ip = None
    if request is not None:
        ip = request.headers.get("x-forwarded-for", request.client.host if request.client else None)
    db.add(AuditLog(
        user_id=user_id, action=action, entity=entity,
        entity_id=entity_id, ip=ip, detail=detail,
    ))
    # caller commits
