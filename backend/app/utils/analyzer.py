"""URL safety analyzer for phishing detection.

Provides comprehensive URL analysis including:
- Static analysis: URL structure, TLD checks, keyword detection
- Domain intelligence: DNS lookups, domain age, WHOIS data
- Dynamic behavior: HTTP checks, redirects, SSL verification
- Reputation: Blacklist checks, threat indicators
"""
import asyncio
import ipaddress
import re
import socket
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from urllib.parse import parse_qs, urlparse, unquote

import httpx

from app.utils.dns import (
    extract_domain_from_url,
    get_registered_domain,
    get_a_records,
    get_ns_records,
    perform_full_dns_lookup,
)


class RiskLevel(str, Enum):
    """Risk level classification."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class QuickAnalysisResponse:
    """Response model for quick URL analysis."""

    def __init__(
        self,
        url: str,
        risk_level: RiskLevel,
        score: int,
        can_submit: bool,
        message: str,
        quick_flags: list[str],
        analysis_id: Optional[str] = None,
    ):
        self.url = url
        self.risk_level = risk_level
        self.score = score
        self.can_submit = can_submit
        self.message = message
        self.quick_flags = quick_flags
        self.analysis_id = analysis_id

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON response."""
        return {
            "url": self.url,
            "risk_level": self.risk_level.value,
            "score": self.score,
            "can_submit": self.can_submit,
            "message": self.message,
            "quick_flags": self.quick_flags,
            "analysis_id": self.analysis_id,
        }


