"""CSV Report generation service for PhishTrack."""
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case
from app.config import settings
from app.utils.timezone import now_utc


REPORTS_DIR = Path("/app") / "reports" / "resolved_cases"
EXPORTS_DIR = Path("/app") / "reports" / "exports"


def ensure_reports_dir() -> Path:
    """Ensure the reports directory exists."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR


def ensure_exports_dir() -> Path:
    """Ensure the exports directory exists."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return EXPORTS_DIR


def get_resolution_date(history: list) -> Optional[datetime]:
    """Extract the resolution date from case history.

    Args:
        history: Case history entries

    Returns:
        Datetime of resolution or None
    """
    if not history:
        return None

    for entry in reversed(history):
        if isinstance(entry, dict):
            # Look for status change to RESOLVED
            if entry.get("type") == "system" and "RESOLVED" in entry.get("message", ""):
                timestamp_str = entry.get("timestamp")
                if timestamp_str:
                    try:
                        return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass

    return None


def get_resolution_method(history: list) -> str:
    """Determine how the case was resolved based on history.

    Args:
        history: Case history entries

    Returns:
        Resolution method string
    """
    if not history:
        return "unknown"

    # Look for the last HTTP/DNS check that indicated resolution
    for entry in reversed(history):
        if isinstance(entry, dict):
            entry_type = entry.get("type", "")
            message = entry.get("message", "")

            if entry_type == "http_check":
                return "http"
            elif entry_type == "dns_check":
                return "dns"

    # Check if emails were sent
    for entry in history:
        if isinstance(entry, dict) and entry.get("type") == "email_sent":
            return "email"

    return "manual"


async def generate_resolved_cases_csv(db: AsyncSession, user_id: str) -> tuple[str, str, int]:
    """Generate CSV report of all RESOLVED cases.

    Args:
        db: Database session
        user_id: ID of user generating the report

    Returns:
        Tuple of (report_id, file_path, cases_count)
    """
    # Query all resolved cases
    result = await db.execute(
        select(Case).where(Case.status == "RESOLVED").order_by(Case.created_at)
    )
    cases = result.scalars().all()

    # Generate report ID
    report_id = str(uuid4())

    # Ensure reports directory exists
    ensure_reports_dir()

    # Generate filename with timestamp
    timestamp = now_utc().strftime("%Y-%m-%d_%H%M%S")
    filename = f"{timestamp}_resolved_cases.csv"
    file_path = REPORTS_DIR / filename

    # CSV columns
    columns = [
        "case_id",
        "url",
        "domain",
        "ip",
        "status",
        "created_at",
        "resolved_at",
        "time_to_resolution_days",
        "registrar",
        "asn",
        "abuse_contacts",
        "emails_sent",
        "history_entries",
        "resolution_method",
    ]

    # Write CSV
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()

        for case in cases:
            # Extract domain from URL
            domain_info = case.domain_info if isinstance(case.domain_info, dict) else {}
            domain = domain_info.get("domain", "")
            if not domain:
                try:
                    from urllib.parse import urlparse

                    parsed = urlparse(case.url)
                    domain = parsed.netloc or parsed.path
                except Exception:
                    domain = ""

            # Get resolution date
            resolved_at = get_resolution_date(case.history) if case.history else None

            # Calculate time to resolution
            time_to_resolution_days = None
            if resolved_at and case.created_at:
                time_to_resolution_days = (resolved_at - case.created_at).total_seconds() / 86400

            # Get resolution method
            resolution_method = get_resolution_method(case.history) if case.history else "unknown"

            # Format abuse contacts
            abuse_contacts_json = json.dumps(case.abuse_contacts) if case.abuse_contacts else "[]"

            # Count history entries
            history_count = len(case.history) if case.history else 0

            writer.writerow({
                "case_id": str(case.id),
                "url": case.url,
                "domain": domain,
                "ip": domain_info.get("ip", ""),
                "status": case.status,
                "created_at": case.created_at.isoformat() if case.created_at else "",
                "resolved_at": resolved_at.isoformat() if resolved_at else "",
                "time_to_resolution_days": f"{time_to_resolution_days:.2f}" if time_to_resolution_days else "",
                "registrar": domain_info.get("registrar", ""),
                "asn": domain_info.get("asn", ""),
                "abuse_contacts": abuse_contacts_json,
                "emails_sent": case.emails_sent,
                "history_entries": history_count,
                "resolution_method": resolution_method,
            })

    # Get file size
    file_size = file_path.stat().st_size

    return report_id, str(file_path), len(cases), file_size


