"""HTTP monitoring tasks for PhishTrack."""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from celery import shared_task
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models import Case
from app.tasks.celery_app import celery_app
from app.utils.http import check_http_status
from app.utils.timezone import now_utc


async def get_case_by_id(case_id: UUID) -> Optional[Case]:
    """Get a case by ID.

    Args:
        case_id: Case UUID

    Returns:
        Case object or None
    """
    async with async_session_factory() as session:
        result = await session.execute(select(Case).where(Case.id == str(case_id)))
        return result.scalar_one_or_none()


async def add_case_history(
    case_id: UUID,
    entry_type: str,
    message: str,
    status: Optional[int] = None,
) -> None:
    """Add a history entry to a case.

    Args:
        case_id: Case UUID
        entry_type: Type of history entry
        message: History message
        status: Optional HTTP status code
    """
    async with async_session_factory() as session:
        case = await session.get(Case, str(case_id))
        if case:
            case.add_history_entry(entry_type, message, status)
            case.updated_at = now_utc()
            await session.commit()


async def update_case_status(
    case_id: UUID,
    new_status: str,
    next_monitor_at: Optional[datetime] = None,
) -> None:
    """Update case status and monitoring schedule.

    Args:
        case_id: Case UUID
        new_status: New status value
        next_monitor_at: Optional next monitoring time
    """
    async with async_session_factory() as session:
        case = await session.get(Case, str(case_id))
        if case:
            case.status = new_status
            case.last_monitored_at = now_utc()
            if next_monitor_at:
                case.next_monitor_at = next_monitor_at
            case.updated_at = now_utc()
            await session.commit()


async def schedule_next_monitor(case_id: UUID, case: Case) -> None:
    """Schedule the next monitoring check for a case.

    Args:
        case_id: Case UUID
        case: Case object
    """
    async with async_session_factory() as session:
        case = await session.get(Case, str(case_id))
        if case:
            interval = case.monitor_interval or settings.DEFAULT_MONITOR_INTERVAL
            case.next_monitor_at = now_utc() + timedelta(seconds=interval)
            case.last_monitored_at = now_utc()
            await session.commit()


@shared_task(
    name="monitor.url",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def monitor_url_task(self, case_id: str) -> dict:
    """Monitor a URL for takedown.

    Args:
        self: Celery task instance
        case_id: Case UUID as string

    Returns:
        Dictionary with monitoring results
    """
    import asyncio

    # Clear any existing event loop to avoid conflicts
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop:
        asyncio.set_event_loop(None)

    # Use asyncio.run which creates a fresh loop and handles cleanup
    return asyncio.run(_monitor_url_async(UUID(case_id)))


async def _monitor_url_async(case_id: UUID) -> dict:
    """Async implementation of URL monitoring.

    Args:
        case_id: Case UUID

    Returns:
        Dictionary with monitoring results
    """
    try:
        # Get case
        case = await get_case_by_id(case_id)
        if not case:
            return {
                "success": False,
                "error": f"Case {case_id} not found",
            }

        # Skip if already resolved
        if case.status == "RESOLVED":
            return {
                "success": True,
                "message": "Case already resolved",
                "case_id": str(case_id),
            }

        # Perform HTTP check
        http_result = await check_http_status(
            case.url,
            user_agent=settings.HTTP_USER_AGENT,
            timeout=settings.HTTP_TIMEOUT,
        )

        # Determine message
        if http_result.is_live:
            if http_result.is_taken_down:
                message = f"Site appears down: {http_result.error or 'HTTP ' + str(http_result.status_code)}"
                # Check if actually taken down
                if http_result.status_code in (404, 410) or http_result.error:
                    # Mark as resolved
                    await update_case_status(case_id, "RESOLVED")
                    await add_case_history(
                        case_id,
                        "http_check",
                        f"SUCCESS: Site is down - marking as RESOLVED ({http_result.status_code or 'DNS failure'})",
                        status=http_result.status_code,
                    )
                    # Teams notification
                    from app.services.teams_notify import send_case_resolved_notification
                    await send_case_resolved_notification(case)
                    return {
                        "success": True,
                        "case_id": str(case_id),
                        "status": "RESOLVED",
                        "http_status": http_result.status_code,
                        "message": "Site taken down - case resolved",
                    }
            else:
                message = f"Site still active: HTTP {http_result.status_code}"
        else:
            message = f"Site unreachable: {http_result.error}"
            # Connection error likely means taken down
            await update_case_status(case_id, "RESOLVED")
            await add_case_history(
                case_id,
                "http_check",
                f"SUCCESS: Site unreachable - marking as RESOLVED ({http_result.error})",
            )
            # Teams notification
            from app.services.teams_notify import send_case_resolved_notification
            await send_case_resolved_notification(case)
            return {
                "success": True,
                "case_id": str(case_id),
                "status": "RESOLVED",
                "message": "Site unreachable - case resolved",
            }

        # Add history entry
        await add_case_history(
            case_id,
            "http_check",
            message,
            status=http_result.status_code,
        )

        # Schedule next monitor
        await schedule_next_monitor(case_id, case)

        return {
            "success": True,
            "case_id": str(case_id),
            "status": case.status,
            "http_status": http_result.status_code,
            "is_live": http_result.is_live,
            "message": message,
        }

    except Exception as e:
        import traceback

        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "case_id": str(case_id),
        }


