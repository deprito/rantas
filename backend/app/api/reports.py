"""Reports API endpoints for PhishTrack."""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_db
from app.models import GeneratedReport
from app.schemas import (
    GenerateReportResponse,
    ReportCreate,
    ReportListResponse,
    ReportResponse,
    ReportType,
)
from app.services.report_generator import generate_resolved_cases_csv

router = APIRouter(prefix="/reports", tags=["reports"])


async def generate_report_task(report_id: str, db: AsyncSession, user_id: str):
    """Background task to generate a report.

    Args:
        report_id: ID of the report to generate
        db: Database session
        user_id: ID of user who requested the report
    """
    from app.database import get_db_context

    async with get_db_context() as db:
        try:
            # Get the report record
            result = await db.execute(select(GeneratedReport).where(GeneratedReport.id == report_id))
            report = result.scalar_one_or_none()

            if not report:
                return

            # Generate the CSV report
            report_id_str, file_path, cases_count, file_size = await generate_resolved_cases_csv(
                db, user_id
            )

            # Update the report record
            report.file_path = file_path
            report.cases_count = cases_count
            report.file_size_bytes = file_size
            report.status = "completed"

            await db.commit()

        except Exception as e:
            # Update report status to failed
            result = await db.execute(select(GeneratedReport).where(GeneratedReport.id == report_id))
            report = result.scalar_one_or_none()

            if report:
                report.status = "failed"
                report.error_message = str(e)[:1000]
                await db.commit()


@router.post("/generate/resolved-cases", response_model=GenerateReportResponse)
async def generate_resolved_cases_report(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate CSV report of all resolved cases.

    The report is generated in the background. Use the GET /reports/{report_id}
    endpoint to check the status and GET /reports/{report_id}/download to download
    the completed report.
    """
    # Check if user has permission to generate reports
    # For now, any authenticated user can generate reports

    # Create the report record
    report = GeneratedReport(
        report_type="resolved_cases_csv",
        status="generating",
        created_by=str(current_user.id),
    )

    db.add(report)
    await db.commit()
    await db.refresh(report)

    # Schedule the background task
    background_tasks.add_task(generate_report_task, str(report.id), db, str(current_user.id))

    return GenerateReportResponse(
        report_id=report.id,
        status="generating",
        message="Report generation started. Use the report_id to check status.",
    )


@router.get("", response_model=ReportListResponse)
async def list_reports(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    report_type: Optional[ReportType] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List all generated reports.

    Args:
        current_user: Current authenticated user
        db: Database session
        report_type: Optional filter by report type
        limit: Maximum number of reports to return
        offset: Number of reports to skip

    Returns:
        List of reports
    """
    query = select(GeneratedReport).order_by(GeneratedReport.created_at.desc())

    if report_type:
        query = query.where(GeneratedReport.report_type == report_type.value)

    # Get total count
    from sqlalchemy import func

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    reports = result.scalars().all()

    return ReportListResponse(
        reports=[
            ReportResponse(
                id=report.id,
                report_type=report.report_type,
                status=report.status,
                file_path=report.file_path,
                created_at=report.created_at,
                created_by=report.created_by,
                cases_count=report.cases_count,
                file_size_bytes=report.file_size_bytes,
                error_message=report.error_message,
            )
            for report in reports
        ],
        total=total,
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific report.

    Args:
        report_id: ID of the report
        current_user: Current authenticated user
        db: Database session

    Returns:
        Report details
    """
    result = await db.execute(select(GeneratedReport).where(GeneratedReport.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    return ReportResponse(
        id=report.id,
        report_type=report.report_type,
        status=report.status,
        file_path=report.file_path,
        created_at=report.created_at,
        created_by=report.created_by,
        cases_count=report.cases_count,
        file_size_bytes=report.file_size_bytes,
        error_message=report.error_message,
    )


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Download a generated report file.

    Args:
        report_id: ID of the report
        current_user: Current authenticated user
        db: Database session

    Returns:
        CSV file download
    """
    result = await db.execute(select(GeneratedReport).where(GeneratedReport.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    if report.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report is not ready for download. Current status: {report.status}",
        )

    if not report.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file not found",
        )

    file_path = Path(report.file_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report file does not exist on disk",
        )

    # Generate filename for download
    filename = file_path.name

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="text/csv",
        content_disposition_type="attachment",
    )


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Delete a generated report.

    Args:
        report_id: ID of the report
        current_user: Current authenticated user
        db: Database session
    """
    result = await db.execute(select(GeneratedReport).where(GeneratedReport.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # Delete the file if it exists
    if report.file_path:
        from app.services.report_generator import delete_report

        delete_report(report.file_path)

    # Delete the database record
    await db.delete(report)
    await db.commit()

    return None
