"""WHOIS and RDAP utilities for PhishTrack OSINT module."""
import asyncio
import re
import subprocess
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

import httpx


class RDAPResult:
    """Container for RDAP/WHOIS lookup results."""

    def __init__(
        self,
        domain: str,
        registrar: Optional[str] = None,
        created_date: Optional[str] = None,
        updated_date: Optional[str] = None,
        expires_date: Optional[str] = None,
        abuse_emails: Optional[list[str]] = None,
        status: Optional[list[str]] = None,
        nameservers: Optional[list[str]] = None,
        raw: Optional[dict] = None,
        error: Optional[str] = None,
    ):
        self.domain = domain
        self.registrar = registrar
        self.created_date = created_date
        self.updated_date = updated_date
        self.expires_date = expires_date
        self.abuse_emails = abuse_emails or []
        self.status = status or []
        self.nameservers = nameservers or []
        self.raw = raw or {}
        self.error = error
        self.success = error is None

    @property
    def domain_age_days(self) -> Optional[int]:
        """Calculate domain age in days."""
        if not self.created_date:
            return None
        try:
            from datetime import timezone
            created = datetime.fromisoformat(self.created_date.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            # Make created timezone-aware if it's naive
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return (now - created).days
        except Exception:
            return None


RDAP_BOOTSTRAP_URL = "https://rdap.org/domain/"

# Blocklist of known incorrect/unreliable abuse emails
# These will be filtered out from RDAP/WHOIS results
ABUSE_EMAIL_BLOCKLIST = {
    "report@abuseradar.com",  # Not a direct abuse contact
    "abuse@abuseradar.com",   # Third-party service, not actual provider
}

# Known hosting provider abuse contacts
# Used as fallback when RDAP/WHOIS doesn't return abuse emails
# These emails override any unreliable RDAP-returned emails
KNOWN_HOSTING_ABUSE = {
    # ASN-based mapping (most reliable)
    "AS14061": "abuse@digitalocean.com",  # DigitalOcean
    "AS16509": "abuse@amazonaws.com",  # Amazon AWS
    "AS15169": "network-abuse@google.com",  # Google Cloud
    "AS8075": "abuse@microsoft.com",  # Microsoft Azure
    "AS13335": "abuse@cloudflare.com",  # Cloudflare
    "AS16276": "abuse@ovh.net",  # OVH
    "AS24940": "abuse@hetzner.com",  # Hetzner
    "AS20473": "abuse@vultr.com",  # Vultr
    "AS63949": "abuse@linode.com",  # Linode/Akamai
    "AS47583": "abuse@hostinger.com",  # Hostinger International Limited
    "AS63949": "abuse@linode.com",  # Linode

    # Organization name-based fallback (case-insensitive match)
    "digitalocean": "abuse@digitalocean.com",
    "amazon": "abuse@amazonaws.com",
    "aws": "abuse@amazonaws.com",
    "google": "network-abuse@google.com",
    "microsoft": "abuse@microsoft.com",
    "azure": "abuse@microsoft.com",
    "cloudflare": "abuse@cloudflare.com",
    "ovh": "abuse@ovh.net",
    "hetzner": "abuse@hetzner.com",
    "vultr": "abuse@vultr.com",
    "linode": "abuse@linode.com",
    "hostinger": "abuse@hostinger.com",
}

# Alternative RDAP bootstrap servers to try
RDAP_ALTERNATIVES = [
    "https://rdap.identitystudios.com/domain/",
    "https://rdap.cloudflare.com/domain/",
    "https://rdap.identitydigital.services/rdap/domain/",
]

# TLD-specific RDAP servers (from ceker + additional)
# These are used directly for specific TLDs instead of the generic bootstrap
TLD_RDAP_SERVERS = {
    # Indonesian domains (Pandi)
    "id": "https://rdap.pandi.id/rdap/domain/",
    "my.id": "https://rdap.pandi.id/rdap/domain/",
    "co.id": "https://rdap.pandi.id/rdap/domain/",
    "ac.id": "https://rdap.pandi.id/rdap/domain/",
    "or.id": "https://rdap.pandi.id/rdap/domain/",
    "go.id": "https://rdap.pandi.id/rdap/domain/",
    "desa.id": "https://rdap.pandi.id/rdap/domain/",
    "sch.id": "https://rdap.pandi.id/rdap/domain/",
    # Common ccSLDs that might have specific RDAP servers
    "uk": "https://rdap.nominet.uk/domain/",
    "co.uk": "https://rdap.nominet.uk/domain/",
    "org.uk": "https://rdap.nominet.uk/domain/",
    "me.uk": "https://rdap.nominet.uk/domain/",
    "au": "https://rdap.auda.org.au/domain/",
    "com.au": "https://rdap.auda.org.au/domain/",
    "net.au": "https://rdap.auda.org.au/domain/",
    "org.au": "https://rdap.auda.org.au/domain/",
    "jp": "https://rdap.jprs.jp/domain/",
    "co.jp": "https://rdap.jprs.jp/domain/",
    "in": "https://rdap.registry.in/",
    "co.in": "https://rdap.registry.in/",
    "ac.in": "https://rdap.registry.in/",
    # European ccTLDs
    "de": "https://rdap.denic.de/domain/",
    "fr": "https://rdap.nic.fr/domain/",
    "nl": "https://rdap.sidn.nl/domain/",
    "be": "https://rdap.dns.be/domain/",
    "it": "https://rdap.nic.it/domain/",
    "es": "https://rdap.red.es/domain/",
    "se": "https://rdap.iis.se/domain/",
    "no": "https://rdap.norid.no/domain/",
    "dk": "https://rdap.dk-hostmaster.dk/domain/",
    "pl": "https://rdap.dns.pl/domain/",
    "ch": "https://rdap.switch.ch/domain/",
    "at": "https://rdap.nic.at/domain/",
    "cz": "https://rdap.nic.cz/domain/",
    # Other common TLDs
    # Identity Digital (formerly Afilias/Donuts) TLDs
    "info": "https://rdap.identitydigital.services/rdap/domain/",
    "biz": "https://rdap.identitydigital.services/rdap/domain/",
    "life": "https://rdap.identitydigital.services/rdap/domain/",
    "online": "https://rdap.identitydigital.services/rdap/domain/",
    "site": "https://rdap.identitydigital.services/rdap/domain/",
    "website": "https://rdap.identitydigital.services/rdap/domain/",
    "cloud": "https://rdap.nic.cloud/rdap/domain/",
    "ca": "https://rdap.ca/domain/",
    "br": "https://rdap.registro.br/domain/",
    "mx": "https://rdap.mx/nic/domain/",
    "ar": "https://rdap.nic.ar/domain/",
    "cl": "https://rdap.nic.cl/domain/",
    "co": "https://rdap.nic.co/domain/",
    "nz": "https://rdap.srs.net.nz/domain/",
    "za": "https://rdap.registry.net.za/domain/",
    "ru": "https://rdap.tcinet.ru/domain/",
    "kr": "https://rdap.kr/domain/",
    "tw": "https://rdap.twnic.tw/domain/",
    "th": "https://rdap.thnic.co.th/domain/",
    "vn": "https://rdap.vnnic.vn/domain/",
    "sg": "https://rdap.sgnic.sg/domain/",
    "hk": "https://rdap.hkirc.hk/domain/",
    "my": "https://rdap.mydnr.my/domain/",
    "ph": "https://rdap.ph/domain/",
    "id": "https://rdap.pandi.id/rdap/domain/",
}


async def query_rdap(domain: str, timeout: int = 10) -> RDAPResult:
    """Query RDAP for domain information.

    Args:
        domain: Domain to query
        timeout: HTTP timeout in seconds

    Returns:
        RDAPResult with domain information
    """
    # Build list of endpoints to try
    endpoints = []

    # First, try TLD-specific RDAP server if available
    # Need to extract the suffix (TLD or ccSLD)
    from app.utils.dns import get_registered_domain

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

    for base_url in endpoints:
        url = f"{base_url}{domain}"

        try:
            async with httpx.AsyncClient(timeout=timeout, verify=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                result = parse_rdap_response(domain, data)

                # If we got meaningful data, return it
                if result.registrar or result.created_date or result.abuse_emails:
                    return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                continue  # Try next endpoint
            if base_url == endpoints[-1]:  # Last endpoint
                return RDAPResult(domain, error=f"HTTP {e.response.status_code}: {e.response.text[:100]}")
        except httpx.TimeoutException:
            continue  # Try next endpoint
        except Exception as e:
            if base_url == endpoints[-1]:  # Last endpoint
                return RDAPResult(domain, error=str(e)[:200])
            continue

    # All endpoints failed
    return RDAPResult(domain, error="RDAP query failed - no data available")


def parse_rdap_response(domain: str, data: dict) -> RDAPResult:
    """Parse RDAP JSON response.

    Args:
        domain: Domain being queried
        data: RDAP JSON response

    Returns:
        Parsed RDAPResult
    """
    registrar = None
    created_date = None
    updated_date = None
    expires_date = None
    abuse_emails = []
    nameservers = []
    status = []

    # Extract events (dates)
    events = data.get("events", [])
    for event in events:
        event_action = event.get("eventAction", "").lower()
        event_date = event.get("eventDate")
        if event_date:
            if "registration" in event_action or "created" in event_action:
                created_date = event_date
            elif "last updated" in event_action or "updated" in event_action:
                updated_date = event_date
            elif "expiration" in event_action or "expires" in event_action:
                expires_date = event_date

    # Extract registrar/entity name
    entities = data.get("entities", [])
    for entity in entities:
        roles = entity.get("roles", [])
        if "registrar" in roles or "registration" in roles:
            vcard_array = entity.get("vcardArray", [])
            if vcard_array and isinstance(vcard_array, list) and len(vcard_array) > 1:
                for vcard in vcard_array[1]:
                    if isinstance(vcard, list) and len(vcard) > 3:
                        if vcard[0] == "fn":
                            registrar = vcard[3]
                            break
            if not registrar:
                registrar = entity.get("handle")

    # Also check top-level registrar field
    if not registrar and "registrar" in data:
        registrar = data["registrar"]

    # Extract abuse emails from entities - use enhanced extraction
    enhanced_emails = extract_abuse_emails_from_rdap(data)
    for email in enhanced_emails:
        if email not in abuse_emails:
            abuse_emails.append(email)

    # Extract nameservers
    nameservers_data = data.get("nameservers", [])
    for ns in nameservers_data:
        if "ldhName" in ns:
            nameservers.append(ns["ldhName"])

    # Extract status
    status_data = data.get("status", [])
    if isinstance(status_data, list):
        status = status_data

    return RDAPResult(
        domain=domain,
        registrar=registrar,
        created_date=created_date,
        updated_date=updated_date,
        expires_date=expires_date,
        abuse_emails=abuse_emails,
        status=status,
        nameservers=nameservers,
        raw=data,
    )


async def query_rdap_with_fallback(domain: str, timeout: int = 10) -> RDAPResult:
    """Query RDAP with fallback to WHOIS servers.

    Args:
        domain: Domain to query
        timeout: HTTP timeout in seconds

    Returns:
        RDAPResult with domain information
    """
    # First try RDAP
    result = await query_rdap(domain, timeout)

    if result.success and (result.abuse_emails or result.registrar):
        return result

    # If RDAP failed or returned limited info, try authoritative RDAP
    tld = domain.split(".")[-1] if "." in domain else ""

    # Some TLDs don't support RDAP well, add specific fallbacks
    if tld:
        tld_rdap_map = {
            "com": "https://rdap.verisign.com/com/v1/domain/",
            "net": "https://rdap.verisign.com/net/v1/domain/",
            "org": "https://rdap.publicinterestregistry.org/org/",
            "info": "https://rdap.identitydigital.services/rdap/domain/",
            "biz": "https://rdap.identitydigital.services/rdap/domain/",
            "io": "https://rdap.nic.io/domain/",
            "co": "https://rdap.nic.co/domain/",
            "ai": "https://rdap.nic.ai/domain/",
            "life": "https://rdap.identitydigital.services/rdap/domain/",
            "online": "https://rdap.identitydigital.services/rdap/domain/",
            "site": "https://rdap.identitydigital.services/rdap/domain/",
            "website": "https://rdap.identitydigital.services/rdap/domain/",
            "cloud": "https://rdap.nic.cloud/rdap/domain/",
        }

        if tld in tld_rdap_map:
            try:
                tld_url = f"{tld_rdap_map[tld]}{domain}"
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(tld_url)
                    if response.status_code == 200:
                        data = response.json()
                        result = parse_rdap_response(domain, data)
                        if result.registrar or result.created_date or result.abuse_emails:
                            return result
            except Exception:
                pass

    return result


def extract_abuse_emails_from_text(text: str) -> list[str]:
    """Extract abuse email addresses from text.

    Args:
        text: Text to search for emails

    Returns:
        List of found abuse emails
    """
    # Email regex pattern
    email_pattern = r"[\w.+-]+@[\w-]+\.[\w.-]+"
    emails = re.findall(email_pattern, text, re.IGNORECASE)

    # Filter for abuse-related emails
    abuse_emails = []
    for email in set(emails):
        email_lower = email.lower()
        if any(keyword in email_lower for keyword in ["abuse", "security", "spam", "noc", "hostmaster"]):
            abuse_emails.append(email_lower)

    return abuse_emails


def extract_abuse_emails_from_rdap(data: dict) -> list[str]:
    """Extract abuse emails from RDAP response with enhanced parsing.

    Scans entire RDAP response for email patterns in various fields including
    remarks, notices, descriptions, and entities. Also searches for common
    abuse-related keywords in context.

    Args:
        data: RDAP JSON response dictionary

    Returns:
        List of found abuse emails
    """
    import re
    abuse_emails = set()
    abuse_keywords = [
        "abuse", "security", "spam", "report", "incident",
        "noc", "hostmaster", "contact", "support"
    ]

    def extract_from_text(text: str, context: str = "") -> None:
        """Extract emails from text, checking context for abuse keywords."""
        if not text:
            return
        emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text, re.IGNORECASE)
        for email in emails:
            email_lower = email.lower()
            email_context = context.lower() + " " + email_lower
            if any(keyword in email_context for keyword in abuse_keywords):
                abuse_emails.add(email_lower)

    # 1. Check entities with abuse-related roles (including nested entities)
    def process_entity(entity: dict, parent_roles: list[str] = None) -> None:
        """Process an entity and its nested entities."""
        if not isinstance(entity, dict):
            return

        roles = entity.get("roles", [])
        all_roles = list(roles) + (parent_roles or [])
        vcard_array = entity.get("vcardArray", [])

        # Extract from vcard
        if vcard_array and isinstance(vcard_array, list) and len(vcard_array) > 1:
            for vcard in vcard_array[1]:
                if isinstance(vcard, list) and len(vcard) > 3:
                    if vcard[0] == "email" and vcard[3]:
                        email = vcard[3].lower()
                        # Always include if role is abuse/technical/administrative
                        if any(role in all_roles for role in ["abuse", "technical", "administrative"]):
                            abuse_emails.add(email)
                        # Otherwise check the email itself
                        elif any(keyword in email for keyword in abuse_keywords):
                            abuse_emails.add(email)

        # Check entity publicIds (some registrars put contact info here)
        public_ids = entity.get("publicIds", [])
        for pid in public_ids:
            extract_from_text(pid.get("id", ""), " ".join(all_roles))

        # Check entity handle (sometimes contains contact info)
        extract_from_text(entity.get("handle", ""), " ".join(all_roles))

        # Recursively process nested entities (e.g., registrar contains abuse contact)
        nested_entities = entity.get("entities", [])
        if nested_entities:
            for nested in nested_entities:
                process_entity(nested, all_roles)

    entities = data.get("entities", [])
    for entity in entities:
        process_entity(entity)

    # 2. Scan remarks fields for abuse contact info
    remarks = data.get("remarks", [])
    if not isinstance(remarks, list):
        remarks = [remarks] if remarks else []
    for remark in remarks:
        if isinstance(remark, dict):
            description = remark.get("description", [])
            if not isinstance(description, list):
                description = [description] if description else []
            for desc in description:
                if isinstance(desc, str):
                    extract_from_text(desc, "remarks")

    # 3. Scan notices fields
    notices = data.get("notices", [])
    if not isinstance(notices, list):
        notices = [notices] if notices else []
    for notice in notices:
        if isinstance(notice, dict):
            description = notice.get("description", [])
            if not isinstance(description, list):
                description = [description] if description else []
            for desc in description:
                if isinstance(desc, str):
                    extract_from_text(desc, "notices")

    # 4. Check status array for related info
    status_array = data.get("status", [])
    if isinstance(status_array, list):
        for status_val in status_array:
            extract_from_text(status_val, "status")

    # 5. Check events for any contact information
    events = data.get("events", [])
    for event in events:
        if isinstance(event, dict):
            extract_from_text(event.get("eventActor", ""), "events")
            extract_from_text(event.get("link", ""), "events")

    # 6. Check links in the response
    links = data.get("links", [])
    for link in links:
        if isinstance(link, dict):
            href = link.get("href", "")
            # Some RDAP responses include contact URLs
            if "abuse" in href.lower() or "contact" in href.lower():
                extract_from_text(href, "links")

    # 7. Deep scan entire raw JSON string for any abuse-related emails
    # This catches emails in non-standard fields
    json_str = str(data)
    all_emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", json_str, re.IGNORECASE)
    for email in all_emails:
        email_lower = email.lower()
        if any(keyword in email_lower for keyword in ["abuse", "security", "spam", "noc"]):
            abuse_emails.add(email_lower)

    # Filter out blocklisted emails
    filtered_emails = [email for email in abuse_emails if email not in ABUSE_EMAIL_BLOCKLIST]

    return sorted(list(filtered_emails))


def get_registrar_whois_server(domain: str) -> Optional[str]:
    """Get the WHOIS server for a domain's registrar.

    Args:
        domain: Domain to query

    Returns:
        WHOIS server hostname or None
    """
    tld = domain.split(".")[-1] if "." in domain else ""

    # Common TLD WHOIS servers
    tld_servers = {
        "com": "whois.verisign-grs.com",
        "net": "whois.verisign-grs.com",
        "org": "whois.pir.org",
        "info": "whois.afilias.net",
        "biz": "whois.biz",
        "name": "whois.nic.name",
        "io": "whois.nic.io",
        "co": "whois.nic.co",
        "ai": "whois.nic.ai",
    }

    return tld_servers.get(tld)


async def query_ip_rdap(ip: str, timeout: int = 10) -> dict:
    """Query RDAP for IP address information.

    Args:
        ip: IP address to query
        timeout: HTTP timeout in seconds

    Returns:
        Dictionary with IP information
    """
    # Multiple RDAP endpoints for IP queries
    # RIPE is included for European IP ranges that may have hosting-specific abuse contacts
    ip_rdap_endpoints = [
        f"https://rdap.org/ip/{ip}",
        f"https://rdap.cloudflare.com/ip/{ip}",
        f"https://rdap.db.ripe.net/ip/{ip}",  # For RIPE-managed IPs (e.g., DigitalOcean EU)
    ]

    for url in ip_rdap_endpoints:
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    continue
                data = response.json()

                # Extract relevant information
                result = {
                    "ip": ip,
                    "cidr": None,
                    "asn": None,
                    "asn_country": None,
                    "abuse_emails": [],
                    "raw": data,
                }

                # Extract network info
                if "cidr" in data:
                    cidr_data = data["cidr"][0] if isinstance(data["cidr"], list) else data["cidr"]
                    result["cidr"] = cidr_data.get("v4Prefix") or cidr_data.get("v6Prefix")

                # Extract ASN info - check multiple places
                # 1. Check entities with ASN role
                entities = data.get("entities", [])
                for entity in entities:
                    if "asn" in entity.get("roles", []):
                        asn_handle = entity.get("handle")
                        if asn_handle:
                            result["asn"] = asn_handle
                            break

                # 2. Check if ASN is directly in the response
                if not result["asn"] and "asn" in data:
                    result["asn"] = data["asn"]

                # 3. Check network info for ASN
                if not result["asn"] and "network" in data:
                    network = data["network"]
                    if isinstance(network, dict):
                        result["asn"] = network.get("asn")

                # Get abuse emails from entities
                for entity in entities:
                    roles = entity.get("roles", [])
                    if "abuse" in roles or "technical" in roles:
                        vcard_array = entity.get("vcardArray", [])
                        if vcard_array and isinstance(vcard_array) and len(vcard_array) > 1:
                            for vcard in vcard_array[1]:
                                if isinstance(vcard, list) and len(vcard) > 3:
                                    if vcard[0] == "email" and vcard[3]:
                                        email = vcard[3].lower()
                                        # Skip blocklisted emails
                                        if email in ABUSE_EMAIL_BLOCKLIST:
                                            continue
                                        if email not in result["abuse_emails"]:
                                            result["abuse_emails"].append(email)

                # ALWAYS check for known hosting provider and add if matched
                # This ensures we get BOTH registrar AND hosting contacts
                if result["asn"]:
                    # Extract ASN number from string (e.g., "AS47583 Hostinger" -> "AS47583")
                    asn_key = result["asn"]
                    # If ASN contains more than just the number, extract the ASXXXXX part
                    if " " in asn_key:
                        asn_key = asn_key.split(" ")[0]

                    if asn_key in KNOWN_HOSTING_ABUSE:
                        fallback_email = KNOWN_HOSTING_ABUSE[asn_key]
                        if fallback_email not in result["abuse_emails"]:
                            result["abuse_emails"].append(fallback_email)

                # Also check by organization name in RDAP data if no ASN match or no abuse emails
                if not result["abuse_emails"] or not (result["asn"] and any(asn in result["asn"] for asn in KNOWN_HOSTING_ABUSE.keys())):
                    # First check network name (e.g., "HOSTINGER-HOSTING")
                    network_name = data.get("name", "").lower()
                    if network_name:
                        for org_key, abuse_email in KNOWN_HOSTING_ABUSE.items():
                            if org_key in network_name and "@" in abuse_email:
                                if abuse_email not in result["abuse_emails"]:
                                    result["abuse_emails"].append(abuse_email)
                                break

                    # If not found via network name, check entity vcard fn fields
                    if not result["abuse_emails"]:
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
                                                    break

                # If we got meaningful data, return it
                if result["asn"] or result["abuse_emails"] or result["cidr"]:
                    return result

        except Exception as e:
            continue  # Try next endpoint

    # All endpoints failed, try free IP API fallback
    return await query_ip_api_fallback(ip)


async def query_ip_api_fallback(ip: str) -> dict:
    """Query IP information using free APIs as fallback.

    Args:
        ip: IP address to query

    Returns:
        Dictionary with IP information
    """
    # Try ip-api.com (free tier, no key needed for basic usage)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"http://ip-api.com/json/{ip}")
            if response.status_code == 200:
                data = response.json()
                return {
                    "ip": ip,
                    "asn": data.get("as"),
                    "asn_country": data.get("countryCode"),
                    "cidr": data.get("isp"),
                    "org": data.get("org"),
                    "abuse_emails": [],
                    "source": "ip-api.com",
                }
    except Exception:
        pass

    # Try ipinfo.io as another fallback
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"http://ipinfo.io/{ip}/json")
            if response.status_code == 200:
                data = response.json()
                return {
                    "ip": ip,
                    "asn": data.get("org", "").split(" ")[0] if data.get("org") else None,
                    "asn_country": data.get("country"),
                    "cidr": data.get("org"),
                    "org": data.get("org"),
                    "abuse_emails": [],
                    "source": "ipinfo.io",
                }
    except Exception:
        pass

    return {
        "ip": ip,
        "error": "All IP queries failed",
        "asn": None,
        "abuse_emails": [],
        "source": "none",
    }


