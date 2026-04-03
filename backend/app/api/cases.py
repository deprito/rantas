"""API endpoints for case management."""
from datetime import datetime, timedelta
from typing import Annotated, Optional
from uuid import UUID, uuid4
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select, and_, or_
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
from app.models import Case, User, Role
from app.permissions import Permission, get_role_permissions
from app.schemas import (
    AbuseContact,
    Case as CaseSchema,
    CaseCreate,
    CaseExportRequest,
    CaseExportResponse,
    CaseSource,
    CaseStatus,
    CaseSummary,
    CaseUpdate,
    DomainInfo,
    HistoryEntry,
    SendReportRequest,
)
from app.tasks.osint import analyze_url_task
from app.tasks.evidence import capture_screenshot_task
from app.utils.timezone import now_utc

router = APIRouter(prefix="/cases", tags=["cases"])

# Store export metadata (in production, use a database table)
_exports_cache: dict[str, dict] = {}


@router.post("", response_model=CaseSchema, status_code=status.HTTP_201_CREATED)
async def create_case(
    case_data: CaseCreate,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.CASE_CREATE))],
    db: AsyncSession = Depends(get_db),
) -> CaseSchema:
    """Create a new case for URL investigation.

    Args:
        case_data: Case creation data with URL and optional monitor interval
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created case
    """
    try:
        # Check for duplicate URL
        existing_result = await db.execute(
            select(Case, User.username, User.email)
            .outerjoin(User, Case.created_by == User.id)
            .where(Case.url == case_data.url)
        )
        existing = existing_result.first()

        if existing:
            # Return existing case instead of creating duplicate
            case, username, email = existing
            return _case_to_schema(case, username, email)

        # Create new case
        new_case = Case(
            url=case_data.url,
            status=CaseStatus.ANALYZING.value,
            monitor_interval=case_data.monitor_interval or settings.DEFAULT_MONITOR_INTERVAL,
            created_by=current_user.id,
        )

        # Add initial history entry
        new_case.add_history_entry(
            "system",
            "Case created - initiating analysis",
        )

        db.add(new_case)
        await db.flush()
        await db.refresh(new_case)

        # Convert to schema before commit
        case_schema = _case_to_schema(
            new_case,
            created_by_username=current_user.username,
            created_by_email=current_user.email,
        )

        # Log case creation
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_CREATED,
            resource_type=ResourceType.CASE,
            resource_id=str(new_case.id),
            details={"url": case_data.url},
        )
        await db.commit()

        # Trigger OSINT analysis task
        analyze_url_task.delay(str(new_case.id), case_data.url)

        # Trigger screenshot capture for ANALYZING cases
        if new_case.status == CaseStatus.ANALYZING.value:
            capture_screenshot_task.delay(str(new_case.id), case_data.url)

        return case_schema

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create case: {str(e)}",
        )


@router.get("", response_model=dict)
async def list_cases(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[CaseStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> dict:
    """List all cases with optional filtering and pagination.

    Args:
        status_filter: Optional status filter
        page: Page number (1-indexed)
        page_size: Items per page
        current_user: Current authenticated user
        db: Database session

    Returns:
        Dictionary with cases list and pagination info
    """
    try:
        # Get user's role and permissions
        role_result = await db.execute(select(Role).where(Role.id == current_user.role_id))
        role = role_result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User has no role assigned",
            )

        permissions = get_role_permissions(role.name)

        # Build query with left join to User to get creator info
        query = select(Case, User.username, User.email).outerjoin(
            User, Case.created_by == User.id
        )

        # Filter by user's permissions
        can_view_any = Permission.CASE_VIEW_ANY in permissions or "*" in permissions
        can_view_own = Permission.CASE_VIEW_OWN in permissions

        if not can_view_any and can_view_own:
            # User can only see their own cases
            query = query.where(Case.created_by == current_user.id)

        if status_filter:
            query = query.where(Case.status == status_filter.value)

        # Order by created_at descending
        query = query.order_by(Case.created_at.desc())

        # Get total count
        from sqlalchemy import func

        count_query = select(func.count(Case.id)).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(query)
        rows = result.all()

        # Convert rows to case schemas with user info
        cases = []
        for row in rows:
            case, username, email = row
            cases.append(_case_to_schema(
                case,
                created_by_username=username,
                created_by_email=email,
            ))

        return {
            "cases": cases,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list cases: {str(e)}",
        )


@router.get("/summary", response_model=list[CaseSummary])
async def list_case_summaries(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[CaseStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum items to return"),
) -> list[CaseSummary]:
    """Get a summary list of cases.

    Args:
        current_user: Current authenticated user
        db: Database session
        status_filter: Optional status filter
        limit: Maximum items to return

    Returns:
        List of case summaries
    """
    try:
        # Get user's role and permissions
        role_result = await db.execute(select(Role).where(Role.id == current_user.role_id))
        role = role_result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User has no role assigned",
            )

        permissions = get_role_permissions(role.name)

        # Build query
        query = select(Case)

        # Filter by user's permissions
        can_view_any = Permission.CASE_VIEW_ANY in permissions or "*" in permissions
        can_view_own = Permission.CASE_VIEW_OWN in permissions

        if not can_view_any and can_view_own:
            # User can only see their own cases
            query = query.where(Case.created_by == current_user.id)

        if status_filter:
            query = query.where(Case.status == status_filter.value)

        query = query.order_by(Case.created_at.desc()).limit(limit)

        result = await db.execute(query)
        cases = result.scalars().all()

        return [_case_to_summary(c) for c in cases]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list case summaries: {str(e)}",
        )


