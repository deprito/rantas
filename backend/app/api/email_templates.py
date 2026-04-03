"""API endpoints for email template management."""
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    get_current_active_user,
    log_audit_action,
    AuditAction,
    ResourceType,
)
from app.auth.dependencies import PermissionChecker
from app.config import settings
from app.database import get_db, get_db_context
from app.models import EmailTemplate, User, Role
from app.permissions import Permission, get_role_permissions
from app.schemas_auth import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
    MessageResponse,
)
from app.utils.timezone import now_utc

router = APIRouter(prefix="/email-templates", tags=["email-templates"])


@router.get("", response_model=list[EmailTemplateResponse])
async def list_email_templates(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.EMAIL_TEMPLATE_VIEW))],
    db: AsyncSession = Depends(get_db),
) -> list[EmailTemplateResponse]:
    """List all email templates.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of email templates
    """
    try:
        result = await db.execute(select(EmailTemplate).order_by(EmailTemplate.is_default.desc(), EmailTemplate.name))
        templates = result.scalars().all()

        return [
            EmailTemplateResponse(
                id=t.id,
                name=t.name,
                subject=t.subject,
                body=t.body,
                html_body=t.html_body,
                cc=t.cc,
                is_default=t.is_default,
                prefer_xarf=getattr(t, 'prefer_xarf', False),
                xarf_reporter_ref_template=getattr(t, 'xarf_reporter_ref_template', None),
                created_by=t.created_by,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in templates
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list email templates: {str(e)}",
        )


@router.get("/{template_id}", response_model=EmailTemplateResponse)
async def get_email_template(
    template_id: UUID,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.EMAIL_TEMPLATE_VIEW))],
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateResponse:
    """Get a specific email template.

    Args:
        template_id: Template UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Email template details
    """
    try:
        template = await db.get(EmailTemplate, str(template_id))

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Email template {template_id} not found",
            )

        return EmailTemplateResponse(
            id=template.id,
            name=template.name,
            subject=template.subject,
            body=template.body,
            html_body=template.html_body,
            cc=template.cc,
            is_default=template.is_default,
            prefer_xarf=getattr(template, 'prefer_xarf', False),
            xarf_reporter_ref_template=getattr(template, 'xarf_reporter_ref_template', None),
            created_by=template.created_by,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get email template: {str(e)}",
        )


@router.post("", response_model=EmailTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_email_template(
    template_data: EmailTemplateCreate,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.EMAIL_TEMPLATE_CREATE))],
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateResponse:
    """Create a new email template.

    Args:
        template_data: Template creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created email template
    """
    try:
        # Check if this is the first template (to make it default)
        existing_count_result = await db.execute(select(func.count()).select_from(EmailTemplate))
        is_first_template = existing_count_result.scalar() == 0

        # Check if name already exists
        name_exists = await db.execute(
            select(EmailTemplate).where(EmailTemplate.name == template_data.name)
        )
        if name_exists.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email template with name '{template_data.name}' already exists",
            )

        # Create new template (make default if it's the first one)
        new_template = EmailTemplate(
            name=template_data.name,
            subject=template_data.subject,
            body=template_data.body,
            html_body=template_data.html_body,
            cc=template_data.cc,
            is_default=is_first_template,  # First template becomes default
            prefer_xarf=template_data.prefer_xarf,
            xarf_reporter_ref_template=template_data.xarf_reporter_ref_template,
            created_by=current_user.id,
        )

        db.add(new_template)
        await db.flush()
        await db.refresh(new_template)

        # Log template creation
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_CREATED,  # Using generic CREATED action
            resource_type=ResourceType.CONFIG,  # Using CONFIG as resource type
            resource_id=str(new_template.id),
            details={"name": template_data.name},
        )
        await db.commit()

        return EmailTemplateResponse(
            id=new_template.id,
            name=new_template.name,
            subject=new_template.subject,
            body=new_template.body,
            html_body=new_template.html_body,
            is_default=new_template.is_default,
            prefer_xarf=new_template.prefer_xarf,
            xarf_reporter_ref_template=new_template.xarf_reporter_ref_template,
            created_by=new_template.created_by,
            created_at=new_template.created_at,
            updated_at=new_template.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create email template: {str(e)}",
        )


