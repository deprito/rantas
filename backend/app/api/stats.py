"""API endpoints for statistics and reporting dashboard."""
import csv
import io
from datetime import datetime, timedelta
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select, func, case as sql_case, and_, extract, union_all, or_
import os
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import PermissionChecker, get_current_active_user
from app.database import get_db
from app.models import Case, User, PublicSubmission, HistoricalCase
from app.permissions import Permission
from app.utils.dns import extract_domain_from_url
from app.schemas import (
    StatsOverview,
    StatusDistribution,
    StatusDistributionItem,
    TrendsResponse,
    TrendDataPoint,
    TopDomainsResponse,
    TopDomainItem,
    TopRegistrarsResponse,
    TopRegistrarItem,
    EmailEffectiveness,
    ResolutionMetrics,
    BrandImpactedResponse,
    BrandImpactedItem,
    PeriodType,
    CaseStatus,
    GenerateReportResponse,
    ReportStatus,
    UserStatsResponse,
    UserStatsItem,
    HistoricalCaseImport,
    ImportResponse,
)
from app.utils.timezone import now_utc

router = APIRouter(prefix="/stats", tags=["statistics"])

# Directory for static templates
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "templates")


@router.get("/overview", response_model=StatsOverview)
async def get_stats_overview(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_VIEW))],
    db: AsyncSession = Depends(get_db),
    start_date: Optional[datetime] = Query(None, description="Filter from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter until this date"),
    include_historical: bool = Query(False, description="Include imported historical data"),
) -> StatsOverview:
    """Get overview statistics for the dashboard.

    Args:
        current_user: Current authenticated user
        db: Database session
        start_date: Optional start date filter
        end_date: Optional end date filter
        include_historical: Include imported historical data

    Returns:
        Overview statistics
    """
    try:
        # Build date filter conditions
        date_filters = []
        if start_date:
            date_filters.append(Case.created_at >= start_date)
        if end_date:
            date_filters.append(Case.created_at <= end_date)

        # Base query for regular cases
        main_query = select(
            func.count(Case.id).label('total_cases'),
            func.sum(sql_case((Case.status == CaseStatus.RESOLVED.value, 1), else_=0)).label('resolved_cases'),
            func.sum(sql_case((Case.status == CaseStatus.FAILED.value, 1), else_=0)).label('failed_cases'),
            func.sum(sql_case(
                (and_(Case.status != CaseStatus.RESOLVED.value, Case.status != CaseStatus.FAILED.value), 1),
                else_=0
            )).label('active_cases'),
            func.coalesce(func.sum(Case.emails_sent), 0).label('total_emails'),
            func.avg(sql_case(
                (Case.status == CaseStatus.RESOLVED.value,
                 extract('epoch', Case.updated_at - Case.created_at) / 3600),
                else_=None
            )).label('avg_resolution_hours'),
            func.sum(sql_case((or_(Case.source == "internal", Case.source.is_(None)), 1), else_=0)).label('internal_cases'),
            func.sum(sql_case((Case.source == "public", 1), else_=0)).label('public_cases'),
        )

        if date_filters:
            main_query = main_query.where(and_(*date_filters))

        result = await db.execute(main_query)
        row = result.one()

        total_cases = row.total_cases or 0
        resolved_cases = row.resolved_cases or 0
        failed_cases = row.failed_cases or 0
        active_cases = row.active_cases or 0
        total_emails_sent = row.total_emails or 0
        average_resolution_time_hours = row.avg_resolution_hours
        internal_cases = row.internal_cases or 0
        public_cases = row.public_cases or 0

        # If include_historical, add historical case data
        if include_historical:
            hist_date_filters = []
            if start_date:
                hist_date_filters.append(HistoricalCase.created_at >= start_date)
            if end_date:
                hist_date_filters.append(HistoricalCase.created_at <= end_date)

            hist_query = select(
                func.count(HistoricalCase.id).label('total_cases'),
                func.sum(sql_case((HistoricalCase.status == CaseStatus.RESOLVED.value, 1), else_=0)).label('resolved_cases'),
                func.sum(sql_case((HistoricalCase.status == CaseStatus.FAILED.value, 1), else_=0)).label('failed_cases'),
                func.sum(sql_case(
                    (and_(HistoricalCase.status != CaseStatus.RESOLVED.value, HistoricalCase.status != CaseStatus.FAILED.value), 1),
                    else_=0
                )).label('active_cases'),
                func.coalesce(func.sum(HistoricalCase.emails_sent), 0).label('total_emails'),
                func.avg(sql_case(
                    (HistoricalCase.status == CaseStatus.RESOLVED.value,
                     extract('epoch', HistoricalCase.updated_at - HistoricalCase.created_at) / 3600),
                    else_=None
                )).label('avg_resolution_hours'),
                func.sum(sql_case((or_(HistoricalCase.source == "internal", HistoricalCase.source.is_(None)), 1), else_=0)).label('internal_cases'),
                func.sum(sql_case((HistoricalCase.source == "public", 1), else_=0)).label('public_cases'),
            )

            if hist_date_filters:
                hist_query = hist_query.where(and_(*hist_date_filters))

            hist_result = await db.execute(hist_query)
            hist_row = hist_result.one()

            total_cases += hist_row.total_cases or 0
            resolved_cases += hist_row.resolved_cases or 0
            failed_cases += hist_row.failed_cases or 0
            active_cases += hist_row.active_cases or 0
            total_emails_sent += hist_row.total_emails or 0

            # Recalculate average resolution time combining both datasets
            if average_resolution_time_hours and hist_row.avg_resolution_hours:
                avg_resolved = (row.resolved_cases or 0) + (hist_row.resolved_cases or 0)
                if avg_resolved > 0:
                    average_resolution_time_hours = (
                        (average_resolution_time_hours * (row.resolved_cases or 0) +
                         hist_row.avg_resolution_hours * (hist_row.resolved_cases or 0)) / avg_resolved
                    )
            elif hist_row.avg_resolution_hours:
                average_resolution_time_hours = hist_row.avg_resolution_hours

            internal_cases += hist_row.internal_cases or 0
            public_cases += hist_row.public_cases or 0

        # Calculate success rate
        terminal_cases = resolved_cases + failed_cases
        success_rate = (resolved_cases / terminal_cases * 100) if terminal_cases > 0 else 0.0

        # OPTIMIZED: Today's stats in a single query (only regular cases for today)
        today_start = now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
        today_query = select(
            func.count(Case.id).filter(Case.created_at >= today_start).label('created_today'),
            func.count(Case.id).filter(
                and_(Case.status == CaseStatus.RESOLVED.value, Case.updated_at >= today_start)
            ).label('resolved_today'),
        )
        today_result = await db.execute(today_query)
        today_row = today_result.one()
        cases_created_today = today_row.created_today or 0
        cases_resolved_today = today_row.resolved_today or 0

        # Pending submissions (separate table)
        pending_submissions_result = await db.execute(
            select(func.count(PublicSubmission.id)).where(
                PublicSubmission.status == "pending"
            )
        )
        pending_submissions = pending_submissions_result.scalar() or 0

        # Brand impacted statistics - combine both tables if include_historical
        brand_counts: dict[str, int] = {}
        cases_with_brand = 0
        cases_without_brand = 0

        # Process regular cases
        brand_query = select(Case.brand_impacted, func.count(Case.id)).group_by(Case.brand_impacted)
        if date_filters:
            brand_query = brand_query.where(and_(*date_filters))

        brand_result = await db.execute(brand_query)
        brand_rows = brand_result.all()

        for brand, count in brand_rows:
            if brand:
                brand_counts[brand] = brand_counts.get(brand, 0) + count
                cases_with_brand += count
            else:
                cases_without_brand += count

        # Process historical cases if include_historical
        if include_historical:
            hist_brand_query = select(HistoricalCase.brand_impacted, func.count(HistoricalCase.id)).group_by(HistoricalCase.brand_impacted)
            hist_date_filters = []
            if start_date:
                hist_date_filters.append(HistoricalCase.created_at >= start_date)
            if end_date:
                hist_date_filters.append(HistoricalCase.created_at <= end_date)
            if hist_date_filters:
                hist_brand_query = hist_brand_query.where(and_(*hist_date_filters))

            hist_brand_result = await db.execute(hist_brand_query)
            hist_brand_rows = hist_brand_result.all()

            for brand, count in hist_brand_rows:
                if brand:
                    brand_counts[brand] = brand_counts.get(brand, 0) + count
                    cases_with_brand += count
                else:
                    cases_without_brand += count

        # Get top 5 brands
        top_brands = [brand for brand, _ in sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)][:5]

        return StatsOverview(
            total_cases=total_cases,
            active_cases=active_cases,
            resolved_cases=resolved_cases,
            failed_cases=failed_cases,
            success_rate=round(success_rate, 2),
            average_resolution_time_hours=round(average_resolution_time_hours, 2) if average_resolution_time_hours else None,
            total_emails_sent=total_emails_sent,
            cases_created_today=cases_created_today,
            cases_resolved_today=cases_resolved_today,
            internal_cases=internal_cases,
            public_cases=public_cases,
            pending_submissions=pending_submissions,
            top_brands=top_brands,
            total_cases_with_brand=cases_with_brand,
            total_cases_without_brand=cases_without_brand,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get overview stats: {str(e)}",
        )


