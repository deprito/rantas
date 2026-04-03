"""Email sending tasks for PhishTrack takedown notices."""
import os
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from mimetypes import guess_type
from pathlib import Path
from smtplib import SMTP, SMTPException
from socket import gaierror
from typing import List, Optional
from uuid import UUID

from celery import shared_task
from jinja2 import Template

from app.config import settings
from app.database import async_session_factory
from app.services.graph_email import send_graph_email
from app.models import Case, EmailTemplate
from app.tasks.celery_app import celery_app
from app.utils.whois import extract_abuse_emails_from_text
from app.utils.timezone import now_utc


# Takedown notice email template
TAKEDOWN_TEMPLATE = Template("""
**IMPORTANT: ABUSE NOTICE - CASE ID: {{ case_id }}**

{{ organization }} Abuse Team,

We are writing to report active phishing infrastructure hosted on your network.

**Phishing URL:** {{ target_url }}
**Domain:** {{ domain }}
**IP Address:** {{ ip }}
**Reported:** {{ reported_date }}

**Evidence of Phishing:**
This site is being used to target users of [Brand/Service] with fraudulent
login pages designed to steal credentials and financial information.

**Action Requested:**
1. Suspend the domain {{ domain }}
2. Take down the fraudulent content at {{ target_url }}
3. Preserve any logs/evidence for law enforcement if requested

**Case Reference:** {{ case_id }}
**Reporter Email:** {{ reporter_email }}

Please confirm receipt of this notice and inform us of any actions taken.
We request a response within 24 hours.

This notice is sent in accordance with acceptable use policies and
anti-phishing industry best practices.

--
PhishTrack Automated Abuse Reporting
{{ case_id }}

**Confidentiality Notice:** This message contains confidential information
related to an ongoing security investigation. Recipients are required to
maintain the confidentiality of this information.
""".strip())


def send_smtp_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    cc: Optional[str] = None,
    attachments: Optional[List[str]] = None,
) -> dict:
    """Send an email via SMTP.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Plain text email body
        html_body: Optional HTML email body
        cc: Optional CC email addresses (comma-separated)
        attachments: Optional list of file paths to attach

    Returns:
        Dictionary with send status
    """
    if not settings.SMTP_ENABLED:
        return {
            "success": False,
            "error": "SMTP is disabled in configuration",
        }

    if not settings.SMTP_HOST or not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        return {
            "success": False,
            "error": "SMTP credentials not configured",
        }

    try:
        # Create email message
        msg = EmailMessage()
        msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Date"] = now_utc()

        # Add CC if provided
        if cc:
            msg["Cc"] = cc

        # Set body
        msg.set_content(body)

        # Add HTML version if provided
        if html_body:
            msg.add_alternative(html_body, subtype="html")

        # Add attachments if provided
        if attachments:
            for attachment_path in attachments:
                path = Path(attachment_path)
                if not path.exists():
                    continue

                # Guess MIME type
                mime_type, encoding = guess_type(str(path))
                if mime_type is None:
                    mime_type = "application/octet-stream"

                main_type, sub_type = mime_type.split("/", 1)

                # Read file and add as attachment
                with open(path, "rb") as f:
                    data = f.read()

                msg.add_attachment(
                    data,
                    maintype=main_type,
                    subtype=sub_type,
                    filename=path.name,
                )

        # Send via SMTP
        with SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()

            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)

        return {
            "success": True,
            "to": to_email,
            "cc": cc,
            "attachments": attachments or [],
            "message_id": msg["Message-ID"],
        }

    except gaierror as e:
        return {
            "success": False,
            "error": f"DNS/Connection error: {str(e)}",
        }
    except SMTPException as e:
        return {
            "success": False,
            "error": f"SMTP error: {str(e)}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        }


def send_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    cc: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    inline_images: Optional[dict] = None,
) -> dict:
    """Send an email via available method.

    Tries Graph API first if enabled, falls back to SMTP.
    Both Graph API and SMTP support attachments.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Plain text email body
        html_body: Optional HTML email body
        cc: Optional CC email addresses (comma-separated)
        attachments: Optional list of file paths to attach
        inline_images: Optional dict mapping content_id to file_path for inline images (Graph API only)

    Returns:
        Dictionary with send status
    """
    # Try Graph API first
    if settings.GRAPH_ENABLED:
        result = send_graph_email(to_email, subject, body, html_body, cc, attachments, inline_images)
        if result.get("success"):
            return result
        # Log Graph API failure but try SMTP as fallback

    # Fall back to SMTP (does not support inline_images, so they are ignored)
    return send_smtp_email(to_email, subject, body, html_body, cc, attachments)


