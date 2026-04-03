"""Celery task for checking HTTP status of all detected domains."""
import logging
from typing import Optional

import httpx
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_context
from app.models import DetectedDomain
from app.utils.timezone import now_utc

logger = logging.getLogger(__name__)


@shared_task(name="http_status.check_all", bind=True, max_retries=2)
def check_all_detected_domains_http_status(self):
    """Check HTTP status for all detected domains.

    This task runs every 2 hours to update HTTP status codes
    for all detected domains in the database.

    Not configurable - always runs on all domains.
    """
    import asyncio

    async def run_checks():
        async with get_db_context() as db:
            # Get all detected domains
            result = await db.execute(select(DetectedDomain))
            domains = result.scalars().all()

            if not domains:
                logger.info("No detected domains to check")
                return {"checked": 0, "updated": 0, "failed": 0}

            logger.info(f"Checking HTTP status for {len(domains)} domains")

            updated = 0
            failed = 0

            for domain in domains:
                status_code = await _check_http_status(domain.domain)

                # Update domain
                domain.http_status_code = status_code
                domain.http_checked_at = now_utc() if status_code else None
                updated += 1

            await db.commit()

            logger.info(f"HTTP status check complete: {updated} updated, {failed} failed")
            return {
                "checked": len(domains),
                "updated": updated,
                "failed": failed,
            }

    return asyncio.run(run_checks())


async def _check_http_status(domain: str) -> Optional[int]:
    """Check HTTP status code for a domain.

    Args:
        domain: Domain to check

    Returns:
        HTTP status code or None if check failed
    """
    try:
        urls = [f"https://{domain}", f"http://{domain}"]

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            for url in urls:
                try:
                    response = await client.head(url, follow_redirects=False)
                    return response.status_code
                except (httpx.ConnectError, httpx.ConnectTimeout):
                    continue
                except Exception:
                    continue
        return None
    except Exception:
        return None