@router.get("/status-distribution", response_model=StatusDistribution)
async def get_status_distribution(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_VIEW))],
    db: AsyncSession = Depends(get_db),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    include_historical: bool = Query(False, description="Include imported historical data"),
) -> StatusDistribution:
    """Get case status distribution for pie chart.

    Args:
        current_user: Current authenticated user
        db: Database session
        start_date: Optional start date filter
        end_date: Optional end date filter
        include_historical: Include imported historical data

    Returns:
        Status distribution data
    """
    try:
        # Query for regular cases
        query = select(Case.status, func.count(Case.id)).group_by(Case.status)
        if start_date:
            query = query.where(Case.created_at >= start_date)
        if end_date:
            query = query.where(Case.created_at <= end_date)

        result = await db.execute(query)
        status_counts_dict: dict[str, int] = {status: count for status, count in result.all()}

        # Add historical cases if requested
        if include_historical:
            hist_query = select(HistoricalCase.status, func.count(HistoricalCase.id)).group_by(HistoricalCase.status)
            if start_date:
                hist_query = hist_query.where(HistoricalCase.created_at >= start_date)
            if end_date:
                hist_query = hist_query.where(HistoricalCase.created_at <= end_date)

            hist_result = await db.execute(hist_query)
            for status, count in hist_result.all():
                status_counts_dict[status] = status_counts_dict.get(status, 0) + count

        total = sum(status_counts_dict.values())

        distribution = [
            StatusDistributionItem(
                status=status_val,
                count=count,
                percentage=round((count / total * 100) if total > 0 else 0, 2),
            )
            for status_val, count in status_counts_dict.items()
        ]

        return StatusDistribution(distribution=distribution, total=total)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status distribution: {str(e)}",
        )


