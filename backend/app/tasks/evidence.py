"""Celery tasks for capturing and managing evidence (screenshots, HTML, etc.)."""
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from celery import shared_task
from sqlalchemy import select

from app.config import settings
from app.database import get_sync_db_context
from app.models import Case, Evidence
from app.services.browserless import BrowserlessClient
from app.utils.timezone import now_utc


def get_screenshot_storage_path() -> Path:
    """Get the base path for storing screenshot evidence.

    Returns:
        Path object for the evidence storage directory
    """
    base_path = Path(getattr(settings, "EVIDENCE_STORAGE_PATH", "./evidence"))
    screenshots_path = base_path / "screenshots"
    return screenshots_path


def generate_screenshot_path(case_id: str, url: str) -> str:
    """Generate a unique file path for a screenshot.

    Args:
        case_id: Case UUID
        url: URL being captured

    Returns:
        Full path for the screenshot file
    """
    screenshots_path = get_screenshot_storage_path()

    # Create a sanitized filename from URL and case ID
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path

    # Sanitize domain for filename
    safe_domain = "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in domain)

    # Generate filename with timestamp
    timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_domain}_{case_id[:8]}_{timestamp}.png"

    return str(screenshots_path / filename)


def add_case_history_sync(
    case_id: UUID,
    entry_type: str,
    message: str,
    status: Optional[int] = None,
) -> None:
    """Synchronous wrapper for adding a history entry to a case.

    Args:
        case_id: Case UUID
        entry_type: Type of history entry
        message: History message
        status: Optional HTTP status code
    """
    with get_sync_db_context() as session:
        result = session.execute(select(Case).where(Case.id == str(case_id)))
        case = result.scalar_one_or_none()
        if case:
            case.add_history_entry(entry_type, message, status)
            case.updated_at = now_utc()
            session.commit()


def create_evidence_record_sync(
    case_id: str,
    evidence_type: str,
    file_path: str,
    content_hash: Optional[str] = None,
    meta: Optional[dict] = None,
) -> Optional[str]:
    """Create an evidence record in the database.

    Args:
        case_id: Case UUID
        evidence_type: Type of evidence ('screenshot', 'html')
        file_path: Path to the evidence file
        content_hash: SHA-256 hash of the content
        meta: Additional metadata

    Returns:
        Evidence ID if successful, None otherwise
    """
    try:
        with get_sync_db_context() as session:
            # Check if case exists
            case_result = session.execute(select(Case).where(Case.id == case_id))
            case = case_result.scalar_one_or_none()

            if not case:
                return None

            # Check for duplicate screenshots by content hash
            if content_hash:
                existing = session.execute(
                    select(Evidence).where(
                        Evidence.case_id == case_id,
                        Evidence.type == evidence_type,
                        Evidence.content_hash == content_hash,
                    )
                ).scalar_one_or_none()

                if existing:
                    # Duplicate screenshot, delete the new file and return existing
                    new_file = Path(file_path)
                    if new_file.exists():
                        new_file.unlink()
                    return str(existing.id)

            # Create new evidence record
            evidence = Evidence(
                case_id=case_id,
                type=evidence_type,
                file_path=file_path,
                content_hash=content_hash,
                meta=meta or {},
            )
            session.add(evidence)
            session.commit()

            return str(evidence.id)

    except Exception as e:
        print(f"Error creating evidence record: {e}")
        return None


@shared_task(
    name="evidence.capture_screenshot",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def capture_screenshot_task(
    self,
    case_id: str,
    url: str,
    full_page: bool = True,
) -> dict:
    """Capture a screenshot of a URL and store it as evidence.

    This task is triggered automatically when a case enters ANALYZING status
    or can be triggered manually via the API.

    Args:
        self: Celery task instance
        case_id: Case UUID as string
        url: URL to capture
        full_page: Whether to capture the full page

    Returns:
        Dictionary with capture results
    """
    api_key = getattr(settings, "BROWSERLESS_API_KEY", "")
    endpoint = getattr(settings, "BROWSERLESS_ENDPOINT", "https://connected.browserless.io")
    viewport_width = getattr(settings, "BROWSERLESS_VIEWPORT_WIDTH", 1440)
    viewport_height = getattr(settings, "BROWSERLESS_VIEWPORT_HEIGHT", 900)

    # Add history entry
    add_case_history_sync(
        UUID(case_id),
        "system",
        f"Initiating screenshot capture for {url}",
    )

    # Check if API key is configured
    if not api_key:
        error_msg = "Browserless API key not configured"
        add_case_history_sync(UUID(case_id), "system", f"Screenshot capture failed: {error_msg}")
        return {
            "success": False,
            "case_id": case_id,
            "error": error_msg,
        }

    # Initialize Browserless client
    client = BrowserlessClient(
        api_key=api_key,
        endpoint=endpoint,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        verify_ssl=settings.BROWSERLESS_VERIFY_SSL,
    )

    # Generate output path
    output_path = generate_screenshot_path(case_id, url)

    # Capture screenshot
    result = client.capture_screenshot_sync(
        url=url,
        output_path=output_path,
        full_page=full_page,
    )

    if result.get("success"):
        # Create evidence record
        evidence_id = create_evidence_record_sync(
            case_id=case_id,
            evidence_type="screenshot",
            file_path=result["file_path"],
            content_hash=result.get("content_hash"),
            meta={
                "url": url,
                "viewport_width": result.get("viewport_width"),
                "viewport_height": result.get("viewport_height"),
                "full_page": result.get("full_page"),
                "file_size": result.get("file_size"),
                "captured_at": result.get("captured_at"),
            },
        )

        # Add history entry
        add_case_history_sync(
            UUID(case_id),
            "system",
            f"Screenshot captured successfully (evidence_id: {evidence_id})",
        )

        return {
            "success": True,
            "case_id": case_id,
            "evidence_id": evidence_id,
            "file_path": result["file_path"],
            "file_size": result.get("file_size"),
            "content_hash": result.get("content_hash"),
        }

    else:
        error_msg = result.get("error", "Unknown error")
        add_case_history_sync(
            UUID(case_id),
            "system",
            f"Screenshot capture failed: {error_msg}",
        )

        return {
            "success": False,
            "case_id": case_id,
            "error": error_msg,
        }


__all__ = ["capture_screenshot_task"]