@shared_task(name="monitor.check_due")
def check_due_monitors_task() -> dict:
    """Check for cases that are due for monitoring and spawn tasks.

    This task is run periodically by Celery Beat to find cases
    whose next_monitor_at has passed.

    Returns:
        Dictionary with check results
    """
    import asyncio

    # Clear any existing event loop to avoid conflicts
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop:
        asyncio.set_event_loop(None)

    # Use asyncio.run which creates a fresh loop and handles cleanup
    return asyncio.run(_check_due_monitors_async())


async def _check_due_monitors_async() -> dict:
    """Async implementation of due monitor checking.

    Returns:
        Dictionary with check results
    """
    try:
        now = now_utc()

        # Find cases due for monitoring
        async with async_session_factory() as session:
            result = await session.execute(
                select(Case).where(
                    Case.next_monitor_at.isnot(None),
                    Case.next_monitor_at <= now,
                    Case.status != "RESOLVED",
                )
            )
            due_cases = result.scalars().all()

        # Spawn monitoring tasks for each due case
        task_count = 0
        for case in due_cases:
            monitor_url_task.delay(str(case.id))
            task_count += 1

        return {
            "success": True,
            "cases_checked": len(due_cases),
            "tasks_spawned": task_count,
            "timestamp": now.isoformat(),
        }

    except Exception as e:
        import traceback

        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


@shared_task(name="monitor.cleanup")
def cleanup_old_results_task() -> dict:
    """Clean up old Celery task results from Redis.

    Returns:
        Dictionary with cleanup results
    """
    try:
        # This is handled by Celery's result_expires configuration
        # This task can be used for additional cleanup if needed
        return {
            "success": True,
            "message": "Cleanup completed",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@shared_task(
    name="monitor.verify_domain",
    bind=True,
)
def verify_domain_task(self, domain: str) -> dict:
    """Verify if a domain is still resolving.

    Args:
        self: Celery task instance
        domain: Domain to verify

    Returns:
        Dictionary with verification results
    """
    import asyncio

    # Clear any existing event loop to avoid conflicts
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop:
        asyncio.set_event_loop(None)

    # Use asyncio.run which creates a fresh loop and handles cleanup
    return asyncio.run(_verify_domain_async(domain))


async def _verify_domain_async(domain: str) -> dict:
    """Async implementation of domain verification.

    Args:
        domain: Domain to verify

    Returns:
        Dictionary with verification results
    """
    from app.utils.dns import is_dns_resolving, get_a_records

    try:
        resolving = is_dns_resolving(domain)
        a_records = get_a_records(domain) if resolving else []

        return {
            "success": True,
            "domain": domain,
            "resolving": resolving,
            "a_records": a_records,
            "ip": a_records[0] if a_records else None,
            "timestamp": now_utc().isoformat(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "domain": domain,
        }


@shared_task(
    name="monitor.batch_check",
    bind=True,
)
def batch_check_task(self, case_ids: list[str]) -> dict:
    """Perform HTTP checks on multiple cases in batch.

    Args:
        self: Celery task instance
        case_ids: List of case UUID strings

    Returns:
        Dictionary with batch check results
    """
    import asyncio

    # Clear any existing event loop to avoid conflicts
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop:
        asyncio.set_event_loop(None)

    # Use asyncio.run which creates a fresh loop and handles cleanup
    return asyncio.run(_batch_check_async([UUID(cid) for cid in case_ids]))


async def _batch_check_async(case_ids: list[UUID]) -> dict:
    """Async implementation of batch checking.

    Args:
        case_ids: List of case UUIDs

    Returns:
        Dictionary with batch check results
    """
    results = []
    for case_id in case_ids:
        result = await _monitor_url_async(case_id)
        results.append(result)

    return {
        "success": True,
        "total": len(case_ids),
        "results": results,
    }


__all__ = [
    "monitor_url_task",
    "check_due_monitors_task",
    "cleanup_old_results_task",
    "verify_domain_task",
    "batch_check_task",
]
