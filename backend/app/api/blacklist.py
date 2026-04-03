"""Blacklist management API endpoints.

Provides endpoints for managing domain blacklist sources and whitelist entries.
This allows filtering of suspicious URLs against known threat intelligence sources.
"""
import re
from datetime import datetime
from typing import Annotated, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, or_, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, require_admin
from app.config import settings
from app.database import get_db
from app.models import (
    BlacklistSource,
    BlacklistDomain,
    WhitelistEntry,
    User,
)
from app.permissions import Permission, has_permission
from app.utils.timezone import now_utc


router = APIRouter(prefix="/blacklist", tags=["blacklist"])


# ==================== Helper Functions ====================


async def check_permission(user: User, permission: str, db: AsyncSession) -> None:
    """Check if user has a specific permission.

    Args:
        user: User to check
        permission: Permission string required
        db: Database session

    Raises:
        HTTPException: If user lacks permission
    """
    from app.permissions import get_role_permissions
    from app.models import Role
    from sqlalchemy import select

    # Admin users have all permissions
    result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = result.scalar_one_or_none()

    if role and role.name == "ADMIN":
        return

    user_permissions = get_role_permissions(role.name) if role else []

    if not has_permission(user_permissions, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission} required",
        )


def extract_domain_from_url(url: str) -> Optional[str]:
    """Extract domain from URL.

    Args:
        url: URL string to parse

    Returns:
        Domain string or None if invalid URL
    """
    try:
        parsed = urlparse(url)
        if parsed.netloc:
            return parsed.netloc.lower()
        return None
    except Exception:
        return None


async def check_if_whitelisted(db: AsyncSession, domain: str) -> bool:
    """Check if a domain is whitelisted.

    Args:
        db: Database session
        domain: Domain to check

    Returns:
        True if domain or any parent domain is whitelisted
    """
    # Exact match first
    result = await db.execute(
        select(WhitelistEntry).where(WhitelistEntry.domain == domain)
    )
    if result.scalar_one_or_none():
        return True

    # Check parent domains (e.g., subdomain.example.com -> example.com)
    parts = domain.split(".")
    for i in range(1, len(parts) - 1):
        parent_domain = ".".join(parts[i:])
        result = await db.execute(
            select(WhitelistEntry).where(WhitelistEntry.domain == parent_domain)
        )
        if result.scalar_one_or_none():
            return True

    return False


async def check_if_blacklisted(
    db: AsyncSession, domain: str
) -> tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """Check if a domain is blacklisted.

    Args:
        db: Database session
        domain: Domain to check

    Returns:
        Tuple of (is_blacklisted, matched_domain, source_name, threat_category)
    """
    # Check exact match
    result = await db.execute(
        select(BlacklistDomain, BlacklistSource)
        .join(BlacklistSource, BlacklistDomain.source_id == BlacklistSource.id, isouter=True)
        .where(
            BlacklistDomain.domain == domain,
            BlacklistDomain.is_active == True,
        )
    )
    row = result.first()
    if row:
        blacklist_domain, source = row
        return (
            True,
            blacklist_domain.domain,
            source.name if source else "Manual",
            blacklist_domain.threat_category,
        )

    # Check wildcard matches (e.g., *.example.com matches subdomain.example.com)
    result = await db.execute(
        select(BlacklistDomain, BlacklistSource)
        .join(BlacklistSource, BlacklistDomain.source_id == BlacklistSource.id, isouter=True)
        .where(
            BlacklistDomain.is_wildcard == True,
            BlacklistDomain.is_active == True,
        )
    )
    for row in result.all():
        blacklist_domain, source = row
        # Remove leading *. from wildcard domain
        wildcard_domain = blacklist_domain.domain.replace("*.", "")
        if domain == wildcard_domain or domain.endswith(f".{wildcard_domain}"):
            return (
                True,
                blacklist_domain.domain,
                source.name if source else "Manual",
                blacklist_domain.threat_category,
            )

    return False, None, None, None


# ==================== Request/Response Schemas ====================