class StaticURLAnalyzer:
    """Static URL analyzer for pattern-based threat detection.

    Performs instant analysis without external network calls.
    """

    # Suspicious TLDs commonly used in phishing
    SUSPICIOUS_TLDS = {
        "xyz", "top", "win", "bid", "trade", "download", "racing", "online",
        "sale", "site", "stream", "xyz", "club", "click", "link", "loan",
        "review", "faith", "accountant", "cricket", "date", "gaming", "tech",
        "science", "tk", "ml", "ga", "cf", "gq", "pw", "cc",
    }

    # Legitimate TLDs for financial services (often impersonated)
    FINANCIAL_TLDS = {
        "bank", "finance", "insurance", "investments", "money", "credit",
        "card", "loan", "mortgage", "trading", "broker", "pay",
    }

    # High-risk country TLDs (common for spam/phishing)
    HIGH_RISK_COUNTRY_TLDS = {
        "cn", "ru", "kp", "ng", "pk", "bd", "za", "ua", "by",
    }

    # Known brands commonly impersonated in phishing
    KNOWN_BRANDS = {
        "example", "testcorp", "amazonaws", "amazon",
    }

    # Internal brand variations to detect typosquatting
    # Maps canonical brand name to list of known typosquat patterns
    TYPOSQUAT_PATTERNS = {
        "example": [
            # === Character Omissions (missing one char) ===
            "exmple",        # missing 'a'
            "exaple",        # missing 'm'
            "exmple",        # missing 'a'

            # === Character Repetitions (double letters) ===
            "eexample",      # double 'e'
            "exxample",      # double 'x'
            "exaample",      # double 'a'
            "exammple",      # double 'm'
            "examplee",      # double 'e' at end

            # === Adjacent Character Swaps ===
            "exampel",       # l<->e swap
            "exampel",       # e<->l swap
            "exampel",       # le->el

            # === Visual/Letter-to-Number Substitutions ===
            "3xample",       # e->3
            "ex4mple",       # a->4
            "examp1e",       # l->1
            "3x4mpl3",       # multiple subs

            # === Keyboard Proximity (nearby keys) ===
            "wxample",       # e->w
            "dxample",       # e->d
            "ezample",       # x->z
            "ecample",       # x->c
            "exzmple",       # a->z
            "exsmple",       # a->s
            "exanple",       # m->n
            "examoke",       # l->k

            # === Phonetically Similar ===
            "exampul",       # le->ul
            "egzample",      # x->gz
            "eksample",      # x->ks

            # === Common Misspellings ===
            "exampel",       # le->el
            "examble",       # p->b
            "exanple",       # m->n
        ],
        "testcorp": [
            # === Character Omissions ===
            "testorp",       # missing 'c'
            "testcrp",       # missing 'o'
            "testcor",       # missing 'p'

            # === Character Repetitions ===
            "ttestcorp",     # double 't'
            "tesstcorp",     # double 's'
            "testtcorp",     # double 't'
            "testccorp",     # double 'c'
            "testcoorp",     # double 'o'
            "testcorrp",     # double 'r'
            "testcorpp",     # double 'p'

            # === Character Swaps ===
            "tsetcorp",      # e<->s swap
            "tesctcorp",     # t<->c swap
            "testocorp",     # c<->o swap

            # === Visual/Letter-to-Number Substitutions ===
            "7estcorp",      # t->7
            "te5tcorp",      # s->5
            "testc0rp",      # o->0
            "7e57c0rp",      # multiple subs

            # === Keyboard Proximity ===
            "yestcorp",      # t->y
            "restcorp",      # t->r
            "teatcorp",      # s->a
            "tedtcorp",      # s->d
            "testxorp",      # c->x
            "testvorp",      # c->v
            "testcirp",      # o->i
            "testcoro",      # p->o

            # === Common Misspellings ===
            "tescorp",       # missing 't'
            "testcopr",      # p<->r swap
            "etscorp",       # missing first 't'
        ],
        "amazonaws": [
            # === Number Substitutions ===
            "amaz0naws",     # o->0
            "amaz0naws",     # o->0 (first o)
            "amaz0n4ws",     # o->0, a->4
            "am4zonaws",     # a->4
            "amazon4ws",     # a->4
            "amazonaw5",     # s->5

            # === Character Omissions ===
            "amzonaws",      # missing a
            "amaonaws",      # missing z
            "amaznaws",      # missing o
            "amazonas",      # missing w

            # === Character Repetitions ===
            "aamazonaws",    # double a
            "ammazonaws",    # double m
            "amazzonaws",    # double z
            "amazoonaws",    # double o
            "amazonnaws",    # double n
            "amazonaaws",    # double a
            "amazonawws",    # double w
            "amazonawss",    # double s

            # === Character Swaps ===
            "maazonaws",     # a<->m swap
            "amzaonaws",     # a<->z swap
            "amozonaws",     # z<->o swap

            # === Phonetically Similar ===
            "amaxonaws",     # o->x
            "amazinaws",     # on->in
            "arnazonaws",    # m->n

            # === Common Misspellings ===
            "ammazon",       # extra m
            "amazzon",       # double z
            "anazonaws",     # m->n
            "emazonaws",     # a->e
            "umazonaws",     # a->u
        ],
    }

    # Suspicious keywords in URLs (from ceker + existing)
    SUSPICIOUS_KEYWORDS = {
        "login", "signin", "verify", "confirm", "account", "update",
        "secure", "banking", "wallet", "crypto", "bitcoin", "password",
        "authenticate", "validation", "suspend", "restore", "recover",
        "unlock", "expired", "security", "billing", "payment",
        "transaction", "transfer", "deposit", "withdraw", "claim",
        "reward", "prize", "winner", "lottery", "bonus", "free",
        # Additional from ceker
        "urgent", "immediate", "critical", "alert", "notice",
    }

    # Keywords that are suspicious when in the hostname (from ceker)
    HOSTNAME_PHISHING_KEYWORDS = {
        "verify", "confirm", "update", "secure", "account", "login", "urgent",
        "signin", "auth", "authenticate", "validation", "suspend", "restore",
        "recover", "unlock", "expired", "security", "billing", "wallet",
    }

    # Suspicious URL patterns
    PATTERNS = {
        "ip_address": re.compile(r"^https?://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"),
        "hex_ip": re.compile(r"^https?://0x[0-9a-f]+", re.IGNORECASE),
        "decimal_ip": re.compile(r"^https?://\d{8,10}"),
        "lots_of_hyphens": re.compile(r"-{5,}"),
        "lots_of_dots": re.compile(r"\.{4,}"),
        "base64_like": re.compile(r"[A-Za-z0-9+/]{40,}={0,2}"),
        "random_subdomain": re.compile(r"^[a-z0-9]{20,}", re.IGNORECASE),
        "punycode": re.compile(r"xn--"),
        "lookalike": re.compile(r"([a-z])\\1{3,}"),  # Repeated chars
    }

    # Legitimate domains that should not be flagged
    WHITELIST = {
        "google.com", "facebook.com", "microsoft.com", "apple.com",
        "amazon.com", "amazonaws.com", "s3.amazonaws.com", "aws.amazon.com",
        "netflix.com", "paypal.com", "ebay.com",
        "linkedin.com", "twitter.com", "instagram.com", "zoom.us",
        "adobe.com", "dropbox.com", "slack.com", "github.com",
        "stackoverflow.com", "wikipedia.org", "reddit.com", "yahoo.com",
    }

    @classmethod
    def analyze(cls, url: str) -> tuple[int, list[str]]:
        """Perform static URL analysis.

        Args:
            url: URL to analyze

        Returns:
            Tuple of (risk_score, list_of_flags)
        """
        score = 0
        flags = []

        try:
            # Use get_registered_domain for proper ccSLD handling
            domain_parts = get_registered_domain(url)
            registered_domain = domain_parts["registered_domain"]
            suffix = domain_parts["suffix"]  # e.g., "co.uk", "my.id", "com"

            # Check whitelist
            if registered_domain in cls.WHITELIST:
                return 0, ["Whitelisted domain"]

            # Check for IP address instead of domain
            if cls.PATTERNS["ip_address"].match(url):
                score += 40
                flags.append("Uses IP address")

            # Check for hex/decimal IP encoding
            if cls.PATTERNS["hex_ip"].match(url):
                score += 35
                flags.append("Uses hex-encoded IP")

            if cls.PATTERNS["decimal_ip"].match(url):
                score += 35
                flags.append("Uses decimal-encoded IP")

            # Check TLD/suffix (now properly handles ccSLDs)
            if suffix in cls.SUSPICIOUS_TLDS:
                score += 20
                flags.append(f"Suspicious TLD: .{suffix}")

            if suffix in cls.HIGH_RISK_COUNTRY_TLDS:
                score += 15
                flags.append(f"High-risk country TLD: .{suffix}")

            # Get the full netloc for punycode and lookalike checks
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()

            # Check for punycode (IDN homograph attacks)
            if cls.PATTERNS["punycode"].search(netloc):
                score += 30
                flags.append("Uses punycode (possible homograph attack)")

            # Check for lookalike characters (repeated letters)
            if cls.PATTERNS["lookalike"].search(netloc):
                score += 15
                flags.append("Suspicious repeated characters")

            # Check for random-looking subdomains
            subdomain = domain_parts["subdomain"]
            if cls.PATTERNS["random_subdomain"].match(subdomain):
                score += 10
                flags.append("Random-looking subdomain")

            # Check for unusual domain structure (subdomain heavy)
            # From ceker: hostname.split('.').length > 3 is suspicious
            # But exclude 'www' subdomain which is normal and legitimate
            parsed = urlparse(url)
            hostname_parts = parsed.hostname.split('.') if parsed.hostname else []

            # Don't count 'www' as an unusual subdomain
            if hostname_parts and hostname_parts[0] == 'www':
                # Remove 'www' to check the actual subdomain structure
                actual_parts = hostname_parts[1:]
            else:
                actual_parts = hostname_parts

            if len(actual_parts) > 3:
                score += 15
                flags.append("Unusual domain structure (subdomain heavy)")

            # Check for phishing keywords in hostname (from ceker)
            if parsed.hostname:
                hostname_lower = parsed.hostname.lower()
                for keyword in cls.HOSTNAME_PHISHING_KEYWORDS:
                    if keyword in hostname_lower:
                        # Exclude legitimate domains like verify.com, confirm.io
                        legitimate_domains = ["verify.com", "confirm.io", "login.gov"]
                        if not any(hostname_lower.endswith(legit) for legit in legitimate_domains):
                            score += 20
                            flags.append(f"Hostname contains phishing keyword: {keyword}")
                            break

            # Check for suspicious URL structure
            if cls.PATTERNS["lots_of_hyphens"].search(url):
                score += 10
                flags.append("Excessive hyphens in URL")

            if cls.PATTERNS["lots_of_dots"].search(url):
                score += 10
                flags.append("Excessive dots in URL")

            # Check for brand impersonation
            # Check domain name and subdomain for brand names
            for brand in cls.KNOWN_BRANDS:
                domain_name = domain_parts["domain"]
                if brand in domain_name.lower():
                    # But it's not the real brand
                    if not registered_domain.endswith(f"{brand}.com") and not registered_domain.endswith(f"{brand}.org") and not registered_domain.endswith(f"{brand}.co.id"):
                        score += 25
                        flags.append(f"Possible {brand.capitalize()} impersonation")
                        break

            # Check for typosquatting of internal brands
            domain_name_lower = domain_parts["domain"].lower()
            for brand, patterns in cls.TYPOSQUAT_PATTERNS.items():
                for pattern in patterns:
                    if pattern in domain_name_lower and pattern != brand:
                        # It's a typosquat, not the real brand
                        score += 35
                        flags.append(f"Possible typosquat of {brand}")
                        break
                    elif pattern in domain_name_lower:
                        # Contains the pattern - check if it's the real domain
                        if not registered_domain.endswith(f"{brand}.co.id") and not registered_domain.endswith(f"{brand}.com"):
                            score += 30
                            flags.append(f"Possible {brand} impersonation")
                            break

            # Check path for suspicious keywords
            path = parsed.path.lower() + " " + unquote(parsed.path).lower()
            for keyword in cls.SUSPICIOUS_KEYWORDS:
                if keyword in path:
                    score += 5
                    flags.append(f"Suspicious keyword: {keyword}")

            # Check query parameters
            if parsed.query:
                query_params = parse_qs(parsed.query)
                for param in query_params:
                    if any(kw in param.lower() for kw in ["token", "session", "auth", "key", "id"]):
                        score += 3
                        flags.append(f"Sensitive query parameter: {param}")
                        break

            # Check URL length (very long URLs are suspicious)
            if len(url) > 200:
                score += 10
                flags.append("Unusually long URL")

            # Check for port specification (non-standard)
            if ":" in parsed.netloc:
                port = parsed.netloc.split(":")[-1]
                try:
                    port_num = int(port)
                    if port_num not in [80, 443]:
                        score += 15
                        flags.append(f"Uses non-standard port: {port}")
                except ValueError:
                    pass

        except Exception:
            # If parsing fails, give moderate risk score
            score = 20
            flags.append("Invalid URL structure")

        return min(score, 100), flags