@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_VIEW))],
    db: AsyncSession = Depends(get_db),
    period: PeriodType = Query(PeriodType.WEEK, description="Time period for grouping"),
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    include_historical: bool = Query(False, description="Include imported historical data"),
) -> TrendsResponse:
    """Get case trends over time for line chart.

    Args:
        current_user: Current authenticated user
        db: Database session
        period: Grouping period (day, week, month)
        days: Number of days to look back
        include_historical: Include imported historical data

    Returns:
        Trends data
    """
    try:
        end_date = now_utc()
        start_date = end_date - timedelta(days=days)

        # Get all cases in the date range
        cases_result = await db.execute(
            select(Case).where(Case.created_at >= start_date)
        )
        cases = cases_result.scalars().all()

        # Build date-based aggregation
        data_points: dict[str, TrendDataPoint] = {}

        # Generate all date keys in the range
        current_date = start_date.date()
        while current_date <= end_date.date():
            if period == PeriodType.DAY:
                date_key = current_date.isoformat()
            elif period == PeriodType.WEEK:
                # Start of week (Monday)
                week_start = current_date - timedelta(days=current_date.weekday())
                date_key = week_start.isoformat()
            else:  # MONTH
                date_key = f"{current_date.year}-{current_date.month:02d}-01"

            if date_key not in data_points:
                data_points[date_key] = TrendDataPoint(
                    date=date_key,
                    created=0,
                    resolved=0,
                    failed=0,
                )

            current_date += timedelta(days=1)

        # Aggregate case data
        for case in cases:
            case_date = case.created_at.date()
            if period == PeriodType.DAY:
                date_key = case_date.isoformat()
            elif period == PeriodType.WEEK:
                week_start = case_date - timedelta(days=case_date.weekday())
                date_key = week_start.isoformat()
            else:  # MONTH
                date_key = f"{case_date.year}-{case_date.month:02d}-01"

            if date_key in data_points:
                data_points[date_key].created += 1

                if case.status == CaseStatus.RESOLVED.value:
                    data_points[date_key].resolved += 1
                elif case.status == CaseStatus.FAILED.value:
                    data_points[date_key].failed += 1

        # Add historical cases if requested
        if include_historical:
            hist_cases_result = await db.execute(
                select(HistoricalCase).where(HistoricalCase.created_at >= start_date)
            )
            hist_cases = hist_cases_result.scalars().all()

            for case in hist_cases:
                case_date = case.created_at.date()
                if period == PeriodType.DAY:
                    date_key = case_date.isoformat()
                elif period == PeriodType.WEEK:
                    week_start = case_date - timedelta(days=case_date.weekday())
                    date_key = week_start.isoformat()
                else:  # MONTH
                    date_key = f"{case_date.year}-{case_date.month:02d}-01"

                if date_key in data_points:
                    data_points[date_key].created += 1

                    if case.status == CaseStatus.RESOLVED.value:
                        data_points[date_key].resolved += 1
                    elif case.status == CaseStatus.FAILED.value:
                        data_points[date_key].failed += 1

        # Sort by date
        sorted_data = sorted(data_points.values(), key=lambda x: x.date)

        return TrendsResponse(
            period=period.value,
            start_date=start_date.date().isoformat(),
            end_date=end_date.date().isoformat(),
            data=sorted_data,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trends: {str(e)}",
        )


@router.get("/top-domains", response_model=TopDomainsResponse)
async def get_top_domains(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_VIEW))],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=50, description="Number of domains to return"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    include_historical: bool = Query(False, description="Include imported historical data"),
) -> TopDomainsResponse:
    """Get top reported domains.

    Args:
        current_user: Current authenticated user
        db: Database session
        limit: Number of domains to return
        start_date: Optional start date filter
        end_date: Optional end date filter
        include_historical: Include imported historical data

    Returns:
        Top domains data
    """
    try:
        query = select(Case)
        if start_date:
            query = query.where(Case.created_at >= start_date)
        if end_date:
            query = query.where(Case.created_at <= end_date)

        result = await db.execute(query)
        cases = result.scalars().all()

        # Aggregate by domain
        domain_stats: dict[str, dict] = {}
        for case in cases:
            domain = extract_domain_from_url(case.url)
            if domain not in domain_stats:
                domain_stats[domain] = {
                    "case_count": 0,
                    "resolved_count": 0,
                    "failed_count": 0,
                }
            domain_stats[domain]["case_count"] += 1
            if case.status == CaseStatus.RESOLVED.value:
                domain_stats[domain]["resolved_count"] += 1
            elif case.status == CaseStatus.FAILED.value:
                domain_stats[domain]["failed_count"] += 1

        # Add historical cases if requested
        if include_historical:
            hist_query = select(HistoricalCase)
            if start_date:
                hist_query = hist_query.where(HistoricalCase.created_at >= start_date)
            if end_date:
                hist_query = hist_query.where(HistoricalCase.created_at <= end_date)

            hist_result = await db.execute(hist_query)
            hist_cases = hist_result.scalars().all()

            for case in hist_cases:
                domain = extract_domain_from_url(case.url)
                if domain not in domain_stats:
                    domain_stats[domain] = {
                        "case_count": 0,
                        "resolved_count": 0,
                        "failed_count": 0,
                    }
                domain_stats[domain]["case_count"] += 1
                if case.status == CaseStatus.RESOLVED.value:
                    domain_stats[domain]["resolved_count"] += 1
                elif case.status == CaseStatus.FAILED.value:
                    domain_stats[domain]["failed_count"] += 1

        # Convert to list and sort
        domains = []
        for domain, stats in domain_stats.items():
            total = stats["resolved_count"] + stats["failed_count"]
            resolution_rate = (stats["resolved_count"] / total * 100) if total > 0 else 0
            domains.append(
                TopDomainItem(
                    domain=domain,
                    case_count=stats["case_count"],
                    resolved_count=stats["resolved_count"],
                    failed_count=stats["failed_count"],
                    resolution_rate=round(resolution_rate, 2),
                )
            )

        # Sort by case count and limit
        domains.sort(key=lambda x: x.case_count, reverse=True)
        domains = domains[:limit]

        return TopDomainsResponse(domains=domains, total=len(domain_stats))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get top domains: {str(e)}",
        )


