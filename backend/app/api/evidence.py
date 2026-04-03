"""API endpoints for evidence management."""
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_active_user
from app.auth.dependencies import PermissionChecker
from app.config import settings
from app.database import get_db, get_db_context
from app.models import Evidence, Case, User
from app.permissions import Permission, get_role_permissions
from app.schemas import EvidenceSchema, CaptureScreenshotRequest
from app.tasks.evidence import capture_screenshot_task

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post("/capture", status_code=status.HTTP_202_ACCEPTED)
async def capture_screenshot(
    request_data: CaptureScreenshotRequest,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.EVIDENCE_CREATE))],
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a screenshot capture for a case.

    Args:
        request_data: Screenshot capture request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Task result with evidence ID
    """
    try:
        # Verify case exists
        case = await db.get(Case, str(request_data.case_id))

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {request_data.case_id} not found",
            )

        # Use provided URL or fall back to case URL
        url = request_data.url if request_data.url else case.url

        # Trigger screenshot capture task
        result = capture_screenshot_task.delay(
            str(request_data.case_id),
            url,
            request_data.full_page,
        )

        return {
            "success": True,
            "task_id": result.id,
            "case_id": str(request_data.case_id),
            "status": "capturing",
            "message": "Screenshot capture started",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger screenshot capture: {str(e)}",
        )


@router.get("/case/{case_id}", response_model=list[EvidenceSchema])
async def list_case_evidence(
    case_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    evidence_type: Optional[str] = Query(None, description="Filter by evidence type"),
) -> list[EvidenceSchema]:
    """List all evidence for a specific case.

    Args:
        case_id: Case UUID
        current_user: Current authenticated user
        db: Database session
        evidence_type: Optional filter for evidence type

    Returns:
        List of evidence records
    """
    try:
        # Get user's role and permissions
        from app.models import Role

        role_result = await db.execute(select(Role).where(Role.id == current_user.role_id))
        role = role_result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User has no role assigned",
            )

        permissions = get_role_permissions(role.name)

        # Check if case exists and user has permission to view it
        case = await db.get(Case, str(case_id))

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found",
            )

        # Check view permissions
        can_view_any = Permission.CASE_VIEW_ANY in permissions or "*" in permissions
        can_view_own = Permission.CASE_VIEW_OWN in permissions

        if not can_view_any and (can_view_own and case.created_by != current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this case",
            )

        # Query evidence
        query = select(Evidence).where(Evidence.case_id == str(case_id))

        if evidence_type:
            query = query.where(Evidence.type == evidence_type)

        query = query.order_by(Evidence.created_at.desc())

        result = await db.execute(query)
        evidence_list = result.scalars().all()

        return [_evidence_to_schema(e) for e in evidence_list]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list evidence: {str(e)}",
        )


@router.get("/{evidence_id}", response_model=EvidenceSchema)
async def get_evidence(
    evidence_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> EvidenceSchema:
    """Get details of a specific evidence record.

    Args:
        evidence_id: Evidence UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Evidence details
    """
    try:
        from app.models import Role

        evidence = await db.get(Evidence, str(evidence_id))

        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evidence {evidence_id} not found",
            )

        # Get user's role and permissions
        role_result = await db.execute(select(Role).where(Role.id == current_user.role_id))
        role = role_result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User has no role assigned",
            )

        permissions = get_role_permissions(role.name)

        # Check if user can view the associated case
        case = await db.get(Case, evidence.case_id)

        can_view_any = Permission.CASE_VIEW_ANY in permissions or "*" in permissions
        can_view_own = Permission.CASE_VIEW_OWN in permissions

        if not can_view_any and (can_view_own and case and case.created_by != current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this evidence",
            )

        return _evidence_to_schema(evidence)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get evidence: {str(e)}",
        )


@router.get("/{evidence_id}/download")
async def download_evidence(
    evidence_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
):
    """Download an evidence file.

    Args:
        evidence_id: Evidence UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        File response with the evidence file
    """
    try:
        from app.models import Role

        evidence = await db.get(Evidence, str(evidence_id))

        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evidence {evidence_id} not found",
            )

        if not evidence.file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence file not available",
            )

        # Get user's role and permissions
        role_result = await db.execute(select(Role).where(Role.id == current_user.role_id))
        role = role_result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User has no role assigned",
            )

        permissions = get_role_permissions(role.name)

        # Check if user can view the associated case
        case = await db.get(Case, evidence.case_id)

        can_view_any = Permission.CASE_VIEW_ANY in permissions or "*" in permissions
        can_view_own = Permission.CASE_VIEW_OWN in permissions

        if not can_view_any and (can_view_own and case and case.created_by != current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to download this evidence",
            )

        # Check if file exists
        file_path = Path(evidence.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence file not found on disk",
            )

        # Determine media type
        media_type = "application/octet-stream"
        if evidence.type == "screenshot":
            media_type = "image/png"
        elif evidence.type == "html":
            media_type = "text/html"

        # Generate filename
        filename = file_path.name

        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=filename,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download evidence: {str(e)}",
        )


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(
    evidence_id: UUID,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.EVIDENCE_DELETE))],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete an evidence record and its file.

    Args:
        evidence_id: Evidence UUID
        current_user: Current authenticated user
        db: Database session
    """
    try:
        evidence = await db.get(Evidence, str(evidence_id))

        if not evidence:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evidence {evidence_id} not found",
            )

        # Delete the file if it exists
        if evidence.file_path:
            file_path = Path(evidence.file_path)
            if file_path.exists():
                file_path.unlink()

        # Delete the database record
        await db.delete(evidence)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete evidence: {str(e)}",
        )


def _evidence_to_schema(evidence: Evidence) -> EvidenceSchema:
    """Convert an Evidence model to an EvidenceSchema.

    Args:
        evidence: Evidence model instance

    Returns:
        EvidenceSchema instance
    """
    return EvidenceSchema(
        id=UUID(evidence.id),
        case_id=UUID(evidence.case_id),
        type=evidence.type,
        file_path=evidence.file_path,
        content_hash=evidence.content_hash,
        metadata=evidence.meta,
        created_at=evidence.created_at,
    )


__all__ = ["router"]