def generate_takedown_notice(
    case_id: UUID,
    target_url: str,
    domain: str,
    ip: Optional[str],
    contact_type: str,
    template_subject: Optional[str] = None,
    template_body: Optional[str] = None,
    template_html_body: Optional[str] = None,
    brand_impacted: Optional[str] = None,
) -> tuple[str, str, Optional[str]]:
    """Generate takedown notice email content.

    Args:
        case_id: Case UUID
        target_url: Phishing URL
        domain: Domain name
        ip: IP address
        contact_type: Type of abuse contact (registrar/hosting)
        template_subject: Optional custom subject template
        template_body: Optional custom body template
        template_html_body: Optional custom HTML body template
        brand_impacted: Optional brand impacted by this phishing case

    Returns:
        Tuple of (subject, body text, html body or None)
    """
    org_name = {
        "registrar": "Domain Registrar",
        "hosting": "Hosting Provider",
        "dns": "DNS Provider",
    }.get(contact_type, "Service Provider")

    template_vars = {
        "case_id": str(case_id),
        "organization": org_name,
        "target_url": target_url,
        "domain": domain,
        "ip": ip or "Unknown",
        "reported_date": now_utc().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "reporter_email": settings.SMTP_FROM_EMAIL,
        "brand_impacted": brand_impacted or "Not specified",
    }

    # Use custom template if provided, otherwise use default
    if template_body:
        body_template = Template(template_body)
        body = body_template.render(**template_vars)
    else:
        body = TAKEDOWN_TEMPLATE.render(**template_vars)

    # Generate subject
    if template_subject:
        subject_template = Template(template_subject)
        subject = subject_template.render(**template_vars)
    else:
        subject = f"[Case-ID: {case_id}] URGENT: Phishing Takedown Request - {domain}"

    # Generate HTML body if template provided
    html_body = None
    if template_html_body:
        html_template = Template(template_html_body)
        html_body = html_template.render(**template_vars)

    return subject, body, html_body


async def get_email_template(template_id: Optional[str]) -> Optional[dict]:
    """Get an email template from the database.

    Args:
        template_id: Template UUID or None

    Returns:
        Dictionary with 'subject', 'body', 'html_body', 'cc', and 'prefer_xarf' keys, or None if not found
    """
    if not template_id:
        # Try to get the default template
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(
                select(EmailTemplate).where(EmailTemplate.is_default == True)
            )
            template = result.scalar_one_or_none()
            if template:
                return {
                    "subject": template.subject,
                    "body": template.body,
                    "html_body": template.html_body,
                    "cc": template.cc,
                    "prefer_xarf": getattr(template, 'prefer_xarf', False),
                }
    else:
        # Get specific template
        from sqlalchemy import select

        async with async_session_factory() as session:
            template = await session.get(EmailTemplate, template_id)
            if template:
                return {
                    "subject": template.subject,
                    "body": template.body,
                    "html_body": template.html_body,
                    "cc": template.cc,
                    "prefer_xarf": getattr(template, 'prefer_xarf', False),
                }

    # No template found, return None (will use hardcoded default)
    return None


async def get_case_by_id(case_id: UUID) -> Optional[Case]:
    """Get a case by ID.

    Args:
        case_id: Case UUID

    Returns:
        Case object or None
    """
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(select(Case).where(Case.id == str(case_id)))
        return result.scalar_one_or_none()


async def add_case_history(
    case_id: UUID,
    entry_type: str,
    message: str,
) -> None:
    """Add a history entry to a case.

    Args:
        case_id: Case UUID
        entry_type: Type of history entry
        message: History message
    """
    async with async_session_factory() as session:
        case = await session.get(Case, str(case_id))
        if case:
            case.add_history_entry(entry_type, message)
            case.updated_at = now_utc()
            await session.commit()


async def increment_case_emails_sent(case_id: UUID) -> None:
    """Increment the emails sent counter for a case.

    Args:
        case_id: Case UUID
    """
    async with async_session_factory() as session:
        case = await session.get(Case, str(case_id))
        if case:
            case.emails_sent += 1
            case.last_email_sent_at = now_utc()
            case.updated_at = now_utc()
            await session.commit()


