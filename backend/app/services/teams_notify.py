"""Microsoft Teams webhook notification service for PhishTrack.

Sends Adaptive Card notifications to a Teams channel via incoming webhook
when cases are resolved.
"""
import httpx
from typing import Optional
from app.config import settings
from app.utils.timezone import now_utc, format_datetime


def _build_adaptive_card(case) -> dict:
    """Build an Adaptive Card payload for a resolved case.

    Args:
        case: Case model instance (or dict-like with case fields)

    Returns:
        Dictionary with the Adaptive Card message payload
    """
    # Extract case info
    case_id = str(case.id) if hasattr(case, "id") else str(case.get("id", ""))
    url = case.url if hasattr(case, "url") else case.get("url", "Unknown")
    brand = (
        case.brand_impacted
        if hasattr(case, "brand_impacted")
        else case.get("brand_impacted")
    ) or "Not specified"

    # Extract domain info
    domain_info = (
        case.domain_info if hasattr(case, "domain_info") else case.get("domain_info")
    ) or {}
    domain = domain_info.get("domain", "Unknown")
    registrar = domain_info.get("registrar", "Unknown")
    ip = domain_info.get("ip", "Unknown")
    age_days = domain_info.get("age_days")

    age_text = f"{age_days} days" if age_days is not None else "Unknown"

    resolved_at = format_datetime(now_utc(), "%Y-%m-%d %H:%M:%S WIB")

    # Build PhishTrack UI link
    case_url = f"http://localhost:3000/cases/{case_id}"

    # Adaptive Card schema v1.2 for mobile compatibility
    card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "✅ Case Resolved",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": "Good",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "URL", "value": url},
                                {"title": "Brand", "value": brand},
                                {"title": "Domain", "value": domain},
                                {"title": "Registrar", "value": registrar},
                                {"title": "IP", "value": ip},
                                {"title": "Domain Age", "value": age_text},
                                {"title": "Resolved", "value": resolved_at},
                            ],
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "View Case",
                            "url": case_url,
                        }
                    ],
                },
            }
        ],
    }

    return card


def send_case_resolved_notification_sync(case) -> None:
    """Send Teams notification for a resolved case (synchronous version).

    Fire-and-forget: logs errors but never raises.
    Use this in Celery tasks / sync contexts.

    Args:
        case: Case model instance
    """
    webhook_url = settings.TEAMS_WEBHOOK_URL
    if not webhook_url:
        return

    try:
        payload = _build_adaptive_card(case)
        with httpx.Client(timeout=10) as client:
            response = client.post(webhook_url, json=payload)
            if response.status_code not in (200, 202):
                print(
                    f"Teams webhook failed ({response.status_code}): "
                    f"{response.text[:200]}"
                )
    except Exception as e:
        print(f"Teams webhook error: {e}")


async def send_case_resolved_notification(case) -> None:
    """Send Teams notification for a resolved case (async version).

    Fire-and-forget: logs errors but never raises.
    Use this in async API handlers and async task functions.

    Args:
        case: Case model instance
    """
    webhook_url = settings.TEAMS_WEBHOOK_URL
    if not webhook_url:
        return

    try:
        payload = _build_adaptive_card(case)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code not in (200, 202):
                print(
                    f"Teams webhook failed ({response.status_code}): "
                    f"{response.text[:200]}"
                )
    except Exception as e:
        print(f"Teams webhook error: {e}")


# ==================== Export Notification Functions ====================


def _build_export_card(
    export_type: str,
    file_url: str,
    cases_count: int,
    filters: dict,
) -> dict:
    """Build an Adaptive Card payload for an export notification.

    Args:
        export_type: Type of export ("csv" or "json")
        file_url: URL to download the exported file
        cases_count: Number of cases in the export
        filters: Dictionary of filters applied

    Returns:
        Dictionary with the Adaptive Card message payload
    """
    from app.config import settings

    # Format filter information
    filter_text = ""
    if filters.get("start_date") or filters.get("end_date"):
        start = filters.get("start_date") or "..."
        end = filters.get("end_date") or "..."
        filter_text += f"Date Range: {start} to {end}\n"
    if filters.get("status"):
        filter_text += f"Status: {filters['status']}\n"
    if filters.get("source"):
        filter_text += f"Source: {filters['source']}"

    if not filter_text:
        filter_text = "All cases"

    # Build dashboard URL
    dashboard_url = f"{settings.BASE_URL.rstrip('/')}/cases"

    # Format type for display
    format_display = export_type.upper()

    # Adaptive Card schema v1.2 for mobile compatibility
    card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "Cases Export Ready",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": "Accent",
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Format", "value": format_display},
                                {"title": "Cases", "value": str(cases_count)},
                                {"title": "Filters", "value": filter_text},
                            ],
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "Download File",
                            "url": file_url,
                        },
                        {
                            "type": "Action.OpenUrl",
                            "title": "View Dashboard",
                            "url": dashboard_url,
                        },
                    ],
                },
            }
        ],
    }

    return card