# ==================== Export Endpoints ====================
# Note: These routes must be defined before /{case_id} routes to avoid path conflicts


@router.post("/export", response_model=CaseExportResponse)
async def export_cases(
    export_request: CaseExportRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> CaseExportResponse:
    """Export cases to CSV or JSON format.

    Args:
        export_request: Export request with format, filters, and Teams notification option
        current_user: Current authenticated user
        db: Database session

    Returns:
        Export response with download URL
    """
    try:
        # Build filters dict
        filters = {
            "start_date": export_request.start_date,
            "end_date": export_request.end_date,
            "status": export_request.status,
            "source": export_request.source,
        }

        # Generate export based on format
        if export_request.format == "csv":
            from app.services.report_generator import generate_cases_csv

            export_id, file_path, cases_count, file_size = await generate_cases_csv(
                db, filters, str(current_user.id)
            )
        else:  # json
            from app.services.report_generator import generate_cases_json

            export_id, file_path, cases_count, file_size = await generate_cases_json(
                db, filters, str(current_user.id)
            )

        # Generate download URL
        filename = Path(file_path).name
        download_url = f"{settings.BASE_URL.rstrip('/')}/api/cases/exports/{export_id}"

        # Store export metadata in cache
        _exports_cache[export_id] = {
            "file_path": file_path,
            "filename": filename,
            "format": export_request.format,
        }

        # Send Teams notification if requested
        if export_request.send_to_teams:
            from app.services.teams_notify import send_export_notification

            await send_export_notification(
                export_type=export_request.format,
                file_url=download_url,
                cases_count=cases_count,
                filters=filters,
            )

        # Log export action
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_VIEWED,  # Reuse existing action
            resource_type=ResourceType.CASE,
            resource_id=None,
            details={
                "action": "export",
                "format": export_request.format,
                "cases_count": cases_count,
                "filters": filters,
            },
        )
        await db.commit()

        return CaseExportResponse(
            export_id=export_id,
            download_url=download_url,
            format=export_request.format,
            cases_count=cases_count,
            status="completed",
            file_size_bytes=file_size,
        )

    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export cases: {str(e)}",
        )


@router.get("/exports/{export_id}")
async def download_export(
    export_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> FileResponse:
    """Download an exported case file.

    Args:
        export_id: Export ID from export response
        current_user: Current authenticated user

    Returns:
        File response with the exported file
    """
    # Check if export exists in cache
    export_metadata = _exports_cache.get(export_id)
    if not export_metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export {export_id} not found or has expired",
        )

    file_path = Path(export_metadata["file_path"])
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found on server",
        )

    # Determine media type
    media_type = "text/csv" if export_metadata["format"] == "csv" else "application/json"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=export_metadata["filename"],
    )