class BlacklistSourceCreate(BaseModel):
    """Request schema for creating a blacklist source."""

    name: str = Field(..., min_length=1, max_length=255)
    source_type: str = Field("remote", pattern="^(local|remote|manual)$")
    url: Optional[str] = None
    file_path: Optional[str] = None
    threat_category: Optional[str] = Field(None, max_length=100)
    sync_interval_hours: int = Field(24, ge=1, le=168)
    is_active: bool = True


class BlacklistSourceUpdate(BaseModel):
    """Request schema for updating a blacklist source."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_active: Optional[bool] = None
    sync_interval_hours: Optional[int] = Field(None, ge=1, le=168)
    threat_category: Optional[str] = Field(None, max_length=100)
    url: Optional[str] = None
    file_path: Optional[str] = None


class BlacklistSourceResponse(BaseModel):
    """Response schema for a blacklist source."""

    id: str
    name: str
    source_type: str
    url: Optional[str]
    file_path: Optional[str]
    threat_category: Optional[str]
    sync_interval_hours: int
    is_active: bool
    last_synced_at: Optional[str]
    entry_count: int
    created_at: str
    updated_at: str
    created_by: Optional[str]


class WhitelistEntryCreate(BaseModel):
    """Request schema for creating a whitelist entry."""

    domain: str = Field(..., min_length=1, max_length=500)
    reason: Optional[str] = Field(None, max_length=1000)


class WhitelistEntryResponse(BaseModel):
    """Response schema for a whitelist entry."""

    id: str
    domain: str
    reason: Optional[str]
    added_at: str
    added_by: Optional[str]


class BlacklistCheckResponse(BaseModel):
    """Response schema for blacklist check."""

    is_blacklisted: bool
    matched_domain: Optional[str] = None
    source_name: Optional[str] = None
    threat_category: Optional[str] = None
    is_whitelisted: bool


class WhitelistListResponse(BaseModel):
    """Response schema for whitelist list."""

    entries: list[WhitelistEntryResponse]
    total: int


# ==================== Helper Functions ====================


def extract_domain_from_url(url: str) -> Optional[str]:
    """Extract domain from URL.

    Args:
        url: URL string to parse

    Returns:
        Domain string or None if invalid URL
    """
    try:
        parsed = urlparse(url)
        if parsed.netloc:
            return parsed.netloc.lower()
        return None
    except Exception:
        return None


async def check_if_whitelisted(db: AsyncSession, domain: str) -> bool:
    """Check if a domain is whitelisted.

    Args:
        db: Database session
        domain: Domain to check

    Returns:
        True if domain or any parent domain is whitelisted
    """
    # Exact match first
    result = await db.execute(
        select(WhitelistEntry).where(WhitelistEntry.domain == domain)
    )
    if result.scalar_one_or_none():
        return True

    # Check parent domains (e.g., subdomain.example.com -> example.com)
    parts = domain.split(".")
    for i in range(1, len(parts) - 1):
        parent_domain = ".".join(parts[i:])
        result = await db.execute(
            select(WhitelistEntry).where(WhitelistEntry.domain == parent_domain)
        )
        if result.scalar_one_or_none():
            return True

    return False


async def check_if_blacklisted(
    db: AsyncSession, domain: str
) -> tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """Check if a domain is blacklisted.

    Args:
        db: Database session
        domain: Domain to check

    Returns:
        Tuple of (is_blacklisted, matched_domain, source_name, threat_category)
    """
    # Check exact match
    result = await db.execute(
        select(BlacklistDomain, BlacklistSource)
        .join(BlacklistSource, BlacklistDomain.source_id == BlacklistSource.id, isouter=True)
        .where(
            BlacklistDomain.domain == domain,
            BlacklistDomain.is_active == True,
        )
    )
    row = result.first()
    if row:
        blacklist_domain, source = row
        return (
            True,
            blacklist_domain.domain,
            source.name if source else "Manual",
            blacklist_domain.threat_category,
        )

    # Check wildcard matches (e.g., *.example.com matches subdomain.example.com)
    result = await db.execute(
        select(BlacklistDomain, BlacklistSource)
        .join(BlacklistSource, BlacklistDomain.source_id == BlacklistSource.id, isouter=True)
        .where(
            BlacklistDomain.is_wildcard == True,
            BlacklistDomain.is_active == True,
        )
    )
    for row in result.all():
        blacklist_domain, source = row
        # Remove leading *. from wildcard domain
        wildcard_domain = blacklist_domain.domain.replace("*.", "")
        if domain == wildcard_domain or domain.endswith(f".{wildcard_domain}"):
            return (
                True,
                blacklist_domain.domain,
                source.name if source else "Manual",
                blacklist_domain.threat_category,
            )

    return False, None, None, None


# ==================== Blacklist Source Endpoints ====================


@router.get("/sources", response_model=list[BlacklistSourceResponse])
async def get_blacklist_sources(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get all blacklist sources (authenticated users).

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of blacklist sources
    """
    await check_permission(current_user, Permission.BLACKLIST_VIEW, db)

    result = await db.execute(
        select(BlacklistSource).order_by(BlacklistSource.created_at.desc())
    )
    sources = result.scalars().all()

    return [
        BlacklistSourceResponse(
            id=str(source.id),
            name=source.name,
            source_type=source.source_type,
            url=source.url,
            file_path=source.file_path,
            threat_category=source.threat_category,
            sync_interval_hours=source.sync_interval_hours,
            is_active=source.is_active,
            last_synced_at=source.last_synced_at.isoformat() if source.last_synced_at else None,
            entry_count=source.entry_count,
            created_at=source.created_at.isoformat() if source.created_at else None,
            updated_at=source.updated_at.isoformat() if source.updated_at else None,
            created_by=str(source.created_by) if source.created_by else None,
        )
        for source in sources
    ]


