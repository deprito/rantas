"""API endpoints for CertStream hunting feature.

Provides endpoints for managing detected typosquat domains from
CertStream monitoring, including listing, updating status,
creating cases from detections, and hunting statistics.
"""
import logging
from datetime import datetime, timedelta
from typing import Annotated, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    get_current_active_user,
    log_audit_action,
    AuditAction,
    ResourceType,
)
from app.auth.dependencies import PermissionChecker, get_current_active_user_sse
from app.config import settings
from app.database import get_db
from app.models import DetectedDomain, Case, User, Role
from app.permissions import Permission, get_role_permissions
from app.schemas import (
    DetectedDomain as DetectedDomainSchema,
    DetectedDomainStatus,
    DetectedDomainUpdate,
    DetectedDomainList,
    HuntingStats,
    HuntingConfig,
    HuntingStatus,
    CaseFromDetectionRequest,
    Case as CaseSchema,
    CaseStatus,
)
from app.models import HuntingConfig as HuntingConfigModel
from app.tasks.osint import analyze_url_task
from app.tasks.evidence import capture_screenshot_task
from app.utils.timezone import now_utc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hunting", tags=["hunting"])

# Default hunting configuration
DEFAULT_CONFIG = HuntingConfig()


@router.get("/detected", response_model=DetectedDomainList)
async def list_detected_domains(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
    status_filter: Optional[DetectedDomainStatus] = Query(
        None, description="Filter by status"
    ),
    brand_filter: Optional[str] = Query(None, description="Filter by matched brand"),
    http_status_filter: Optional[int] = Query(None, description="Filter by HTTP status code (200, 404, 500, etc.)"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum detection score"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> DetectedDomainList:
    """List detected domains with optional filtering and pagination.

    Args:
        current_user: Current authenticated user
        db: Database session
        status_filter: Optional status filter
        brand_filter: Optional brand filter
        http_status_filter: Optional HTTP status code filter
        min_score: Optional minimum score filter
        page: Page number (1-indexed)
        page_size: Items per page

    Returns:
        DetectedDomainList with domains list and pagination info
    """
    try:
        # Build query
        query = select(DetectedDomain)

        # Apply filters
        if status_filter:
            query = query.where(DetectedDomain.status == status_filter.value)

        if brand_filter:
            query = query.where(DetectedDomain.matched_brand.ilike(f"%{brand_filter}%"))

        if http_status_filter is not None:
            query = query.where(DetectedDomain.http_status_code == http_status_filter)

        if min_score is not None:
            query = query.where(DetectedDomain.detection_score >= min_score)

        # Order by detection score (highest first) then by cert_seen_at (newest first)
        query = query.order_by(
            DetectedDomain.detection_score.desc(),
            DetectedDomain.cert_seen_at.desc(),
        )

        # Get total count BEFORE applying pagination
        # Create a separate count query with same filters
        count_query = select(func.count(DetectedDomain.id))
        if status_filter:
            count_query = count_query.where(DetectedDomain.status == status_filter.value)
        if brand_filter:
            count_query = count_query.where(DetectedDomain.matched_brand.ilike(f"%{brand_filter}%"))
        if http_status_filter is not None:
            count_query = count_query.where(DetectedDomain.http_status_code == http_status_filter)
        if min_score is not None:
            count_query = count_query.where(DetectedDomain.detection_score >= min_score)
        total = (await db.execute(count_query)).scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(query)
        domains = result.scalars().all()

        # Convert to schemas
        domain_schemas = [
            DetectedDomainSchema(
                id=d.id,
                domain=d.domain,
                cert_data=d.cert_data,
                matched_brand=d.matched_brand,
                matched_pattern=d.matched_pattern,
                detection_score=d.detection_score,
                cert_seen_at=d.cert_seen_at,
                created_at=d.created_at,
                status=DetectedDomainStatus(d.status),
                http_status_code=d.http_status_code,
                http_checked_at=d.http_checked_at,
                notes=d.notes,
                case_id=UUID(d.case_id) if d.case_id else None,
            )
            for d in domains
        ]

        return DetectedDomainList(
            domains=domain_schemas,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list detected domains: {str(e)}",
        )


@router.get("/detected/{domain_id}", response_model=DetectedDomainSchema)
async def get_detected_domain(
    domain_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> DetectedDomainSchema:
    """Get details of a specific detected domain.

    Args:
        domain_id: Detected domain UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        DetectedDomain details
    """
    try:
        result = await db.execute(
            select(DetectedDomain).where(DetectedDomain.id == str(domain_id))
        )
        domain = result.scalar_one_or_none()

        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Detected domain {domain_id} not found",
            )

        return DetectedDomainSchema(
            id=domain.id,
            domain=domain.domain,
            cert_data=domain.cert_data,
            matched_brand=domain.matched_brand,
            matched_pattern=domain.matched_pattern,
            detection_score=domain.detection_score,
            cert_seen_at=domain.cert_seen_at,
            created_at=domain.created_at,
            status=DetectedDomainStatus(domain.status),
            http_status_code=domain.http_status_code,
            http_checked_at=domain.http_checked_at,
            notes=domain.notes,
            case_id=UUID(domain.case_id) if domain.case_id else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get detected domain: {str(e)}",
        )


@router.patch("/detected/{domain_id}", response_model=DetectedDomainSchema)
async def update_detected_domain(
    domain_id: UUID,
    updates: DetectedDomainUpdate,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.HUNTING_UPDATE))],
    db: AsyncSession = Depends(get_db),
) -> DetectedDomainSchema:
    """Update a detected domain (status, notes).

    Args:
        domain_id: Detected domain UUID
        updates: Update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated detected domain
    """
    try:
        domain = await db.get(DetectedDomain, str(domain_id))

        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Detected domain {domain_id} not found",
            )

        # Apply updates
        if updates.status is not None:
            domain.status = updates.status.value

        if updates.notes is not None:
            domain.notes = updates.notes

        # Log update
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_UPDATED,  # Reuse existing action
            resource_type=ResourceType.CASE,  # Use CASE type for now
            resource_id=str(domain_id),
            details={"action": "update_detected_domain", "updates": updates.model_dump(exclude_none=True)},
        )
        await db.commit()

        return DetectedDomainSchema(
            id=domain.id,
            domain=domain.domain,
            cert_data=domain.cert_data,
            matched_brand=domain.matched_brand,
            matched_pattern=domain.matched_pattern,
            detection_score=domain.detection_score,
            cert_seen_at=domain.cert_seen_at,
            created_at=domain.created_at,
            status=DetectedDomainStatus(domain.status),
            http_status_code=domain.http_status_code,
            http_checked_at=domain.http_checked_at,
            notes=domain.notes,
            case_id=UUID(domain.case_id) if domain.case_id else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update detected domain: {str(e)}",
        )


