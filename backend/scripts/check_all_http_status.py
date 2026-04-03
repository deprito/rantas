"""Script to check HTTP status for all detected domains."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from sqlalchemy import select
from app.database import async_session_factory
from app.models import DetectedDomain
from app.utils.timezone import now_utc


async def _check_http_status(domain: str) -> int | None:
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


async def check_all_domains():
    """Check HTTP status for all detected domains."""
    async with async_session_factory() as db:
        # Get all detected domains
        result = await db.execute(select(DetectedDomain))
        domains = result.scalars().all()

        if not domains:
            print("No detected domains to check")
            return

        print(f"Checking HTTP status for {len(domains)} domains...")

        status_counts = {}
        updated = 0

        for i, domain in enumerate(domains, 1):
            status_code = await _check_http_status(domain.domain)

            # Update domain
            old_status = domain.http_status_code
            domain.http_status_code = status_code
            domain.http_checked_at = now_utc() if status_code else None
            updated += 1

            # Count status codes
            status_str = str(status_code) if status_code else "None"
            status_counts[status_str] = status_counts.get(status_str, 0) + 1

            # Print progress
            changed = f" (was {old_status})" if old_status != status_code else ""
            print(f"[{i}/{len(domains)}] {domain.domain}: {status_str}{changed}")

        await db.commit()

        print(f"\n=== Summary ===")
        print(f"Total checked: {len(domains)}")
        print(f"Updated: {updated}")
        print(f"\nStatus code distribution:")
        for code, count in sorted(status_counts.items()):
            print(f"  {code}: {count}")


if __name__ == "__main__":
    asyncio.run(check_all_domains())