def query_ip_whois_sync(ip: str, timeout: int = 30) -> dict:
    """Query traditional WHOIS for an IP address.

    Uses subprocess to call system whois command and parses
    abuse-mailbox, OrgAbuseEmail, and other abuse contact fields.

    Args:
        ip: IP address to query
        timeout: Command timeout in seconds

    Returns:
        Dictionary with abuse_emails and other info
    """
    result = {
        "ip": ip,
        "abuse_emails": [],
        "source": "whois",
        "raw": None,
    }

    try:
        # Run system whois command
        whois_process = subprocess.run(
            ["whois", ip],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if whois_process.returncode != 0:
            result["error"] = f"whois command failed: {whois_process.stderr[:200]}"
            return result

        whois_output = whois_process.stdout
        result["raw"] = whois_output

        # Parse abuse emails from various WHOIS fields
        abuse_emails = set()

        # Common abuse email field patterns in WHOIS output
        # Format varies by regional registry (ARIN, RIPE, APNIC, etc.)

        # Pattern 1: abuse-mailbox: email
        abuse_mailbox_matches = re.findall(
            r"abuse-mailbox:\s*([^\s\r\n]+@[\w.-]+)",
            whois_output,
            re.IGNORECASE
        )
        abuse_emails.update(abuse_mailbox_matches)

        # Pattern 2: OrgAbuseEmail: email
        org_abuse_matches = re.findall(
            r"OrgAbuseEmail:\s*([^\s\r\n]+@[\w.-]+)",
            whois_output,
            re.IGNORECASE
        )
        abuse_emails.update(org_abuse_matches)

        # Pattern 3: AbuseHandle: (some registrars put email here)
        abuse_handle_matches = re.findall(
            r"AbuseHandle:\s*([^\s\r\n]+@[\w.-]+)",
            whois_output,
            re.IGNORECASE
        )
        abuse_emails.update(abuse_handle_matches)

        # Pattern 4: OrgTechEmail: email (technical contact often handles abuse)
        org_tech_matches = re.findall(
            r"OrgTechEmail:\s*([^\s\r\n]+@[\w.-]+)",
            whois_output,
            re.IGNORECASE
        )
        abuse_emails.update(org_tech_matches)

        # Pattern 5: Emails in remarks: fields with abuse keywords
        remarks_blocks = re.findall(
            r"remarks:\s*([^\r\n]+)",
            whois_output,
            re.IGNORECASE
        )
        abuse_keywords = ["abuse", "security", "spam", "report", "incident"]
        for remark in remarks_blocks:
            emails_in_remark = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", remark, re.IGNORECASE)
            for email in emails_in_remark:
                email_lower = email.lower()
                if any(keyword in email_lower for keyword in abuse_keywords):
                    abuse_emails.add(email_lower)

        # Pattern 6: Emails in descr: fields with abuse keywords
        descr_blocks = re.findall(
            r"descr:\s*([^\r\n]+)",
            whois_output,
            re.IGNORECASE
        )
        for descr in descr_blocks:
            emails_in_descr = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", descr, re.IGNORECASE)
            for email in emails_in_descr:
                email_lower = email.lower()
                if any(keyword in email_lower for keyword in abuse_keywords):
                    abuse_emails.add(email_lower)

        # Pattern 7: General abuse-related email patterns in any line
        # Look for lines containing abuse keywords followed by email
        lines = whois_output.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ["abuse", "security"]):
                # Extract emails from this line
                emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", line, re.IGNORECASE)
                for email in emails:
                    abuse_emails.add(email.lower())

        # Convert set to sorted list, filtering out blocklisted emails
        filtered_emails = [email for email in abuse_emails if email.lower() not in ABUSE_EMAIL_BLOCKLIST]
        result["abuse_emails"] = sorted(list(filtered_emails))

        # Use known hosting provider fallback if no abuse emails found
        if not result["abuse_emails"]:
            # Extract ASN from whois output if present  
            asn_match = re.search(r"(?:origin(?:as)?|asn):\\s*(AS\\d+)", whois_output, re.IGNORECASE)
            if asn_match:
                asn = asn_match.group(1).upper()
                if asn in KNOWN_HOSTING_ABUSE:
                    result["abuse_emails"] = [KNOWN_HOSTING_ABUSE[asn]]


        # Also extract netname/organisation if present
        netname_match = re.search(r"netname:\s*([^\r\n]+)", whois_output, re.IGNORECASE)
        if netname_match:
            result["netname"] = netname_match.group(1).strip()

        org_match = re.search(r"organisation:\s*([^\r\n]+)", whois_output, re.IGNORECASE)
        if not org_match:
            org_match = re.search(r"org(?:name)?:\s*([^\r\n]+)", whois_output, re.IGNORECASE)
        if org_match:
            result["organisation"] = org_match.group(1).strip()

        return result

    except subprocess.TimeoutExpired:
        result["error"] = "whois command timed out"
        return result
    except FileNotFoundError:
        result["error"] = "whois command not found - install whois package"
        return result
    except Exception as e:
        result["error"] = f"whois query error: {str(e)[:200]}"
        return result