@shared_task(
    name="email.send_report",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def send_report_task(
    self,
    case_id: str,
    template_id: Optional[str] = None,
    selected_contacts: Optional[list[str]] = None,
    is_followup: bool = False,
    brand_impacted: Optional[str] = None,
) -> dict:
    """Send takedown report emails for a case.

    Args:
        self: Celery task instance
        case_id: Case UUID as string
        template_id: Optional email template UUID to use
        selected_contacts: Optional list of email addresses to send to (if not provided, sends to all)
        is_followup: If True, this is a follow-up report and status should not change
        brand_impacted: Optional brand impacted by this phishing case

    Returns:
        Dictionary with send results
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
    return asyncio.run(_send_report_async(UUID(case_id), template_id, selected_contacts, is_followup, brand_impacted))


async def _send_report_async(
    case_id: UUID,
    template_id: Optional[str] = None,
    selected_contacts: Optional[list[str]] = None,
    is_followup: bool = False,
    brand_impacted: Optional[str] = None,
) -> dict:
    """Async implementation of email sending.

    Args:
        case_id: Case UUID
        template_id: Optional email template UUID to use
        selected_contacts: Optional list of email addresses to send to (if not provided, sends to all)
        is_followup: If True, this is a follow-up report and status should not change
        brand_impacted: Optional brand impacted by this phishing case

    Returns:
        Dictionary with send results
    """
    try:
        # Get email template
        template = await get_email_template(template_id)
        template_subject = template["subject"] if template else None
        template_body = template["body"] if template else None
        template_html_body = template["html_body"] if template else None
        template_cc = template["cc"] if template else None
        prefer_xarf = template["prefer_xarf"] if template else False

        # Get case details
        case = await get_case_by_id(case_id)
        if not case:
            return {
                "success": False,
                "error": f"Case {case_id} not found",
            }

        # Extract domain info
        domain_info = case.domain_info or {}
        domain = domain_info.get("domain", "")
        ip = domain_info.get("ip")
        target_url = case.url

        if not domain:
            return {
                "success": False,
                "error": "No domain information available",
            }

        # Get abuse contacts
        abuse_contacts = case.abuse_contacts or []

        # Filter by selected contacts if provided
        if selected_contacts:
            selected_set = set(selected_contacts)
            abuse_contacts = [c for c in abuse_contacts if c.get("email") in selected_set]

        if not abuse_contacts:
            await add_case_history(
                case_id,
                "system",
                "No abuse contacts available - skipping email send",
            )
            return {
                "success": False,
                "error": "No abuse contacts available",
            }

        # Generate XARF attachment if template prefers it
        xarf_attachments = None
        if prefer_xarf:
            try:
                from app.services.xarf_generator import XARFGenerator
                xarf_gen = XARFGenerator(case)
                xarf_path = xarf_gen.to_json_file()
                xarf_attachments = [xarf_path]

                # Validate XARF report
                validation_errors = xarf_gen.validate()
                if validation_errors:
                    await add_case_history(
                        case_id,
                        "system",
                        f"XARF validation warnings: {', '.join(validation_errors)}",
                    )
            except Exception as e:
                await add_case_history(
                    case_id,
                    "system",
                    f"Failed to generate XARF attachment: {str(e)}",
                )
                xarf_attachments = None

        # Query for screenshot evidence to include inline
        from sqlalchemy import select
        from app.models import Evidence

        inline_images = None
        screenshot_path = None

        async with async_session_factory() as session:
            result = await session.execute(
                select(Evidence).where(
                    Evidence.case_id == str(case_id),
                    Evidence.type == "screenshot"
                )
            )
            screenshot = result.scalar_one_or_none()
            if screenshot and screenshot.file_path:
                from pathlib import Path
                # Check if file exists
                if Path(screenshot.file_path).exists():
                    screenshot_path = screenshot.file_path
                    inline_images = {"screenshot": screenshot.file_path}

        # Send emails to each contact
        results = []
        for contact in abuse_contacts:
            contact_type = contact.get("type", "hosting")
            email = contact.get("email")

            if not email:
                continue

            # Generate takedown notice
            subject, body, html_body = generate_takedown_notice(
                case_id,
                target_url,
                domain,
                ip,
                contact_type,
                template_subject=template_subject,
                template_body=template_body,
                template_html_body=template_html_body,
                brand_impacted=brand_impacted,
            )

            # Add inline screenshot to HTML body if available
            if screenshot_path and html_body:
                screenshot_html = """
<div style="margin-top: 20px; padding: 10px; border: 1px solid #ddd; background: #f9f9f9;">
  <p style="margin: 0 0 10px 0; font-weight: bold;">Screenshot Evidence:</p>
  <img src="cid:screenshot" alt="Screenshot" style="max-width: 100%; border: 1px solid #ccc;">
</div>
"""
                html_body = html_body + screenshot_html

            # Send email with optional XARF attachment and inline screenshot
            send_result = send_email(email, subject, body, html_body, template_cc, xarf_attachments, inline_images)
            results.append({
                "email": email,
                "type": contact_type,
                "result": send_result,
                "xarf_attached": xarf_attachments is not None,
            })

            # Add history entry
            if send_result.get("success"):
                xarf_note = " with XARF attachment" if xarf_attachments else ""
                history_message = (
                    f"Follow-up report{xarf_note} sent to {email} ({contact_type})"
                    if is_followup
                    else f"Takedown notice{xarf_note} sent to {email} ({contact_type})"
                )
                await add_case_history(
                    case_id,
                    "email_sent",
                    history_message,
                )
                await increment_case_emails_sent(case_id)
            else:
                await add_case_history(
                    case_id,
                    "system",
                    f"Failed to send email to {email}: {send_result.get('error', 'Unknown error')}",
                )

        # Update case status if emails were sent successfully
        # Skip status change for follow-up reports (case stays in MONITORING)
        successful_sends = sum(1 for r in results if r["result"].get("success"))
        if successful_sends > 0 and not is_followup:
            # Set next monitoring time
            from datetime import timedelta

            async with async_session_factory() as session:
                case = await session.get(Case, str(case_id))
                if case:
                    case.next_monitor_at = now_utc() + timedelta(seconds=case.monitor_interval)
                    case.status = "MONITORING"
                    await session.commit()

        return {
            "success": True,
            "case_id": str(case_id),
            "emails_sent": successful_sends,
            "total_contacts": len(abuse_contacts),
            "xarf_enabled": prefer_xarf,
            "results": results,
        }

    except Exception as e:
        import traceback

        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


@shared_task(
    name="email.send_followup",
    bind=True,
    max_retries=2,
)
def send_followup_task(self, case_id: str, days_elapsed: int = 7) -> dict:
    """Send a follow-up email for a case that hasn't been resolved.

    Args:
        self: Celery task instance
        case_id: Case UUID as string
        days_elapsed: Days since initial report

    Returns:
        Dictionary with send results
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
    return asyncio.run(_send_followup_async(UUID(case_id), days_elapsed))


async def _send_followup_async(case_id: UUID, days_elapsed: int) -> dict:
    """Async implementation of follow-up email sending.

    Args:
        case_id: Case UUID
        days_elapsed: Days since initial report

    Returns:
        Dictionary with send results
    """
    case = await get_case_by_id(case_id)
    if not case:
        return {
            "success": False,
            "error": f"Case {case_id} not found",
        }

    if case.status == "RESOLVED":
        return {
            "success": True,
            "message": "Case already resolved, no follow-up needed",
        }

    # Add follow-up history
    await add_case_history(
        case_id,
        "system",
        f"Sending follow-up reminder after {days_elapsed} days",
    )

    # Re-send the report as a follow-up
    result = await _send_report_async(case_id, is_followup=True)

    return result


@shared_task(name="email.process_webhook")
def process_email_webhook_task(
    from_email: str,
    subject: str,
    body: str,
    headers: dict,
) -> dict:
    """Process an incoming email webhook.

    Args:
        from_email: Sender email address
        subject: Email subject line
        body: Email body
        headers: Email headers

    Returns:
        Dictionary with processing result
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
    return asyncio.run(_process_webhook_async(from_email, subject, body, headers))


async def _process_webhook_async(
    from_email: str,
    subject: str,
    body: str,
    headers: dict,
) -> dict:
    """Async implementation of webhook processing.

    Args:
        from_email: Sender email address
        subject: Email subject line
        body: Email body
        headers: Email headers

    Returns:
        Dictionary with processing result
    """
    import re

    # Try to extract case ID from subject
    case_id_match = re.search(r"[Case-ID:\s]+([a-f0-9-]{36})", subject, re.IGNORECASE)
    if not case_id_match:
        return {
            "success": False,
            "error": "No case ID found in subject line",
        }

    case_id_str = case_id_match.group(1)

    try:
        case_id = UUID(case_id_str)
    except ValueError:
        return {
            "success": False,
            "error": f"Invalid case ID format: {case_id_str}",
        }

    # Get the case
    case = await get_case_by_id(case_id)
    if not case:
        return {
            "success": False,
            "error": f"Case {case_id} not found",
        }

    # Add history entry
    await add_case_history(
        case_id,
        "email_received",
        f"Received reply from {from_email}: {subject[:100]}",
    )

    # Check for resolution indicators in email body
    body_lower = body.lower()
    resolution_keywords = [
        "suspended",
        "taken down",
        "resolved",
        "deleted",
        "removed",
        "shut down",
        "deactivated",
    ]

    is_resolution = any(keyword in body_lower for keyword in resolution_keywords)

    if is_resolution and case.status != "RESOLVED":
        # Update case to resolved
        async with async_session_factory() as session:
            case = await session.get(Case, str(case_id))
            if case:
                case.status = "RESOLVED"
                case.add_history_entry(
                    "email_received",
                    f"Resolution confirmed via email from {from_email}",
                )
                await session.commit()
                # Teams notification
                from app.services.teams_notify import send_case_resolved_notification
                await send_case_resolved_notification(case)

    return {
        "success": True,
        "case_id": str(case_id),
        "from_email": from_email,
        "resolution_indicated": is_resolution,
    }


__all__ = [
    "send_report_task",
    "send_followup_task",
    "process_email_webhook_task",
    "send_smtp_email",
    "send_email",
    "generate_takedown_notice",
]
