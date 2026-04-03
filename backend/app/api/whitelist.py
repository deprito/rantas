"""Whitelist management API endpoints.

Provides endpoints for managing domain whitelist entries.
This allows overriding blacklist filters for trusted domains.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, require_admin
from app.auth import log_audit_action, AuditAction, ResourceType
from app.database import get_db
from app.models import User, WhitelistEntry

router = APIRouter(prefix="/whitelist", tags=["whitelist"])


# ==================== Schemas ====================

class WhitelistEntryCreate(BaseModel):
    """Request schema for creating a whitelist entry."""
    domain: str = Field(..., min_length=1, max_length=500)
    reason: Optional[str] = Field(None, max_length=500)


class WhitelistEntryResponse(BaseModel):
    """Response schema for a whitelist entry."""
    id: str
    domain: str
    reason: Optional[str]
    added_at: str
    added_by: Optional[str]


class WhitelistListResponse(BaseModel):
    """Response schema for whitelist list."""
    entries: list[WhitelistEntryResponse]
    total: int


# ==================== Endpoints ====================

@router.get("", response_model=WhitelistListResponse)
async def get_whitelist(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get whitelist entries (authenticated users).

    Returns all domains that have been whitelisted and will not be flagged.
    """
    result = await db.execute(select(WhitelistEntry).order_by(WhitelistEntry.added_at.desc()))
    entries = result.scalars().all()

    return WhitelistListResponse(
        entries=[
            WhitelistEntryResponse(
                id=str(entry.id),
                domain=entry.domain,
                reason=entry.reason,
                added_at=entry.added_at.isoformat(),
                added_by=str(entry.added_by) if entry.added_by else None,
            )
            for entry in entries
        ],
        total=len(entries),
    )


@router.post("", response_model=WhitelistEntryResponse, status_code=status.HTTP_201_CREATED)
async def add_to_whitelist(
    data: WhitelistEntryCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Add a domain to the whitelist (admin only).

    Whitelisted domains will never be flagged as suspicious, even if they
    appear in blacklist sources.
    """
    # Check if domain is already whitelisted
    existing = await db.execute(
        select(WhitelistEntry).where(WhitelistEntry.domain == data.domain)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Domain is already whitelisted",
        )

    entry = WhitelistEntry(
        domain=data.domain,
        reason=data.reason,
        added_by=current_user.id,
    )
    db.add(entry)
    await db.commit()

    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.CONFIG_UPDATED,
        resource_type=ResourceType.CONFIG,
        resource_id=str(entry.id),
        details={"action": "whitelist_added", "domain": data.domain},
    )

    await db.refresh(entry)

    return WhitelistEntryResponse(
        id=str(entry.id),
        domain=entry.domain,
        reason=entry.reason,
        added_at=entry.added_at.isoformat(),
        added_by=str(entry.added_by) if entry.added_by else None,
    )


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_whitelist(
    entry_id: str,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Remove a domain from the whitelist (admin only).

    Args:
        entry_id: ID of the whitelist entry to remove
    """
    entry = await db.get(WhitelistEntry, entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Whitelist entry not found",
        )

    domain = entry.domain
    await db.delete(entry)
    await db.commit()

    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.CONFIG_UPDATED,
        resource_type=ResourceType.CONFIG,
        resource_id=entry_id,
        details={"action": "whitelist_removed", "domain": domain},
    )
