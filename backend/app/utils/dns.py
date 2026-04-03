"""DNS lookup utilities for PhishTrack OSINT module."""
import socket
from typing import Optional

import dns.resolver
import dns.exception


class DNSResult:
    """Container for DNS lookup results."""

    def __init__(
        self,
        domain: str,
        a_records: Optional[list[str]] = None,
        aaaa_records: Optional[list[str]] = None,
        ns_records: Optional[list[str]] = None,
        mx_records: Optional[list[str]] = None,
        txt_records: Optional[list[str]] = None,
        cname: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.domain = domain
        self.a_records = a_records or []
        self.aaaa_records = aaaa_records or []
        self.ns_records = ns_records or []
        self.mx_records = mx_records or []
        self.txt_records = txt_records or []
        self.cname = cname
        self.error = error
        self.success = error is None


def resolve_dns(domain: str, record_type: str, resolver: Optional[dns.resolver.Resolver] = None) -> list[str]:
    """Resolve DNS records for a domain.

    Args:
        domain: Domain to query
        record_type: DNS record type (A, AAAA, NS, MX, TXT, CNAME)
        resolver: Optional custom DNS resolver

    Returns:
        List of record values
    """
    if resolver is None:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 10

    try:
        answers = resolver.resolve(domain, record_type, raise_on_no_answer=False)
        if record_type == "MX":
            return [f"{r.exchange} {r.preference}" for r in answers]
        elif record_type == "TXT":
            return [r.to_text().strip('"') for r in answers]
        elif record_type == "CNAME":
            return [str(answers[0].target)] if answers else []
        else:
            return [str(r) for r in answers]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.DNSException):
        return []
    except Exception:
        return []


def get_a_records(domain: str, resolver: Optional[dns.resolver.Resolver] = None) -> list[str]:
    """Get A records for a domain."""
    return resolve_dns(domain, "A", resolver)


def get_aaaa_records(domain: str, resolver: Optional[dns.resolver.Resolver] = None) -> list[str]:
    """Get AAAA (IPv6) records for a domain."""
    return resolve_dns(domain, "AAAA", resolver)


def get_ns_records(domain: str, resolver: Optional[dns.resolver.Resolver] = None) -> list[str]:
    """Get NS (nameserver) records for a domain."""
    return resolve_dns(domain, "NS", resolver)


def get_mx_records(domain: str, resolver: Optional[dns.resolver.Resolver] = None) -> list[str]:
    """Get MX (mail exchange) records for a domain."""
    return resolve_dns(domain, "MX", resolver)


def get_txt_records(domain: str, resolver: Optional[dns.resolver.Resolver] = None) -> list[str]:
    """Get TXT records for a domain."""
    return resolve_dns(domain, "TXT", resolver)


def get_cname(domain: str, resolver: Optional[dns.resolver.Resolver] = None) -> Optional[str]:
    """Get CNAME record for a domain."""
    results = resolve_dns(domain, "CNAME", resolver)
    return results[0] if results else None


def get_primary_ip(domain: str, resolver: Optional[dns.resolver.Resolver] = None) -> Optional[str]:
    """Get the primary IP address for a domain.

    Args:
        domain: Domain to lookup
        resolver: Optional custom DNS resolver

    Returns:
        First A record IP or None
    """
    a_records = get_a_records(domain, resolver)
    return a_records[0] if a_records else None