@router.get("/{case_id}", response_model=CaseSchema)
async def get_case(
    case_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> CaseSchema:
    """Get details of a specific case.

    Args:
        case_id: Case UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Case details
    """
    try:
        # Get user's permissions
        role_result = await db.execute(select(Role).where(Role.id == current_user.role_id))
        role = role_result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User has no role assigned",
            )

        permissions = get_role_permissions(role.name)

        # Query case with user info
        result = await db.execute(
            select(Case, User.username, User.email)
            .outerjoin(User, Case.created_by == User.id)
            .where(Case.id == str(case_id))
        )
        row = result.first()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found",
            )

        case, username, email = row

        # Check if user can view this case
        can_view_any = Permission.CASE_VIEW_ANY in permissions or "*" in permissions
        can_view_own = Permission.CASE_VIEW_OWN in permissions

        if not can_view_any and (can_view_own and case.created_by != current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this case",
            )

        # Log case view
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_VIEWED,
            resource_type=ResourceType.CASE,
            resource_id=str(case_id),
        )
        await db.commit()

        return _case_to_schema(
            case,
            created_by_username=username,
            created_by_email=email,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get case: {str(e)}",
        )


@router.patch("/{case_id}", response_model=CaseSchema)
async def update_case(
    case_id: UUID,
    updates: CaseUpdate,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.CASE_UPDATE))],
    db: AsyncSession = Depends(get_db),
) -> CaseSchema:
    """Update a case.

    Args:
        case_id: Case UUID
        updates: Update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated case
    """
    try:
        case = await db.get(Case, str(case_id))

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found",
            )

        # Apply updates
        if updates.status is not None:
            old_status = case.status
            case.update_status(updates.status.value)
            # Send Teams notification when case is resolved
            if updates.status.value == "RESOLVED" and old_status != "RESOLVED":
                from app.services.teams_notify import send_case_resolved_notification
                await send_case_resolved_notification(case)

        if updates.domain_info is not None:
            case.domain_info = updates.domain_info.model_dump()

        if updates.abuse_contacts is not None:
            case.abuse_contacts = [c.model_dump() for c in updates.abuse_contacts]

        if updates.brand_impacted is not None:
            case.brand_impacted = updates.brand_impacted

        if updates.history is not None:
            # Append new history entries
            existing_ids = {h.get("id") for h in case.history if isinstance(h, dict) and "id" in h}
            for entry in updates.history:
                entry_dict = entry.model_dump()
                if entry_dict["id"] not in existing_ids:
                    if isinstance(case.history, dict):
                        case.history = [entry_dict]
                    else:
                        case.history = list(case.history) + [entry_dict]

        case.updated_at = now_utc()

        # Log case update
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_UPDATED,
            resource_type=ResourceType.CASE,
            resource_id=str(case_id),
        )
        await db.commit()

        # Fetch updated case with user info
        case, username, email = await _get_case_with_user(str(case.id), db)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found after update",
            )

        return _case_to_schema(case, username, email)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update case: {str(e)}",
        )


@router.delete("/all", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_cases(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.CASE_DELETE))],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete all cases.

    Args:
        current_user: Current authenticated user
        db: Database session
    """
    try:
        # Get all cases
        result = await db.execute(select(Case))
        cases = result.scalars().all()

        # Delete all cases
        for case in cases:
            await db.delete(case)

        # Log the action
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_DELETED,
            resource_type=ResourceType.CASE,
            resource_id=None,
            details={"count": len(cases), "action": "delete_all"},
        )
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete all cases: {str(e)}",
        )


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: UUID,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.CASE_DELETE))],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a case.

    Args:
        case_id: Case UUID
        current_user: Current authenticated user
        db: Database session
    """
    try:
        case = await db.get(Case, str(case_id))

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found",
            )

        await db.delete(case)

        # Log case deletion
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_DELETED,
            resource_type=ResourceType.CASE,
            resource_id=str(case_id),
        )
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete case: {str(e)}",
        )


@router.post("/{case_id}/reanalyze", response_model=CaseSchema)
async def reanalyze_case(
    case_id: UUID,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.CASE_UPDATE))],
    db: AsyncSession = Depends(get_db),
) -> CaseSchema:
    """Re-run OSINT analysis on a case.

    Args:
        case_id: Case UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated case
    """
    try:
        case = await db.get(Case, str(case_id))

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found",
            )

        # Update status and add history
        case.status = CaseStatus.ANALYZING.value
        case.add_history_entry("system", "Re-analysis initiated")

        # Log reanalysis
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_UPDATED,
            resource_type=ResourceType.CASE,
            resource_id=str(case_id),
            details={"action": "reanalyze"},
        )
        await db.commit()

        # Trigger analysis task
        analyze_url_task.delay(str(case.id), case.url)

        # Trigger screenshot capture
        capture_screenshot_task.delay(str(case.id), case.url)

        # Fetch case with user info for response
        case, username, email = await _get_case_with_user(str(case.id), db)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found after reanalysis",
            )

        return _case_to_schema(case, username, email)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reanalyze case: {str(e)}",
        )