@router.get("/top-registrars", response_model=TopRegistrarsResponse)
async def get_top_registrars(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_VIEW))],
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=50, description="Number of registrars to return"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    include_historical: bool = Query(False, description="Include imported historical data"),
) -> TopRegistrarsResponse:
    """Get top registrars by case count.

    Args:
        current_user: Current authenticated user
        db: Database session
        limit: Number of registrars to return
        start_date: Optional start date filter
        end_date: Optional end date filter
        include_historical: Include imported historical data

    Returns:
        Top registrars data
    """
    try:
        query = select(Case)
        if start_date:
            query = query.where(Case.created_at >= start_date)
        if end_date:
            query = query.where(Case.created_at <= end_date)

        result = await db.execute(query)
        cases = result.scalars().all()

        # Aggregate by registrar
        registrar_stats: dict[str, dict] = {}
        for case in cases:
            registrar = None
            if isinstance(case.domain_info, dict):
                registrar = case.domain_info.get("registrar")
            if not registrar:
                registrar = "Unknown"

            if registrar not in registrar_stats:
                registrar_stats[registrar] = {
                    "case_count": 0,
                    "resolved_count": 0,
                    "total_resolution_hours": 0,
                }
            registrar_stats[registrar]["case_count"] += 1

            if case.status == CaseStatus.RESOLVED.value:
                registrar_stats[registrar]["resolved_count"] += 1
                # Calculate resolution time in hours
                if case.created_at and case.updated_at:
                    delta = case.updated_at - case.created_at
                    hours = delta.total_seconds() / 3600
                    registrar_stats[registrar]["total_resolution_hours"] += hours

        # Add historical cases if requested
        if include_historical:
            hist_query = select(HistoricalCase)
            if start_date:
                hist_query = hist_query.where(HistoricalCase.created_at >= start_date)
            if end_date:
                hist_query = hist_query.where(HistoricalCase.created_at <= end_date)

            hist_result = await db.execute(hist_query)
            hist_cases = hist_result.scalars().all()

            for case in hist_cases:
                registrar = None
                if isinstance(case.domain_info, dict):
                    registrar = case.domain_info.get("registrar")
                if not registrar:
                    registrar = "Unknown"

                if registrar not in registrar_stats:
                    registrar_stats[registrar] = {
                        "case_count": 0,
                        "resolved_count": 0,
                        "total_resolution_hours": 0,
                    }
                registrar_stats[registrar]["case_count"] += 1

                if case.status == CaseStatus.RESOLVED.value:
                    registrar_stats[registrar]["resolved_count"] += 1
                    # Calculate resolution time in hours
                    if case.created_at and case.updated_at:
                        delta = case.updated_at - case.created_at
                        hours = delta.total_seconds() / 3600
                        registrar_stats[registrar]["total_resolution_hours"] += hours

        # Convert to list
        registrars = []
        for registrar, stats in registrar_stats.items():
            resolution_rate = (
                (stats["resolved_count"] / stats["case_count"] * 100)
                if stats["case_count"] > 0 else 0
            )
            avg_resolution = (
                (stats["total_resolution_hours"] / stats["resolved_count"])
                if stats["resolved_count"] > 0 else None
            )
            registrars.append(
                TopRegistrarItem(
                    registrar=registrar,
                    case_count=stats["case_count"],
                    resolved_count=stats["resolved_count"],
                    resolution_rate=round(resolution_rate, 2),
                    avg_resolution_hours=round(avg_resolution, 2) if avg_resolution else None,
                )
            )

        # Sort by case count and limit
        registrars.sort(key=lambda x: x.case_count, reverse=True)
        registrars = registrars[:limit]

        return TopRegistrarsResponse(registrars=registrars, total=len(registrar_stats))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get top registrars: {str(e)}",
        )


@router.get("/email-effectiveness", response_model=EmailEffectiveness)
async def get_email_effectiveness(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_VIEW))],
    db: AsyncSession = Depends(get_db),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    include_historical: bool = Query(False, description="Include imported historical data"),
) -> EmailEffectiveness:
    """Get email effectiveness metrics.

    Args:
        current_user: Current authenticated user
        db: Database session
        start_date: Optional start date filter
        end_date: Optional end date filter
        include_historical: Include imported historical data

    Returns:
        Email effectiveness metrics
    """
    try:
        date_filters = []
        if start_date:
            date_filters.append(Case.created_at >= start_date)
        if end_date:
            date_filters.append(Case.created_at <= end_date)

        query = select(
            func.coalesce(func.sum(Case.emails_sent), 0).label('total_emails_sent'),
            func.count(Case.id).filter(Case.emails_sent > 0).label('cases_with_emails'),
            func.count(Case.id).filter(
                and_(Case.emails_sent > 0, Case.status == CaseStatus.RESOLVED.value)
            ).label('cases_resolved_after_email'),
        )

        if date_filters:
            query = query.where(and_(*date_filters))

        result = await db.execute(query)
        row = result.one()

        total_emails_sent = row.total_emails_sent or 0
        cases_with_emails = row.cases_with_emails or 0
        cases_resolved_after_email = row.cases_resolved_after_email or 0

        # Add historical cases if requested
        if include_historical:
            hist_date_filters = []
            if start_date:
                hist_date_filters.append(HistoricalCase.created_at >= start_date)
            if end_date:
                hist_date_filters.append(HistoricalCase.created_at <= end_date)

            hist_query = select(
                func.coalesce(func.sum(HistoricalCase.emails_sent), 0).label('total_emails_sent'),
                func.count(HistoricalCase.id).filter(HistoricalCase.emails_sent > 0).label('cases_with_emails'),
                func.count(HistoricalCase.id).filter(
                    and_(HistoricalCase.emails_sent > 0, HistoricalCase.status == CaseStatus.RESOLVED.value)
                ).label('cases_resolved_after_email'),
            )

            if hist_date_filters:
                hist_query = hist_query.where(and_(*hist_date_filters))

            hist_result = await db.execute(hist_query)
            hist_row = hist_result.one()

            total_emails_sent += hist_row.total_emails_sent or 0
            cases_with_emails += hist_row.cases_with_emails or 0
            cases_resolved_after_email += hist_row.cases_resolved_after_email or 0

        avg_emails_per_case = (
            total_emails_sent / cases_with_emails if cases_with_emails > 0 else 0
        )
        email_success_rate = (
            (cases_resolved_after_email / cases_with_emails * 100)
            if cases_with_emails > 0 else 0
        )

        return EmailEffectiveness(
            total_emails_sent=total_emails_sent,
            cases_with_emails=cases_with_emails,
            avg_emails_per_case=round(avg_emails_per_case, 2),
            cases_resolved_after_email=cases_resolved_after_email,
            email_success_rate=round(email_success_rate, 2),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get email effectiveness: {str(e)}",
        )



