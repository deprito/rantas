"""User management API endpoints (admin only)."""

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    get_current_active_user,
    hash_password,
    log_audit_action,
    AuditAction,
    ResourceType,
)
from app.auth.dependencies import require_admin
from app.config import settings
from app.database import get_db, get_db_context
from app.models import User, Role
from app.permissions import get_role_permissions, RoleName, ROLE_DESCRIPTIONS
from app.schemas_auth import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserWithPermissions,
    UserListResponse,
    ResetPasswordRequest,
    MessageResponse,
    RoleResponse,
    RoleCreate,
    RoleUpdate,
)
from app.utils.timezone import now_utc

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    current_user: Annotated[User, Depends(require_admin)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all users with pagination and filtering (admin only).

    Args:
        current_user: Current authenticated user (must be admin)
        page: Page number
        page_size: Items per page
        search: Search by username or email
        is_active: Filter by active status
        db: Database session

    Returns:
        Paginated list of users
    """
    query = select(User)

    # Apply filters
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern),
            )
        )

    if is_active is not None:
        query = query.where(User.is_active == is_active)

    # Get total count
    from sqlalchemy import func

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    users = result.scalars().all()

    # Get roles for all users
    user_list = []
    for user in users:
        role_result = await db.execute(select(Role).where(Role.id == user.role_id))
        role = role_result.scalar_one_or_none()

        user_list.append(
            UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                is_active=user.is_active,
                role=RoleResponse(
                    id=role.id if role else uuid4(),
                    name=role.name if role else "UNKNOWN",
                    description=role.description if role else "",
                    permissions=role.permissions if role else {},
                    created_at=role.created_at if role else now_utc(),
                ),
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_login_at=user.last_login_at,
            )
        )

    return UserListResponse(
        users=user_list,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{user_id}", response_model=UserWithPermissions)
async def get_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific user (admin only).

    Args:
        user_id: User UUID
        current_user: Current authenticated user (must be admin)
        db: Database session

    Returns:
        User details with permissions
    """
    user = await db.get(User, str(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get user's role
    role_result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = role_result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User has no role assigned",
        )

    # Get user permissions
    permissions = get_role_permissions(role.name)

    return UserWithPermissions(
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
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Create a new user (admin only).

    Args:
        user_data: User creation data
        current_user: Current authenticated user (must be admin)
        db: Database session

    Returns:
        Created user

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

    # Verify role exists (convert UUID to string for DB comparison)
    role_result = await db.execute(select(Role).where(Role.id == str(user_data.role_id)))
    role = role_result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role ID",
        )

    # Create user
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

    # Log user creation
    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_CREATED,
        resource_type=ResourceType.USER,
        resource_id=str(new_user.id),
        details={
            "username": new_user.username,
            "email": new_user.email,
            "role": role.name,
        },
    )
    await db.commit()

    return UserResponse(
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
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    updates: UserUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Update a user (admin only).

    Args:
        user_id: User UUID
        updates: Update data
        current_user: Current authenticated user (must be admin)
        db: Database session

    Returns:
        Updated user

    Raises:
        HTTPException: If user not found
    """
    user = await db.get(User, str(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent self-deactivation
    if user.id == current_user.id and updates.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    # Track changes for audit log
    changes = {}

    # Apply updates
    if updates.email is not None:
        user.email = updates.email
        changes["email"] = updates.email

    if updates.is_active is not None:
        user.is_active = updates.is_active
        changes["is_active"] = updates.is_active

    if updates.role_id is not None:
        # Verify role exists (convert UUID to string for DB comparison)
        role_result = await db.execute(select(Role).where(Role.id == str(updates.role_id)))
        role = role_result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role ID",
            )

        user.role_id = str(updates.role_id)
        changes["role"] = role.name

    user.updated_at = now_utc()

    # Get role for response
    role_result = await db.execute(select(Role).where(Role.id == user.role_id))
    role = role_result.scalar_one_or_none()

    # Log update
    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_UPDATED,
        resource_type=ResourceType.USER,
        resource_id=str(user.id),
        details={"target_user": user.username, "changes": changes},
    )
    await db.commit()

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        role=RoleResponse(
            id=role.id if role else uuid4(),
            name=role.name if role else "UNKNOWN",
            description=role.description if role else "",
            permissions=role.permissions if role else {},
            created_at=role.created_at if role else now_utc(),
        ),
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login_at=user.last_login_at,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Delete a user (admin only).

    Args:
        user_id: User UUID
        current_user: Current authenticated user (must be admin)
        db: Database session

    Raises:
        HTTPException: If user not found or trying to delete self
    """
    user = await db.get(User, str(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    # Log deletion
    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_DELETED,
        resource_type=ResourceType.USER,
        resource_id=str(user.id),
        details={"username": user.username, "email": user.email},
    )

    await db.delete(user)
    await db.commit()


@router.post("/{user_id}/reset-password", response_model=MessageResponse)
async def reset_user_password(
    user_id: UUID,
    password_data: ResetPasswordRequest,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's password (admin only).

    Args:
        user_id: User UUID
        password_data: New password
        current_user: Current authenticated user (must be admin)
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If user not found
    """
    user = await db.get(User, str(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update password
    user.hashed_password = hash_password(password_data.new_password)
    user.updated_at = now_utc()

    # Log password reset
    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_PASSWORD_RESET,
        resource_type=ResourceType.USER,
        resource_id=str(user.id),
        details={"target_user": user.username},
    )
    await db.commit()

    return MessageResponse(message=f"Password reset for user {user.username}")


@router.get("/roles/list", response_model=list[RoleResponse])
async def list_roles(
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """List all available roles (admin only).

    Args:
        current_user: Current authenticated user (must be admin)
        db: Database session

    Returns:
        List of roles
    """
    result = await db.execute(select(Role))
    roles = result.scalars().all()

    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            permissions=role.permissions,
            created_at=role.created_at,
        )
        for role in roles
    ]


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific role (admin only)."""
    role = await db.get(Role, str(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        created_at=role.created_at,
    )


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    updates: RoleUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Update a role's permissions or description (admin only)."""
    role = await db.get(Role, str(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    changes = {}
    if updates.description is not None:
        role.description = updates.description
        changes["description"] = updates.description

    if updates.permissions is not None:
        role.permissions = updates.permissions
        changes["permissions"] = updates.permissions

    role.updated_at = now_utc()

    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_UPDATED,
        resource_type=ResourceType.USER,
        resource_id=str(role_id),
        details={"role": role.name, "changes": changes},
    )
    await db.commit()

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        created_at=role.created_at,
    )


@router.post("/roles", response_model=RoleResponse, status_code=201)
async def create_role(
    role_data: RoleCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Create a new role (admin only)."""
    # Check if role name already exists
    existing = await db.execute(
        select(Role).where(Role.name == role_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Role name already exists")

    new_role = Role(
        id=str(uuid4()),
        name=role_data.name,
        description=role_data.description,
        permissions=role_data.permissions,
        created_at=now_utc(),
    )

    db.add(new_role)
    await db.flush()

    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_CREATED,
        resource_type=ResourceType.USER,
        resource_id=str(new_role.id),
        details={"role": new_role.name},
    )
    await db.commit()

    return RoleResponse(
        id=new_role.id,
        name=new_role.name,
        description=new_role.description,
        permissions=new_role.permissions,
        created_at=new_role.created_at,
    )


@router.delete("/roles/{role_id}", status_code=204)
async def delete_role(
    role_id: UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Delete a role (admin only)."""
    role = await db.get(Role, str(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Check if any users have this role
    users_with_role = await db.execute(
        select(User).where(User.role_id == str(role_id))
    )
    if users_with_role.scalars().first():
        raise HTTPException(
            status_code=400,
            detail="Cannot delete role: users are still assigned to it",
        )

    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.USER_DELETED,
        resource_type=ResourceType.USER,
        resource_id=str(role_id),
        details={"role": role.name},
    )

    await db.delete(role)
    await db.commit()