@router.post("/{case_id}/send-report", response_model=CaseSchema)
async def send_abuse_report(
    case_id: UUID,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.CASE_SEND_REPORT))],
    db: AsyncSession = Depends(get_db),
    report_data: SendReportRequest = SendReportRequest(),
) -> CaseSchema:
    """Manually send abuse report for a case.

    Args:
        case_id: Case UUID
        report_data: Optional report data including template_id
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated case
    """
    try:
        case = await db.get(Case, str(case_id))

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found",
            )

        # Check if case has abuse contacts
        if not case.abuse_contacts or len(case.abuse_contacts) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No abuse contacts found for this case. Cannot send report.",
            )

        # Update status to REPORTING (in progress)
        case.status = "REPORTING"
        case.add_history_entry("system", f"Abuse report triggered for {len(case.abuse_contacts)} contact(s)")
        case.updated_at = now_utc()

        # Store brand_impacted if provided
        if report_data.brand_impacted:
            case.brand_impacted = report_data.brand_impacted

        # Log report send
        details = {"contacts_count": len(case.abuse_contacts)}
        if report_data.template_id:
            details["template_id"] = str(report_data.template_id)
        if report_data.brand_impacted:
            details["brand_impacted"] = report_data.brand_impacted

        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_REPORT_SENT,
            resource_type=ResourceType.CASE,
            resource_id=str(case_id),
            details=details,
        )
        await db.commit()

        # Trigger email task with template_id, selected_contacts, and brand_impacted if provided
        from app.tasks.email import send_report_task
        template_id_str = str(report_data.template_id) if report_data.template_id else None
        selected_contacts = report_data.selected_contacts if report_data.selected_contacts else None
        brand_impacted = report_data.brand_impacted if report_data.brand_impacted else None
        send_report_task.delay(str(case_id), template_id=template_id_str, selected_contacts=selected_contacts, brand_impacted=brand_impacted)

        # Fetch case with user info for response
        case, username, email = await _get_case_with_user(str(case.id), db)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found after sending report",
            )

        return _case_to_schema(case, username, email)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send report: {str(e)}",
        )


@router.post("/{case_id}/send-followup", response_model=CaseSchema)
async def send_followup_report(
    case_id: UUID,
    report_data: SendReportRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> CaseSchema:
    """Send a follow-up abuse report for a case in MONITORING or REPORTED status.

    Unlike send-report, this does not change the case status - it stays in MONITORING.

    Args:
        case_id: Case UUID
        report_data: Optional report data including template_id and selected_contacts
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated case
    """
    try:
        case = await db.get(Case, str(case_id))

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found",
            )

        # Only allow follow-up for MONITORING or REPORTED cases
        if case.status not in (CaseStatus.MONITORING.value, CaseStatus.REPORTED.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Follow-up reports can only be sent for cases in MONITORING or REPORTED status. Current status: {case.status}",
            )

        # Check if case has abuse contacts
        if not case.abuse_contacts or len(case.abuse_contacts) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No abuse contacts found for this case. Cannot send follow-up report.",
            )

        # Calculate number of contacts (using selected contacts if provided)
        contacts_count = len(case.abuse_contacts)
        if report_data.selected_contacts:
            contacts_count = len(report_data.selected_contacts)

        # Add history entry - note this is a follow-up
        case.add_history_entry("system", f"Follow-up report triggered for {contacts_count} contact(s)")
        case.updated_at = now_utc()

        # Log audit action with is_followup flag
        details = {"is_followup": True, "contacts_count": contacts_count}
        if report_data.template_id:
            details["template_id"] = str(report_data.template_id)

        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_REPORT_SENT,
            resource_type=ResourceType.CASE,
            resource_id=str(case_id),
            details=details,
        )
        await db.commit()

        # Trigger email task with is_followup flag
        from app.tasks.email import send_report_task
        template_id_str = str(report_data.template_id) if report_data.template_id else None
        selected_contacts = report_data.selected_contacts if report_data.selected_contacts else None
        send_report_task.delay(
            str(case_id),
            template_id=template_id_str,
            selected_contacts=selected_contacts,
            is_followup=True,
        )

        # Fetch case with user info for response
        case, username, email = await _get_case_with_user(str(case.id), db)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found after sending follow-up",
            )

        return _case_to_schema(case, username, email)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send follow-up report: {str(e)}",
        )


