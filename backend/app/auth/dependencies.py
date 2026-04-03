"""FastAPI dependencies for authentication and authorization."""

from typing import Annotated, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.auth.security import decode_access_token, validate_session
from app.database import get_db, get_db_context
from app.models import User, Role
from app.permissions import Permission, has_permission


# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user from JWT token.

    This function validates:
    1. JWT token signature and expiration
    2. Session exists in database and is active
    3. Token hash matches the session
    4. Session has not expired

    Args:
        credentials: HTTP Bearer credentials
        db: Database session

    Returns:
        Current authenticated user

    Raises:
        HTTPException: If token is invalid, session not found/inactive, or user not found
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        session_id: str = payload.get("session_id")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate session if token contains session_id
    # (Legacy tokens without session_id are still accepted for backward compatibility)
    if session_id:
        session_valid = await validate_session(db, token, session_id, user_id)
        if not session_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session invalid or expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Get user from database with role preloaded (optimization)
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get the current active user.

    Args:
        current_user: Current authenticated user

    Returns:
        Current active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_user_permissions(current_user: Annotated[User, Depends(get_current_active_user)]) -> List[str]:
    """Get the list of permissions for the current user.

    Args:
        current_user: Current authenticated user

    Returns:
        List of permission strings
    """
    from app.permissions import get_role_permissions

    # In a full implementation, we would fetch the role name from the database
    # For now, we'll get it from the user's role
    from app.database import get_db, get_db_context

    async with get_db_context() as db:
        result = await db.execute(select(Role).where(Role.id == current_user.role_id))
        role = result.scalar_one_or_none()

        if role:
            return get_role_permissions(role.name)

    return []


class PermissionChecker:
    """Dependency class for checking user permissions."""

    def __init__(self, required_permission: str):
        """Initialize with the required permission.

        Args:
            required_permission: Permission string required
        """
        self.required_permission = required_permission

    async def __call__(
        self,
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: AsyncSession = Depends(get_db),
    ) -> User:
        """Check if user has the required permission.

        Args:
            current_user: Current authenticated user
            db: Database session

        Returns:
            The user if permission check passes

        Raises:
            HTTPException: If user lacks required permission
        """
        # Get user's role
        result = await db.execute(select(Role).where(Role.id == current_user.role_id))
        role = result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no role assigned",
            )

        from app.permissions import get_role_permissions

        user_permissions = get_role_permissions(role.name)

        if not has_permission(user_permissions, self.required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {self.required_permission} required",
            )

        return current_user


# Convenience functions for common permission checks
RequireCaseViewAny = Annotated[User, Depends(PermissionChecker(Permission.CASE_VIEW_ANY))]
RequireCaseCreate = Annotated[User, Depends(PermissionChecker(Permission.CASE_CREATE))]
RequireCaseUpdate = Annotated[User, Depends(PermissionChecker(Permission.CASE_UPDATE))]
RequireCaseDelete = Annotated[User, Depends(PermissionChecker(Permission.CASE_DELETE))]
RequireCaseSendReport = Annotated[User, Depends(PermissionChecker(Permission.CASE_SEND_REPORT))]
RequireUserViewAny = Annotated[User, Depends(PermissionChecker(Permission.USER_VIEW_ANY))]
RequireUserCreate = Annotated[User, Depends(PermissionChecker(Permission.USER_CREATE))]
RequireUserUpdate = Annotated[User, Depends(PermissionChecker(Permission.USER_UPDATE))]
RequireUserDelete = Annotated[User, Depends(PermissionChecker(Permission.USER_DELETE))]
RequireConfigView = Annotated[User, Depends(PermissionChecker(Permission.CONFIG_VIEW))]
RequireConfigUpdate = Annotated[User, Depends(PermissionChecker(Permission.CONFIG_UPDATE))]
RequireAuditView = Annotated[User, Depends(PermissionChecker(Permission.AUDIT_VIEW))]
RequireEvidenceView = Annotated[User, Depends(PermissionChecker(Permission.EVIDENCE_VIEW))]
RequireEvidenceCreate = Annotated[User, Depends(PermissionChecker(Permission.EVIDENCE_CREATE))]
RequireEvidenceDelete = Annotated[User, Depends(PermissionChecker(Permission.EVIDENCE_DELETE))]
RequireStatsView = Annotated[User, Depends(PermissionChecker(Permission.STATS_VIEW))]
RequireStatsExport = Annotated[User, Depends(PermissionChecker(Permission.STATS_EXPORT))]


def require_permission(required_permission: str) -> PermissionChecker:
    """Create a dependency that requires a specific permission.

    Args:
        required_permission: Permission string required

    Returns:
        PermissionChecker instance for use with FastAPI Depends()
    """
    return PermissionChecker(required_permission)


async def require_admin(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """Check if user is an admin.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        The user if admin

    Raises:
        HTTPException: If user is not an admin
    """
    result = await db.execute(select(Role).where(Role.id == current_user.role_id))
    role = result.scalar_one_or_none()

    if not role or role.name != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user


# Type alias for current user
CurrentUser = Annotated[User, Depends(get_current_active_user)]


async def get_current_user_sse(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user from JWT token for SSE connections.

    This function is designed for Server-Sent Events (SSE) endpoints where
    the EventSource API cannot send custom headers. It falls back to checking
    for the token in a query parameter.

    Validation order:
    1. Bearer token in Authorization header (standard auth)
    2. Token query parameter (for SSE connections with EventSource)

    Args:
        request: FastAPI Request object
        db: Database session

    Returns:
        Current authenticated user

    Raises:
        HTTPException: If token is invalid, session not found/inactive, or user not found
    """
    token = None

    # Try Bearer header first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    # Fallback to query parameter for SSE (EventSource cannot send custom headers)
    if not token:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        session_id: str = payload.get("session_id")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate session if token contains session_id
    # (Legacy tokens without session_id are still accepted for backward compatibility)
    if session_id:
        session_valid = await validate_session(db, token, session_id, user_id)
        if not session_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session invalid or expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Get user from database with role preloaded (optimization)
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user_sse(
    current_user: Annotated[User, Depends(get_current_user_sse)],
) -> User:
    """Get the current active user for SSE connections.

    Combines get_current_user_sse with active user check.

    Args:
        current_user: Current authenticated user from SSE-compatible auth

    Returns:
        Current active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user
