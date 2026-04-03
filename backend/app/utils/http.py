"""HTTP checking utilities for PhishTrack monitoring module."""
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.utils.dns import extract_domain_from_url


class HTTPCheckResult:
    """Container for HTTP check results."""

    def __init__(
        self,
        url: str,
        status_code: Optional[int] = None,
        is_live: bool = False,
        error: Optional[str] = None,
        final_url: Optional[str] = None,
        redirect_count: int = 0,
        response_time_ms: Optional[float] = None,
        server: Optional[str] = None,
        content_type: Optional[str] = None,
    ):
        self.url = url
        self.status_code = status_code
        self.is_live = is_live
        self.error = error
        self.final_url = final_url or url
        self.redirect_count = redirect_count
        self.response_time_ms = response_time_ms
        self.server = server
        self.content_type = content_type

    @property
    def is_taken_down(self) -> bool:
        """Check if the site appears to be taken down."""
        if self.error:
            # DNS failure or connection error usually means taken down
            return True
        # 404, 410, or 5xx errors suggest takedown
        if self.status_code in (404, 410, 451):
            return True
        if self.status_code and self.status_code >= 500:
            return True
        return False

    @property
    def is_phishing_still_active(self) -> bool:
        """Check if the phishing site is still active."""
        return self.is_live and not self.is_taken_down


async def check_http_status(
    url: str,
    user_agent: Optional[str] = None,
    timeout: int = 10,
    max_redirects: int = 5,
    follow_redirects: bool = True,
) -> HTTPCheckResult:
    """Check HTTP status of a URL.

    Args:
        url: URL to check
        user_agent: Custom User-Agent header
        timeout: Request timeout in seconds
        max_redirects: Maximum number of redirects to follow
        follow_redirects: Whether to follow redirects

    Returns:
        HTTPCheckResult with status information
    """
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
        "Connection": "keep-alive",
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=follow_redirects,
            max_redirects=max_redirects,
        ) as client:
            import time

            start_time = time.time()
            response = await client.get(url, headers=headers)
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
        # This could be DNS failure or connection refused
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
    except httpx.HTTPStatusError as e:
        return HTTPCheckResult(
            url=url,
            status_code=e.response.status_code,
            is_live=True,
            error=f"HTTP error: {e.response.status_code}",
        )
    except Exception as e:
        return HTTPCheckResult(
            url=url,
            is_live=False,
            error=f"Unexpected error: {str(e)}",
        )


async def check_domain_liveness(
    domain: str,
    scheme: str = "https",
    user_agent: Optional[str] = None,
    timeout: int = 10,
) -> HTTPCheckResult:
    """Check if a domain is serving content.

    Args:
        domain: Domain to check
        scheme: HTTP scheme (http or https)
        user_agent: Custom User-Agent header
        timeout: Request timeout in seconds

    Returns:
        HTTPCheckResult with liveness information
    """
    url = f"{scheme}://{domain}"
    return await check_http_status(url, user_agent, timeout)


async def check_multiple_paths(
    domain: str,
    paths: Optional[list[str]] = None,
    user_agent: Optional[str] = None,
    timeout: int = 10,
) -> dict[str, HTTPCheckResult]:
    """Check multiple paths on a domain.

    Args:
        domain: Domain to check
        paths: List of paths to check (defaults to common paths)
        user_agent: Custom User-Agent header
        timeout: Request timeout in seconds

    Returns:
        Dictionary mapping paths to HTTPCheckResults
    """
    if paths is None:
        paths = ["/", "/login", "/signin", "/account", "/wp-admin", "/admin"]

    results = {}
    for path in paths:
        url = f"https://{domain}{path}"
        results[path] = await check_http_status(url, user_agent, timeout)

    return results


def is_phishing_indicators(response_text: str) -> dict[str, bool]:
    """Check response text for common phishing indicators.

    Args:
        response_text: HTML response body

    Returns:
        Dictionary with detected indicators
    """
    indicators = {
        "password_field": "<input" in response_text and "password" in response_text.lower(),
        "login_form": "<form" in response_text.lower() and any(
            kw in response_text.lower() for kw in ["login", "signin", "sign-in", "log-in", "log in"]
        ),
        "brand_keywords": any(
            brand in response_text.lower()
            for brand in [
                "paypal",
                "apple",
                "microsoft",
                "amazon",
                "google",
                "facebook",
                "instagram",
                "bank",
                "chase",
                "wells fargo",
                "netflix",
                "spotify",
            ]
        ),
        "suspicious_iframe": "<iframe" in response_text.lower(),
        "http_external_link": "http://" in response_text and "https://" not in response_text[:100],
        "crypto_wallet": any(
            kw in response_text.lower()
            for kw in ["bitcoin", "crypto", "wallet", "blockchain", "ethereum", "btc", "eth"]
        ),
    }

    return indicators


async def check_with_multiple_user_agents(
    url: str,
    timeout: int = 10,
) -> dict[str, HTTPCheckResult]:
    """Check URL with multiple user agents to detect bot filtering.

    Args:
        url: URL to check
        timeout: Request timeout per agent

    Returns:
        Dictionary mapping agent names to results
    """
    user_agents = {
        "mobile": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
            "Mobile/15E148 Safari/604.1"
        ),
        "desktop_chrome": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "desktop_safari": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15"
        ),
    }

    results = {}
    for agent_name, agent_string in user_agents.items():
        results[agent_name] = await check_http_status(url, agent_string, timeout)

    return results