@router.get("/sources/{source_id}", response_model=BlacklistSourceResponse)
async def get_blacklist_source(
    source_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get a specific blacklist source (authenticated users).

    Args:
        source_id: ID of the blacklist source
        current_user: Current authenticated user
        db: Database session

    Returns:
        Blacklist source details

    Raises:
        HTTPException: If source not found
    """
    await check_permission(current_user, Permission.BLACKLIST_VIEW, db)

    source = await db.get(BlacklistSource, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blacklist source not found",
        )

    return BlacklistSourceResponse(
        id=str(source.id),
        name=source.name,
        source_type=source.source_type,
        url=source.url,
        file_path=source.file_path,
        threat_category=source.threat_category,
        sync_interval_hours=source.sync_interval_hours,
        is_active=source.is_active,
        last_synced_at=source.last_synced_at.isoformat() if source.last_synced_at else None,
        entry_count=source.entry_count,
        created_at=source.created_at.isoformat() if source.created_at else None,
        updated_at=source.updated_at.isoformat() if source.updated_at else None,
        created_by=str(source.created_by) if source.created_by else None,
    )


@router.post("/sources", response_model=BlacklistSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_blacklist_source(
    data: BlacklistSourceCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Create a new blacklist source (admin only).

    Args:
        data: Blacklist source creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created blacklist source
    """
    await check_permission(current_user, Permission.BLACKLIST_MANAGE, db)

    # Validate source-specific fields
    if data.source_type == "remote" and not data.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL is required for remote sources",
        )
    if data.source_type == "local" and not data.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File path is required for local sources",
        )

    source = BlacklistSource(
        name=data.name,
        source_type=data.source_type,
        url=data.url,
        file_path=data.file_path,
        threat_category=data.threat_category,
        sync_interval_hours=data.sync_interval_hours,
        is_active=data.is_active,
        created_by=str(current_user.id),
    )

    db.add(source)
    await db.commit()
    await db.refresh(source)

    return BlacklistSourceResponse(
        id=str(source.id),
        name=source.name,
        source_type=source.source_type,
        url=source.url,
        file_path=source.file_path,
        threat_category=source.threat_category,
        sync_interval_hours=source.sync_interval_hours,
        is_active=source.is_active,
        last_synced_at=source.last_synced_at.isoformat() if source.last_synced_at else None,
        entry_count=source.entry_count,
        created_at=source.created_at.isoformat() if source.created_at else None,
        updated_at=source.updated_at.isoformat() if source.updated_at else None,
        created_by=str(source.created_by) if source.created_by else None,
    )