async def query_ip_whois_async(ip: str, timeout: int = 30) -> dict:
    """Async wrapper for IP WHOIS query.

    Args:
        ip: IP address to query
        timeout: Command timeout in seconds

    Returns:
        Dictionary with abuse_emails and other info
    """
    # Run the synchronous function in an executor to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, query_ip_whois_sync, ip, timeout)


async def query_whois_python_fallback(domain: str) -> dict:
    """Query WHOIS information using python-whois library.

    Args:
        domain: Domain to query

    Returns:
        Dictionary with domain information
    """
    try:
        import whois

        w = whois.whois(domain)

        # Extract information from the result - python-whois returns direct attributes
        registrar = getattr(w, 'registrar', None)

        # Parse dates - they are direct attributes on the whois result
        created_date = getattr(w, 'creation_date', None)
        expires_date = getattr(w, 'expiration_date', None)
        updated_date = getattr(w, 'last_updated', None)

        # Handle list of dates (some domains return multiple dates)
        if isinstance(created_date, list):
            created_date = created_date[0] if created_date else None
        if isinstance(expires_date, list):
            expires_date = expires_date[0] if expires_date else None
        if isinstance(updated_date, list):
            updated_date = updated_date[0] if updated_date else None

        # Extract emails
        emails_list = getattr(w, 'emails', []) or []
        emails = []
        if emails_list:
            import re
            if isinstance(emails_list, list):
                for email in emails_list:
                    if isinstance(email, str):
                        emails.append(email.lower())
            elif isinstance(emails_list, str):
                for email in re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', emails_list):
                    emails.append(email.lower())

        # Format dates as ISO strings
        created_date_str = None
        expires_date_str = None
        updated_date_str = None

        if created_date:
            if hasattr(created_date, 'isoformat'):
                created_date_str = created_date.isoformat()
            else:
                created_date_str = str(created_date)

        if expires_date:
            if hasattr(expires_date, 'isoformat'):
                expires_date_str = expires_date.isoformat()
            else:
                expires_date_str = str(expires_date)

        if updated_date:
            if hasattr(updated_date, 'isoformat'):
                updated_date_str = updated_date.isoformat()
            else:
                updated_date_str = str(updated_date)

        # Get nameservers
        nameservers = getattr(w, 'name_servers', []) or []
        if not isinstance(nameservers, list):
            nameservers = [nameservers] if nameservers else []

        return {
            "domain": domain,
            "registrar": registrar,
            "created_date": created_date_str,
            "updated_date": updated_date_str,
            "expires_date": expires_date_str,
            "abuse_emails": emails,
            "nameservers": nameservers,
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


async def query_whois_api_fallback(domain: str) -> dict:
    """Query WHOIS information using free APIs as fallback.

    Tries multiple sources:
    1. whois.com (web scraping)
    2. rdap.cc (WHOIS to RDAP gateway)
    3. whoisjs.com (JSON WHOIS API)

    Args:
        domain: Domain to query

    Returns:
        Dictionary with domain information
    """
    import re

    result = {
        "domain": domain,
        "registrar": None,
        "created_date": None,
        "abuse_emails": [],
        "nameservers": [],
        "source": "none",
    }

    # Try whois.com API (web scraping)
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(
                f"https://www.whois.com/whois/{domain}/",
                headers={"User-Agent": "Mozilla/5.0 (compatible; PhishTrack/1.0)"}
            )
            if response.status_code == 200:
                text = response.text

                # Extract registrar
                registrar_match = re.search(r'Registrar\s*:\s*([^\n<]+)', text, re.IGNORECASE)
                if registrar_match:
                    result["registrar"] = registrar_match.group(1).strip()

                # Extract dates (multiple formats)
                for pattern in [
                    r'Creation Date\s*:\s*([^\n<]+)',
                    r'Created On\s*:\s*([^\n<]+)',
                    r'Registered\s*:\s*([^\n<]+)',
                    r'created\s*:\s*([^\n<]+)',
                ]:
                    created_match = re.search(pattern, text, re.IGNORECASE)
                    if created_match:
                        result["created_date"] = created_match.group(1).strip()
                        break

                # Extract abuse email
                all_emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text, re.IGNORECASE)
                for email in all_emails:
                    email_lower = email.lower()
                    if any(k in email_lower for k in ["abuse", "security", "spam", "noc"]):
                        if email_lower not in result["abuse_emails"]:
                            result["abuse_emails"].append(email_lower)

                # Extract nameservers
                ns_matches = re.findall(r'Name Server\s*:\s*([^\n<]+)', text, re.IGNORECASE)
                if ns_matches:
                    result["nameservers"] = [ns.strip().lower() for ns in ns_matches[:4]]

                if result["registrar"] or result["abuse_emails"]:
                    result["source"] = "whois.com"
                    return result
    except Exception:
        pass

    # Try whoisjs.com (JSON API)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"https://whoisjs.com/{domain}")
            if response.status_code == 200:
                data = response.json()

                if data.get("registrar"):
                    result["registrar"] = data["registrar"]

                if data.get("created"):
                    result["created_date"] = data["created"]

                if data.get("nameservers"):
                    result["nameservers"] = data["nameservers"]

                # Extract emails from various fields
                for field in ["registrant_email", "admin_email", "tech_email", "billing_email"]:
                    if data.get(field):
                        email = data[field].lower()
                        if email not in result["abuse_emails"]:
                            result["abuse_emails"].append(email)

                if result["registrar"] or result["abuse_emails"]:
                    result["source"] = "whoisjs.com"
                    return result
    except Exception:
        pass

    # Try rdap.cc as another fallback
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"https://rdap.cc/domain/{domain}")
            if response.status_code == 200:
                data = response.json()
                rdap_result = parse_rdap_response(domain, data)

                if rdap_result.registrar:
                    result["registrar"] = rdap_result.registrar
                if rdap_result.created_date:
                    result["created_date"] = rdap_result.created_date
                if rdap_result.abuse_emails:
                    result["abuse_emails"].extend(rdap_result.abuse_emails)
                if rdap_result.nameservers:
                    result["nameservers"] = rdap_result.nameservers

                if result["registrar"] or result["abuse_emails"]:
                    result["source"] = "rdap.cc"
                    return result
    except Exception:
        pass

    return result


async def get_domain_osint(domain: str, ip: Optional[str] = None, timeout: int = 10) -> dict:
    """Get comprehensive OSINT data for a domain.

    Args:
        domain: Domain to investigate
        ip: Optional IP address to also lookup
        timeout: HTTP timeout in seconds

    Returns:
        Dictionary with domain and IP OSINT data
    """
    result = {
        "domain": domain,
        "domain_info": None,
        "ip_info": None,
    }

    # Get domain RDAP info
    rdap_result = await query_rdap_with_fallback(domain, timeout)
    result["domain_info"] = {
        "registrar": rdap_result.registrar,
        "created_date": rdap_result.created_date,
        "updated_date": rdap_result.updated_date,
        "expires_date": rdap_result.expires_date,
        "age_days": rdap_result.domain_age_days,
        "abuse_emails": rdap_result.abuse_emails,
        "nameservers": rdap_result.nameservers,
        "status": rdap_result.status,
    }

    # Get IP RDAP info if provided
    if ip:
        ip_info = await query_ip_rdap(ip, timeout)
        result["ip_info"] = ip_info

    return result