@router.get("/resolution-metrics", response_model=ResolutionMetrics)
async def get_resolution_metrics(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_VIEW))],
    db: AsyncSession = Depends(get_db),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    include_historical: bool = Query(False, description="Include imported historical data"),
) -> ResolutionMetrics:
    """Get resolution time metrics.

    Args:
        current_user: Current authenticated user
        db: Database session
        start_date: Optional start date filter
        end_date: Optional end date filter
        include_historical: Include imported historical data

    Returns:
        Resolution metrics
    """
    try:
        # Build date filters
        date_filters = [Case.status == CaseStatus.RESOLVED.value]
        if start_date:
            date_filters.append(Case.created_at >= start_date)
        if end_date:
            date_filters.append(Case.created_at <= end_date)

        resolution_hours_expr = extract('epoch', Case.updated_at - Case.created_at) / 3600

        agg_query = select(
            func.count(Case.id).label('resolved_count'),
            func.avg(resolution_hours_expr).label('avg_hours'),
            func.min(resolution_hours_expr).label('min_hours'),
            func.max(resolution_hours_expr).label('max_hours'),
        ).where(and_(*date_filters))

        result = await db.execute(agg_query)
        row = result.one()

        resolved_count = row.resolved_count or 0

        if resolved_count == 0:
            # Try historical cases if include_historical is True
            if include_historical:
                hist_date_filters = [HistoricalCase.status == CaseStatus.RESOLVED.value]
                if start_date:
                    hist_date_filters.append(HistoricalCase.created_at >= start_date)
                if end_date:
                    hist_date_filters.append(HistoricalCase.created_at <= end_date)

                hist_resolution_hours_expr = extract('epoch', HistoricalCase.updated_at - HistoricalCase.created_at) / 3600

                hist_agg_query = select(
                    func.count(HistoricalCase.id).label('resolved_count'),
                    func.avg(hist_resolution_hours_expr).label('avg_hours'),
                    func.min(hist_resolution_hours_expr).label('min_hours'),
                    func.max(hist_resolution_hours_expr).label('max_hours'),
                ).where(and_(*hist_date_filters))

                hist_result = await db.execute(hist_agg_query)
                hist_row = hist_result.one()

                resolved_count = hist_row.resolved_count or 0
                if resolved_count == 0:
                    return ResolutionMetrics(resolved_count=0)

                avg_hours = hist_row.avg_hours
                min_hours = hist_row.min_hours
                max_hours = hist_row.max_hours

                # Get median from historical cases
                median_query = (
                    select(hist_resolution_hours_expr.label('hours'))
                    .where(and_(*hist_date_filters))
                    .order_by(hist_resolution_hours_expr)
                )
                times_result = await db.execute(median_query)
                resolution_times = [r.hours for r in times_result.all() if r.hours is not None]

                if not resolution_times:
                    return ResolutionMetrics(resolved_count=resolved_count)

                n = len(resolution_times)
                if n % 2 == 0:
                    median_hours = (resolution_times[n // 2 - 1] + resolution_times[n // 2]) / 2
                else:
                    median_hours = resolution_times[n // 2]

                return ResolutionMetrics(
                    average_hours=round(avg_hours, 2) if avg_hours else None,
                    median_hours=round(median_hours, 2),
                    min_hours=round(min_hours, 2) if min_hours else None,
                    max_hours=round(max_hours, 2) if max_hours else None,
                    resolved_count=resolved_count,
                )
            return ResolutionMetrics(resolved_count=0)

        avg_hours = row.avg_hours
        min_hours = row.min_hours
        max_hours = row.max_hours

        # For median, get resolution times from regular cases
        median_query = (
            select(resolution_hours_expr.label('hours'))
            .where(and_(*date_filters))
            .order_by(resolution_hours_expr)
        )
        times_result = await db.execute(median_query)
        resolution_times = [r.hours for r in times_result.all() if r.hours is not None]

        # Add historical cases if requested
        if include_historical:
            hist_date_filters = [HistoricalCase.status == CaseStatus.RESOLVED.value]
            if start_date:
                hist_date_filters.append(HistoricalCase.created_at >= start_date)
            if end_date:
                hist_date_filters.append(HistoricalCase.created_at <= end_date)

            hist_resolution_hours_expr = extract('epoch', HistoricalCase.updated_at - HistoricalCase.created_at) / 3600

            hist_median_query = (
                select(hist_resolution_hours_expr.label('hours'))
                .where(and_(*hist_date_filters))
                .order_by(hist_resolution_hours_expr)
            )
            hist_times_result = await db.execute(hist_median_query)
            hist_resolution_times = [r.hours for r in hist_times_result.all() if r.hours is not None]

            # Merge and recalculate stats with historical data
            resolution_times.extend(hist_resolution_times)
            resolved_count += len(hist_resolution_times)

            # Recalculate avg, min, max with combined data
            if hist_resolution_times:
                hist_avg_query = select(
                    func.avg(hist_resolution_hours_expr).label('avg_hours'),
                    func.min(hist_resolution_hours_expr).label('min_hours'),
                    func.max(hist_resolution_hours_expr).label('max_hours'),
                ).where(and_(*hist_date_filters))
                hist_agg_result = await db.execute(hist_avg_query)
                hist_agg_row = hist_agg_result.one()

                # Combine averages
                if avg_hours and hist_agg_row.avg_hours:
                    total_resolved = (row.resolved_count or 0) + (len(hist_resolution_times))
                    avg_hours = (avg_hours * (row.resolved_count or 0) + hist_agg_row.avg_hours * len(hist_resolution_times)) / total_resolved
                elif hist_agg_row.avg_hours:
                    avg_hours = hist_agg_row.avg_hours

                min_hours = min(min_hours or float('inf'), hist_agg_row.min_hours or float('inf'))
                max_hours = max(max_hours or 0, hist_agg_row.max_hours or 0)

        if not resolution_times:
            return ResolutionMetrics(resolved_count=resolved_count)

        n = len(resolution_times)
        resolution_times.sort()
        if n % 2 == 0:
            median_hours = (resolution_times[n // 2 - 1] + resolution_times[n // 2]) / 2
        else:
            median_hours = resolution_times[n // 2]

        return ResolutionMetrics(
            average_hours=round(avg_hours, 2) if avg_hours else None,
            median_hours=round(median_hours, 2),
            min_hours=round(min_hours, 2) if min_hours else None,
            max_hours=round(max_hours, 2) if max_hours else None,
            resolved_count=resolved_count,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get resolution metrics: {str(e)}",
        )


@router.get("/brand-impacted", response_model=BrandImpactedResponse)
async def get_brand_impacted_stats(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_VIEW))],
    db: AsyncSession = Depends(get_db),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    include_historical: bool = Query(False, description="Include imported historical data"),
) -> BrandImpactedResponse:
    """Get statistics by brand impacted.

    Args:
        current_user: Current authenticated user
        db: Database session
        start_date: Optional start date filter
        end_date: Optional end date filter
        include_historical: Include imported historical data

    Returns:
        Brand impacted statistics
    """
    try:
        # Build date filters
        date_filters = []
        if start_date:
            date_filters.append(Case.created_at >= start_date)
        if end_date:
            date_filters.append(Case.created_at <= end_date)

        # Query for cases grouped by brand_impacted
        query = select(Case)
        if date_filters:
            query = query.where(and_(*date_filters))

        result = await db.execute(query)
        cases = result.scalars().all()

        # Aggregate by brand
        brand_stats: dict[str, dict] = {}
        cases_without_brand = 0

        for case in cases:
            brand = case.brand_impacted
            if not brand:
                cases_without_brand += 1
                continue

            if brand not in brand_stats:
                brand_stats[brand] = {
                    "case_count": 0,
                    "resolved_count": 0,
                    "failed_count": 0,
                }

            brand_stats[brand]["case_count"] += 1
            if case.status == CaseStatus.RESOLVED.value:
                brand_stats[brand]["resolved_count"] += 1
            elif case.status == CaseStatus.FAILED.value:
                brand_stats[brand]["failed_count"] += 1

        # Add historical cases if requested
        if include_historical:
            hist_date_filters = []
            if start_date:
                hist_date_filters.append(HistoricalCase.created_at >= start_date)
            if end_date:
                hist_date_filters.append(HistoricalCase.created_at <= end_date)

            hist_query = select(HistoricalCase)
            if hist_date_filters:
                hist_query = hist_query.where(and_(*hist_date_filters))

            hist_result = await db.execute(hist_query)
            hist_cases = hist_result.scalars().all()

            for case in hist_cases:
                brand = case.brand_impacted
                if not brand:
                    cases_without_brand += 1
                    continue

                if brand not in brand_stats:
                    brand_stats[brand] = {
                        "case_count": 0,
                        "resolved_count": 0,
                        "failed_count": 0,
                    }

                brand_stats[brand]["case_count"] += 1
                if case.status == CaseStatus.RESOLVED.value:
                    brand_stats[brand]["resolved_count"] += 1
                elif case.status == CaseStatus.FAILED.value:
                    brand_stats[brand]["failed_count"] += 1

        # Convert to list and calculate resolution rates
        brands = []
        for brand, stats in brand_stats.items():
            terminal_cases = stats["resolved_count"] + stats["failed_count"]
            resolution_rate = (
                (stats["resolved_count"] / terminal_cases * 100)
                if terminal_cases > 0 else 0
            )
            brands.append(
                BrandImpactedItem(
                    brand=brand,
                    case_count=stats["case_count"],
                    resolved_count=stats["resolved_count"],
                    failed_count=stats["failed_count"],
                    resolution_rate=round(resolution_rate, 2),
                )
            )

        # Sort by case count descending
        brands.sort(key=lambda x: x.case_count, reverse=True)

        total_with_brand = sum(b.case_count for b in brands)

        return BrandImpactedResponse(
            brands=brands,
            total_cases_with_brand=total_with_brand,
            total_cases_without_brand=cases_without_brand,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get brand impacted stats: {str(e)}",
        )


@router.get("/users", response_model=UserStatsResponse)
async def get_user_stats(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_VIEW))],
    db: AsyncSession = Depends(get_db),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    include_historical: bool = Query(False, description="Include imported historical data"),
) -> UserStatsResponse:
    """Get user statistics leaderboard.

    Args:
        current_user: Current authenticated user
        db: Database session
        start_date: Optional start date filter
        end_date: Optional end date filter
        include_historical: Include imported historical data

    Returns:
        User statistics leaderboard ranked by total cases
    """
    try:
        # Build date filters
        date_filters = []
        if start_date:
            date_filters.append(Case.created_at >= start_date)
        if end_date:
            date_filters.append(Case.created_at <= end_date)

        # Query for cases with user information
        query = select(Case).where(Case.created_by.is_not(None))
        if date_filters:
            query = query.where(and_(*date_filters))

        result = await db.execute(query)
        cases = result.scalars().all()

        # Aggregate by user
        user_stats: dict[str, dict] = {}
        user_info_cache: dict[str, dict] = {}  # Cache user info

        for case in cases:
            user_id = case.created_by
            if not user_id:
                continue

            # Initialize user stats if not exists
            if user_id not in user_stats:
                user_stats[user_id] = {
                    "total_cases": 0,
                    "internal_cases": 0,
                    "public_cases": 0,
                    "resolved_count": 0,
                    "failed_count": 0,
                }

            user_stats[user_id]["total_cases"] += 1

            # Count by source
            if case.source == "public":
                user_stats[user_id]["public_cases"] += 1
            else:
                user_stats[user_id]["internal_cases"] += 1

            # Count terminal statuses
            if case.status == CaseStatus.RESOLVED.value:
                user_stats[user_id]["resolved_count"] += 1
            elif case.status == CaseStatus.FAILED.value:
                user_stats[user_id]["failed_count"] += 1

        # Add historical cases if requested
        if include_historical:
            hist_date_filters = []
            if start_date:
                hist_date_filters.append(HistoricalCase.created_at >= start_date)
            if end_date:
                hist_date_filters.append(HistoricalCase.created_at <= end_date)

            # Query historical cases with reported_by
            hist_query = select(HistoricalCase).where(HistoricalCase.reported_by.is_not(None))
            if hist_date_filters:
                hist_query = hist_query.where(and_(*hist_date_filters))

            hist_result = await db.execute(hist_query)
            hist_cases = hist_result.scalars().all()

            for case in hist_cases:
                user_id = case.reported_by
                if not user_id:
                    continue

                # Initialize user stats if not exists
                if user_id not in user_stats:
                    user_stats[user_id] = {
                        "total_cases": 0,
                        "internal_cases": 0,
                        "public_cases": 0,
                        "resolved_count": 0,
                        "failed_count": 0,
                    }

                user_stats[user_id]["total_cases"] += 1

                # Count by source
                if case.source == "public":
                    user_stats[user_id]["public_cases"] += 1
                else:
                    user_stats[user_id]["internal_cases"] += 1

                # Count terminal statuses
                if case.status == CaseStatus.RESOLVED.value:
                    user_stats[user_id]["resolved_count"] += 1
                elif case.status == CaseStatus.FAILED.value:
                    user_stats[user_id]["failed_count"] += 1

        # If no cases with creators, return empty response
        if not user_stats:
            return UserStatsResponse(users=[], total=0)

        # Fetch user information for all user_ids
        user_ids = list(user_stats.keys())
        users_result = await db.execute(
            select(User.id, User.username, User.email).where(User.id.in_(user_ids))
        )
        users_data = users_result.all()

        # Build user info cache
        for user_id, username, email in users_data:
            user_info_cache[user_id] = {
                "username": username,
                "email": email,
            }

        # Convert to list and calculate resolution rates
        users = []
        for user_id, stats in user_stats.items():
            user_info = user_info_cache.get(user_id, {"username": "Unknown", "email": ""})
            terminal_cases = stats["resolved_count"] + stats["failed_count"]
            resolution_rate = (
                (stats["resolved_count"] / terminal_cases * 100)
                if terminal_cases > 0 else 0
            )
            users.append(
                UserStatsItem(
                    user_id=user_id,
                    username=user_info["username"],
                    email=user_info["email"],
                    total_cases=stats["total_cases"],
                    internal_cases=stats["internal_cases"],
                    public_cases=stats["public_cases"],
                    resolved_count=stats["resolved_count"],
                    failed_count=stats["failed_count"],
                    resolution_rate=round(resolution_rate, 2),
                )
            )

        # Sort by total cases descending
        users.sort(key=lambda x: x.total_cases, reverse=True)

        return UserStatsResponse(users=users, total=len(users))

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user stats: {str(e)}",
        )