def send_export_notification_sync(
    export_type: str,
    file_url: str,
    cases_count: int,
    filters: dict,
) -> None:
    """Send Teams notification for export completion (synchronous version).

    Fire-and-forget: logs errors but never raises.
    Use this in Celery tasks / sync contexts.

    Args:
        export_type: Type of export ("csv" or "json")
        file_url: URL to download the exported file
        cases_count: Number of cases in the export
        filters: Dictionary of filters applied
    """
    webhook_url = settings.TEAMS_WEBHOOK_URL
    if not webhook_url:
        return

    try:
        payload = _build_export_card(export_type, file_url, cases_count, filters)
        with httpx.Client(timeout=10) as client:
            response = client.post(webhook_url, json=payload)
            if response.status_code not in (200, 202):
                print(
                    f"Teams export webhook failed ({response.status_code}): "
                    f"{response.text[:200]}"
                )
    except Exception as e:
        print(f"Teams export webhook error: {e}")


async def send_export_notification(
    export_type: str,
    file_url: str,
    cases_count: int,
    filters: dict,
) -> None:
    """Send Teams notification for export completion (async version).

    Fire-and-forget: logs errors but never raises.
    Use this in async API handlers and async task functions.

    Args:
        export_type: Type of export ("csv" or "json")
        file_url: URL to download the exported file
        cases_count: Number of cases in the export
        filters: Dictionary of filters applied
    """
    webhook_url = settings.TEAMS_WEBHOOK_URL
    if not webhook_url:
        return

    try:
        payload = _build_export_card(export_type, file_url, cases_count, filters)
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code not in (200, 202):
                print(
                    f"Teams export webhook failed ({response.status_code}): "
                    f"{response.text[:200]}"
                )
    except Exception as e:
        print(f"Teams export webhook error: {e}")


# ==================== Typosquat Alert Functions ====================


def _build_typosquat_card(
    domain: str,
    matched_brand: str,
    detection_score: int,
    matched_pattern: str,
) -> dict:
    """Build an Adaptive Card payload for a typosquat alert.

    Args:
        domain: The detected typosquat domain
        matched_brand: Brand that was typosquatted
        detection_score: Confidence score (0-100)
        matched_pattern: Pattern that matched

    Returns:
        Dictionary with the Adaptive Card message payload
    """
    from app.config import settings

    # Build hunting URL
    hunting_url = f"{settings.BASE_URL.rstrip('/')}/hunting"

    # Determine score color
    if detection_score >= 90:
        color = "Attention"
        severity = "Critical"
    elif detection_score >= 80:
        color = "Warning"
        severity = "High"
    elif detection_score >= 70:
        color = "Good"
        severity = "Medium"
    else:
        color = "Default"
        severity = "Low"

    # Format domain URL
    domain_url = f"https://{domain}" if not domain.startswith("http") else domain

    # Get cert link if available from CertStream
    cert_index = ""  # Could be passed in if needed

    # Adaptive Card schema v1.2 for mobile compatibility
    card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": "🎯 Typosquat Detected",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": color,
                        },
                        {
                            "type": "FactSet",
                            "facts": [
                                {"title": "Domain", "value": f"[{domain}]({domain_url})"},
                                {"title": "Matched Brand", "value": matched_brand.upper()},
                                {"title": "Pattern", "value": matched_pattern},
                                {"title": "Confidence", "value": f"{detection_score}/100"},
                                {"title": "Severity", "value": severity},
                            ],
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "View Hunting Feed",
                            "url": hunting_url,
                        },
                    ],
                },
            }
        ],
    }

    return card


def send_typosquat_alert_sync(
    domain: str,
    matched_brand: str,
    detection_score: int,
    matched_pattern: str,
) -> None:
    """Send Teams notification for typosquat detection (synchronous version).

    Fire-and-forget: logs errors but never raises.
    Use this in Celery tasks / sync contexts.

    Args:
        domain: The detected typosquat domain
        matched_brand: Brand that was typosquatted
        detection_score: Confidence score (0-100)
        matched_pattern: Pattern that matched
    """
    webhook_url = settings.TEAMS_WEBHOOK_URL
    if not webhook_url:
        return

    try:
        payload = _build_typosquat_card(
            domain=domain,
            matched_brand=matched_brand,
            detection_score=detection_score,
            matched_pattern=matched_pattern,
        )
        with httpx.Client(timeout=10) as client:
            response = client.post(webhook_url, json=payload)
            if response.status_code not in (200, 202):
                print(
                    f"Teams typosquat webhook failed ({response.status_code}): "
                    f"{response.text[:200]}"
                )
    except Exception as e:
        print(f"Teams typosquat webhook error: {e}")


async def send_typosquat_alert(
    domain: str,
    matched_brand: str,
    detection_score: int,
    matched_pattern: str,
) -> None:
    """Send Teams notification for typosquat detection (async version).

    Fire-and-forget: logs errors but never raises.
    Use this in async API handlers and async task functions.

    Args:
        domain: The detected typosquat domain
        matched_brand: Brand that was typosquatted
        detection_score: Confidence score (0-100)
        matched_pattern: Pattern that matched
    """
    webhook_url = settings.TEAMS_WEBHOOK_URL
    if not webhook_url:
        return

    try:
        payload = _build_typosquat_card(
            domain=domain,
            matched_brand=matched_brand,
            detection_score=detection_score,
            matched_pattern=matched_pattern,
        )
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code not in (200, 202):
                print(
                    f"Teams typosquat webhook failed ({response.status_code}): "
                    f"{response.text[:200]}"
                )
    except Exception as e:
        print(f"Teams typosquat webhook error: {e}")