@router.delete("/detected/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_detected_domain(
    domain_id: UUID,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.HUNTING_DELETE))],
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a detected domain.

    Args:
        domain_id: Detected domain UUID
        current_user: Current authenticated user
        db: Database session
    """
    try:
        domain = await db.get(DetectedDomain, str(domain_id))

        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Detected domain {domain_id} not found",
            )

        await db.delete(domain)

        # Log deletion
        await log_audit_action(
            db,
            user_id=current_user.id,
            action=AuditAction.CASE_DELETED,  # Reuse existing action
            resource_type=ResourceType.CASE,
            resource_id=str(domain_id),
            details={"action": "delete_detected_domain", "domain": domain.domain},
        )
        await db.commit()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete detected domain: {str(e)}",
        )


@router.post("/detected/{domain_id}/check-http", response_model=DetectedDomainSchema)
async def check_domain_http_status(
    domain_id: UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> DetectedDomainSchema:
    """Check HTTP status for a detected domain.

    Makes an HTTP request to the domain and updates the http_status_code field.

    Args:
        domain_id: Detected domain UUID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated detected domain with HTTP status
    """
    import httpx

    try:
        domain = await db.get(DetectedDomain, str(domain_id))

        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Detected domain {domain_id} not found",
            )

        # Check HTTP status
        url = f"https://{domain.domain}"
        status_code = None
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.head(url, timeout=10.0)
                status_code = response.status_code
        except Exception:
            try:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    response = await client.get(url, timeout=10.0)
                    status_code = response.status_code
            except Exception:
                status_code = None

        # Update domain with HTTP status
        domain.http_status_code = status_code
        domain.http_checked_at = now_utc()

        await db.commit()
        await db.refresh(domain)

        return DetectedDomainSchema(
            id=domain.id,
            domain=domain.domain,
            cert_data=domain.cert_data,
            matched_brand=domain.matched_brand,
            matched_pattern=domain.matched_pattern,
            detection_score=domain.detection_score,
            cert_seen_at=domain.cert_seen_at,
            created_at=domain.created_at,
            status=DetectedDomainStatus(domain.status),
            http_status_code=domain.http_status_code,
            http_checked_at=domain.http_checked_at,
            notes=domain.notes,
            case_id=UUID(domain.case_id) if domain.case_id else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check HTTP status: {str(e)}",
        )


@router.post("/detected/{domain_id}/create-case", response_model=CaseSchema)
async def create_case_from_detection(
    domain_id: UUID,
    case_data: CaseFromDetectionRequest,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.CASE_CREATE))],
    db: AsyncSession = Depends(get_db),
) -> CaseSchema:
    """Create a case from a detected domain.

    Args:
        domain_id: Detected domain UUID
        case_data: Case creation data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created case
    """
    try:
        # Get the detected domain
        detected = await db.get(DetectedDomain, str(domain_id))

        if not detected:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Detected domain {domain_id} not found",
            )

        # Check if case already linked
        if detected.case_id:
            # Return existing case
            case = await db.get(Case, detected.case_id)
            if case:
                # Get user info
                result = await db.execute(
                    select(User.username, User.email).where(User.id == case.created_by)
                )
                username, email = result.first() or (None, None)

                return _case_to_schema(case, username, email)

        # Construct URL from domain
        url = f"https://{detected.domain}"

        # Check for duplicate URL
        existing_result = await db.execute(
            select(Case, User.username, User.email)
            .outerjoin(User, Case.created_by == User.id)
            .where(Case.url == url)
        )
        existing = existing_result.first()

        if existing:
            # Link to existing case and return
            case, username, email = existing
            detected.case_id = str(case.id)
            detected.status = DetectedDomainStatus.CASE_CREATED.value
            await db.commit()
            return _case_to_schema(case, username, email)

        # Create new case
        new_case = Case(
            url=url,
            status=CaseStatus.ANALYZING.value,
            monitor_interval=case_data.monitor_interval or settings.DEFAULT_MONITOR_INTERVAL,
            created_by=current_user.id,
            brand_impacted=case_data.brand_impacted or detected.matched_brand,
        )

        # Add initial history entry
        new_case.add_history_entry(
            "system",
            f"Case created from Hunting detection - typosquat of {detected.matched_brand}",
        )

        db.add(new_case)
        await db.flush()
        await db.refresh(new_case)

        # Link detection to case
        detected.case_id = str(new_case.id)
        detected.status = DetectedDomainStatus.CASE_CREATED.value

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
            details={
                "url": url,
                "source": "hunting",
                "detected_domain_id": str(domain_id),
                "matched_brand": detected.matched_brand,
            },
        )
        await db.commit()

        # Trigger OSINT analysis task
        analyze_url_task.delay(str(new_case.id), url)

        # Trigger screenshot capture
        capture_screenshot_task.delay(str(new_case.id), url)

        return case_schema

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create case from detection: {str(e)}",
        )


@router.get("/stats", response_model=HuntingStats)
async def get_hunting_stats(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> HuntingStats:
    """Get hunting statistics.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        HuntingStats with overview statistics
    """
    try:
        # Get total count
        total_result = await db.execute(select(func.count(DetectedDomain.id)))
        total_detected = total_result.scalar() or 0

        # Get counts by status
        status_counts = await db.execute(
            select(DetectedDomain.status, func.count(DetectedDomain.id))
            .group_by(DetectedDomain.status)
        )
        status_dict = {status: count for status, count in status_counts.all()}

        pending = status_dict.get("pending", 0)
        reviewed = status_dict.get("reviewed", 0)
        ignored = status_dict.get("ignored", 0)
        cases_created = status_dict.get("case_created", 0)

        # Get high confidence count (score >= 80)
        high_conf_result = await db.execute(
            select(func.count(DetectedDomain.id)).where(
                DetectedDomain.detection_score >= 80
            )
        )
        high_confidence = high_conf_result.scalar() or 0

        # Get top brands
        top_brands_result = await db.execute(
            select(DetectedDomain.matched_brand, func.count(DetectedDomain.id).label("count"))
            .where(DetectedDomain.matched_brand.isnot(None))
            .group_by(DetectedDomain.matched_brand)
            .order_by(func.count(DetectedDomain.id).desc())
            .limit(5)
        )
        top_brands = [brand for brand, _ in top_brands_result.all()]

        # Get HTTP status code counts
        http_status_result = await db.execute(
            select(
                func.coalesce(DetectedDomain.http_status_code, -1),
                func.count(DetectedDomain.id)
            )
            .group_by(DetectedDomain.http_status_code)
        )
        http_status_counts = {}
        for status_code, count in http_status_result.all():
            if status_code == -1:
                http_status_counts["null"] = count
            elif status_code is not None:
                http_status_counts[str(status_code)] = count

        return HuntingStats(
            total_detected=total_detected,
            pending=pending,
            reviewed=reviewed,
            ignored=ignored,
            cases_created=cases_created,
            high_confidence=high_confidence,
            top_brands=top_brands,
            http_status_counts=http_status_counts,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get hunting stats: {str(e)}",
        )


@router.get("/config", response_model=HuntingConfig)
async def get_hunting_config(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> HuntingConfig:
    """Get hunting configuration.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Current hunting configuration
    """
    from app.utils.analyzer import StaticURLAnalyzer
    from app.utils.typosquat_patterns import BRAND_PATTERNS, WHITELIST

    try:
        # Get config from database
        result = await db.execute(select(HuntingConfigModel))
        config = result.scalar_one_or_none()

        if config:
            # Merge default patterns with database patterns
            # Use database patterns if set, otherwise use hardcoded defaults
            default_patterns = config.default_brand_patterns if config.default_brand_patterns else {}
            whitelist = config.whitelist_patterns if config.whitelist_patterns else []

            # Initialize with hardcoded defaults for any brands not in DB
            merged_default_patterns = dict(BRAND_PATTERNS)
            for brand, patterns in default_patterns.items():
                merged_default_patterns[brand] = patterns

            # If whitelist is empty in DB, use hardcoded defaults
            merged_whitelist = list(whitelist) if whitelist else [
                r'^example\.com$',
                r'^example\.org$',
                r'^example\.net$',
                r'^testcorp\.com$',
                r'^testcorp\.org$',
            ]

            return HuntingConfig(
                monitor_enabled=config.monitor_enabled,
                min_score_threshold=config.min_score_threshold,
                alert_threshold=config.alert_threshold,
                monitored_brands=config.monitored_brands,
                retention_days=config.retention_days,
                raw_log_retention_days=config.raw_log_retention_days,
                custom_brand_patterns=config.custom_brand_patterns or {},
                custom_brand_regex_patterns=config.custom_brand_regex_patterns or {},
                default_brand_patterns=merged_default_patterns,
                whitelist_patterns=merged_whitelist,
            )

        # Return default if no config in database (initialize from hardcoded patterns)
        return HuntingConfig(
            monitor_enabled=True,
            min_score_threshold=50,
            alert_threshold=80,
            monitored_brands=list(settings.BRAND_IMPACTED) or ["example", "testcorp"],
            retention_days=90,
            raw_log_retention_days=3,
            custom_brand_patterns={},
            custom_brand_regex_patterns={},
            default_brand_patterns=dict(BRAND_PATTERNS),
            whitelist_patterns=[
                r'^example\.com$',
                r'^example\.org$',
                r'^example\.net$',
                r'^testcorp\.com$',
                r'^testcorp\.org$',
            ],
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get hunting config: {str(e)}",
        )


@router.put("/config", response_model=HuntingConfig)
async def update_hunting_config(
    config_update: HuntingConfig,
    current_user: Annotated[User, Depends(PermissionChecker(Permission.HUNTING_UPDATE))],
    db: AsyncSession = Depends(get_db),
) -> HuntingConfig:
    """Update hunting configuration.

    Args:
        config_update: New configuration
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated configuration
    """
    try:
        # Get existing config
        result = await db.execute(select(HuntingConfigModel))
        config = result.scalar_one_or_none()

        if config:
            # Update existing
            config.monitor_enabled = config_update.monitor_enabled
            config.min_score_threshold = config_update.min_score_threshold
            config.alert_threshold = config_update.alert_threshold
            config.monitored_brands = config_update.monitored_brands
            config.retention_days = config_update.retention_days
            config.raw_log_retention_days = config_update.raw_log_retention_days
            config.custom_brand_patterns = config_update.custom_brand_patterns
            config.custom_brand_regex_patterns = config_update.custom_brand_regex_patterns
            config.default_brand_patterns = config_update.default_brand_patterns
            config.whitelist_patterns = config_update.whitelist_patterns
        else:
            # Create new config
            config = HuntingConfigModel(
                monitor_enabled=config_update.monitor_enabled,
                min_score_threshold=config_update.min_score_threshold,
                alert_threshold=config_update.alert_threshold,
                monitored_brands=config_update.monitored_brands,
                retention_days=config_update.retention_days,
                raw_log_retention_days=config_update.raw_log_retention_days,
                custom_brand_patterns=config_update.custom_brand_patterns,
                custom_brand_regex_patterns=config_update.custom_brand_regex_patterns,
                default_brand_patterns=config_update.default_brand_patterns,
                whitelist_patterns=config_update.whitelist_patterns,
            )
            db.add(config)

        await db.commit()
        await db.refresh(config)

        return HuntingConfig(
            monitor_enabled=config.monitor_enabled,
            min_score_threshold=config.min_score_threshold,
            alert_threshold=config.alert_threshold,
            monitored_brands=config.monitored_brands,
            retention_days=config.retention_days,
            raw_log_retention_days=config.raw_log_retention_days,
            custom_brand_patterns=config.custom_brand_patterns or {},
            custom_brand_regex_patterns=config.custom_brand_regex_patterns or {},
            default_brand_patterns=config.default_brand_patterns or {},
            whitelist_patterns=config.whitelist_patterns or [],
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update hunting config: {str(e)}",
        )


@router.get("/status", response_model=HuntingStatus)
async def get_hunting_status(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> HuntingStatus:
    """Get real-time CertStream monitor status.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        HuntingStatus with monitor status and statistics
    """
    import time
    total_start = time.time()
    logger.info(f"[DEBUG] Hunting status request started at {total_start}")

    try:
        # Get config from database
        query_start = time.time()
        result = await db.execute(select(HuntingConfigModel))
        config = result.scalar_one_or_none()
        logger.info(f"[DEBUG] Config query took {time.time() - query_start:.3f}s")

        # Get latest detection timestamp
        query_start = time.time()
        latest_result = await db.execute(
            select(DetectedDomain.cert_seen_at)
            .order_by(DetectedDomain.cert_seen_at.desc())
            .limit(1)
        )
        last_seen_at = latest_result.scalar_one_or_none()
        logger.info(f"[DEBUG] Latest detection query took {time.time() - query_start:.3f}s")

        if config:
            logger.info(f"[DEBUG] Total status time: {time.time() - total_start:.3f}s")
            return HuntingStatus(
                monitor_is_running=config.monitor_is_running,
                monitor_enabled=config.monitor_enabled,
                monitor_started_at=config.monitor_started_at,
                monitor_last_heartbeat=config.monitor_last_heartbeat,
                monitor_last_seen_at=last_seen_at,
                certificates_processed=config.certificates_processed,
                domains_detected=config.domains_detected,
                error_message=config.error_message,
            )

        # Return default status if no config
        return HuntingStatus(
            monitor_is_running=False,
            monitor_enabled=True,
            monitor_started_at=None,
            monitor_last_heartbeat=None,
            monitor_last_seen_at=last_seen_at,
            certificates_processed=0,
            domains_detected=0,
            error_message=None,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get hunting status: {str(e)}",
        )


@router.post("/monitor/toggle")
async def toggle_monitor(
    current_user: Annotated[User, Depends(PermissionChecker(Permission.HUNTING_UPDATE))],
    db: AsyncSession = Depends(get_db),
) -> HuntingStatus:
    """Toggle CertStream monitor on/off.

    This sets a flag that the CertStream worker checks to determine
    whether to run or stop monitoring.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated HuntingStatus
    """
    try:
        import redis
        from app.config import settings

        # Get or create config
        result = await db.execute(select(HuntingConfigModel))
        config = result.scalar_one_or_none()

        if not config:
            config = HuntingConfigModel(
                monitor_enabled=True,
                min_score_threshold=50,
                alert_threshold=80,
                monitored_brands=list(settings.BRAND_IMPACTED) or ["example", "testcorp"],
                retention_days=90,
            )
            db.add(config)

        # Toggle the enabled flag
        config.monitor_enabled = not config.monitor_enabled

        # Update running state and clear error message
        if config.monitor_enabled:
            from app.utils.timezone import now_utc
            config.error_message = None
            config.monitor_is_running = True
            config.monitor_last_heartbeat = now_utc()  # Reset heartbeat when starting
        else:
            config.monitor_is_running = False

        await db.commit()
        await db.refresh(config)

        # Trigger Celery task when enabling
        if config.monitor_enabled:
            try:
                from app.workers.certstream_worker import run_ct_log_monitor_task
                run_ct_log_monitor_task.delay()
                logger.info("Dispatched CT log monitor task")
            except Exception as e:
                logger.error(f"Failed to dispatch CT log monitor task: {e}")

        return HuntingStatus(
            monitor_is_running=config.monitor_is_running,
            monitor_enabled=config.monitor_enabled,
            monitor_started_at=config.monitor_started_at,
            monitor_last_heartbeat=config.monitor_last_heartbeat,
            monitor_last_seen_at=None,  # Will be updated by worker
            certificates_processed=config.certificates_processed,
            domains_detected=config.domains_detected,
            error_message=config.error_message,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle monitor: {str(e)}",
        )


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
    from app.schemas import DomainInfo, AbuseContact, HistoryEntry, CaseSource

    # Ensure history is a list
    history_list = case.history if case.history is not None else []

    # Convert history entries
    history = []
    for h in history_list:
        if isinstance(h, dict):
            try:
                entry_data = h.copy()
                if "timestamp" in entry_data and isinstance(entry_data["timestamp"], str):
                    entry_data["timestamp"] = datetime.fromisoformat(
                        entry_data["timestamp"].replace("Z", "+00:00")
                    )
                history.append(HistoryEntry(**entry_data))
            except Exception:
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
        brand_impacted=case.brand_impacted or "",
        created_by=str(case.created_by) if case.created_by else None,
        created_by_username=created_by_username,
        created_by_email=created_by_email,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


@router.get("/raw-stream")
async def get_raw_certstream_sse(
    current_user: Annotated[User, Depends(get_current_active_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Server-Sent Events endpoint for real-time raw CertStream data.

    Streams all certificates from CertStream in real-time, unfiltered.
    First sends recent entries from Redis, then streams new entries as they arrive.

    Args:
        current_user: Current authenticated user
        limit: Initial number of recent entries to send

    Returns:
        SSE stream with real-time certificate data
    """
    from fastapi.responses import StreamingResponse
    import redis
    import json
    import asyncio
    from app.config import settings

    async def event_stream():
        """Generate SSE events for real-time CertStream data."""
        # Create Redis connection for pub/sub
        r = None
        pubsub = None

        try:
            r = redis.from_url(settings.REDIS_URL, decode_responses=False)
            pubsub = r.pubsub()

            # Subscribe to the certstream channel
            pubsub.subscribe("certstream:raw:stream")

            # First, send recent entries from the list
            try:
                raw_entries = r.lrange("certstream:raw", 0, limit - 1)
                for entry_bytes in reversed(raw_entries):  # Send in chronological order
                    try:
                        # Decode bytes to string if needed
                        entry_str = entry_bytes.decode('utf-8') if isinstance(entry_bytes, bytes) else entry_bytes
                        entry = json.loads(entry_str)
                        yield f"data: {json.dumps(entry)}\n\n"
                    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                        continue
            except Exception as e:
                logger.error(f"Error reading initial entries: {e}")

            # Send a "ready" event to indicate we're now streaming live
            yield f"event: ready\ndata: {{\"status\": \"live\"}}\n\n"

            # Now stream new entries as they arrive
            while True:
                try:
                    # Check for new messages with timeout
                    message = pubsub.get_message(timeout=1)

                    if message and message.get("type") == "message":
                        try:
                            entry_data = message.get("data")
                            if entry_data:
                                # Decode bytes to string if needed
                                entry_str = entry_data.decode('utf-8') if isinstance(entry_data, bytes) else entry_data
                                # Verify it's valid JSON
                                entry = json.loads(entry_str)
                                yield f"data: {json.dumps(entry)}\n\n"
                        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                            continue

                    # Keep connection alive with periodic ping
                    await asyncio.sleep(0.1)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in SSE stream: {e}")
                    break

        except GeneratorExit:
            pass
        except Exception as e:
            logger.error(f"Error in SSE event stream: {e}")
        finally:
            # Clean up Redis connection
            if pubsub:
                try:
                    pubsub.close()
                except Exception:
                    pass
            if r:
                try:
                    r.close()
                except Exception:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/certpatrol-stream")