@router.get("/export/csv")
async def export_csv(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_EXPORT))],
    db: AsyncSession = Depends(get_db),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    status_filter: Optional[CaseStatus] = Query(None),
) -> StreamingResponse:
    """Export cases as CSV file.

    Args:
        current_user: Current authenticated user
        db: Database session
        start_date: Optional start date filter
        end_date: Optional end date filter
        status_filter: Optional status filter

    Returns:
        CSV file download
    """
    try:
        query = select(Case)
        if start_date:
            query = query.where(Case.created_at >= start_date)
        if end_date:
            query = query.where(Case.created_at <= end_date)
        if status_filter:
            query = query.where(Case.status == status_filter.value)

        query = query.order_by(Case.created_at.desc())

        result = await db.execute(query)
        cases = result.scalars().all()

        # Collect all unique user_ids from cases for creator lookup
        user_ids = list(set([case.created_by for case in cases if case.created_by]))
        user_info_cache: dict[str, str] = {}

        if user_ids:
            users_result = await db.execute(
                select(User.id, User.username).where(User.id.in_(user_ids))
            )
            for user_id, username in users_result:
                user_info_cache[user_id] = username

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "ID",
            "URL",
            "Status",
            "Domain",
            "Registrar",
            "IP",
            "Brand Impacted",
            "Emails Sent",
            "Created By",
            "Created At",
            "Updated At",
            "Resolution Time (hours)",
        ])

        # Data rows
        for case in cases:
            domain = ""
            registrar = ""
            ip = ""
            if isinstance(case.domain_info, dict):
                domain = case.domain_info.get("domain", "")
                registrar = case.domain_info.get("registrar", "")
                ip = case.domain_info.get("ip", "")

            resolution_hours = ""
            if case.status == CaseStatus.RESOLVED.value and case.created_at and case.updated_at:
                delta = case.updated_at - case.created_at
                resolution_hours = round(delta.total_seconds() / 3600, 2)

            created_by = user_info_cache.get(str(case.created_by), "") if case.created_by else ""

            writer.writerow([
                case.id,
                case.url,
                case.status,
                domain,
                registrar,
                ip,
                case.brand_impacted or "",
                case.emails_sent,
                created_by,
                case.created_at.isoformat() if case.created_at else "",
                case.updated_at.isoformat() if case.updated_at else "",
                resolution_hours,
            ])

        output.seek(0)

        # Generate filename with timestamp
        timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
        filename = f"phishtrack_cases_{timestamp}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export CSV: {str(e)}",
        )