def get_report_path(report_id: str, filename: str) -> Path:
    """Get the full path for a report file.

    Args:
        report_id: Report ID
        filename: Report filename

    Returns:
        Full path to report file
    """
    return REPORTS_DIR / filename


def delete_report(file_path: str) -> bool:
    """Delete a report file.

    Args:
        file_path: Path to report file

    Returns:
        True if deleted, False otherwise
    """
    try:
        path = Path(file_path)
        if path.exists() and path.is_file():
            path.unlink()
            return True
    except Exception:
        pass
    return False


# ==================== Case Export Functions ====================


def _parse_date_filter(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date filter string to datetime.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        Datetime object or None
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


async def generate_cases_csv(
    db: AsyncSession,
    filters: dict,
    user_id: Optional[str] = None,
) -> tuple[str, str, int, int]:
    """Generate CSV export of cases with filters.

    Args:
        db: Database session
        filters: Dictionary of filters (start_date, end_date, status, source)
        user_id: Optional ID of user generating the export

    Returns:
        Tuple of (export_id, file_path, cases_count, file_size)
    """
    # Build query
    query = select(Case)

    # Apply filters
    start_date = _parse_date_filter(filters.get("start_date"))
    end_date = _parse_date_filter(filters.get("end_date"))
    status_filter = filters.get("status")
    source_filter = filters.get("source")

    conditions = []
    if start_date:
        conditions.append(Case.created_at >= start_date)
    if end_date:
        # End of the day
        end_datetime = end_date.replace(hour=23, minute=59, second=59)
        conditions.append(Case.created_at <= end_datetime)
    if status_filter:
        conditions.append(Case.status == status_filter.value if hasattr(status_filter, 'value') else status_filter)
    if source_filter:
        conditions.append(Case.source == source_filter.value if hasattr(source_filter, 'value') else source_filter)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Case.created_at.desc())

    # Execute query
    result = await db.execute(query)
    cases = result.scalars().all()

    # Generate export ID
    export_id = str(uuid4())

    # Ensure exports directory exists
    ensure_exports_dir()

    # Generate filename with timestamp
    timestamp = now_utc().strftime("%Y-%m-%d_%H%M%S")
    filename = f"{timestamp}_cases_export.csv"
    file_path = EXPORTS_DIR / filename

    # CSV columns
    columns = [
        "case_id",
        "url",
        "domain",
        "ip",
        "status",
        "source",
        "brand_impacted",
        "created_at",
        "updated_at",
        "registrar",
        "asn",
        "domain_age",
        "abuse_contacts",
        "emails_sent",
        "resolution_method",
    ]

    # Write CSV
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()

        for case in cases:
            # Extract domain from URL
            domain_info = case.domain_info if isinstance(case.domain_info, dict) else {}
            domain = domain_info.get("domain", "")
            if not domain:
                try:
                    from urllib.parse import urlparse

                    parsed = urlparse(case.url)
                    domain = parsed.netloc or parsed.path
                except Exception:
                    domain = ""

            # Get resolution method (only for resolved cases)
            resolution_method = ""
            if case.status == "RESOLVED":
                resolution_method = get_resolution_method(case.history) if case.history else ""

            # Format abuse contacts
            abuse_contacts_json = json.dumps(case.abuse_contacts) if case.abuse_contacts else "[]"

            writer.writerow({
                "case_id": str(case.id),
                "url": case.url,
                "domain": domain,
                "ip": domain_info.get("ip", ""),
                "status": case.status,
                "source": case.source,
                "brand_impacted": case.brand_impacted or "",
                "created_at": case.created_at.isoformat() if case.created_at else "",
                "updated_at": case.updated_at.isoformat() if case.updated_at else "",
                "registrar": domain_info.get("registrar", ""),
                "asn": domain_info.get("asn", ""),
                "domain_age": domain_info.get("age_days", ""),
                "abuse_contacts": abuse_contacts_json,
                "emails_sent": case.emails_sent,
                "resolution_method": resolution_method,
            })

    # Get file size
    file_size = file_path.stat().st_size

    return export_id, str(file_path), len(cases), file_size