class DomainIntelligenceAnalyzer:
    """Domain intelligence analyzer using DNS and WHOIS data."""

    @classmethod
    async def analyze(cls, domain: str, include_whois: bool = True) -> tuple[int, list[str]]:
        """Perform domain intelligence analysis.

        Args:
            domain: Domain to analyze
            include_whois: Whether to perform WHOIS/RDAP lookup for domain age

        Returns:
            Tuple of (risk_score, list_of_flags)
        """
        score = 0
        flags = []

        # === PRIORITY 1: Domain Age (from ceker) ===
        # Domain age is the highest priority factor
        if include_whois:
            from app.utils.whois import (
                query_rdap_with_fallback,
                query_whois_api_fallback,
                query_whois_python_fallback,
            )

            rdap_successful = False
            domain_age_days = None
            domain_expires = None

            try:
                rdap_result = await query_rdap_with_fallback(domain, timeout=5)
                if rdap_result.success:
                    rdap_successful = True
                    domain_age_days = rdap_result.domain_age_days
                    domain_expires = datetime.fromisoformat(rdap_result.expires_date) if rdap_result.expires_date else None
            except Exception:
                pass  # RDAP failed, continue to WHOIS fallback

            # If RDAP failed, try WHOIS API fallback
            if not rdap_successful:
                whois_api_result = await query_whois_api_fallback(domain)
                if whois_api_result.get("created_date") or whois_api_result.get("registrar"):
                    # Extract domain age from WHOIS API
                    created_date_str = whois_api_result.get("created_date")
                    if created_date_str:
                        try:
                            from datetime import timezone
                            # Try parsing various date formats
                            for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"]:
                                try:
                                    created_date = datetime.strptime(created_date_str.split("(")[0].strip(), fmt)
                                    if created_date.tzinfo is None:
                                        created_date = created_date.replace(tzinfo=timezone.utc)
                                    now = datetime.now(timezone.utc)
                                    domain_age_days = (now - created_date).days
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass

                    # Extract expiration date
                    expires_str = whois_api_result.get("expires_date")
                    if expires_str:
                        try:
                            from datetime import timezone
                            for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"]:
                                try:
                                    domain_expires = datetime.strptime(expires_str.split("(")[0].strip(), fmt)
                                    if domain_expires.tzinfo is None:
                                        domain_expires = domain_expires.replace(tzinfo=timezone.utc)
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass

                    rdap_successful = True

                else:
                    # Try python-whois fallback
                    whois_python_result = await query_whois_python_fallback(domain)
                    if whois_python_result.get("created_date"):
                        created_date_val = whois_python_result.get("created_date")
                        if created_date_val:
                            try:
                                from datetime import timezone

                                # Check if it's already a datetime object
                                if isinstance(created_date_val, datetime):
                                    created_date = created_date_val
                                else:
                                    # Parse as string
                                    created_date_str = str(created_date_val).split("(")[0].strip()

                                    # Handle timezone offset in ISO format (e.g., +00:00)
                                    if "+" in created_date_str and "T" in created_date_str:
                                        # Replace +HH:MM with Z for simpler parsing
                                        created_date_str = created_date_str.rsplit("+", 1)[0] + "Z"

                                    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"]:
                                        try:
                                            created_date = datetime.strptime(created_date_str, fmt)
                                            if created_date.tzinfo is None:
                                                created_date = created_date.replace(tzinfo=timezone.utc)
                                            break
                                        except ValueError:
                                            continue

                                now = datetime.now(timezone.utc)
                                domain_age_days = (now - created_date).days
                            except Exception as e:
                                # Log error for debugging
                                import sys
                                print(f"Error parsing created_date: {e}", file=sys.stderr)
                                import traceback
                                traceback.print_exc(file=sys.stderr)

                        expires_val = whois_python_result.get("expires_date")
                        if expires_val:
                            try:
                                from datetime import timezone

                                # Check if it's already a datetime object
                                if isinstance(expires_val, datetime):
                                    domain_expires = expires_val
                                else:
                                    # Parse as string
                                    expires_str = str(expires_val).split("(")[0].strip()

                                    # Handle timezone offset in ISO format (e.g., +00:00)
                                    if "+" in expires_str and "T" in expires_str:
                                        expires_str = expires_str.rsplit("+", 1)[0] + "Z"

                                    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"]:
                                        try:
                                            domain_expires = datetime.strptime(expires_str, fmt)
                                            if domain_expires.tzinfo is None:
                                                domain_expires = domain_expires.replace(tzinfo=timezone.utc)
                                            break
                                        except ValueError:
                                            continue
                            except Exception as e:
                                import sys
                                print(f"Error parsing expires_date: {e}", file=sys.stderr)

                        rdap_successful = True

            # Calculate domain age risk if we got data from RDAP or WHOIS
            if rdap_successful and (domain_age_days is not None or domain_expires is not None):
                age_score, age_flags = cls.analyze_domain_age_risk(
                    domain_age_days=domain_age_days,
                    domain_expires=domain_expires,
                )
                score += age_score
                flags.extend(age_flags)
            elif not rdap_successful:
                # Add informational flag only, no points added
                flags.append("RDAP/WHOIS data unavailable (domain may be very new)")

        # === PRIORITY 2: DNS checks ===
        try:
            # DNS lookup
            dns_result = perform_full_dns_lookup(domain, timeout=5)

            # Only analyze DNS results if lookup succeeded
            if not dns_result.success:
                # Skip DNS analysis - don't penalize for temporary DNS issues
                return min(score, 100), flags

            # Check if A records point to suspicious IPs
            if dns_result.a_records:
                for ip in dns_result.a_records[:3]:  # Check first 3 IPs
                    try:
                        ip_obj = ipaddress.ip_address(ip)
                        # Check for private IP
                        if ip_obj.is_private:
                            score += 40
                            flags.append("Points to private IP address")
                        # Check for loopback
                        elif ip_obj.is_loopback:
                            score += 50
                            flags.append("Points to loopback address")
                        # Check for link-local
                        elif ip_obj.is_link_local:
                            score += 45
                            flags.append("Points to link-local address")
                    except ValueError:
                        pass

            # Check nameservers
            if dns_result.ns_records:
                # Check for free hosting providers
                free_ns_patterns = ["blogspot", "wordpress", "wix", "squarespace", "github"]
                for ns in dns_result.ns_records:
                    if any(pattern in ns.lower() for pattern in free_ns_patterns):
                        score += 5
                        flags.append("Hosted on free platform")
                        break

        except Exception:
            pass

        return min(score, 100), flags

    @classmethod
    def analyze_domain_age_risk(
        cls,
        domain_age_days: Optional[int],
        domain_expires: Optional[datetime] = None,
    ) -> tuple[int, list[str]]:
        """Analyze domain age and expiration for risk assessment.

        Based on ceker's WHOIS-based risk classification:
        - Domain age < 20 days = WARNING (highest priority)
        - Domain age < 90 days = SUSPICIOUS
        - Domain expires < 30 days = warning

        Args:
            domain_age_days: Age of domain in days (None if unknown)
            domain_expires: Domain expiration date (None if unknown)

        Returns:
            Tuple of (risk_score, list_of_flags)
        """
        score = 0
        flags = []

        if domain_age_days is not None:
            # Very new domain (< 20 days) - highest risk (from ceker)
            if domain_age_days < 20:
                score += 40
                flags.append(f"Very new domain ({domain_age_days} days old)")
            # New domain (< 90 days) - suspicious (from ceker)
            elif domain_age_days < 90:
                score += 20
                flags.append(f"Recently registered domain ({domain_age_days} days old)")
            # Moderately new domain (< 180 days)
            elif domain_age_days < 180:
                score += 10
                flags.append(f"New domain ({domain_age_days} days old)")

        # Check domain expiration (from ceker)
        if domain_expires is not None:
            # Make both datetimes timezone-aware for comparison
            from datetime import timezone
            now = datetime.now(timezone.utc)
            if domain_expires.tzinfo is None:
                domain_expires = domain_expires.replace(tzinfo=timezone.utc)
            days_until_expiry = (domain_expires - now).days
            if days_until_expiry < 0:
                score += 30
                flags.append("Domain has expired")
            elif days_until_expiry < 30:
                score += 20
                flags.append(f"Domain expires soon ({days_until_expiry} days)")
            elif days_until_expiry < 90:
                score += 10
                flags.append(f"Domain expiring in {days_until_expiry} days")

        return min(score, 100), flags


