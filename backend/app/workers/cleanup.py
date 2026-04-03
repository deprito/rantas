"""Celery beat task for cleaning up old detected domains and raw logs.

This module provides periodic tasks that:
1. Delete detected domains older than the retention period (default 90 days)
2. Delete raw CT log entries from Redis older than retention period (default 3 days)
"""
import json
import logging
from datetime import datetime, timedelta

from celery import shared_task
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db_context
from app.models import DetectedDomain
from app.utils.timezone import now_utc

logger = logging.getLogger(__name__)


@shared_task(
    name="cleanup.detected_domains",
    bind=True,
)
def cleanup_old_detected_domains(self) -> dict:
    """Clean up detected domains older than retention period.

    This task runs daily (configured in celery_app.py beat_schedule)
    and deletes detected domains that are older than the configured
    retention period (default 90 days).

    Returns:
        Dict with cleanup results
    """
    import asyncio

    logger.info("Starting cleanup of old detected domains...")

    retention_days = getattr(settings, "HUNTING_RETENTION_DAYS", 90)

    async def do_cleanup():
        cutoff_date = now_utc() - timedelta(days=retention_days)

        async with get_db_context() as db:
            # Count old domains
            count_result = await db.execute(
                select(DetectedDomain.id).where(
                    DetectedDomain.cert_seen_at < cutoff_date
                )
            )
            old_ids = count_result.scalars().all()
            count = len(old_ids)

            if count == 0:
                logger.info("No old detected domains to clean up")
                return {
                    "deleted_count": 0,
                    "retention_days": retention_days,
                    "message": "No old domains to clean up",
                }

            # Delete old domains
            await db.execute(
                delete(DetectedDomain).where(
                    DetectedDomain.cert_seen_at < cutoff_date
                )
            )
            await db.commit()

            logger.info(f"Deleted {count} detected domains older than {retention_days} days")

            return {
                "deleted_count": count,
                "retention_days": retention_days,
                "message": f"Deleted {count} old domains",
            }

    try:
        result = asyncio.run(do_cleanup())
        return result
    except Exception as e:
        logger.error(f"Cleanup task error: {e}")
        return {
            "deleted_count": 0,
            "retention_days": retention_days,
            "error": str(e),
        }


@shared_task(
    name="cleanup.raw_logs",
    bind=True,
)
def cleanup_old_raw_logs(self) -> dict:
    """Clean up raw CT log entries from Redis older than retention period.

    This task runs hourly (configured in celery_app.py beat_schedule)
    and removes raw certificate transparency log entries from Redis
    that are older than the configured retention period (default 3 days).

    Returns:
        Dict with cleanup results
    """
    import redis

    logger.info("Starting cleanup of old raw CT log entries...")

    retention_days = getattr(settings, "RAW_LOG_RETENTION_DAYS", 3)
    cutoff_timestamp = (now_utc() - timedelta(days=retention_days)).timestamp()

    try:
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )

        # Get all entries from the raw log list
        raw_entries = r.lrange("certpatrol:raw", 0, -1)

        kept_count = 0
        deleted_count = 0

        for entry_json in raw_entries:
            try:
                entry = json.loads(entry_json)
                seen_at_str = entry.get("seen_at")
                if seen_at_str:
                    # Parse timestamp
                    seen_at = datetime.fromisoformat(seen_at_str.replace('Z', '+00:00'))
                    if seen_at.timestamp() < cutoff_timestamp:
                        # Old entry - mark for deletion
                        deleted_count += 1
                    else:
                        kept_count += 1
                else:
                    # Entry without timestamp - remove it
                    deleted_count += 1
            except (json.JSONDecodeError, ValueError):
                # Invalid entry - remove it
                deleted_count += 1

        # Rebuild list with only recent entries
        if deleted_count > 0:
            r.delete("certpatrol:raw")
            if kept_count > 0:
                # Re-add only recent entries (in reverse order since lpush adds to front)
                recent_entries = []
                for entry_json in raw_entries:
                    try:
                        entry = json.loads(entry_json)
                        seen_at_str = entry.get("seen_at")
                        if seen_at_str:
                            seen_at = datetime.fromisoformat(seen_at_str.replace('Z', '+00:00'))
                            if seen_at.timestamp() >= cutoff_timestamp:
                                recent_entries.append(entry_json)
                    except Exception:
                        pass

                for entry in reversed(recent_entries):
                    r.lpush("certpatrol:raw", entry)

        logger.info(f"Raw log cleanup completed: {deleted_count} deleted, {kept_count} kept")

        return {
            "status": "completed",
            "deleted_count": deleted_count,
            "kept_count": kept_count,
            "retention_days": retention_days,
        }

    except Exception as e:
        logger.error(f"Raw log cleanup task error: {e}")
        return {
            "status": "error",
            "deleted_count": 0,
            "kept_count": 0,
            "retention_days": retention_days,
            "error": str(e),
        }


__all__ = ["cleanup_old_detected_domains", "cleanup_old_raw_logs"]
