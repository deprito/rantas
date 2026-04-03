"""OSINT investigation tasks for PhishTrack."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_sync_db_context
from app.models import Case
from app.tasks.celery_app import celery_app
from app.utils.dns import (
    extract_domain_from_url,
    get_a_records,
    get_ns_records,
    is_dns_resolving,
    perform_full_dns_lookup,
)
from app.utils.http import check_http_status
from app.utils.timezone import now_utc
import httpx  # Synchronous httpx for Celery tasks


def has_emails_sent(case_id: UUID) -> bool:
    """Check if a case has already had takedown emails sent (sync version).

    Args:
        case_id: Case UUID

    Returns:
        True if emails_sent > 0, False otherwise
    """
    with get_sync_db_context() as session:
        result = session.execute(select(Case).where(Case.id == str(case_id)))
        case = result.scalar_one_or_none()
        return case.emails_sent > 0 if case else False


async def has_emails_sent_async(case_id: UUID) -> bool:
    """Check if a case has already had takedown emails sent (async version).

    Args:
        case_id: Case UUID

    Returns:
        True if emails_sent > 0, False otherwise
    """
    from app.database import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(select(Case).where(Case.id == str(case_id)))
        case = result.scalar_one_or_none()
        return case.emails_sent > 0 if case else False


def _analyze_url_sync(case_id: UUID, url: str) -> dict:
    """Synchronous implementation of URL analysis for Celery.

    Args:
        case_id: Case UUID
        url: URL to analyze

    Returns:
        Dictionary with analysis results
    """
    try:
        # Add initial history entry
        add_case_history_sync(case_id, "system", "Initiating analysis...")

        # Extract domain
        domain = extract_domain_from_url(url)

        # Perform DNS lookup (sync version is already used)
        add_case_history_sync(case_id, "dns_check", "Initiating DNS lookup...")
        dns_result = perform_full_dns_lookup(domain, timeout=10)

        if dns_result.error:
            add_case_history_sync(
                case_id,
                "dns_check",
                f"DNS lookup failed: {dns_result.error}",
            )
            # Continue anyway - RDAP might still work

        # Get primary IP
        primary_ip = dns_result.a_records[0] if dns_result.a_records else None

        # Record DNS completion
        if primary_ip:
            add_case_history_sync(
                case_id,
                "dns_check",
                f"DNS lookup complete: {len(dns_result.a_records)} A records, "
                f"{len(dns_result.ns_records)} NS records, IP: {primary_ip}"
            )
        else:
            add_case_history_sync(
                case_id,
                "dns_check",
                f"DNS lookup returned {len(dns_result.a_records)} A records, "
                f"{len(dns_result.ns_records)} NS records - will try RDAP directly"
            )

        # Perform RDAP/WHOIS lookup (sync version)
        add_case_history_sync(case_id, "dns_check", "Querying WHOIS/RDAP...")
        rdap_result = query_rdap_sync(domain, timeout=15, case_id=case_id)

        # If RDAP didn't return registrar info, created date, OR abuse emails, try WHOIS fallback
        # This catches cases where RDAP returns registrar data but no abuse contacts (common with Cloudflare)
        if not rdap_result.registrar or not rdap_result.created_date or not rdap_result.abuse_emails:
            add_case_history_sync(
                case_id, "dns_check",
                f"RDAP incomplete (registrar={bool(rdap_result.registrar)}, "
                f"created={bool(rdap_result.created_date)}, "
                f"abuse_emails={len(rdap_result.abuse_emails)}), trying WHOIS fallback..."
            )
            whois_data = query_whois_python_fallback_sync(domain)
            if whois_data.get("registrar") and not rdap_result.registrar:
                rdap_result.registrar = whois_data["registrar"]
            if whois_data.get("created_date") and not rdap_result.created_date:
                rdap_result.created_date = whois_data["created_date"]
            if whois_data.get("abuse_emails"):
                add_case_history_sync(
                    case_id, "dns_check",
                    f"WHOIS fallback found {len(whois_data['abuse_emails'])} abuse email(s)"
                )
                for email in whois_data["abuse_emails"]:
                    if email not in rdap_result.abuse_emails:
                        rdap_result.abuse_emails.append(email)
            if whois_data.get("nameservers") and not rdap_result.nameservers:
                rdap_result.nameservers = whois_data["nameservers"]

            # If still no abuse emails, try external API fallback
            if not rdap_result.abuse_emails and not whois_data.get("error"):
                add_case_history_sync(case_id, "dns_check", "Trying external WHOIS API fallback...")
                try:
                    import asyncio
                    whois_api_result = asyncio.run(
                        _query_whois_api_fallback_sync_wrapper(domain)
                    )
                    if whois_api_result.get("abuse_emails"):
                        add_case_history_sync(
                            case_id, "dns_check",
                            f"External API found {len(whois_api_result['abuse_emails'])} abuse email(s) "
                            f"via {whois_api_result.get('source', 'unknown')}"
                        )
                        for email in whois_api_result["abuse_emails"]:
                            if email not in rdap_result.abuse_emails:
                                rdap_result.abuse_emails.append(email)
                    if whois_api_result.get("registrar") and not rdap_result.registrar:
                        rdap_result.registrar = whois_api_result["registrar"]
                    if whois_api_result.get("created_date") and not rdap_result.created_date:
                        rdap_result.created_date = whois_api_result["created_date"]
                except Exception as e:
                    add_case_history_sync(
                        case_id, "dns_check",
                        f"External API fallback failed: {str(e)[:100]}"
                    )

        # Gather abuse contacts
        abuse_contacts = []

        # From domain WHOIS/RDAP
        for email in rdap_result.abuse_emails:
            abuse_contacts.append({
                "type": "registrar",
                "email": email,
            })

        # From IP RDAP if we have an IP
        if primary_ip:
            add_case_history_sync(case_id, "dns_check", f"Querying IP RDAP for {primary_ip}...")
            ip_info = query_ip_rdap_sync(primary_ip, timeout=10, case_id=case_id)
            # Only fallback to API if RDAP failed AND didn't find abuse emails
            # (RDAP may return abuse emails even without ASN)
            if ("error" in ip_info or not ip_info.get("asn")) and not ip_info.get("abuse_emails"):
                # RDAP failed, try API fallback
                add_case_history_sync(case_id, "dns_check", f"RDAP lookup failed for {primary_ip}, trying API fallback...")
                ip_info = query_ip_api_fallback_sync(primary_ip)
            if "abuse_emails" in ip_info:
                for email in ip_info["abuse_emails"]:
                    if email not in [ac["email"] for ac in abuse_contacts]:
                        abuse_contacts.append({
                            "type": "hosting",
                            "email": email,
                        })

            # If still no abuse emails from IP, try traditional WHOIS
            if not ip_info.get("abuse_emails") or len(ip_info.get("abuse_emails", [])) == 0:
                add_case_history_sync(case_id, "dns_check", f"Trying WHOIS fallback for IP {primary_ip}...")
                ip_whois = query_ip_whois_fallback_sync(primary_ip)
                if ip_whois.get("abuse_emails"):
                    add_case_history_sync(
                        case_id,
                        "dns_check",
                        f"WHOIS found {len(ip_whois['abuse_emails'])} abuse contact(s) for IP"
                    )
                    for email in ip_whois["abuse_emails"]:
                        if email not in [ac["email"] for ac in abuse_contacts]:
                            abuse_contacts.append({
                                "type": "hosting",
                                "email": email,
                            })
                elif ip_whois.get("error"):
                    add_case_history_sync(
                        case_id,
                        "dns_check",
                        f"IP WHOIS lookup skipped: {ip_whois['error']}"
                    )

        # Perform HTTP check (sync version)
        add_case_history_sync(case_id, "http_check", "Checking HTTP status...")
        http_result = check_http_status_sync(
            url,
            user_agent=settings.HTTP_USER_AGENT,
            timeout=settings.HTTP_TIMEOUT,
        )

        http_message = f"HTTP check: "
        if http_result.is_live:
            http_message += f"Site is live (HTTP {http_result.status_code})"
        elif http_result.error:
            http_message += f"Site error: {http_result.error}"
        else:
            http_message += "Site not responding"

        add_case_history_sync(
            case_id,
            "http_check",
            http_message,
            status=http_result.status_code,
        )

        # Compile domain info
        domain_info = {
            "domain": domain,
            "ip": primary_ip,
            "ns_records": dns_result.ns_records,
            "registrar": rdap_result.registrar,
            "age_days": rdap_result.domain_age_days,
            "created_date": rdap_result.created_date,
            "whois_created": rdap_result.created_date,
            "whois_updated": rdap_result.updated_date,
            "whois_expires": rdap_result.expires_date,
            "asn": None,
        }

        # Log domain age for debugging
        add_case_history_sync(
            case_id,
            "dns_check",
            f"Domain info: registrar={rdap_result.registrar}, "
            f"created={rdap_result.created_date}, "
            f"age_days={rdap_result.domain_age_days}"
        )

        # Add ASN from IP lookup if available
        if primary_ip:
            ip_info = query_ip_rdap_sync(primary_ip, timeout=5, case_id=case_id)
            asn = ip_info.get("asn")
            if not asn or "error" in ip_info:
                # RDAP failed, try API fallback
                ip_info = query_ip_api_fallback_sync(primary_ip)
                asn = ip_info.get("asn")

            if asn:
                domain_info["asn"] = asn
                add_case_history_sync(
                    case_id,
                    "dns_check",
                    f"Found ASN: {asn}",
                )

        # Update case with collected information
        add_case_history_sync(
            case_id,
            "dns_check",
            f"Storing domain_info: {domain_info}"
        )
        update_case_domain_info_sync(case_id, domain_info)
        update_case_abuse_contacts_sync(case_id, abuse_contacts)

        # Determine if phishing is still active
        if http_result.is_taken_down:
            # Site appears to be taken down already
            update_case_status_sync(case_id, "RESOLVED")
            add_case_history_sync(
                case_id,
                "http_check",
                "Site appears to be taken down - marking as RESOLVED",
            )
            # Teams notification (sync)
            from app.services.teams_notify import send_case_resolved_notification_sync
            with get_sync_db_context() as session:
                resolved_case = session.execute(select(Case).where(Case.id == str(case_id))).scalar_one_or_none()
                if resolved_case:
                    send_case_resolved_notification_sync(resolved_case)
        elif abuse_contacts:
            # Have abuse contacts - check if takedown was already sent
            already_sent = has_emails_sent(case_id)
            if already_sent:
                # Already sent takedown, go to monitoring mode
                update_case_status_sync(case_id, "MONITORING")
                add_case_history_sync(
                    case_id,
                    "system",
                    f"Analysis complete - {len(abuse_contacts)} abuse contact(s) found. "
                    f"Takedown already sent, monitoring for takedown.",
                )
            else:
                # Ready to send report - wait for user to trigger
                update_case_status_sync(case_id, "READY_TO_REPORT")
                add_case_history_sync(
                    case_id,
                    "system",
                    f"Analysis complete - {len(abuse_contacts)} abuse contact(s) found. Ready to report.",
                )
        else:
            # No abuse contacts found, mark as failed to report
            update_case_status_sync(case_id, "FAILED")
            add_case_history_sync(
                case_id,
                "system",
                "Analysis complete but no abuse contacts found - cannot send report",
            )

        return {
            "success": True,
            "case_id": str(case_id),
            "domain_info": domain_info,
            "abuse_contacts": abuse_contacts,
            "http_status": http_result.status_code,
            "is_live": http_result.is_live,
        }

    except Exception as e:
        import traceback

        error_msg = f"Analysis failed: {str(e)}"
        add_case_history_sync(case_id, "system", error_msg)
        update_case_status_sync(case_id, "MONITORING")

        return {
            "success": False,
            "error": error_msg,
            "traceback": traceback.format_exc(),
            "case_id": str(case_id),
        }


# Synchronous database operations for Celery tasks


def add_case_history_sync(
    case_id: UUID,
    entry_type: str,
    message: str,
    status: Optional[int] = None,
) -> None:
    """Synchronous wrapper for adding a history entry to a case."""
    with get_sync_db_context() as session:
        result = session.execute(select(Case).where(Case.id == str(case_id)))
        case = result.scalar_one_or_none()
        if case:
            case.add_history_entry(entry_type, message, status)
            case.updated_at = now_utc()
            session.commit()


def update_case_status_sync(case_id: UUID, status_value: str) -> None:
    """Synchronous wrapper for updating case status."""
    with get_sync_db_context() as session:
        result = session.execute(select(Case).where(Case.id == str(case_id)))
        case = result.scalar_one_or_none()
        if case:
            old_status = case.status
            case.status = status_value
            case.updated_at = now_utc()
            case.add_history_entry("system", f"Status updated to {status_value}")
            session.commit()


def update_case_domain_info_sync(case_id: UUID, domain_info: dict) -> None:
    """Synchronous wrapper for updating case domain information."""
    try:
        with get_sync_db_context() as session:
            result = session.execute(select(Case).where(Case.id == str(case_id)))
            case = result.scalar_one_or_none()
            if case:
                # Merge instead of replace - preserve source field and submission metadata
                existing_info = case.domain_info or {}
                existing_info.update(domain_info)
                case.domain_info = existing_info
                case.updated_at = now_utc()
                session.commit()
    except Exception as e:
        import traceback
        add_case_history_sync(
            case_id,
            "system",
            f"ERROR updating domain_info: {str(e)[:200]}"
        )


def update_case_abuse_contacts_sync(case_id: UUID, abuse_contacts: list) -> None:
    """Synchronous wrapper for updating case abuse contacts."""
    with get_sync_db_context() as session:
        result = session.execute(select(Case).where(Case.id == str(case_id)))
        case = result.scalar_one_or_none()
        if case:
            case.abuse_contacts = abuse_contacts
            case.updated_at = now_utc()
            session.commit()


# Synchronous wrappers for async functions


def query_rdap_sync(domain: str, timeout: int = 10, case_id: UUID = None):
    """Synchronous RDAP query using httpx with retry logic.

    Includes TLD-specific RDAP servers for better coverage (e.g., Pandi for .id domains).
    Implements retry logic with exponential backoff for transient failures.

    Args:
        domain: Domain to query
        timeout: HTTP timeout in seconds
        case_id: Optional case UUID for debug logging

    Returns:
        RDAPResult with domain information
    """
    from app.utils.whois import (
        RDAPResult, parse_rdap_response, RDAP_ALTERNATIVES, RDAP_BOOTSTRAP_URL, TLD_RDAP_SERVERS
    )
    from app.utils.dns import get_registered_domain
    import httpx
    import time

    # Build list of endpoints to try
    endpoints = []

    # First, try TLD-specific RDAP server if available
    try:
        domain_parts = get_registered_domain(domain)
        suffix = domain_parts["suffix"]  # e.g., "my.id", "co.uk", "com"

        # Check if we have a TLD-specific server
        if suffix in TLD_RDAP_SERVERS:
            endpoints.append(TLD_RDAP_SERVERS[suffix])

        # Also try individual TLD part for ccSLDs
        if "." in suffix:
            tld_part = suffix.split(".")[-1]  # e.g., "id" from "my.id"
            if tld_part in TLD_RDAP_SERVERS:
                tld_server = TLD_RDAP_SERVERS[tld_part]
                if tld_server not in endpoints:
                    endpoints.append(tld_server)
    except Exception:
        pass  # Fall back to generic servers

    # Add generic bootstrap servers
    endpoints.extend([RDAP_BOOTSTRAP_URL] + RDAP_ALTERNATIVES)

    # Remove duplicates while preserving order
    seen = set()
    unique_endpoints = []
    for endpoint in endpoints:
        if endpoint not in seen:
            seen.add(endpoint)
            unique_endpoints.append(endpoint)
    endpoints = unique_endpoints

    last_error = None

    for endpoint_idx, base_url in enumerate(endpoints):
        url = f"{base_url}{domain}"

        # Retry logic: up to 2 retries per endpoint with exponential backoff
        max_retries = 2 if endpoint_idx == 0 else 1  # More retries for primary endpoint
        base_timeout = timeout

        for attempt in range(max_retries):
            try:
                # Increase timeout for retries (exponential backoff)
                current_timeout = base_timeout * (1 + attempt * 0.5)

                with httpx.Client(timeout=current_timeout, verify=True) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    data = response.json()

                    result = parse_rdap_response(domain, data)

                    # Log successful query
                    if case_id:
                        email_count = len(result.abuse_emails)
                        log_msg = (
                            f"RDAP success from {base_url}: "
                            f"registrar={result.registrar}, "
                            f"created={result.created_date}, "
                            f"abuse_emails={email_count}"
                        )
                        add_case_history_sync(case_id, "dns_check", log_msg)

                    # If we got meaningful data, return it
                    if result.registrar or result.created_date or result.abuse_emails:
                        return result

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP {e.response.status_code}"
                if e.response.status_code == 404:
                    break  # Don't retry 404s
                if e.response.status_code >= 500:
                    # Server error - retry with backoff
                    if attempt < max_retries - 1:
                        time.sleep(1 * (attempt + 1))
                        continue
                if base_url == endpoints[-1] and attempt == max_retries - 1:
                    if case_id:
                        add_case_history_sync(
                            case_id, "dns_check",
                            f"RDAP failed for all endpoints: {last_error}"
                        )
                    return RDAPResult(domain, error=f"HTTP {e.response.status_code}")

            except httpx.TimeoutException as e:
                last_error = f"Timeout after {current_timeout}s"
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                # Timeout on last retry - try next endpoint
                if case_id:
                    add_case_history_sync(
                        case_id, "dns_check",
                        f"RDAP timeout for {base_url} (attempt {attempt + 1}/{max_retries})"
                    )
                break

            except httpx.ConnectError as e:
                last_error = f"Connection error: {str(e)[:100]}"
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                if case_id:
                    add_case_history_sync(
                        case_id, "dns_check",
                        f"RDAP connection error for {base_url}: {last_error}"
                    )
                break

            except Exception as e:
                last_error = str(e)[:200]
                if case_id:
                    add_case_history_sync(
                        case_id, "dns_check",
                        f"RDAP error for {base_url}: {last_error}"
                    )
                break

    # All endpoints failed
    if case_id:
        add_case_history_sync(
            case_id, "dns_check",
            f"RDAP query failed for all {len(endpoints)} endpoints"
        )
    return RDAPResult(domain, error="RDAP query failed - no data available")


def query_ip_rdap_sync(ip: str, timeout: int = 10, case_id: UUID = None):
    """Synchronous IP RDAP query with retry logic.

    Args:
        ip: IP address to query
        timeout: HTTP timeout in seconds
        case_id: Optional case UUID for debug logging

    Returns:
        Dictionary with IP information
    """
    from app.utils.whois import RDAP_ALTERNATIVES, extract_abuse_emails_from_rdap
    import httpx
    import time

    # Multiple RDAP endpoints for IP queries
    # RIPE is included for European IP ranges that may have hosting-specific abuse contacts
    ip_rdap_endpoints = [
        f"https://rdap.org/ip/{ip}",
        f"https://rdap.cloudflare.com/ip/{ip}",
        f"https://rdap.db.ripe.net/ip/{ip}",  # For RIPE-managed IPs (e.g., DigitalOcean EU)
    ]

    last_error = None

    for endpoint_idx, url in enumerate(ip_rdap_endpoints):
        # Retry logic for each endpoint
        max_retries = 2

        for attempt in range(max_retries):
            try:
                current_timeout = timeout * (1 + attempt * 0.5)

                with httpx.Client(timeout=current_timeout, follow_redirects=True) as client:
                    response = client.get(url)
                    if response.status_code != 200:
                        last_error = f"HTTP {response.status_code}"
                        if response.status_code >= 500 and attempt < max_retries - 1:
                            time.sleep(1 * (attempt + 1))
                            continue
                        break

                    data = response.json()

                    result = {
                        "ip": ip,
                        "cidr": None,
                        "asn": None,
                        "abuse_emails": [],
                    }

                    # Extract network info
                    if "cidr" in data:
                        cidr_data = data["cidr"][0] if isinstance(data["cidr"], list) else data["cidr"]
                        result["cidr"] = cidr_data.get("v4Prefix") or cidr_data.get("v6Prefix")

                    # Extract ASN info
                    entities = data.get("entities", [])
                    for entity in entities:
                        if "asn" in entity.get("roles", []):
                            asn_handle = entity.get("handle")
                            if asn_handle:
                                result["asn"] = asn_handle
                                break

                    # Use enhanced abuse email extraction
                    enhanced_emails = extract_abuse_emails_from_rdap(data)
                    result["abuse_emails"] = enhanced_emails

                    # ALWAYS check for known hosting provider and add if matched
                    # This ensures we get BOTH registrar AND hosting contacts
                    from app.utils.whois import KNOWN_HOSTING_ABUSE

                    # Extract ASN number from string (e.g., "AS47583 Hostinger" -> "AS47583")
                    asn_key = result["asn"]
                    if asn_key and " " in asn_key:
                        asn_key = asn_key.split(" ")[0]

                    if asn_key and asn_key in KNOWN_HOSTING_ABUSE:
                        fallback_email = KNOWN_HOSTING_ABUSE[asn_key]
                        if fallback_email not in result["abuse_emails"]:
                            result["abuse_emails"].append(fallback_email)
                            if case_id:
                                add_case_history_sync(
                                    case_id, "dns_check",
                                    f"Added hosting provider abuse email for {asn_key}: {fallback_email}"
                                )

                    if not result["abuse_emails"] or not asn_key:
                        # Check by organization name in RDAP data
                        fallback_added = False

                        # First check network name (e.g., "HOSTINGER-HOSTING")
                        network_name = data.get("name", "").lower()
                        if network_name:
                            for org_key, abuse_email in KNOWN_HOSTING_ABUSE.items():
                                if org_key in network_name and "@" in abuse_email:
                                    if abuse_email not in result["abuse_emails"]:
                                        result["abuse_emails"].append(abuse_email)
                                        fallback_added = True
                                        if case_id:
                                            add_case_history_sync(
                                                case_id, "dns_check",
                                                f"Added hosting provider abuse email for network '{network_name}': {abuse_email}"
                                            )
                                    break

                        # If not found via network name, check entity vcard fn fields
                        if not fallback_added:
                            for entity in entities:
                                vcard_array = entity.get("vcardArray", [])
                                if vcard_array and isinstance(vcard_array, list) and len(vcard_array) > 1:
                                    for vcard in vcard_array[1]:
                                        if isinstance(vcard, list) and len(vcard) > 3:
                                            if vcard[0] == "fn":  # Full name/organization
                                                org_name = vcard[3].lower()
                                                for org_key, abuse_email in KNOWN_HOSTING_ABUSE.items():
                                                    if org_key in org_name and "@" in abuse_email:
                                                        if abuse_email not in result["abuse_emails"]:
                                                            result["abuse_emails"].append(abuse_email)
                                                            if case_id:
                                                                add_case_history_sync(
                                                                    case_id, "dns_check",
                                                                    f"Added hosting provider abuse email for '{org_name}': {abuse_email}"
                                                                )
                                                            break

                    # Log success
                    if case_id:
                        add_case_history_sync(
                            case_id, "dns_check",
                            f"IP RDAP success from {url}: asn={result['asn']}, "
                            f"abuse_emails={len(result['abuse_emails'])}"
                        )

                    # If we got meaningful data, return it
                    if result["asn"] or result["abuse_emails"] or result["cidr"]:
                        return result

            except httpx.TimeoutException:
                last_error = f"Timeout after {current_timeout}s"
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                if case_id:
                    add_case_history_sync(
                        case_id, "dns_check",
                        f"IP RDAP timeout for {url}"
                    )
                break

            except Exception as e:
                last_error = str(e)[:100]
                if case_id:
                    add_case_history_sync(
                        case_id, "dns_check",
                        f"IP RDAP error for {url}: {last_error}"
                    )
                break

    if case_id and last_error:
        add_case_history_sync(
            case_id, "dns_check",
            f"All IP RDAP queries failed: {last_error}"
        )

    return {
        "ip": ip,
        "error": "All IP queries failed",
        "asn": None,
        "abuse_emails": [],
    }


def query_ip_api_fallback_sync(ip: str):
    """Synchronous IP API fallback."""
    import httpx

    # Try ip-api.com
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"http://ip-api.com/json/{ip}")
            if response.status_code == 200:
                data = response.json()
                return {
                    "ip": ip,
                    "asn": data.get("as"),
                    "abuse_emails": [],
                }
    except Exception:
        pass

    # Try ipinfo.io
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"http://ipinfo.io/{ip}/json")
            if response.status_code == 200:
                data = response.json()
                return {
                    "ip": ip,
                    "asn": data.get("org", "").split(" ")[0] if data.get("org") else None,
                    "abuse_emails": [],
                }
    except Exception:
        pass

    return {
        "ip": ip,
        "error": "All IP queries failed",
        "asn": None,
        "abuse_emails": [],
    }


def query_ip_whois_fallback_sync(ip: str):
    """Synchronous IP WHOIS fallback for abuse contact extraction.

    Queries traditional WHOIS for abuse-mailbox and other abuse contact fields.

    Args:
        ip: IP address to query

    Returns:
        Dictionary with abuse emails
    """
    from app.utils.whois import query_ip_whois_sync
    return query_ip_whois_sync(ip)


def query_whois_python_fallback_sync(domain: str):
    """Synchronous WHOIS query using python-whois."""
    try:
        import whois

        w = whois.whois(domain)

        return {
            "domain": domain,
            "registrar": getattr(w, 'registrar', None),
            "created_date": _format_date(getattr(w, 'creation_date', None)),
            "expires_date": _format_date(getattr(w, 'expiration_date', None)),
            "abuse_emails": _extract_emails(getattr(w, 'emails', None)),
            "nameservers": getattr(w, 'name_servers', []) if hasattr(w, 'name_servers') else [],
            "source": "python-whois",
        }
    except Exception as e:
        return {
            "domain": domain,
            "registrar": None,
            "created_date": None,
            "abuse_emails": [],
            "nameservers": [],
            "error": str(e),
            "source": "python-whois-error",
        }


def _query_whois_api_fallback_sync_wrapper(domain: str):
    """Synchronous wrapper for async WHOIS API fallback.

    Runs the async query_whois_api_fallback in a new event loop.

    Args:
        domain: Domain to query

    Returns:
        Dictionary with domain information
    """
    from app.utils.whois import query_whois_api_fallback

    # Create new event loop for this async call
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(query_whois_api_fallback(domain))
        return result
    finally:
        loop.close()


def _format_date(date_val):
    """Format a date value to ISO string."""
    if date_val is None:
        return None
    if hasattr(date_val, 'isoformat'):
        return date_val.isoformat()
    if isinstance(date_val, list):
        date_val = date_val[0] if date_val else None
    if hasattr(date_val, 'isoformat'):
        return date_val.isoformat()
    return str(date_val)


def _extract_emails(emails_str):
    """Extract emails from a string or list."""
    import re
    emails = []
    if isinstance(emails_str, str):
        for email in re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', emails_str):
            emails.append(email.lower())
    elif isinstance(emails_str, list):
        for email in emails_str:
            if isinstance(email, str):
                emails.append(email.lower())
    return emails


def check_http_status_sync(url: str, user_agent: str = None, timeout: int = 10) -> object:
    """Synchronous HTTP status check."""
    from app.utils.http import HTTPCheckResult
    import httpx
    import time

    if user_agent is None:
        user_agent = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
            "Mobile/15E148 Safari/604.1"
        )

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    }

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            start_time = time.time()
            response = client.get(url, headers=headers)
            elapsed_ms = (time.time() - start_time) * 1000

            return HTTPCheckResult(
                url=url,
                status_code=response.status_code,
                is_live=True,
                final_url=str(response.url),
                redirect_count=len(response.history),
                response_time_ms=elapsed_ms,
                server=response.headers.get("Server"),
                content_type=response.headers.get("Content-Type"),
            )

    except httpx.UnsupportedProtocol as e:
        return HTTPCheckResult(
            url=url,
            is_live=False,
            error=f"Unsupported protocol: {str(e)}",
        )
    except httpx.TimeoutException:
        return HTTPCheckResult(
            url=url,
            is_live=False,
            error="Connection timeout",
        )
    except httpx.ConnectError as e:
        error_str = str(e).lower()
        if "dns" in error_str or "name" in error_str or "resolve" in error_str:
            return HTTPCheckResult(
                url=url,
                is_live=False,
                error="DNS resolution failed - likely taken down",
            )
        return HTTPCheckResult(
            url=url,
            is_live=False,
            error=f"Connection failed: {str(e)}",
        )
    except Exception as e:
        return HTTPCheckResult(
            url=url,
            is_live=False,
            error=f"Unexpected error: {str(e)}",
        )
from app.database import async_session_factory
from app.utils.whois import (
    query_ip_rdap,
    query_ip_api_fallback,
    query_ip_whois_async,
    query_whois_python_fallback,
    query_rdap_with_fallback,
)


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


async def update_case_status(case_id: UUID, status: str) -> None:
    """Update case status.

    Args:
        case_id: Case UUID
        status: New status
    """
    async with async_session_factory() as session:
        result = await session.execute(select(Case).where(Case.id == str(case_id)))
        case = result.scalar_one_or_none()
        if case:
            case.status = status
            case.updated_at = now_utc()
            case.add_history_entry("system", f"Status updated to {status}")
            await session.commit()


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
        result = await session.execute(select(Case).where(Case.id == str(case_id)))
        case = result.scalar_one_or_none()
        if case:
            case.add_history_entry(entry_type, message, status)
            case.updated_at = now_utc()
            await session.commit()


async def update_case_domain_info(
    case_id: UUID,
    domain_info: dict,
) -> None:
    """Update case domain information.

    Args:
        case_id: Case UUID
        domain_info: Domain information dictionary
    """
    async with async_session_factory() as session:
        result = await session.execute(select(Case).where(Case.id == str(case_id)))
        case = result.scalar_one_or_none()
        if case:
            # Merge instead of replace - preserve source field and submission metadata
            existing_info = case.domain_info or {}
            existing_info.update(domain_info)
            case.domain_info = existing_info
            case.updated_at = now_utc()
            await session.commit()


async def update_case_abuse_contacts(
    case_id: UUID,
    abuse_contacts: list,
) -> None:
    """Update case abuse contacts.

    Args:
        case_id: Case UUID
        abuse_contacts: List of abuse contact dictionaries
    """
    async with async_session_factory() as session:
        result = await session.execute(select(Case).where(Case.id == str(case_id)))
        case = result.scalar_one_or_none()
        if case:
            case.abuse_contacts = abuse_contacts
            case.updated_at = now_utc()
            await session.commit()


@shared_task(
    name="osint.analyze_url",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def analyze_url_task(self, case_id: str, url: str) -> dict:
    """Analyze a URL for OSINT information (synchronous version for Celery).

    Args:
        self: Celery task instance
        case_id: Case UUID as string
        url: URL to analyze

    Returns:
        Dictionary with analysis results
    """
    # Use synchronous version to avoid asyncio issues
    return _analyze_url_sync(UUID(case_id), url)


async def _analyze_url_async(case_id: UUID, url: str) -> dict:
    """Async implementation of URL analysis.

    Args:
        case_id: Case UUID
        url: URL to analyze

    Returns:
        Dictionary with analysis results
    """
    try:
        # Add initial history entry
        await add_case_history(case_id, "system", "Initiating analysis...")

        # Extract domain
        domain = extract_domain_from_url(url)

        # Perform DNS lookup
        await add_case_history(case_id, "dns_check", "Initiating DNS lookup...")
        dns_result = perform_full_dns_lookup(domain, timeout=10)

        if dns_result.error:
            await add_case_history(
                case_id,
                "dns_check",
                f"DNS lookup failed: {dns_result.error}",
            )
            # Continue anyway - RDAP might still work

        # Get primary IP
        primary_ip = dns_result.a_records[0] if dns_result.a_records else None

        # Record DNS completion
        if primary_ip:
            await add_case_history(
                case_id,
                "dns_check",
                f"DNS lookup complete: {len(dns_result.a_records)} A records, "
                f"{len(dns_result.ns_records)} NS records, IP: {primary_ip}",
            )
        else:
            await add_case_history(
                case_id,
                "dns_check",
                f"DNS lookup returned {len(dns_result.a_records)} A records, "
                f"{len(dns_result.ns_records)} NS records - will try RDAP directly",
            )

        # Perform RDAP/WHOIS lookup
        await add_case_history(case_id, "dns_check", "Querying WHOIS/RDAP...")

        rdap_result = await query_rdap_with_fallback(domain, timeout=10)

        # If RDAP didn't return registrar info, try WHOIS fallback
        if not rdap_result.registrar or not rdap_result.created_date:
            await add_case_history(case_id, "dns_check", "RDAP limited data, trying WHOIS fallback...")
            whois_data = await query_whois_python_fallback(domain)
            if whois_data.get("registrar") and not rdap_result.registrar:
                rdap_result.registrar = whois_data["registrar"]
            if whois_data.get("created_date") and not rdap_result.created_date:
                rdap_result.created_date = whois_data["created_date"]
            if whois_data.get("abuse_emails"):
                for email in whois_data["abuse_emails"]:
                    if email not in rdap_result.abuse_emails:
                        rdap_result.abuse_emails.append(email)
            if whois_data.get("nameservers") and not rdap_result.nameservers:
                rdap_result.nameservers = whois_data["nameservers"]

        # Gather abuse contacts
        abuse_contacts = []

        # From domain WHOIS/RDAP
        for email in rdap_result.abuse_emails:
            abuse_contacts.append({
                "type": "registrar",
                "email": email,
            })

        # From IP RDAP if we have an IP
        if primary_ip:
            await add_case_history(case_id, "dns_check", f"Querying IP RDAP for {primary_ip}...")
            ip_info = await query_ip_rdap(primary_ip, timeout=10)
            if "error" in ip_info or not ip_info.get("asn"):
                # RDAP failed, try API fallback
                await add_case_history(case_id, "dns_check", f"RDAP lookup failed for {primary_ip}, trying API fallback...")
                ip_info = await query_ip_api_fallback(primary_ip)
            if "abuse_emails" in ip_info:
                for email in ip_info["abuse_emails"]:
                    if email not in [ac["email"] for ac in abuse_contacts]:
                        abuse_contacts.append({
                            "type": "hosting",
                            "email": email,
                        })

            # If still no abuse emails from IP, try traditional WHOIS
            if not ip_info.get("abuse_emails") or len(ip_info.get("abuse_emails", [])) == 0:
                await add_case_history(case_id, "dns_check", f"Trying WHOIS fallback for IP {primary_ip}...")
                ip_whois = await query_ip_whois_async(primary_ip)
                if ip_whois.get("abuse_emails"):
                    await add_case_history(
                        case_id,
                        "dns_check",
                        f"WHOIS found {len(ip_whois['abuse_emails'])} abuse contact(s) for IP"
                    )
                    for email in ip_whois["abuse_emails"]:
                        if email not in [ac["email"] for ac in abuse_contacts]:
                            abuse_contacts.append({
                                "type": "hosting",
                                "email": email,
                            })
                elif ip_whois.get("error"):
                    await add_case_history(
                        case_id,
                        "dns_check",
                        f"IP WHOIS lookup skipped: {ip_whois['error']}"
                    )

        # Perform HTTP check
        await add_case_history(case_id, "http_check", "Checking HTTP status...")

        http_result = await check_http_status(
            url,
            user_agent=settings.HTTP_USER_AGENT,
            timeout=settings.HTTP_TIMEOUT,
        )

        http_message = f"HTTP check: "
        if http_result.is_live:
            http_message += f"Site is live (HTTP {http_result.status_code})"
        elif http_result.error:
            http_message += f"Site error: {http_result.error}"
        else:
            http_message += "Site not responding"

        await add_case_history(
            case_id,
            "http_check",
            http_message,
            status=http_result.status_code,
        )

        # Compile domain info
        domain_info = {
            "domain": domain,
            "ip": primary_ip,
            "ns_records": dns_result.ns_records,
            "registrar": rdap_result.registrar,
            "age_days": rdap_result.domain_age_days,
            "created_date": rdap_result.created_date,
            "whois_created": rdap_result.created_date,
            "whois_updated": rdap_result.updated_date,
            "whois_expires": rdap_result.expires_date,
            "asn": None,
        }

        # Log domain age for debugging
        await add_case_history(
            case_id,
            "dns_check",
            f"Domain info: registrar={rdap_result.registrar}, "
            f"created={rdap_result.created_date}, "
            f"age_days={rdap_result.domain_age_days}"
        )

        # Add ASN from IP lookup if available
        if primary_ip:
            ip_info = await query_ip_rdap(primary_ip, timeout=5)
            asn = ip_info.get("asn")
            if not asn or "error" in ip_info:
                # RDAP failed, try API fallback
                ip_info = await query_ip_api_fallback(primary_ip)
                asn = ip_info.get("asn")

            if asn:
                domain_info["asn"] = asn
                await add_case_history(
                    case_id,
                    "dns_check",
                    f"Found ASN: {asn}",
                )

        # Update case with collected information
        await update_case_domain_info(case_id, domain_info)
        await update_case_abuse_contacts(case_id, abuse_contacts)

        # Determine if phishing is still active
        if http_result.is_taken_down:
            # Site appears to be taken down already
            await update_case_status(case_id, "RESOLVED")
            await add_case_history(
                case_id,
                "http_check",
                "Site appears to be taken down - marking as RESOLVED",
            )
            # Teams notification
            from app.services.teams_notify import send_case_resolved_notification
            from app.database import async_session_factory
            async with async_session_factory() as session:
                resolved_case = (await session.execute(select(Case).where(Case.id == str(case_id)))).scalar_one_or_none()
                if resolved_case:
                    await send_case_resolved_notification(resolved_case)
        elif abuse_contacts:
            # Have abuse contacts - check if takedown was already sent
            already_sent = await has_emails_sent_async(case_id)
            if already_sent:
                # Already sent takedown, go to monitoring mode
                await update_case_status(case_id, "MONITORING")
                await add_case_history(
                    case_id,
                    "system",
                    f"Analysis complete - {len(abuse_contacts)} abuse contact(s) found. "
                    f"Takedown already sent, monitoring for takedown.",
                )
            else:
                # Ready to send report - wait for user to trigger
                await update_case_status(case_id, "READY_TO_REPORT")
                await add_case_history(
                    case_id,
                    "system",
                    f"Analysis complete - {len(abuse_contacts)} abuse contact(s) found. Ready to report.",
                )
        else:
            # No abuse contacts found, mark as failed to report
            await update_case_status(case_id, "FAILED")
            await add_case_history(
                case_id,
                "system",
                "Analysis complete but no abuse contacts found - cannot send report",
            )

        return {
            "success": True,
            "case_id": str(case_id),
            "domain_info": domain_info,
            "abuse_contacts": abuse_contacts,
            "http_status": http_result.status_code,
            "is_live": http_result.is_live,
        }

    except Exception as e:
        import traceback

        error_msg = f"Analysis failed: {str(e)}"
        await add_case_history(case_id, "system", error_msg)
        await update_case_status(case_id, "MONITORING")

        return {
            "success": False,
            "error": error_msg,
            "traceback": traceback.format_exc(),
            "case_id": str(case_id),
        }


@shared_task(
    name="osint.quick_dns_check",
    bind=True,
)
def quick_dns_check_task(self, domain: str) -> dict:
    """Perform a quick DNS check to see if a domain is resolving.

    Args:
        self: Celery task instance
        domain: Domain to check

    Returns:
        Dictionary with DNS resolution status
    """
    import asyncio

    return asyncio.run(_quick_dns_check_async(domain))


async def _quick_dns_check_async(domain: str) -> dict:
    """Async implementation of quick DNS check.

    Args:
        domain: Domain to check

    Returns:
        Dictionary with DNS resolution status
    """
    try:
        resolving = is_dns_resolving(domain)
        a_records = get_a_records(domain) if resolving else []

        return {
            "domain": domain,
            "resolving": resolving,
            "a_records": a_records,
            "ip": a_records[0] if a_records else None,
        }
    except Exception as e:
        return {
            "domain": domain,
            "resolving": False,
            "error": str(e),
        }


__all__ = [
    "analyze_url_task",
    "quick_dns_check_task",
]
