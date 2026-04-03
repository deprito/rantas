"""Audit logging utilities for tracking user actions."""

from typing import Any, Optional
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def log_audit_action(
    db: AsyncSession,
    user_id: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """Log an audit action to the database.

    Args:
        db: Database session
        user_id: ID of the user performing the action (None for system actions)
        action: Action performed (e.g., 'case_created', 'user_updated')
        resource_type: Type of resource (e.g., 'case', 'user', 'config')
        resource_id: ID of the resource affected
        details: Additional details about the action
        ip_address: IP address of the user

    Returns:
        Created AuditLog entry
    """
    audit_entry = AuditLog(
        id=str(uuid4()),
        user_id=str(user_id) if user_id else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_address,
        created_at=datetime.now(timezone.utc),
    )

    db.add(audit_entry)
    await db.flush()

    return audit_entry


async def get_audit_logs(
    db: AsyncSession,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """Get audit logs with optional filtering.

    Args:
        db: Database session
        user_id: Filter by user ID
        resource_type: Filter by resource type
        resource_id: Filter by resource ID
        action: Filter by action
        limit: Maximum number of logs to return
        offset: Offset for pagination

    Returns:
        List of audit log entries
    """
    from sqlalchemy import select, and_

    query = select(AuditLog)

    conditions = []
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if resource_id:
        conditions.append(AuditLog.resource_id == resource_id)
    if action:
        conditions.append(AuditLog.action == action)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return list(result.scalars().all())


async def count_audit_logs(
    db: AsyncSession,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    action: Optional[str] = None,
) -> int:
    """Count audit logs with optional filtering.

    Args:
        db: Database session
        user_id: Filter by user ID
        resource_type: Filter by resource type
        resource_id: Filter by resource ID
        action: Filter by action

    Returns:
        Count of matching audit log entries
    """
    from sqlalchemy import select, and_, func

    query = select(func.count()).select_from(AuditLog)

    conditions = []
    if user_id:
        conditions.append(AuditLog.user_id == user_id)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if resource_id:
        conditions.append(AuditLog.resource_id == resource_id)
    if action:
        conditions.append(AuditLog.action == action)

    if conditions:
        query = query.where(and_(*conditions))

    result = await db.execute(query)
    return result.scalar() or 0


# Audit action constants
class AuditAction:
    """Standard audit action types."""

    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_PASSWORD_CHANGED = "user_password_changed"
    USER_PASSWORD_RESET = "user_password_reset"

    # Case actions
    CASE_CREATED = "case_created"
    CASE_VIEWED = "case_viewed"
    CASE_UPDATED = "case_updated"
    CASE_DELETED = "case_deleted"
    CASE_REANALYZED = "case_reanalyzed"
    CASE_REPORT_SENT = "case_report_sent"

    # Config actions
    CONFIG_VIEWED = "config_viewed"
    CONFIG_UPDATED = "config_updated"

    # Role actions
    ROLE_CREATED = "role_created"
    ROLE_UPDATED = "role_updated"
    ROLE_DELETED = "role_deleted"

    # Auth failures
    AUTH_FAILED = "auth_failed"
    PERMISSION_DENIED = "permission_denied"


class ResourceType:
    """Resource type constants for audit logging."""

    USER = "user"
    CASE = "case"
    CONFIG = "config"
    ROLE = "role"
    AUDIT_LOG = "audit_log"