@router.patch("/{template_id}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_id: UUID,
    updates: EmailTemplateUpdate,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.EMAIL_TEMPLATE_UPDATE))],
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateResponse:
    """Update an email template.

    Args:
        template_id: Template UUID
        updates: Update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated email template
    """
    try:
        template = await db.get(EmailTemplate, str(template_id))

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Email template {template_id} not found",
            )

        # Apply updates
        if updates.name is not None:
            # Check if new name already exists (excluding current template)
            name_exists = await db.execute(
                select(EmailTemplate).where(
                    and_(EmailTemplate.name == updates.name, EmailTemplate.id != str(template_id))
                )
            )
            if name_exists.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email template with name '{updates.name}' already exists",
                )
            template.name = updates.name

        if updates.subject is not None:
            template.subject = updates.subject

        if updates.body is not None:
            template.body = updates.body

        if updates.html_body is not None:
            template.html_body = updates.html_body

        if updates.cc is not None:
            template.cc = updates.cc

        if updates.prefer_xarf is not None:
            template.prefer_xarf = updates.prefer_xarf

        if updates.xarf_reporter_ref_template is not None:
            template.xarf_reporter_ref_template = updates.xarf_reporter_ref_template

        if updates.is_default is not None:
            # If setting as default, unset all other defaults
            if updates.is_default:
                await db.execute(
                    select(EmailTemplate).where(EmailTemplate.is_default == True)
                )
                all_templates = await db.execute(select(EmailTemplate))
                for t in all_templates.scalars().all():
                    if t.id != str(template_id):
                        t.is_default = False
            template.is_default = updates.is_default

        template.updated_at = now_utc()
        await db.commit()
        await db.refresh(template)

        return EmailTemplateResponse(
            id=template.id,
            name=template.name,
            subject=template.subject,
            body=template.body,
            html_body=template.html_body,
            cc=template.cc,
            is_default=template.is_default,
            prefer_xarf=template.prefer_xarf,
            xarf_reporter_ref_template=template.xarf_reporter_ref_template,
            created_by=template.created_by,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update email template: {str(e)}",
        )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_template(
    template_id: UUID,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.EMAIL_TEMPLATE_DELETE))],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an email template.

    Args:
        template_id: Template UUID
        current_user: Current authenticated user
        db: Database session
    """
    try:
        template = await db.get(EmailTemplate, str(template_id))

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Email template {template_id} not found",
            )

        # Prevent deleting the default template if it's the only one
        if template.is_default:
            other_templates = await db.execute(
                select(EmailTemplate).where(EmailTemplate.id != str(template_id))
            )
            if other_templates.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the only email template. Create a new one first.",
                )

        await db.delete(template)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete email template: {str(e)}",
        )


@router.post("/{template_id}/set-default", response_model=EmailTemplateResponse)
async def set_default_template(
    template_id: UUID,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.EMAIL_TEMPLATE_UPDATE))],
    db: AsyncSession = Depends(get_db),
) -> EmailTemplateResponse:
    """Set an email template as the default.

    Args:
        template_id: Template UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated email template
    """
    try:
        template = await db.get(EmailTemplate, str(template_id))

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Email template {template_id} not found",
            )

        # Unset all other templates' default flag
        all_templates = await db.execute(select(EmailTemplate))
        for t in all_templates.scalars().all():
            t.is_default = False

        # Set this template as default
        template.is_default = True
        template.updated_at = now_utc()

        await db.commit()
        await db.refresh(template)

        return EmailTemplateResponse(
            id=template.id,
            name=template.name,
            subject=template.subject,
            body=template.body,
            html_body=template.html_body,
            cc=template.cc,
            is_default=template.is_default,
            prefer_xarf=template.prefer_xarf,
            xarf_reporter_ref_template=template.xarf_reporter_ref_template,
            created_by=template.created_by,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set default template: {str(e)}",
        )


__all__ = ["router"]