def perform_full_dns_lookup(domain: str, timeout: int = 10) -> DNSResult:
    """Perform comprehensive DNS lookup for a domain.

    Args:
        domain: Domain to lookup
        timeout: Query timeout in seconds

    Returns:
        DNSResult with all discovered records
    """
    import socket
    import concurrent.futures

    # First try system DNS as a quick check
    system_ip = None
    system_error = None
    try:
        system_ip = socket.gethostbyname(domain)
    except socket.gaierror as e:
        system_error = str(e)
    except Exception as e:
        system_error = str(e)

    # Start with system DNS result
    a_records = [system_ip] if system_ip else []
    aaaa_records = []
    ns_records = []
    mx_records = []
    txt_records = []
    cname = None

    # Only try dnspython if system DNS failed and we have time left
    if not system_ip:
        # Configure resolver with fallback DNS servers
        resolver = dns.resolver.Resolver()
        resolver.timeout = 1  # Very short timeout per query
        resolver.lifetime = 2  # Very short lifetime

        # Try multiple DNS server configurations
        dns_configs = [
            ["8.8.8.8", "1.1.1.1"],  # Google + Cloudflare
        ]

        for nameservers in dns_configs:
            resolver.nameservers = nameservers
            try:
                a_records = get_a_records(domain, resolver)
                if a_records:
                    break
            except Exception:
                continue

        for nameservers in dns_configs:
            resolver.nameservers = nameservers
            try:
                ns_records = get_ns_records(domain, resolver)
                if ns_records:
                    break
            except Exception:
                continue

        # Try other record types with best-effort, using timeout
        def get_other_records():
            nonlocal aaaa_records, mx_records, txt_records, cname
            for nameservers in dns_configs:
                resolver.nameservers = nameservers
                try:
                    if not aaaa_records:
                        aaaa_records = get_aaaa_records(domain, resolver)
                    if not mx_records:
                        mx_records = get_mx_records(domain, resolver)
                    if not txt_records:
                        txt_records = get_txt_records(domain, resolver)
                    if not cname:
                        cname = get_cname(domain, resolver)
                    if aaaa_records or mx_records or txt_records or cname:
                        break
                except Exception:
                    pass

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(get_other_records)
                future.result(timeout=2)
        except Exception:
            pass

    return DNSResult(
        domain=domain,
        a_records=a_records,
        aaaa_records=aaaa_records,
        ns_records=ns_records,
        mx_records=mx_records,
        txt_records=txt_records,
        cname=cname,
        error=system_error if not a_records else None,
    )


def reverse_dns_lookup(ip: str) -> Optional[str]:
    """Perform reverse DNS lookup on an IP address.

    Args:
        ip: IP address to lookup

    Returns:
        Hostname or None
    """
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror):
        return None


def is_dns_resolving(domain: str) -> bool:
    """Check if a domain has valid DNS resolution.

    Args:
        domain: Domain to check

    Returns:
        True if domain resolves to an IP
    """
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 3
        resolver.lifetime = 5
        resolver.resolve(domain, "A")
        return True
    except Exception:
        return False


def extract_domain_from_url(url: str) -> str:
    """Extract the registered domain from a URL.

    Properly handles country code second-level domains (ccSLDs) like:
    - .co.uk, .my.id, .com.au, .ac.in

    Args:
        url: URL to parse

    Returns:
        Registered domain name (e.g., 'example.co.uk' for 'www.example.co.uk')
    """
    from urllib.parse import urlparse
    import tldextract

    parsed = urlparse(url)
    netloc = parsed.netloc or parsed.path

    # Remove port if present
    if ":" in netloc:
        netloc = netloc.split(":")[0]

    # Use tldextract for proper domain extraction
    extracted = tldextract.extract(netloc)
    domain = f"{extracted.domain}.{extracted.suffix}" if extracted.domain else netloc

    return domain.lower()


def get_registered_domain(url: str) -> dict:
    """Extract all domain parts from a URL.

    Properly handles country code second-level domains (ccSLDs).

    Args:
        url: URL to parse

    Returns:
        Dict with keys:
            - subdomain: The subdomain part (e.g., "www")
            - domain: The domain name (e.g., "example")
            - suffix: The public suffix/TLD (e.g., "co.uk", "my.id")
            - registered_domain: The full registered domain (e.g., "example.co.uk")
    """
    from urllib.parse import urlparse
    import tldextract

    parsed = urlparse(url)
    netloc = parsed.netloc or parsed.path

    if ":" in netloc:
        netloc = netloc.split(":")[0]

    extracted = tldextract.extract(netloc)

    return {
        "subdomain": extracted.subdomain or "",
        "domain": extracted.domain or "",
        "suffix": extracted.suffix or "",
        "registered_domain": f"{extracted.domain}.{extracted.suffix}" if extracted.domain else netloc,
    }