@router.post("/export/pdf", response_model=GenerateReportResponse)
async def export_pdf(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_EXPORT))],
    db: AsyncSession = Depends(get_db),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
) -> GenerateReportResponse:
    """Generate PDF report (queues a background task).

    Args:
        current_user: Current authenticated user
        db: Database session
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        Report generation response with report ID
    """
    try:
        from uuid import uuid4
        from app.models import GeneratedReport

        # Create report record
        report = GeneratedReport(
            report_type="stats_dashboard_pdf",
            status="generating",
            created_by=current_user.id,
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)

        # Queue PDF generation task
        from app.services.pdf_generator import generate_stats_pdf_task
        generate_stats_pdf_task.delay(
            str(report.id),
            start_date.isoformat() if start_date else None,
            end_date.isoformat() if end_date else None,
        )

        return GenerateReportResponse(
            report_id=report.id,
            status=ReportStatus.GENERATING,
            message="PDF generation started. Check report status for completion.",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start PDF generation: {str(e)}",
        )


@router.get("/template")
async def download_template(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_IMPORT))],
) -> FileResponse:
    """Download CSV template for historical case import.

    Args:
        current_user: Current authenticated user with stats:import permission

    Returns:
        CSV template file download
    """
    template_path = os.path.join(TEMPLATES_DIR, "historical_cases_template.csv")
    if not os.path.exists(template_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template file not found"
        )
    return FileResponse(
        template_path,
        media_type="text/csv",
        filename="historical_cases_template.csv",
    )