@router.put("/sources/{source_id}", response_model=BlacklistSourceResponse)
async def update_blacklist_source(
    source_id: str,
    data: BlacklistSourceUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Update a blacklist source (admin only).

    Args:
        source_id: ID of the blacklist source
        data: Update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated blacklist source

    Raises:
        HTTPException: If source not found
    """
    await check_permission(current_user, Permission.BLACKLIST_MANAGE, db)

    source = await db.get(BlacklistSource, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blacklist source not found",
        )

    # Update fields
    if data.name is not None:
        source.name = data.name
    if data.is_active is not None:
        source.is_active = data.is_active
    if data.sync_interval_hours is not None:
        source.sync_interval_hours = data.sync_interval_hours
    if data.threat_category is not None:
        source.threat_category = data.threat_category
    if data.url is not None:
        source.url = data.url
    if data.file_path is not None:
        source.file_path = data.file_path

    source.updated_at = now_utc()

    await db.commit()
    await db.refresh(source)

    return BlacklistSourceResponse(
        id=str(source.id),
        name=source.name,
        source_type=source.source_type,
        url=source.url,
        file_path=source.file_path,
        threat_category=source.threat_category,
        sync_interval_hours=source.sync_interval_hours,
        is_active=source.is_active,
        last_synced_at=source.last_synced_at.isoformat() if source.last_synced_at else None,
        entry_count=source.entry_count,
        created_at=source.created_at.isoformat() if source.created_at else None,
        updated_at=source.updated_at.isoformat() if source.updated_at else None,
        created_by=str(source.created_by) if source.created_by else None,
    )


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blacklist_source(
    source_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Delete a blacklist source (admin only).

    Args:
        source_id: ID of the blacklist source
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If source not found
    """
    await check_permission(current_user, Permission.BLACKLIST_MANAGE, db)

    source = await db.get(BlacklistSource, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blacklist source not found",
        )

    await db.delete(source)
    await db.commit()


@router.post("/sources/{source_id}/sync")
async def sync_blacklist_source(
    source_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Trigger manual sync for a blacklist source (admin only).

    Args:
        source_id: ID of the blacklist source
        current_user: Current authenticated user
        db: Database session

    Returns:
        Sync result
    """
    await check_permission(current_user, Permission.BLACKLIST_MANAGE, db)

    source = await db.get(BlacklistSource, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blacklist source not found",
        )

    # TODO: Implement actual sync logic
    # For now, just update the last_synced_at timestamp
    source.last_synced_at = now_utc()
    await db.commit()

    return {
        "success": True,
        "message": f"Sync triggered for source: {source.name}",
    }


# ==================== Blacklist Domain Endpoints ====================


@router.post("/domains")
async def add_blacklist_domain(
    domain: str = Query(..., min_length=1, max_length=500),
    threat_category: Optional[str] = Query(None, max_length=100),
    is_wildcard: bool = Query(False),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Add a domain to the blacklist manually.

    Args:
        domain: Domain to add
        threat_category: Optional threat category
        is_wildcard: Whether this is a wildcard domain (*.domain.com)
        request: FastAPI request (for getting auth token if provided)
        db: Database session

    Returns:
        Blacklist check result
    """
    # Try to get current user from token (optional)
    current_user = None
    if request:
        try:
            from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
            from app.auth.security import decode_access_token

            security = HTTPBearer(auto_error=False)
            credentials: HTTPAuthorizationCredentials = await security(request)
            if credentials:
                token = credentials.credentials
                payload = decode_access_token(token)
                user_id: str = payload.get("sub")
                if user_id:
                    from sqlalchemy import select
                    result = await db.execute(select(User).where(User.id == user_id))
                    current_user = result.scalar_one_or_none()
        except Exception:
            pass

    # Check if already exists
    result = await db.execute(
        select(BlacklistDomain).where(
            BlacklistDomain.domain == domain,
            BlacklistDomain.is_wildcard == is_wildcard,
        )
    )
    existing = result.scalar_one_or_none()

    if not existing:
        blacklist_domain = BlacklistDomain(
            domain=domain,
            is_wildcard=is_wildcard,
            threat_category=threat_category,
            source_id=None,  # Manual entry
            created_by=str(current_user.id) if current_user else None,
        )
        db.add(blacklist_domain)
        await db.commit()

    # Return check result
    return BlacklistCheckResponse(
        is_blacklisted=True,
        matched_domain=domain,
        source_name="Manual",
        threat_category=threat_category,
        is_whitelisted=False,
    )


@router.delete("/domains/{domain}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_blacklist_domain(
    domain: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Remove a domain from the blacklist (admin only).

    Args:
        domain: Domain to remove
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If user lacks permission
    """
    await check_permission(current_user, Permission.BLACKLIST_MANAGE, db)

    await db.execute(
        sql_delete(BlacklistDomain).where(BlacklistDomain.domain == domain)
    )
    await db.commit()


@router.get("/check", response_model=BlacklistCheckResponse)
async def check_blacklist(
    url: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """Check if a URL is blacklisted (public endpoint).

    Args:
        url: URL to check
        db: Database session

    Returns:
        Blacklist check result
    """
    domain = extract_domain_from_url(url)
    if not domain:
        return BlacklistCheckResponse(
            is_blacklisted=False,
            is_whitelisted=False,
        )

    # Check whitelist first (whitelist overrides blacklist)
    is_whitelisted = await check_if_whitelisted(db, domain)

    # Check blacklist
    is_blacklisted, matched_domain, source_name, threat_category = await check_if_blacklisted(db, domain)

    return BlacklistCheckResponse(
        is_blacklisted=is_blacklisted and not is_whitelisted,
        matched_domain=matched_domain,
        source_name=source_name,
        threat_category=threat_category,
        is_whitelisted=is_whitelisted,
    )


# ==================== Whitelist Endpoints ====================


@router.get("/whitelist", response_model=WhitelistListResponse)
async def get_whitelist(
    current_user: Annotated[User, Depends(get_current_active_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get whitelist entries (authenticated users).

    Args:
        current_user: Current authenticated user
        page: Page number
        page_size: Items per page
        search: Optional search term for domains
        db: Database session

    Returns:
        Paginated list of whitelist entries
    """
    await check_permission(current_user, Permission.BLACKLIST_VIEW, db)

    query = select(WhitelistEntry)

    if search:
        query = query.where(WhitelistEntry.domain.ilike(f"%{search}%"))

    # Get total count
    from sqlalchemy import func
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.order_by(WhitelistEntry.added_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    entries = result.scalars().all()

    return WhitelistListResponse(
        entries=[
            WhitelistEntryResponse(
                id=str(entry.id),
                domain=entry.domain,
                reason=entry.reason,
                added_at=entry.added_at.isoformat() if entry.added_at else None,
                added_by=str(entry.added_by) if entry.added_by else None,
            )
            for entry in entries
        ],
        total=total,
    )


@router.post("/whitelist", response_model=WhitelistEntryResponse, status_code=status.HTTP_201_CREATED)
async def add_to_whitelist(
    data: WhitelistEntryCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Add a domain to the whitelist (admin only).

    Args:
        data: Whitelist entry creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created whitelist entry
    """
    await check_permission(current_user, Permission.BLACKLIST_MANAGE, db)

    # Check if already exists
    existing = await db.execute(
        select(WhitelistEntry).where(WhitelistEntry.domain == data.domain)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Domain is already whitelisted",
        )

    entry = WhitelistEntry(
        domain=data.domain.lower(),
        reason=data.reason,
        added_by=str(current_user.id),
    )

    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    return WhitelistEntryResponse(
        id=str(entry.id),
        domain=entry.domain,
        reason=entry.reason,
        added_at=entry.added_at.isoformat() if entry.added_at else None,
        added_by=str(entry.added_by) if entry.added_by else None,
    )


@router.delete("/whitelist/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_whitelist(
    entry_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Remove a domain from the whitelist (admin only).

    Args:
        entry_id: ID of the whitelist entry
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If entry not found or user lacks permission
    """
    await check_permission(current_user, Permission.BLACKLIST_MANAGE, db)

    entry = await db.get(WhitelistEntry, entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Whitelist entry not found",
        )

    await db.delete(entry)
    await db.commit()


__all__ = ["router"]