async def generate_cases_json(
    db: AsyncSession,
    filters: dict,
    user_id: Optional[str] = None,
) -> tuple[str, str, int, int]:
    """Generate JSON export of cases with filters.

    Args:
        db: Database session
        filters: Dictionary of filters (start_date, end_date, status, source)
        user_id: Optional ID of user generating the export

    Returns:
        Tuple of (export_id, file_path, cases_count, file_size)
    """
    # Build query
    query = select(Case)

    # Apply filters
    start_date = _parse_date_filter(filters.get("start_date"))
    end_date = _parse_date_filter(filters.get("end_date"))
    status_filter = filters.get("status")
    source_filter = filters.get("source")

    conditions = []
    if start_date:
        conditions.append(Case.created_at >= start_date)
    if end_date:
        # End of the day
        end_datetime = end_date.replace(hour=23, minute=59, second=59)
        conditions.append(Case.created_at <= end_datetime)
    if status_filter:
        conditions.append(Case.status == status_filter.value if hasattr(status_filter, 'value') else status_filter)
    if source_filter:
        conditions.append(Case.source == source_filter.value if hasattr(source_filter, 'value') else source_filter)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Case.created_at.desc())

    # Execute query
    result = await db.execute(query)
    cases = result.scalars().all()

    # Generate export ID
    export_id = str(uuid4())

    # Ensure exports directory exists
    ensure_exports_dir()

    # Generate filename with timestamp
    timestamp = now_utc().strftime("%Y-%m-%d_%H%M%S")
    filename = f"{timestamp}_cases_export.json"
    file_path = EXPORTS_DIR / filename

    # Build cases data
    cases_data = []
    for case in cases:
        domain_info = case.domain_info if isinstance(case.domain_info, dict) else {}

        # Extract domain from URL
        domain = domain_info.get("domain", "")
        if not domain:
            try:
                from urllib.parse import urlparse

                parsed = urlparse(case.url)
                domain = parsed.netloc or parsed.path
            except Exception:
                domain = ""

        # Get resolution method
        resolution_method = ""
        if case.status == "RESOLVED":
            resolution_method = get_resolution_method(case.history) if case.history else ""

        case_dict = {
            "case_id": str(case.id),
            "url": case.url,
            "domain": domain,
            "ip": domain_info.get("ip"),
            "status": case.status,
            "source": case.source,
            "brand_impacted": case.brand_impacted,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "updated_at": case.updated_at.isoformat() if case.updated_at else None,
            "registrar": domain_info.get("registrar"),
            "asn": domain_info.get("asn"),
            "domain_age_days": domain_info.get("age_days"),
            "abuse_contacts": case.abuse_contacts if case.abuse_contacts else [],
            "emails_sent": case.emails_sent,
            "resolution_method": resolution_method if case.status == "RESOLVED" else None,
            "monitor_interval": case.monitor_interval,
        }
        cases_data.append(case_dict)

    # Build export object
    export_data = {
        "exported_at": now_utc().isoformat(),
        "export_id": str(export_id),
        "total_cases": len(cases_data),
        "filters": {
            "start_date": filters.get("start_date"),
            "end_date": filters.get("end_date"),
            "status": filters.get("status"),
            "source": filters.get("source"),
        },
        "cases": cases_data,
    }

    # Write JSON file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    # Get file size
    file_size = file_path.stat().st_size

    return export_id, str(file_path), len(cases), file_size


def get_export_path(export_id: str, filename: str) -> Path:
    """Get the full path for an export file.

    Args:
        export_id: Export ID
        filename: Export filename

    Returns:
        Full path to export file
    """
    return EXPORTS_DIR / filename