async def get_certpatrol_raw_sse(
    current_user: Annotated[User, Depends(get_current_active_user_sse)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Server-Sent Events endpoint for real-time raw CertPatrol (CT Log) data.

    Streams all certificates from CT logs in real-time, unfiltered.
    First sends recent entries from Redis, then streams new entries as they arrive.

    Args:
        current_user: Current authenticated user
        limit: Initial number of recent entries to send

    Returns:
        SSE stream with real-time certificate data from CT logs
    """
    from fastapi.responses import StreamingResponse
    import redis
    import json
    import asyncio
    from app.config import settings

    async def event_stream():
        """Generate SSE events for real-time CT log data."""
        r = None
        pubsub = None

        try:
            r = redis.from_url(settings.REDIS_URL, decode_responses=False)
            pubsub = r.pubsub()

            # Subscribe to the certpatrol channel
            pubsub.subscribe("certpatrol:raw:stream")

            # First, send recent entries from the list
            try:
                raw_entries = r.lrange("certpatrol:raw", 0, limit - 1)
                for entry_bytes in reversed(raw_entries):  # Send in chronological order
                    try:
                        # Decode bytes to string if needed
                        entry_str = entry_bytes.decode('utf-8') if isinstance(entry_bytes, bytes) else entry_bytes
                        entry = json.loads(entry_str)
                        yield f"data: {json.dumps(entry)}\n\n"
                    except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                        continue
            except Exception as e:
                logger.error(f"Error reading initial certpatrol entries: {e}")

            # Send a "ready" event to indicate we're now streaming live
            yield f"event: ready\ndata: {{\"status\": \"live\"}}\n\n"

            # Now stream new entries as they arrive
            while True:
                try:
                    message = pubsub.get_message(timeout=1)

                    if message and message.get("type") == "message":
                        try:
                            entry_data = message.get("data")
                            if entry_data:
                                # Decode bytes to string if needed
                                entry_str = entry_data.decode('utf-8') if isinstance(entry_data, bytes) else entry_data
                                entry = json.loads(entry_str)
                                yield f"data: {json.dumps(entry)}\n\n"
                        except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                            continue

                    await asyncio.sleep(0.1)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in CertPatrol SSE stream: {e}")
                    break

        except GeneratorExit:
            pass
        except Exception as e:
            logger.error(f"Error in CertPatrol SSE event stream: {e}")
        finally:
            if pubsub:
                try:
                    pubsub.close()
                except Exception:
                    pass
            if r:
                try:
                    r.close()
                except Exception:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["router"]
