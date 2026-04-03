"""Role management API endpoints (admin only)."""

from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth import log_audit_action, AuditAction, ResourceType
from app.database import get_db
from app.models import User, Role
from app.schemas_auth import RoleResponse, RoleCreate, RoleUpdate
from app.permissions import RoleName
from app.utils.timezone import now_utc

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=List[RoleResponse])
async def list_roles(
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """List all roles (admin only)."""
    result = await db.execute(select(Role).order_by(Role.name))
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


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Create a new custom role (admin only)."""
    # Check if role name already exists
    existing = await db.execute(select(Role).where(Role.name == role_data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Role name already exists")

    new_role = Role(
        name=role_data.name,
        description=role_data.description,
        permissions=role_data.permissions,
        created_at=now_utc(),
    )
    db.add(new_role)
    await db.commit()

    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.ROLE_CREATED,
        resource_type=ResourceType.ROLE,
        resource_id=new_role.id,
        details={"name": new_role.name, "permissions": new_role.permissions},
    )

    return RoleResponse(
        id=new_role.id,
        name=new_role.name,
        description=new_role.description,
        permissions=new_role.permissions,
        created_at=new_role.created_at,
    )


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    updates: RoleUpdate,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Update role description and permissions (admin only)."""
    role = await db.get(Role, str(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if updates.description is not None:
        role.description = updates.description
    if updates.permissions is not None:
        role.permissions = updates.permissions

    await db.commit()

    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.ROLE_UPDATED,
        resource_type=ResourceType.ROLE,
        resource_id=str(role_id),
        details={"name": role.name, "permissions": role.permissions},
    )

    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        created_at=role.created_at,
    )


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    current_user: Annotated[User, Depends(require_admin)],
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom role (admin only). Cannot delete default roles."""
    role = await db.get(Role, str(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Prevent deleting default roles
    if role.name in [r.value for r in RoleName]:
        raise HTTPException(status_code=400, detail="Cannot delete default system roles")

    await db.delete(role)
    await db.commit()

    await log_audit_action(
        db,
        user_id=current_user.id,
        action=AuditAction.ROLE_DELETED,
        resource_type=ResourceType.ROLE,
        resource_id=str(role_id),
        details={"name": role.name},
    )