class DynamicBehaviorAnalyzer:
    """Dynamic behavior analyzer using HTTP checks."""

    @classmethod
    async def analyze(cls, url: str, timeout: int = 5) -> tuple[int, list[str]]:
        """Perform dynamic behavior analysis.

        Args:
            url: URL to analyze
            timeout: Request timeout in seconds

        Returns:
            Tuple of (risk_score, list_of_flags)
        """
        score = 0
        flags = []

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            ) as client:
                response = await client.get(url)

                # Check status code
                if response.status_code >= 400:
                    score += 15
                    flags.append(f"Returns error status: {response.status_code}")

                # Check for redirects
                if response.status_code in [301, 302, 303, 307, 308]:
                    location = response.headers.get("Location", "")
                    if location:
                        # Check if redirect goes to different domain
                        original_domain = extract_domain_from_url(url)
                        redirect_domain = extract_domain_from_url(location)
                        if original_domain != redirect_domain:
                            score += 20
                            flags.append(f"Redirects to different domain")

                # Check SSL if using HTTPS
                if url.startswith("https://"):
                    # HTTP client already verified SSL
                    pass

                # Check response headers
                headers = response.headers
                # Check for security headers (absence is suspicious)
                security_headers = ["X-Frame-Options", "X-Content-Type-Options", "Strict-Transport-Security"]
                missing_security = [h for h in security_headers if h not in headers]
                if len(missing_security) >= 2:
                    score += 1
                    flags.append("Missing security headers")

                # Check Content-Type
                content_type = headers.get("Content-Type", "")
                if content_type and "html" not in content_type.lower():
                    if "application/octet-stream" in content_type or "binary" in content_type:
                        score += 20
                        flags.append("Suspicious content type")

        except httpx.ConnectError:
            score += 25
            flags.append("Connection failed")
        except httpx.TimeoutException:
            score += 15
            flags.append("Request timeout")
        except httpx.TooManyRedirects:
            score += 30
            flags.append("Too many redirects")
        except httpx.SSLError:
            score += 35
            flags.append("SSL certificate error")
        except Exception:
            score += 10
            flags.append("HTTP check failed")

        return min(score, 100), flags