@router.post("/import", response_model=ImportResponse)
async def import_historical_cases(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.STATS_IMPORT))],
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(..., description="CSV file with historical case data"),
) -> ImportResponse:
    """Import historical cases from CSV file.

    Args:
        current_user: Current authenticated user with stats:import permission
        db: Database session
        file: Uploaded CSV file

    Returns:
        Import response with counts and any errors
    """
    imported_count = 0
    skipped_count = 0
    errors: list[str] = []

    try:
        # Validate file type
        if not file.filename or not file.filename.lower().endswith('.csv'):
            return ImportResponse(
                success=False,
                imported_count=0,
                skipped_count=0,
                errors=["File must be a CSV file"]
            )

        # Read CSV content
        content = await file.read()

        # Try different encodings
        csv_text = None
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                csv_text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if csv_text is None:
            return ImportResponse(
                success=False,
                imported_count=0,
                skipped_count=0,
                errors=["Could not decode file. Please ensure it's UTF-8 encoded."]
            )

        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_text))

        # Validate required columns
        required_columns = ['url', 'created_at']
        if not csv_reader.fieldnames:
            return ImportResponse(
                success=False,
                imported_count=0,
                skipped_count=0,
                errors=["CSV file appears to be empty or has no header row"]
            )

        missing_columns = [col for col in required_columns if col not in csv_reader.fieldnames]
        if missing_columns:
            return ImportResponse(
                success=False,
                imported_count=0,
                skipped_count=0,
                errors=[f"Missing required columns: {', '.join(missing_columns)}"]
            )

        # Process each row
        row_number = 1  # Header is row 0, data starts at row 1
        for row in csv_reader:
            row_number += 1

            try:
                # Validate and parse required fields
                url = row.get('url', '').strip()
                if not url:
                    errors.append(f"Row {row_number}: Missing URL")
                    skipped_count += 1
                    continue

                created_at_str = row.get('created_at', '').strip()
                if not created_at_str:
                    errors.append(f"Row {row_number}: Missing created_at")
                    skipped_count += 1
                    continue

                # Parse datetime - handle multiple formats
                created_at = None
                for date_format, parse_func in [
                    ('iso', lambda s: datetime.fromisoformat(s.replace('Z', '+00:00'))),
                    ('iso_no_z', lambda s: datetime.fromisoformat(s)),
                    ('simple', lambda s: datetime.strptime(s, '%Y-%m-%d %H:%M:%S')),
                    ('date_only', lambda s: datetime.strptime(s, '%Y-%m-%d')),
                ]:
                    try:
                        created_at = parse_func(created_at_str)
                        break
                    except ValueError:
                        continue

                if created_at is None:
                    errors.append(f"Row {row_number}: Invalid created_at format '{created_at_str}'. Use ISO 8601 (e.g., 2024-01-15T10:30:00Z) or YYYY-MM-DD HH:MM:SS")
                    skipped_count += 1
                    continue

                # Ensure datetime is timezone-aware (UTC)
                if created_at.tzinfo is None:
                    from app.utils.timezone import now_utc
                    import pytz
                    created_at = pytz.utc.localize(created_at)

                # Parse optional updated_at
                updated_at = created_at  # Default to created_at
                updated_at_str = row.get('updated_at', '').strip()
                if updated_at_str:
                    updated_parsed = None
                    for date_format, parse_func in [
                        ('iso', lambda s: datetime.fromisoformat(s.replace('Z', '+00:00'))),
                        ('iso_no_z', lambda s: datetime.fromisoformat(s)),
                        ('simple', lambda s: datetime.strptime(s, '%Y-%m-%d %H:%M:%S')),
                        ('date_only', lambda s: datetime.strptime(s, '%Y-%m-%d')),
                    ]:
                        try:
                            updated_parsed = parse_func(updated_at_str)
                            break
                        except ValueError:
                            continue
                    if updated_parsed is not None:
                        if updated_parsed.tzinfo is None:
                            import pytz
                            updated_parsed = pytz.utc.localize(updated_parsed)
                        updated_at = updated_parsed

                # Parse optional fields
                status = row.get('status', 'RESOLVED').strip().upper()
                if status not in ['ANALYZING', 'READY_TO_REPORT', 'REPORTING', 'REPORTED', 'MONITORING', 'RESOLVED', 'FAILED']:
                    status = 'RESOLVED'

                source = row.get('source', 'internal').strip().lower()
                if source not in ['internal', 'public']:
                    source = 'internal'

                brand_impacted = row.get('brand_impacted', '').strip() or None

                emails_sent = 0
                emails_sent_str = row.get('emails_sent', '0').strip()
                if emails_sent_str:
                    try:
                        emails_sent = int(emails_sent_str)
                        if emails_sent < 0:
                            emails_sent = 0
                    except ValueError:
                        pass

                registrar = row.get('registrar', '').strip() or None
                ip = row.get('ip', '').strip() or None

                # Parse reported_by - use user ID from CSV if valid, else use current user
                reported_by = current_user.id  # Default to current user
                reported_by_str = row.get('reported_by', '').strip()
                if reported_by_str:
                    # Validate it's a valid UUID
                    try:
                        from uuid import UUID
                        reported_by_uuid = UUID(reported_by_str)
                        # Check if user exists
                        user_check = await db.execute(
                            select(User.id).where(User.id == str(reported_by_uuid))
                        )
                        if user_check.scalar():
                            reported_by = str(reported_by_uuid)
                    except ValueError:
                        pass  # Not a valid UUID, use default

                # Build domain_info
                domain_info: dict = {}
                if registrar:
                    domain_info['registrar'] = registrar
                if ip:
                    domain_info['ip'] = ip

                # Create HistoricalCase record
                historical_case = HistoricalCase(
                    url=url,
                    status=status,
                    source=source,
                    brand_impacted=brand_impacted,
                    emails_sent=emails_sent,
                    domain_info=domain_info,
                    created_at=created_at,
                    updated_at=updated_at,
                    reported_by=reported_by,
                )
                db.add(historical_case)
                imported_count += 1

            except Exception as e:
                errors.append(f"Row {row_number}: {str(e)}")
                skipped_count += 1
                continue

        # Commit all changes
        await db.commit()

        # Determine success
        success = imported_count > 0 or (imported_count == 0 and skipped_count == 0)

        return ImportResponse(
            success=success,
            imported_count=imported_count,
            skipped_count=skipped_count,
            errors=errors
        )

    except Exception as e:
        await db.rollback()
        return ImportResponse(
            success=False,
            imported_count=imported_count,
            skipped_count=skipped_count,
            errors=[f"Import failed: {str(e)}"]
        )


__all__ = ["router"]
