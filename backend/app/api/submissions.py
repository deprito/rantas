"""API endpoints for public submission management.

Provides endpoints for staff to review, approve, and reject public submissions.
"""
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_active_user
from app.auth.dependencies import PermissionChecker
from app.config import settings
from app.database import get_db
from app.models import User, PublicSubmission, Case
from app.permissions import Permission
from app.schemas import CaseStatus
from app.utils.timezone import now_utc


router = APIRouter(prefix="/submissions", tags=["submissions"])


# ==================== Request/Response Schemas ====================


class PublicSubmissionResponse(BaseModel):
    """Response schema for public submission."""

    id: str
    url: str
    submitter_email: Optional[str]
    status: str
    additional_notes: Optional[str]
    ip_address: Optional[str]
    submitted_at: datetime
    reviewed_at: Optional[datetime]
    reviewed_by: Optional[str]
    case_id: Optional[str]

    class Config:
        from_attributes = True


class SubmissionListResponse(BaseModel):
    """Response schema for submission list."""

    submissions: list[PublicSubmissionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class SubmissionApproveRequest(BaseModel):
    """Request schema for approving a submission."""

    monitor_interval: Optional[int] = Field(
        None,
        ge=1800,
        le=86400,
        description="Monitoring interval in seconds (30 min to 24 hours)",
    )


class SubmissionRejectRequest(BaseModel):
    """Request schema for rejecting a submission."""

    reason: Optional[str] = Field(None, max_length=1000)


# ==================== Endpoints ====================


@router.get("", response_model=SubmissionListResponse)
async def list_submissions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> SubmissionListResponse:
    """List public submissions with optional filtering and pagination.

    Args:
        current_user: Current authenticated user
        db: Database session
        status_filter: Optional status filter (pending, approved, rejected)
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        SubmissionListResponse with submissions list and pagination info
    """
    try:
        # Build query
        query = select(PublicSubmission)

        if status_filter and status_filter in ["pending", "approved", "rejected"]:
            query = query.where(PublicSubmission.status == status_filter)

        # Order by submitted_at descending (newest first)
        query = query.order_by(PublicSubmission.submitted_at.desc())

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(query)
        submissions = result.scalars().all()

        # Convert to response format
        submission_responses = [
            PublicSubmissionResponse(
                id=str(s.id),
                url=s.url,
                submitter_email=s.submitter_email,
                status=s.status,
                additional_notes=s.additional_notes,
                ip_address=s.ip_address,
                submitted_at=s.submitted_at,
                reviewed_at=s.reviewed_at,
                reviewed_by=str(s.reviewed_by) if s.reviewed_by else None,
                case_id=str(s.case_id) if s.case_id else None,
            )
            for s in submissions
        ]

        pages = (total + page_size - 1) // page_size if total > 0 else 1

        return SubmissionListResponse(
            submissions=submission_responses,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list submissions: {str(e)}",
        )


@router.get("/pending-count")
async def get_pending_count(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> int:
    """Get the count of pending submissions.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Count of pending submissions
    """
    try:
        result = await db.execute(
            select(func.count()).where(PublicSubmission.status == "pending")
        )
        count = result.scalar() or 0
        return count

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending count: {str(e)}",
        )


@router.get("/{submission_id}", response_model=PublicSubmissionResponse)
async def get_submission(
    submission_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> PublicSubmissionResponse:
    """Get details of a specific submission.

    Args:
        submission_id: Submission UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        PublicSubmissionResponse with submission details
    """
    try:
        submission = await db.get(PublicSubmission, str(submission_id))

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Submission {submission_id} not found",
            )

        return PublicSubmissionResponse(
            id=str(submission.id),
            url=submission.url,
            submitter_email=submission.submitter_email,
            status=submission.status,
            additional_notes=submission.additional_notes,
            ip_address=submission.ip_address,
            submitted_at=submission.submitted_at,
            reviewed_at=submission.reviewed_at,
            reviewed_by=str(submission.reviewed_by) if submission.reviewed_by else None,
            case_id=str(submission.case_id) if submission.case_id else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get submission: {str(e)}",
        )


@router.post("/{submission_id}/approve", response_model=PublicSubmissionResponse)
async def approve_submission(
    submission_id: UUID,
    data: SubmissionApproveRequest,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.SUBMISSION_APPROVE))],
    db: AsyncSession = Depends(get_db),
) -> PublicSubmissionResponse:
    """Approve a public submission and create a case.

    Args:
        submission_id: Submission UUID
        data: Approval request with optional monitor interval
        current_user: Current authenticated user with approve permission
        db: Database session

    Returns:
        PublicSubmissionResponse with updated submission
    """
    try:
        submission = await db.get(PublicSubmission, str(submission_id))

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Submission {submission_id} not found",
            )

        if submission.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Submission is not pending (current status: {submission.status})",
            )

        # Create a new case from the submission
        new_case = Case(
            url=submission.url,
            status=CaseStatus.ANALYZING.value,
            source="public",
            monitor_interval=data.monitor_interval or settings.DEFAULT_MONITOR_INTERVAL,
            created_by=current_user.id,
        )

        # Add history entry
        notes = submission.additional_notes or "None"
        email = submission.submitter_email or "Anonymous"
        new_case.add_history_entry(
            "system",
            f"Case created from approved public submission. Submitter: {email}. Notes: {notes}",
        )

        # Store submission metadata
        new_case.domain_info = {
            "source": "public_submission",
            "submission_id": str(submission.id),
            "submitter_email": submission.submitter_email,
            "submitter_ip": submission.ip_address,
        }

        db.add(new_case)
        await db.flush()

        # Update submission
        submission.status = "approved"
        submission.reviewed_at = now_utc()
        submission.reviewed_by = current_user.id
        submission.case_id = new_case.id

        await db.commit()
        await db.refresh(submission)

        # Trigger OSINT analysis task
        from app.tasks.osint import analyze_url_task
        from app.tasks.evidence import capture_screenshot_task

        try:
            analyze_url_task.delay(str(new_case.id), submission.url)
            capture_screenshot_task.delay(str(new_case.id), submission.url)
        except Exception as task_error:
            print(f"Warning: Failed to trigger background tasks: {task_error}")

        return PublicSubmissionResponse(
            id=str(submission.id),
            url=submission.url,
            submitter_email=submission.submitter_email,
            status=submission.status,
            additional_notes=submission.additional_notes,
            ip_address=submission.ip_address,
            submitted_at=submission.submitted_at,
            reviewed_at=submission.reviewed_at,
            reviewed_by=str(submission.reviewed_by) if submission.reviewed_by else None,
            case_id=str(submission.case_id) if submission.case_id else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error approving submission: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve submission: {str(e)}",
        )