@router.post("/{case_id}/history", response_model=CaseSchema)
async def add_history_entry(
    case_id: UUID,
    entry_type: str,
    message: str,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.CASE_UPDATE))],
    db: AsyncSession = Depends(get_db),
    entry_status: Optional[int] = None,
) -> CaseSchema:
    """Add a history entry to a case.

    Args:
        case_id: Case UUID
        entry_type: Type of history entry
        message: History message
        current_user: Current authenticated user
        db: Database session
        entry_status: Optional HTTP status code

    Returns:
        Updated case
    """
    try:
        case = await db.get(Case, str(case_id))

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case {case_id} not found",
            )

        case.add_history_entry(entry_type, message, entry_status)

        # Log history addition
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_UPDATED,
            resource_type=ResourceType.CASE,
            resource_id=str(case_id),
            details={"action": "add_history", "entry_type": entry_type},
        )
        await db.commit()

        await db.refresh(case)
        return _case_to_schema(case)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add history entry: {str(e)}",
        )


async def _get_case_with_user(
    case_id: str,
    db: AsyncSession,
) -> tuple[Case, Optional[str], Optional[str]]:
    """Fetch a case with creator information.

    Args:
        case_id: Case UUID as string
        db: Database session

    Returns:
        Tuple of (case, username, email)
    """
    result = await db.execute(
        select(Case, User.username, User.email)
        .outerjoin(User, Case.created_by == User.id)
        .where(Case.id == case_id)
    )
    row = result.first()

    if not row:
        return None, None, None

    case, username, email = row
    return case, username, email


def _case_to_schema(
    case: Case,
    created_by_username: Optional[str] = None,
    created_by_email: Optional[str] = None,
) -> CaseSchema:
    """Convert a Case model to a Case schema.

    Args:
        case: Case model instance
        created_by_username: Optional username of the user who created the case
        created_by_email: Optional email of the user who created the case

    Returns:
        CaseSchema instance
    """
    # Ensure history is a list
    history_list = case.history if case.history is not None else []

    # Convert history entries
    history = []
    for h in history_list:
        if isinstance(h, dict):
            try:
                # Convert string timestamp to datetime if needed
                entry_data = h.copy()
                if "timestamp" in entry_data and isinstance(entry_data["timestamp"], str):
                    from datetime import datetime
                    entry_data["timestamp"] = datetime.fromisoformat(entry_data["timestamp"].replace("Z", "+00:00"))
                history.append(HistoryEntry(**entry_data))
            except Exception:
                # Skip invalid entries
                pass
        else:
            history.append(h)

    # Convert domain_info to DomainInfo schema only if it has required fields
    domain_info = None
    if isinstance(case.domain_info, dict) and case.domain_info.get("domain"):
        try:
            domain_info = DomainInfo(**case.domain_info)
        except Exception:
            pass

    # Use source column directly from database
    source = CaseSource(case.source) if case.source else CaseSource.INTERNAL

    # Convert abuse_contacts to list of AbuseContact
    abuse_contacts = []
    if isinstance(case.abuse_contacts, list):
        for contact in case.abuse_contacts:
            if isinstance(contact, dict):
                try:
                    abuse_contacts.append(AbuseContact(**contact))
                except Exception:
                    pass

    return CaseSchema(
        id=case.id,
        url=case.url,
        status=CaseStatus(case.status),
        source=source,
        domain_info=domain_info,
        abuse_contacts=abuse_contacts,
        history=history,
        monitor_interval=case.monitor_interval,
        brand_impacted=case.brand_impacted,
        created_by=str(case.created_by) if case.created_by else None,
        created_by_username=created_by_username,
        created_by_email=created_by_email,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def _case_to_summary(case: Case) -> CaseSummary:
    """Convert a Case model to a CaseSummary schema.

    Args:
        case: Case model instance

    Returns:
        CaseSummary instance
    """
    history_list = case.history if case.history is not None else []
    history_count = len(history_list) if isinstance(history_list, list) else 0
    has_domain_info = bool(case.domain_info) and bool(case.domain_info.get("domain"))

    # Use source column directly from database
    source = CaseSource(case.source) if case.source else CaseSource.INTERNAL

    return CaseSummary(
        id=case.id,
        url=case.url,
        status=CaseStatus(case.status),
        source=source,
        created_at=case.created_at,
        updated_at=case.updated_at,
        has_domain_info=has_domain_info,
        history_count=history_count,
    )


__all__ = ["router"]