class ReputationAnalyzer:
    """Reputation analyzer using blacklist data."""

    # Simple built-in blacklist for demo purposes
    # In production, this would query external threat intelligence sources
    KNOWN_MALICIOUS_DOMAINS = {
        # This would be populated from external sources
    }

    @classmethod
    def analyze(cls, domain: str) -> tuple[int, list[str]]:
        """Perform reputation analysis.

        Args:
            domain: Domain to analyze

        Returns:
            Tuple of (risk_score, list_of_flags)
        """
        score = 0
        flags = []

        # Check against built-in blacklist
        if domain in cls.KNOWN_MALICIOUS_DOMAINS:
            score += 100
            flags.append("Known malicious domain")

        # Check if domain was recently registered (requires WHOIS)
        # This is a placeholder - actual implementation would query WHOIS

        return score, flags


class URLSafetyAnalyzer:
    """Main URL safety analyzer orchestrator.

    Combines all analyzers and produces a comprehensive risk assessment.
    """

    def __init__(self, enable_deep_analysis: bool = True):
        """Initialize the analyzer.

        Args:
            enable_deep_analysis: Whether to enable DNS/HTTP checks
        """
        self.enable_deep_analysis = enable_deep_analysis

    async def analyze(self, url: str) -> QuickAnalysisResponse:
        """Perform comprehensive URL analysis.

        Args:
            url: URL to analyze

        Returns:
            QuickAnalysisResponse with risk assessment
        """
        # Normalize URL
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        total_score = 0
        all_flags = []

        # 1. Static analysis (always performed)
        static_score, static_flags = StaticURLAnalyzer.analyze(url)
        total_score += static_score
        all_flags.extend(static_flags)

        # Extract domain for further analysis
        try:
            domain = extract_domain_from_url(url)
        except Exception:
            domain = ""

        # 2. Deep analysis (if enabled)
        if self.enable_deep_analysis and domain:
            # Run all deep analyzers in parallel
            dns_score, dns_flags = await DomainIntelligenceAnalyzer.analyze(domain)
            total_score += dns_score
            all_flags.extend(dns_flags)

            http_score, http_flags = await DynamicBehaviorAnalyzer.analyze(url)
            total_score += http_score
            all_flags.extend(http_flags)

            rep_score, rep_flags = ReputationAnalyzer.analyze(domain)
            total_score += rep_score
            all_flags.extend(rep_flags)

        # Cap the score at 100
        total_score = min(total_score, 100)

        # Determine risk level (priority-based, following ceker's pattern)
        risk_level = self._get_risk_level(total_score, all_flags)

        # Generate message
        message = self._generate_message(risk_level, all_flags)

        # Determine if can be submitted
        can_submit = risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]

        # Generate analysis ID
        import hashlib
        import time
        analysis_id = hashlib.md5(f"{url}{time.time()}".encode()).hexdigest()[:16]

        return QuickAnalysisResponse(
            url=url,
            risk_level=risk_level,
            score=total_score,
            can_submit=can_submit,
            message=message,
            quick_flags=list(set(all_flags)),  # Remove duplicates
            analysis_id=analysis_id,
        )

    def _get_risk_level(self, score: int, flags: list[str]) -> RiskLevel:
        """Convert numeric score to risk level with priority-based classification.

        Follows ceker's priority order:
        1. Domain age < 20 days (Very new domain) - HIGHEST PRIORITY
        2. Domain age < 90 days (Recently registered)
        3. Unusual TLD + subdomain heavy
        4. Unusual TLD alone
        5. Not using HTTPS
        6. Other factors

        Args:
            score: Risk score (0-100)
            flags: List of detected flags

        Returns:
            RiskLevel enum value
        """
        # Priority 1: Very new domain (< 20 days) - always HIGH or CRITICAL
        for flag in flags:
            if "Very new domain" in flag:
                if score >= 60:
                    return RiskLevel.CRITICAL
                return RiskLevel.HIGH

        # Priority 2: Recently registered domain (< 90 days)
        for flag in flags:
            if "Recently registered domain" in flag or "New domain" in flag:
                if score >= 40:
                    return RiskLevel.HIGH
                return RiskLevel.MEDIUM

        # Priority 3: Domain expires soon
        for flag in flags:
            if "Domain expires" in flag:
                if score >= 40:
                    return RiskLevel.HIGH
                return RiskLevel.MEDIUM

        # Priority 4: Suspicious domain structure combinations
        has_unusual_tld = any("Suspicious TLD" in f or "High-risk country TLD" in f for f in flags)
        has_subdomain_heavy = any("Unusual domain structure" in f for f in flags)
        has_no_https = any("not using secure connection" in f.lower() or "SSL certificate error" in f for f in flags)

        if has_unusual_tld and has_subdomain_heavy:
            return RiskLevel.HIGH
        if has_unusual_tld:
            return RiskLevel.MEDIUM
        if has_no_https and score >= 30:
            return RiskLevel.MEDIUM

        # Default: score-based classification
        if score < 10:
            return RiskLevel.SAFE
        elif score < 30:
            return RiskLevel.LOW
        elif score < 50:
            return RiskLevel.MEDIUM
        elif score < 75:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def _generate_message(self, risk_level: RiskLevel, flags: list[str]) -> str:
        """Generate user-friendly message.

        Args:
            risk_level: Assessed risk level
            flags: List of detected flags

        Returns:
            User-friendly message
        """
        messages = {
            RiskLevel.SAFE: "This URL appears safe. No suspicious indicators detected.",
            RiskLevel.LOW: "This URL has minor suspicious indicators but is likely safe.",
            RiskLevel.MEDIUM: "This URL has several suspicious indicators. Please verify before proceeding.",
            RiskLevel.HIGH: "This URL shows multiple signs of being a phishing site. Exercise extreme caution.",
            RiskLevel.CRITICAL: "This URL is highly suspicious and likely malicious. Do not enter any credentials.",
        }

        base_message = messages.get(risk_level, "Unable to assess risk.")

        # Add first few flags for context
        if flags and risk_level != RiskLevel.SAFE:
            shown_flags = flags[:3]
            flag_list = ", ".join(shown_flags)
            if len(flags) > 3:
                flag_list += f", and {len(flags) - 3} more"
            base_message += f" Detected: {flag_list}."

        return base_message


# Convenience function for quick analysis
async def quick_analyze(url: str, deep: bool = True) -> QuickAnalysisResponse:
    """Quick URL analysis function.

    Args:
        url: URL to analyze
        deep: Whether to perform deep analysis (DNS/HTTP checks)

    Returns:
        QuickAnalysisResponse with risk assessment
    """
    analyzer = URLSafetyAnalyzer(enable_deep_analysis=deep)
    return await analyzer.analyze(url)


__all__ = [
    "RiskLevel",
    "QuickAnalysisResponse",
    "URLSafetyAnalyzer",
    "StaticURLAnalyzer",
    "DomainIntelligenceAnalyzer",
    "DynamicBehaviorAnalyzer",
    "ReputationAnalyzer",
    "quick_analyze",
]
