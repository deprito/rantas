"""Authentication API endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    get_current_active_user,
    hash_password,
    verify_password,
    create_access_token,
    create_user_session,
    revoke_session,
    validate_session,
    log_audit_action,
    AuditAction,
    ResourceType,
    CurrentUser,
)
from app.auth.dependencies import PermissionChecker
from app.config import settings
from app.database import get_db, get_db_context
from app.models import User, Role
from app.permissions import get_role_permissions, RoleName, ROLE_DESCRIPTIONS
from app.schemas_auth import (
    LoginRequest,
    RegisterRequest,
    ChangePasswordRequest,
    TokenResponse,
    UserResponse,
    UserWithPermissions,
    MessageResponse,
    RoleResponse,
)
from app.utils.timezone import now_utc

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate a user and return a JWT token.

    This endpoint implements single active session per user:
    - Any existing active sessions for the user are revoked
    - A new session is created and tracked in the database

    Args:
        credentials: Login credentials (username, password)
        request: FastAPI request for IP address and user agent
        db: Database session

    Returns:
        Access token and user information

    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by username with role loaded in one query (optimization)
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(User.username == credentials.username)
    )
    user = result.scalar_one_or_none()

    # Verify password
    if not user or not verify_password(credentials.password, user.hashed_password):
        # Log failed attempt
        await log_audit_action(
            db,
            user_id=None,
            action=AuditAction.AUTH_FAILED,
            resource_type=ResourceType.USER,
            details={"username": credentials.username},
            ip_address=_get_client_ip(request),
        )
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Update last login
    user.last_login_at = now_utc()

    # Get user's role (already loaded via selectinload)
    role = user.role
    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User has no role assigned",
        )

    # Get user permissions
    permissions = get_role_permissions(role.name)

    # Generate session ID first
    from uuid import uuid4
    session_id = str(uuid4())

    # Create access token with session_id embedded
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username},
        session_id=session_id,
    )

    # Create user session (this revokes all existing sessions)
    # Pass the session_id to ensure it matches the token
    await create_user_session(
        db,
        user_id=str(user.id),
        token=access_token,
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
        session_id=session_id,
    )

    # Log successful login
    await log_audit_action(
        db,
        user_id=user.id,
        action=AuditAction.USER_LOGIN,
        resource_type=ResourceType.USER,
        resource_id=str(user.id),
        ip_address=_get_client_ip(request),
        details={"session_id": session_id},
    )
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        user=UserWithPermissions(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            role=RoleResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                permissions=role.permissions,
                created_at=role.created_at,
            ),
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
            permissions=permissions,
        ),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user.

    By default, new users get the REPORTER role. Admin can change this later.

    Args:
        user_data: Registration data
        request: FastAPI request for IP address and user agent
        db: Database session

    Returns:
        Access token and user information

    Raises:
        HTTPException: If username or email already exists
    """
    # Check if username exists
    existing = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    # Check if email exists
    existing = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    # Get default role (REPORTER)
    role_result = await db.execute(
        select(Role).where(Role.name == RoleName.REPORTER.value)
    )
    role = role_result.scalar_one_or_none()

    if not role:
        # Create default roles if they don't exist
        await _create_default_roles(db)
        role_result = await db.execute(
            select(Role).where(Role.name == RoleName.REPORTER.value)
        )
        role = role_result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default role not found",
        )

    # Create user
    from uuid import uuid4
    new_user = User(
        id=str(uuid4()),
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        is_active=True,
        role_id=role.id,
        created_at=now_utc(),
        updated_at=now_utc(),
    )

    db.add(new_user)
    await db.flush()

    # Get user permissions
    permissions = get_role_permissions(role.name)

    # Generate session ID first
    from uuid import uuid4
    session_id = str(uuid4())

    # Create access token with session_id embedded
    access_token = create_access_token(
        data={"sub": str(new_user.id), "username": new_user.username},
        session_id=session_id,
    )

    # Create user session (this revokes all existing sessions)
    # Pass the session_id to ensure it matches the token
    await create_user_session(
        db,
        user_id=str(new_user.id),
        token=access_token,
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
        session_id=session_id,
    )

    # Log user creation
    await log_audit_action(
        db,
        user_id=new_user.id,
        action=AuditAction.USER_CREATED,
        resource_type=ResourceType.USER,
        resource_id=str(new_user.id),
        details={"username": new_user.username, "email": new_user.email},
        ip_address=_get_client_ip(request),
    )
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        user=UserWithPermissions(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            is_active=new_user.is_active,
            role=RoleResponse(
                id=role.id,
                name=role.name,
                description=role.description,
                permissions=role.permissions,
                created_at=role.created_at,
            ),
            created_at=new_user.created_at,
            updated_at=new_user.updated_at,
            last_login_at=new_user.last_login_at,
            permissions=permissions,
        ),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: CurrentUser,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Logout a user and invalidate their session.

    The session is marked as inactive in the database, preventing
    further use of the token.

    Args:
        current_user: Current authenticated user
        request: FastAPI request for IP address
        db: Database session

    Returns:
        Success message
    """
    # Get session_id from token if available
    credentials = await _get_credentials(request)
    session_id = None
    if credentials:
        try:
            from app.auth.security import decode_access_token
            payload = decode_access_token(credentials)
            session_id = payload.get("session_id")
        except Exception:
            pass

    # Revoke the session if we have a session_id
    if session_id:
        await revoke_session(db, session_id)

    # Log logout action
    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_LOGOUT,
        resource_type=ResourceType.USER,
        resource_id=str(current_user.id),
        ip_address=_get_client_ip(request),
        details={"session_id": session_id},
    )
    await db.commit()

    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserWithPermissions)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Get information about the currently authenticated user.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Current user information with permissions
    """
    # Get user's role (already loaded if using selectinload in dependency)
    role = current_user.role if hasattr(current_user, 'role') else None
    if not role:
        # Fallback: fetch role if not loaded
        from sqlalchemy.orm import selectinload
        result = await db.execute(
            select(User)
            .options(selectinload(User.role))
            .where(User.id == current_user.id)
        )
        user_with_role = result.scalar_one_or_none()
        role = user_with_role.role if user_with_role else None

    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User has no role assigned",
        )

    # Get user permissions
    permissions = get_role_permissions(role.name)

    return UserWithPermissions(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        role=RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=role.permissions,
            created_at=role.created_at,
        ),
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_login_at=current_user.last_login_at,
        permissions=permissions,
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: CurrentUser,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Change the current user's password.

    Changing password also revokes all active sessions for security.
    The user will need to log in again.

    Args:
        password_data: Old and new password
        current_user: Current authenticated user
        request: FastAPI request for IP address
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If old password is incorrect
    """
    # Verify old password
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )

    # Update password
    current_user.hashed_password = hash_password(password_data.new_password)
    current_user.updated_at = now_utc()

    # Revoke all sessions for security (forces re-login)
    from app.auth import revoke_user_sessions
    await revoke_user_sessions(db, str(current_user.id))

    # Log password change
    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_PASSWORD_CHANGED,
        resource_type=ResourceType.USER,
        resource_id=str(current_user.id),
        ip_address=_get_client_ip(request),
    )
    await db.commit()

    return MessageResponse(message="Password changed successfully. Please log in again.")


def _get_client_ip(request: Request) -> str | None:
    """Get the client's IP address from the request.

    Args:
        request: FastAPI request

    Returns:
        Client IP address or None
    """
    # Check for forwarded IP (behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return None


def _get_user_agent(request: Request) -> str | None:
    """Get the client's user agent from the request.

    Args:
        request: FastAPI request

    Returns:
        User agent string or None
    """
    return request.headers.get("User-Agent")


async def _get_credentials(request: Request) -> str | None:
    """Get the authorization token from the request.

    Args:
        request: FastAPI request

    Returns:
        Bearer token string or None
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]  # Remove "Bearer " prefix
    return None


async def _create_default_roles(db: AsyncSession) -> None:
    """Create default roles if they don't exist.

    Args:
        db: Database session
    """
    from app.permissions import ROLE_PERMISSIONS, RoleName
    from uuid import uuid4

    for role_name, permissions in ROLE_PERMISSIONS.items():
        existing = await db.execute(
            select(Role).where(Role.name == role_name)
        )
        if not existing.scalar_one_or_none():
            role = Role(
                id=str(uuid4()),
                name=role_name,
                description=ROLE_DESCRIPTIONS.get(role_name, ""),
                permissions={"permissions": list(permissions)},
                created_at=now_utc(),
            )
            db.add(role)

    await db.flush()