@router.post("/{submission_id}/reject", response_model=PublicSubmissionResponse)
async def reject_submission(
    submission_id: UUID,
    data: SubmissionRejectRequest,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.SUBMISSION_APPROVE))],
    db: AsyncSession = Depends(get_db),
) -> PublicSubmissionResponse:
    """Reject a public submission.

    Args:
        submission_id: Submission UUID
        data: Rejection request with optional reason
        current_user: Current authenticated user with approve permission
        db: Database session

    Returns:
        PublicSubmissionResponse with updated submission
    """
    try:
        submission = await db.get(PublicSubmission, str(submission_id))

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Submission {submission_id} not found",
            )

        if submission.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Submission is not pending (current status: {submission.status})",
            )

        # Update submission
        submission.status = "rejected"
        submission.reviewed_at = now_utc()
        submission.reviewed_by = current_user.id

        # Store rejection reason in additional_notes
        if data.reason:
            if submission.additional_notes:
                submission.additional_notes = f"{submission.additional_notes}\n\nRejection reason: {data.reason}"
            else:
                submission.additional_notes = f"Rejection reason: {data.reason}"

        await db.commit()
        await db.refresh(submission)

        return PublicSubmissionResponse(
            id=str(submission.id),
            url=submission.url,
            submitter_email=submission.submitter_email,
            status=submission.status,
            additional_notes=submission.additional_notes,
            ip_address=submission.ip_address,
            submitted_at=submission.submitted_at,
            reviewed_at=submission.reviewed_at,
            reviewed_by=str(submission.reviewed_by) if submission.reviewed_by else None,
            case_id=str(submission.case_id) if submission.case_id else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error rejecting submission: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject submission: {str(e)}",
        )


@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_submission(
    submission_id: UUID,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.SUBMISSION_DELETE))],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a public submission.

    Args:
        submission_id: Submission UUID
        current_user: Current authenticated user with delete permission
        db: Database session
    """
    try:
        submission = await db.get(PublicSubmission, str(submission_id))

        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Submission {submission_id} not found",
            )

        await db.delete(submission)
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete submission: {str(e)}",
        )


__all__ = ["router"]
