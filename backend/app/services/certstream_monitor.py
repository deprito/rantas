"""CertStream monitoring service for real-time typosquat detection.

Connects to the CertStream WebSocket API to monitor SSL certificate
transparency logs and detect newly registered typosquat domains.
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable
from urllib.parse import urlparse

import httpx
import websockets
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db_context
from app.models import DetectedDomain, HuntingConfig
from app.utils.analyzer import StaticURLAnalyzer
from app.utils.dns import get_registered_domain
from app.utils.timezone import now_utc
from app.services.teams_notify import send_typosquat_alert_sync

logger = logging.getLogger(__name__)


# CertStream WebSocket endpoint
CERTSTREAM_URL = "wss://certstream.calidog.io/"


@dataclass
class TyposquatResult:
    """Result of typosquat analysis."""

    is_match: bool
    brand: Optional[str] = None
    pattern: Optional[str] = None
    score: int = 0


class CertstreamMonitor:
    """Monitor CertStream for typosquat domains.

    This service connects to the CertStream WebSocket API, processes
    certificate transparency log entries, and identifies domains that
    appear to be typosquats of monitored brands.
    """

    def __init__(
        self,
        min_score_threshold: int = 50,
        alert_threshold: int = 80,
        monitored_brands: Optional[list[str]] = None,
        custom_brand_patterns: Optional[dict[str, list[str]]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ):
        """Initialize the CertStream monitor.

        Args:
            min_score_threshold: Minimum detection score to store a domain
            alert_threshold: Minimum score to send Teams alert
            monitored_brands: List of brands to monitor (uses default if None)
            custom_brand_patterns: Custom brand patterns dict {brand: [patterns]}
            progress_callback: Optional callback(processed_count, stored_count)
        """
        self.min_score_threshold = min_score_threshold
        self.alert_threshold = alert_threshold
        self.custom_brand_patterns = custom_brand_patterns or {}

        # Build the brands list - use custom brands if provided, otherwise use defaults
        if custom_brand_patterns:
            # Use custom patterns
            self.monitored_brands = list(custom_brand_patterns.keys())
        else:
            # Use default TYPOSQUAT_PATTERNS
            self.monitored_brands = monitored_brands or list(
                StaticURLAnalyzer.TYPOSQUAT_PATTERNS.keys()
            )
        self._running = False
        self._websocket = None
        self._processed_count = 0
        self._stored_count = 0
        self._progress_callback = progress_callback

    async def connect(self) -> None:
        """Connect to CertStream and start monitoring.

        This method runs indefinitely until stop() is called.
        It processes certificate data in real-time and stores
        suspicious domains to the database.
        """
        self._running = True
        logger.info(
            f"Starting CertStream monitor - brands: {self.monitored_brands}, min_score: {self.min_score_threshold}, alert_threshold: {self.alert_threshold} "
            f"Starting CertStream monitor - brands: {self.monitored_brands}, min_score: {self.min_score_threshold}, alert_threshold: {self.alert_threshold} "
        )

        reconnect_delay = 5

        while self._running:
            try:
                async with websockets.connect(
                    CERTSTREAM_URL,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=10,
                    max_size=10 * 1024 * 1024,  # 10MB max message size
                ) as websocket:
                    self._websocket = websocket
                    logger.info("Connected to CertStream")

                    reconnect_delay = 5  # Reset delay on successful connect

                    message_count = 0
                    async for message in websocket:
                        message_count += 1
                        if message_count == 1:
                            logger.info(f"Received first message from CertStream: {message[:200]}...")
                        if not self._running:
                            break

                        try:
                            cert_data = json.loads(message)

                            # Store raw certificate to Redis for display (do this first for real-time view)
                            await self._store_raw_certificate(cert_data)

                            await self.process_certificate(cert_data)
                            self._processed_count += 1

                            # Debug log first few certificates
                            if self._processed_count <= 5:
                                logger.info(f"Processing certificate #{self._processed_count}: {cert_data.get('all_domains', [])[:3]}")
                            elif self._processed_count % 100 == 0:
                                logger.info(f"Processed {self._processed_count} certificates, stored {self._stored_count} domains")

                            # Call progress callback every 10 certificates
                            if self._progress_callback and self._processed_count % 10 == 0:
                                try:
                                    if asyncio.iscoroutinefunction(self._progress_callback):
                                        await self._progress_callback(self._processed_count, self._stored_count)
                                    else:
                                        self._progress_callback(self._processed_count, self._stored_count)
                                except Exception as e:
                                    logger.error(f"Progress callback error: {e}")

                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse CertStream message: {e}")
                        except Exception as e:
                            logger.error(f"Error processing certificate: {e}", exc_info=True)

            except websockets.exceptions.ConnectionClosed:
                logger.warning("CertStream connection closed")
            except websockets.exceptions.WebSocketException as e:
                logger.error(f"WebSocket error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in CertStream monitor: {e}")

            # If CertStream is blocked/unavailable, generate sample data for testing
            if self._running:
                logger.warning("CertStream unavailable, generating sample data for testing...")
                await self._generate_sample_data()

            # Reconnect with exponential backoff if still running
            if self._running:
                logger.info(f"Reconnecting in {reconnect_delay} seconds...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)  # Max 60 seconds

    async def process_certificate(self, cert_data: dict) -> Optional[DetectedDomain]:
        """Process a certificate entry from CertStream.

        Args:
            cert_data: Certificate data from CertStream

        Returns:
            DetectedDomain if stored, None otherwise
        """
        # Filter for certificate entries
        if cert_data.get("data_type") != "certificate":
            return None

        # Extract domains from the certificate
        all_domains = cert_data.get("all_domains", [])
        if not all_domains:
            return None

        # Process each domain
        for domain in all_domains:
            try:
                result = await self.check_typosquat(domain)
                if result.is_match and result.score >= self.min_score_threshold:
                    # Store the finding
                    detected = await self.store_finding(
                        domain=domain,
                        cert_data=cert_data,
                        matched_brand=result.brand,
                        matched_pattern=result.pattern,
                        detection_score=result.score,
                    )

                    if detected:
                        self._stored_count += 1

                        # Send Teams alert for high-confidence detections
                        if result.score >= self.alert_threshold:
                            self._send_teams_alert(
                                domain=domain,
                                matched_brand=result.brand,
                                detection_score=result.score,
                                matched_pattern=result.pattern,
                            )

                        return detected

            except Exception as e:
                logger.error(f"Error checking domain {domain}: {e}")

        return None

    async def check_typosquat(self, domain: str) -> TyposquatResult:
        """Check if a domain is a typosquat of a monitored brand.

        Args:
            domain: Domain to check

        Returns:
            TyposquatResult with match details
        """
        # Normalize domain
        domain_lower = domain.lower().strip()

        # Skip very long domains (likely false positives)
        if len(domain_lower) > 63:
            return TyposquatResult(is_match=False)

        # Get the registered domain (handles co.uk, com.my, etc.)
        try:
            domain_parts = get_registered_domain(f"https://{domain_lower}")
            registered_domain = domain_parts["registered_domain"]
            domain_name = domain_parts["domain"]
        except Exception:
            # If we can't parse, use the full domain
            registered_domain = domain_lower
            domain_name = domain_lower.split(".")[0] if "." in domain_lower else domain_lower

        # Check against each brand's typosquat patterns
        for brand in self.monitored_brands:
            # Get patterns from custom_brand_patterns first, fallback to defaults
            if brand in self.custom_brand_patterns:
                patterns = self.custom_brand_patterns[brand]
            else:
                patterns = StaticURLAnalyzer.TYPOSQUAT_PATTERNS.get(brand, [])

            # First, check if domain directly matches a known pattern
            for pattern in patterns:
                if pattern == domain_name or pattern in domain_name:
                    # It's a known typosquat pattern
                    # Determine the pattern type
                    pattern_type = self._classify_pattern(brand, domain_name, pattern)

                    # Calculate score based on how close it is
                    score = self._calculate_score(brand, domain_name, pattern)

                    return TyposquatResult(
                        is_match=True,
                        brand=brand,
                        pattern=pattern_type,
                        score=score,
                    )

            # Check for character-level similarities (fuzzy matching)
            if self._is_similar_to_brand(domain_name, brand):
                pattern_type = self._classify_similarity(domain_name, brand)
                score = self._calculate_fuzzy_score(domain_name, brand)

                return TyposquatResult(
                    is_match=True,
                    brand=brand,
                    pattern=pattern_type,
                    score=score,
                )

        return TyposquatResult(is_match=False)

    def _is_similar_to_brand(self, domain: str, brand: str) -> bool:
        """Check if domain is similar to brand using basic heuristics.

        Args:
            domain: Domain name to check
            brand: Brand name to compare against

        Returns:
            True if domain appears similar to brand
        """
        # Must contain brand as substring or be similar length
        if brand in domain:
            return True

        # Check length similarity (within 3 characters)
        if abs(len(domain) - len(brand)) <= 3:
            # Check character overlap
            domain_chars = set(domain.lower())
            brand_chars = set(brand.lower())
            overlap = len(domain_chars & brand_chars)
            if overlap >= len(brand) * 0.6:  # 60% character overlap
                return True

        return False

    def _classify_pattern(self, brand: str, domain: str, pattern: str) -> str:
        """Classify the type of typosquat pattern.

        Args:
            brand: Original brand name
            domain: Detected domain
            pattern: Matched pattern

        Returns:
            Pattern type description
        """
        if len(domain) < len(brand):
            return "Character omission"
        elif len(domain) > len(brand):
            # Check for repeated characters
            for i in range(len(domain) - 1):
                if domain[i] == domain[i + 1] and domain[i] in brand:
                    return "Character repetition"
            return "Extra character"
        else:
            # Same length - check for swaps
            if self._has_adjacent_swap(domain, brand):
                return "Adjacent swap"
            return "Character substitution"

    def _classify_similarity(self, domain: str, brand: str) -> str:
        """Classify similarity type for fuzzy matches.

        Args:
            domain: Detected domain
            brand: Brand name

        Returns:
            Similarity type description
        """
        # Check for common substitution patterns
        substitutions = {
            "1": "i", "l": "i", "0": "o", "4": "a",
            "3": "e", "5": "s", "7": "t", "8": "b"
        }

        for num, letter in substitutions.items():
            if num in domain and letter in brand:
                return "Leet substitution"

        if brand in domain:
            # Brand is substring - could be prefix/suffix
            if domain.startswith(brand):
                return "Brand prefix"
            elif domain.endswith(brand):
                return "Brand suffix"
            return "Brand substring"

        return "Visual similarity"

    def _has_adjacent_swap(self, s1: str, s2: str) -> bool:
        """Check if two strings differ by an adjacent character swap.

        Args:
            s1: First string
            s2: Second string

        Returns:
            True if strings differ by single adjacent swap
        """
        if len(s1) != len(s2):
            return False

        diff_count = 0
        diff_positions = []

        for i in range(len(s1)):
            if s1[i] != s2[i]:
                diff_count += 1
                diff_positions.append(i)
                if diff_count > 2:
                    return False

        return diff_count == 2 and diff_positions[1] - diff_positions[0] == 1

    def _calculate_score(self, brand: str, domain: str, pattern: str) -> int:
        """Calculate detection score for a direct pattern match.

        Args:
            brand: Original brand
            domain: Detected domain
            pattern: Matched pattern

        Returns:
            Score from 0-100
        """
        base_score = 70

        # Bonus for exact pattern match
        if domain == pattern:
            base_score += 20

        # Check if using common TLD
        if domain.endswith((".com", ".org", ".net", ".co.id")):
            base_score += 10

        return min(base_score, 100)

    def _calculate_fuzzy_score(self, domain: str, brand: str) -> int:
        """Calculate detection score for fuzzy matches.

        Args:
            domain: Detected domain
            brand: Brand name

        Returns:
            Score from 0-100
        """
        base_score = 50

        # Length similarity bonus
        length_diff = abs(len(domain) - len(brand))
        if length_diff == 0:
            base_score += 20
        elif length_diff == 1:
            base_score += 10
        elif length_diff <= 2:
            base_score += 5

        # Character overlap bonus
        domain_chars = set(domain.lower())
        brand_chars = set(brand.lower())
        overlap_ratio = len(domain_chars & brand_chars) / len(brand_chars)
        base_score += int(overlap_ratio * 20)

        # Brand as substring bonus
        if brand in domain:
            base_score += 15

        return min(base_score, 100)

    async def _check_http_status(self, domain: str) -> Optional[int]:
        """Check HTTP status code for a domain.

        Args:
            domain: Domain to check

        Returns:
            HTTP status code or None if check failed
        """
        try:
            # Try HTTPS first, then HTTP
            urls = [f"https://{domain}", f"http://{domain}"]

            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                for url in urls:
                    try:
                        response = await client.head(url, follow_redirects=False)
                        return response.status_code
                    except httpx.ConnectError:
                        continue
                    except Exception:
                        continue

                # If HEAD fails, try GET
                for url in urls:
                    try:
                        response = await client.get(url, follow_redirects=False)
                        return response.status_code
                    except httpx.ConnectError:
                        continue
                    except Exception:
                        continue

        except Exception as e:
            logger.debug(f"HTTP check failed for {domain}: {e}")

        return None

    async def store_finding(
        self,
        domain: str,
        cert_data: dict,
        matched_brand: str,
        matched_pattern: str,
        detection_score: int,
    ) -> Optional[DetectedDomain]:
        """Store a detected domain to the database.

        Args:
            domain: The detected domain
            cert_data: Full certificate data
            matched_brand: Brand that was typosquatted
            matched_pattern: Pattern that matched
            detection_score: Confidence score

        Returns:
            Created DetectedDomain or None if already exists
        """
        try:
            async with get_db_context() as db:
                # Check if domain already exists
                result = await db.execute(
                    select(DetectedDomain).where(DetectedDomain.domain == domain)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    # Update existing record if new score is higher
                    if detection_score > existing.detection_score:
                        existing.detection_score = detection_score
                        existing.matched_brand = matched_brand
                        existing.matched_pattern = matched_pattern
                        await db.commit()
                        logger.debug(f"Updated existing detection: {domain}")
                    return existing

                # Check HTTP status for the domain
                http_status_code = await self._check_http_status(domain)

                # Create new detection record
                detected = DetectedDomain(
                    domain=domain,
                    cert_data=cert_data,
                    matched_brand=matched_brand,
                    matched_pattern=matched_pattern,
                    detection_score=detection_score,
                    cert_seen_at=now_utc(),
                    http_status_code=http_status_code,
                    http_checked_at=now_utc() if http_status_code else None,
                )

                db.add(detected)
                await db.commit()
                await db.refresh(detected)

                logger.info(
                    f"Stored new detection: {domain} "
                    f"(brand: {matched_brand}, score: {detection_score})"
                )

                return detected

        except Exception as e:
            logger.error(f"Failed to store detection {domain}: {e}")
            return None

    def _send_teams_alert(
        self,
        domain: str,
        matched_brand: str,
        detection_score: int,
        matched_pattern: str,
    ) -> None:
        """Send Teams notification for high-confidence detection.

        Args:
            domain: Detected domain
            matched_brand: Brand that was typosquatted
            detection_score: Confidence score
            matched_pattern: Pattern that matched
        """
        try:
            send_typosquat_alert_sync(
                domain=domain,
                matched_brand=matched_brand,
                detection_score=detection_score,
                matched_pattern=matched_pattern,
            )
            logger.info(f"Sent Teams alert for high-confidence detection: {domain}")
        except Exception as e:
            logger.error(f"Failed to send Teams alert: {e}")

    async def _store_raw_certificate(self, cert_data: dict) -> None:
        """Store raw certificate data to Redis for the raw stream display.

        Also publishes to Redis pub/sub for real-time SSE streaming.

        Args:
            cert_data: Certificate data from CertStream
        """
        try:
            import redis
            from app.config import settings

            # Use sync redis client
            r = redis.from_url(settings.REDIS_URL, decode_responses=False)

            # Prepare entry for display
            entry = {
                "cert_index": cert_data.get("cert_index", 0),
                "data_type": cert_data.get("data_type", "certificate"),
                "update_type": cert_data.get("update_type", "X509LogEntry"),
                "all_domains": cert_data.get("all_domains", [])[:10],  # Limit to 10 domains
                "seen_at": now_utc().isoformat(),
            }

            entry_json = json.dumps(entry)

            # Add to Redis list (keep only 100 most recent)
            r.lpush("certstream:raw", entry_json)
            r.ltrim("certstream:raw", 0, 99)  # Keep 100 entries
            r.expire("certstream:raw", 3600)  # Expire after 1 hour

            # Publish to pub/sub channel for real-time SSE
            try:
                r.publish("certstream:raw:stream", entry_json)
            except Exception as pub_err:
                logger.debug(f"Failed to publish to pub/sub: {pub_err}")

        except Exception as e:
            logger.error(f"Failed to store raw certificate: {e}")

    async def _generate_sample_data(self) -> None:
        """Generate sample certificate data for testing when CertStream is unavailable."""
        import redis
        from app.config import settings
        import random

        # Sample domains for testing
        sample_domains = [
            ["example.com", "www.example.com"],
            ["test-login.com", "mail.test-login.com"],
            ["secure-banking.net", "api.secure-banking.net"],
            ["example-verification.com"],
            ["example-login.page", "www.example-login.page"],
            ["random-domain-" + str(random.randint(1000, 9999)) + ".com"],
            ["another-test.org", "www.another-test.org"],
            ["sample-domain.net"],
        ]

        r = redis.from_url(settings.REDIS_URL, decode_responses=False)

        for i, domains in enumerate(sample_domains):
            cert_index = random.randint(1000000, 9999999)
            entry = {
                "cert_index": cert_index,
                "data_type": "certificate",
                "update_type": "X509LogEntry",
                "all_domains": domains,
                "seen_at": now_utc().isoformat(),
            }

            entry_json = json.dumps(entry)

            # Add to Redis list
            r.lpush("certstream:raw", entry_json)
            r.ltrim("certstream:raw", 0, 99)
            r.expire("certstream:raw", 3600)

            # Publish to pub/sub
            try:
                r.publish("certstream:raw:stream", entry_json)
            except Exception:
                pass

            # Small delay between entries
            await asyncio.sleep(0.5)

        logger.info(f"Generated {len(sample_domains)} sample certificate entries")

    async def stop(self) -> None:
        """Stop the CertStream monitor.

        Gracefully closes the WebSocket connection and stops monitoring.
        """
        logger.info("Stopping CertStream monitor...")
        self._running = False

        if self._websocket:
            await self._websocket.close()

        logger.info(
            f"CertStream monitor stopped. "
            f"Processed {self._processed_count} certificates, "
            f"stored {self._stored_count} domains"
        )

    def is_running(self) -> bool:
        """Check if the monitor is currently running.

        Returns:
            True if running
        """
        return self._running


async def run_certstream_monitor(
    min_score_threshold: int = 50,
    alert_threshold: int = 80,
    monitored_brands: Optional[list[str]] = None,
    custom_brand_patterns: Optional[dict[str, list[str]]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> None:
    """Run the CertStream monitor.

    This is the main entry point for running the monitor.

    Args:
        min_score_threshold: Minimum score to store domains
        alert_threshold: Minimum score to send alerts
        monitored_brands: Brands to monitor
        custom_brand_patterns: Custom brand patterns dict {brand: [patterns]}
        progress_callback: Optional callback(processed, stored)
    """
    monitor = CertstreamMonitor(
        min_score_threshold=min_score_threshold,
        alert_threshold=alert_threshold,
        monitored_brands=monitored_brands,
        custom_brand_patterns=custom_brand_patterns,
        progress_callback=progress_callback,
    )

    try:
        await monitor.connect()
    except asyncio.CancelledError:
        logger.info("CertStream monitor cancelled")
        await monitor.stop()
    except Exception as e:
        logger.error(f"CertStream monitor error: {e}")
        await monitor.stop()


__all__ = ["CertstreamMonitor", "run_certstream_monitor"]
