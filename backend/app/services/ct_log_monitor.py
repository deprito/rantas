"""CT Log Monitor using certpatrol and crt.sh API.

Monitors Certificate Transparency logs for newly issued certificates
and detects typosquat domains matching monitored brands.
"""
import asyncio
import json
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db_context
from app.models import DetectedDomain, HuntingConfig as HuntingConfigModel
from app.utils.analyzer import StaticURLAnalyzer
from app.utils.dns import get_registered_domain
from app.utils.timezone import now_utc
from app.services.teams_notify import send_typosquat_alert_sync
from app.services.sunlight_reader import CTLogReader

logger = logging.getLogger(__name__)

# crt.sh API endpoint for CT Log search (fallback)
CRTSH_API = "https://crt.sh/?q={}&output=json&exclude=expired"


class CTLogMonitor:
    """Monitor Certificate Transparency logs for typosquat detection.

    Uses certpatrol library for direct CT log access with crt.sh as fallback.
    """

    # Default CT logs to monitor
    DEFAULT_LOGS = [
        "argon2024h1", "argon2023h2", "argon2023h1",
        "2024h1", "2024h2", "2023h2",
        "aviator", "rocketeer", "icarus", "skywriter"
    ]

    def __init__(
        self,
        min_score_threshold: int = 50,
        alert_threshold: int = 80,
        monitored_brands: Optional[list[str]] = None,
        custom_brand_patterns: Optional[dict[str, list[str]]] = None,
        custom_brand_regex_patterns: Optional[dict[str, list[str]]] = None,
        progress_callback: Optional[callable] = None,
    ):
        """Initialize the CT Log monitor.

        Args:
            min_score_threshold: Minimum detection score to store a domain
            alert_threshold: Minimum score to send Teams alert
            monitored_brands: List of brands to monitor
            custom_brand_patterns: Custom brand patterns dict {brand: [patterns]}
            custom_brand_regex_patterns: Custom regex patterns dict {brand: [regex_patterns]}
            progress_callback: Optional callback for progress updates
        """
        self.min_score_threshold = min_score_threshold
        self.alert_threshold = alert_threshold

        self.custom_brand_patterns = custom_brand_patterns
        self.custom_brand_regex_patterns = custom_brand_regex_patterns

        # Determine monitored brands from custom patterns or use provided/default list
        if custom_brand_patterns or custom_brand_regex_patterns:
            # Use brands from custom patterns
            brands_from_patterns = set()
            if custom_brand_patterns:
                brands_from_patterns.update(custom_brand_patterns.keys())
            if custom_brand_regex_patterns:
                brands_from_patterns.update(custom_brand_regex_patterns.keys())
            self.monitored_brands = list(brands_from_patterns) if brands_from_patterns else (
                monitored_brands or list(StaticURLAnalyzer.TYPOSQUAT_PATTERNS.keys())
            )
        else:
            self.custom_brand_patterns = None
            self.custom_brand_regex_patterns = None
            self.monitored_brands = monitored_brands or list(
                StaticURLAnalyzer.TYPOSQUAT_PATTERNS.keys()
            )

        self._running = False
        self._processed_count = 0
        self._stored_count = 0
        self._progress_callback = progress_callback

        # HTTP client for fallback API requests
        self._client = None

        # Certpatrol components
        self._certpatrol_available = False
        self._ct_logs = {}
        self._checkpoints = {}

        # CT Log Reader (Sunlight/public CT logs)
        self._ct_log_reader: Optional[CTLogReader] = None
        self._sunlight_checkpoints: dict[str, int] = {}

        # Try to import certpatrol
        try:
            import certpatrol
            self.certpatrol = certpatrol
            self._certpatrol_available = True
            logger.info("certpatrol library available for CT log monitoring")
        except ImportError as e:
            logger.warning(f"certpatrol not available: {e}, will use CT log reader / crt.sh API fallback")

        # Initialize CT Log Reader for public logs
        if settings.SUNLIGHT_ENABLED:
            self._ct_log_reader = CTLogReader()
            logger.info("CT Log Reader enabled for public CT logs")

    async def _initialize_certpatrol(self) -> bool:
        """Initialize certpatrol and fetch CT log list.

        Returns:
            True if certpatrol is available and initialized, False otherwise
        """
        if not self._certpatrol_available:
            return False

        try:
            # Fetch usable CT logs
            import certpatrol
            import requests

            session_manager = certpatrol.HTTPSessionManager()
            try:
                self._ct_logs = certpatrol.fetch_usable_ct_logs(session_manager)
                logger.info(f"certpatrol: found {len(self._ct_logs)} usable CT logs")

                # Filter to our default logs if they exist
                available_logs = [k for k in self.DEFAULT_LOGS if k in self._ct_logs]
                if available_logs:
                    self._active_logs = available_logs
                else:
                    # Use any available logs
                    self._active_logs = list(self._ct_logs.keys())[:5]

                logger.info(f"Monitoring CT logs: {self._active_logs}")

                # Initialize checkpoints at current tree size (minus some entries for initial display)
                for log_name in self._active_logs:
                    try:
                        base_url = self._ct_logs[log_name]
                        tree_size = certpatrol.get_sth(base_url, session_manager)
                        # Start 100 entries before current head to get some initial data
                        start_position = max(0, tree_size - 100)
                        self._checkpoints[log_name] = start_position
                        logger.info(f"{log_name}: starting at index {start_position} (head: {tree_size})")
                    except Exception as e:
                        logger.warning(f"{log_name}: failed to get STH: {e}")
                        self._checkpoints[log_name] = 0

                session_manager.close()
                return len(self._active_logs) > 0

            except Exception as e:
                logger.error(f"Failed to initialize certpatrol: {e}")
                return False

        except Exception as e:
            logger.error(f"certpatrol initialization error: {e}")
            return False

    async def _fetch_from_certpatrol(self) -> int:
        """Fetch new entries from CT logs using certpatrol.

        Returns:
            Number of entries processed
        """
        import certpatrol
        import requests

        session_manager = certpatrol.HTTPSessionManager()

        try:
            total_entries = 0
            batch_size = 256

            for log_name in self._active_logs:
                if not self._running:
                    break

                base_url = self._ct_logs[log_name]
                current_pos = self._checkpoints.get(log_name, 0)

                try:
                    # Get current tree size
                    tree_size = certpatrol.get_sth(base_url, session_manager)

                    if tree_size <= current_pos:
                        continue  # No new entries

                    # Fetch new entries (limit to batch_size)
                    new_count = min(tree_size - current_pos, batch_size)
                    end_pos = min(current_pos + new_count, tree_size)

                    if end_pos > current_pos:
                        entries = certpatrol.get_entries(base_url, current_pos, end_pos - 1, session_manager)

                        for entry in entries:
                            if not self._running:
                                break

                            # Parse certificate entry
                            leaf_input = entry.get("leaf_input", "")
                            if leaf_input:
                                cert_data = self._parse_certpatrol_entry(leaf_input)
                                if cert_data:
                                    # Store raw certificate
                                    await self._store_raw_certificate(cert_data, current_pos + total_entries)

                                    # Process for typosquat detection
                                    await self._process_cert_entry(cert_data, current_pos + total_entries)

                                    total_entries += 1
                                    self._processed_count += 1

                        # Update checkpoint
                        self._checkpoints[log_name] = end_pos

                except Exception as e:
                    logger.warning(f"Error fetching from {log_name}: {e}")
                    continue

            session_manager.close()
            return total_entries

        except Exception as e:
            logger.error(f"certpatrol fetch error: {e}")
            try:
                session_manager.close()
            except:
                pass
            return 0

    def _parse_certpatrol_entry(self, leaf_input: str) -> Optional[dict]:
        """Parse a certpatrol leaf entry to extract domains.

        Args:
            leaf_input: Base64-encoded leaf input from CT log

        Returns:
            Certificate data dict with all_domains, or None
        """
        import base64

        try:
            # Decode base64 leaf input
            leaf_bytes = base64.b64decode(leaf_input)

            # Extract domains using proper certificate parsing
            domains = self._extract_domains_from_leaf(leaf_bytes)

            # Validate domains - must be pure ASCII without control characters
            if domains:
                valid_domains = []
                for d in domains:
                    # Strict validation:
                    # 1. Must be a string
                    # 2. Must contain at least one dot
                    # 3. All characters must be printable ASCII (no control characters)
                    # 4. No bytes > 127 (non-ASCII)
                    if isinstance(d, str):
                        # Check if it's valid ASCII domain
                        try:
                            # Encode as ASCII with strict checking - will fail if non-ASCII chars
                            d.encode('ascii')

                            # Check for control characters (ASCII < 32 except space)
                            if any(ord(c) < 32 or ord(c) > 126 for c in d):
                                continue

                            # Must contain at least one dot
                            if '.' not in d:
                                continue

                            # Must only contain valid domain characters
                            if all(c.isalnum() or c in '._-' for c in d):
                                # Must start and end with alphanumeric
                                if d[0].isalnum() and d[-1].isalnum():
                                    valid_domains.append(d.lower())
                        except (UnicodeEncodeError, ValueError):
                            # Contains non-ASCII characters, skip
                            pass

                if valid_domains:
                    return {
                        "data_type": "certificate",
                        "update_type": "X509LogEntry",
                        "all_domains": valid_domains,
                        "seen_at": now_utc().isoformat(),
                    }
        except Exception as e:
            logger.debug(f"Failed to parse certpatrol entry: {e}")

        return None

    def _extract_domains_from_leaf(self, leaf_bytes: bytes) -> Optional[list[str]]:
        """Extract domains from CT log leaf entry.

        Args:
            leaf_bytes: Raw CT log leaf bytes

        Returns:
            List of domain names, or None
        """
        # Skip certpatrol entirely - use cryptography library directly
        try:
            from cryptography.x509 import load_der_x509_certificate
            from cryptography.hazmat.backends import default_backend
            from cryptography.x509 import DNSName, SubjectAlternativeName, NameOID, Extension

            # Extract certificate from CT log leaf
            cert_bytes = self._extract_cert_from_ct_leaf(leaf_bytes)
            if cert_bytes:
                cert = load_der_x509_certificate(cert_bytes, default_backend())
                domains = []

                # Get SANs
                try:
                    san_ext = cert.extensions.get_extension_for_class(SubjectAlternativeName)
                    for name in san_ext.value:
                        if isinstance(name, DNSName):
                            domain = name.value.lower()
                            # Validate: only ASCII alphanumeric, dots, hyphens, underscores
                            if domain and all(c.isalnum() or c in '.-_' for c in domain):
                                if '.' in domain and domain[0].isalnum() and domain[-1].isalnum():
                                    domains.append(domain)
                except Exception:
                    pass

                # Fallback to CN if SAN had no valid domains
                if not domains:
                    try:
                        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
                        if cn_attrs and '.' in cn_attrs[0].value:
                            cn = cn_attrs[0].value.lower()
                            if all(c.isalnum() or c in '.-_' for c in cn):
                                if cn[0].isalnum() and cn[-1].isalnum():
                                    domains.append(cn)
                    except Exception:
                        pass

                if domains:
                    return domains

        except ImportError:
            logger.debug("cryptography library not available")
        except Exception as e:
            logger.debug(f"Certificate parsing failed: {e}")

        return None

    def _extract_cert_from_ct_leaf(self, leaf_bytes: bytes) -> Optional[bytes]:
        """Extract X.509 certificate from CT log MerkleTreeLeaf.

        CT Log entry structure (RFC 6962):
        - Version: 2 bytes (0x0000 for v1)
        - Timestamp: 8 bytes
        - Entry type: 1 byte (0 for X509Entry)
        - Certificate: 3-byte TLS length prefix + DER-encoded certificate

        Args:
            leaf_bytes: Raw CT log leaf bytes

        Returns:
            DER-encoded X.509 certificate bytes, or None
        """
        try:
            # Minimum size: version(2) + timestamp(8) + entry_type(1) + cert_len(3) = 14 bytes
            if len(leaf_bytes) < 14:
                return None

            # After the header (14 bytes), look for X.509 SEQUENCE tag
            # The certificate should start at or after offset 14
            for i in range(14, min(30, len(leaf_bytes) - 20)):
                if leaf_bytes[i:i+1] == b'\x30':
                    # Found ASN.1 SEQUENCE tag - start of X.509 certificate
                    # Check if it uses long-form length (0x82)
                    if i + 1 < len(leaf_bytes) and leaf_bytes[i+1:i+2] == b'\x82':
                        # Long form: next 2 bytes are the length
                        cert_len = int.from_bytes(leaf_bytes[i+2:i+4], 'big')
                        cert_end = i + 4 + cert_len
                        if cert_end <= len(leaf_bytes):
                            return leaf_bytes[i:cert_end]
                        else:
                            # Certificate extends beyond available data
                            # Return what we have
                            return leaf_bytes[i:]
                    else:
                        # Short form or other format
                        # Just return from SEQUENCE tag onwards
                        return leaf_bytes[i:]
        except Exception as e:
            logger.debug(f"CT leaf parsing failed: {e}")

        return None

    async def _fetch_from_crtsh(self) -> int:
        """Fetch certificates from crt.sh API as fallback.

        Returns:
            Number of entries processed
        """
        client = await self._get_client()

        try:
            # Search for common domain patterns to find recent certificates
            # Using specific domains that are commonly seen in CT logs
            queries = ["example.com", "test.com", "*.com", "github.com", "google.com"]

            all_certs = []
            for query in queries:
                try:
                    url = CRTSH_API.format(query)
                    response = await client.get(url, timeout=15.0)
                    if response.status_code == 200:
                        data = response.json()
                        if data:
                            all_certs.extend(data[:50])  # Limit per query
                            logger.info(f"Query {query} returned {len(data)} results")
                except Exception as e:
                    logger.debug(f"Query {query} failed: {e}")
                    continue

            if not all_certs:
                logger.error("No certificates from crt.sh - CT log monitoring failed")
                return 0

            logger.info(f"Fetched {len(all_certs)} certificates from crt.sh")

            processed = 0
            for cert in all_certs:
                if not self._running:
                    break

                name_value = cert.get("name_value", "")
                if not name_value:
                    continue

                all_domains = [
                    d.strip().lower()
                    for d in name_value.split("\n")
                    if d.strip() and not d.strip().startswith("*.")
                ]

                if not all_domains:
                    continue

                entry_timestamp = cert.get("entry_timestamp", "")

                cert_data = {
                    "data_type": "certificate",
                    "update_type": "X509LogEntry",
                    "all_domains": all_domains,
                    "seen_at": entry_timestamp or now_utc().isoformat(),
                }

                cert_index = random.randint(1000000, 9999999)
                await self._store_raw_certificate(cert_data, cert_index)
                await self._process_cert_entry(cert_data, cert_index)

                self._processed_count += 1
                processed += 1

            return processed

        except Exception as e:
            logger.error(f"Failed to fetch from crt.sh: {e}")
            return 0

    async def _fetch_from_sunlight_tiles(self) -> int:
        """Fetch entries from public CT logs using CTLogReader.

        This serves as a secondary/tertiary data source when certpatrol
        is unavailable or returns no results.

        Returns:
            Number of entries processed
        """
        if not self._ct_log_reader:
            return 0

        try:
            total_entries = 0
            entries_per_log = settings.SUNLIGHT_ENTRIES_PER_LOG

            # Get list of public CT logs from settings
            public_logs = settings.SUNLIGHT_PUBLIC_LOGS

            logger.info(f"Fetching from {len(public_logs)} public CT logs ({entries_per_log} entries each)")

            for log_url in public_logs:
                if not self._running:
                    break

                try:
                    # Get current tree size
                    tree_size = await self._ct_log_reader.get_tree_size(log_url)

                    if tree_size is None:
                        logger.debug(f"Could not get tree size for {log_url}")
                        continue

                    # Get checkpoint position for this log
                    current_pos = self._sunlight_checkpoints.get(log_url, 0)

                    # For first run, start from recent entries
                    if current_pos == 0:
                        current_pos = max(0, tree_size - entries_per_log)
                        self._sunlight_checkpoints[log_url] = current_pos
                        logger.info(f"{log_url}: initial position {current_pos} (tree size: {tree_size})")

                    # Fetch new entries if available
                    if tree_size > current_pos:
                        # Calculate how many entries to fetch
                        new_count = min(tree_size - current_pos, entries_per_log)
                        end_pos = min(current_pos + new_count, tree_size)

                        logger.info(f"{log_url}: fetching entries {current_pos}-{end_pos}")

                        entries = await self._ct_log_reader.get_entries(
                            log_url,
                            current_pos,
                            end_pos - 1,
                        )

                        for entry in entries:
                            if not self._running:
                                break

                            # Convert to cert_data format
                            cert_data = {
                                "data_type": "certificate",
                                "update_type": "X509LogEntry",
                                "all_domains": entry.get("all_domains", []),
                                "seen_at": now_utc().isoformat(),
                                "source": "sunlight_ct_log",
                            }

                            # Store raw certificate
                            await self._store_raw_certificate(cert_data, current_pos + total_entries)

                            # Process for typosquat detection
                            await self._process_cert_entry(cert_data, current_pos + total_entries)

                            total_entries += 1
                            self._processed_count += 1

                        # Update checkpoint
                        self._sunlight_checkpoints[log_url] = end_pos
                        logger.info(f"{log_url}: processed {total_entries} entries, new checkpoint: {end_pos}")

                    else:
                        logger.debug(f"{log_url}: no new entries (current: {current_pos}, tree: {tree_size})")

                except Exception as e:
                    logger.warning(f"Error fetching from {log_url}: {e}")
                    continue

            return total_entries

        except Exception as e:
            logger.error(f"CT Log Reader error: {e}")
            return 0

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "AbuseChecker-CTMonitor/1.0"},
            )
        return self._client

    async def _store_raw_certificate(self, cert_data: dict, cert_index: int) -> None:
        """Store raw certificate data to Redis for the CertPatrol stream display.

        Args:
            cert_data: Certificate data dict
            cert_index: Certificate index
        """
        import redis

        try:
            r = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=False
            )

            raw_entry = json.dumps({
                "cert_index": cert_index,
                "data_type": cert_data.get("data_type", "certificate"),
                "update_type": cert_data.get("update_type", "X509LogEntry"),
                "all_domains": cert_data.get("all_domains", []),
                "seen_at": cert_data.get("seen_at", now_utc().isoformat()),
            })

            # Store to certpatrol:raw for unfiltered CT log data
            r.lpush("certpatrol:raw", raw_entry)
            r.ltrim("certpatrol:raw", 0, 499)  # Keep 500 entries

            # Also publish to pub/sub for real-time SSE
            try:
                r.publish("certpatrol:raw:stream", raw_entry)
                logger.debug(f"Published raw cert to Redis pub/sub: {cert_index}")
            except Exception as pub_err:
                logger.warning(f"Failed to publish to pub/sub: {pub_err}")

        except Exception as e:
            logger.debug(f"Failed to store raw cert: {e}")

    def _check_typosquat(
        self,
        domain: str,
        monitored_brands: list[str],
        custom_patterns: dict[str, list[str]] = None,
        custom_regex_patterns: dict[str, list[str]] = None,
        default_patterns: dict[str, list[str]] = None,
        whitelist_patterns: list[str] = None,
    ) -> Optional[tuple[str, str, int]]:
        """Check if a domain is a typosquat of monitored brands.

        Args:
            domain: Domain to check (lowercase)
            monitored_brands: List of brand names to monitor
            custom_patterns: Optional custom brand patterns {brand: [patterns]}
            custom_regex_patterns: Optional custom regex patterns {brand: [regex_patterns]}
            default_patterns: Optional default brand patterns {brand: [patterns]}
            whitelist_patterns: Optional whitelist regex patterns

        Returns:
            Tuple of (matched_brand, matched_pattern, score) or None
        """
        import re
        from app.utils.dns import get_registered_domain

        try:
            # Parse the domain to get registered domain (handles co.id, com.my, etc.)
            domain_parts = get_registered_domain(f"https://{domain}")
            registered = domain_parts["registered_domain"]
            main_domain = domain_parts["domain"]
        except Exception:
            return None

        # Check whitelist first - if domain matches any whitelist pattern, skip
        if whitelist_patterns:
            for pattern in whitelist_patterns:
                try:
                    if re.match(pattern, domain, re.IGNORECASE):
                        logger.debug(f"Domain {domain} matched whitelist pattern: {pattern}")
                        return None
                except re.error:
                    logger.warning(f"Invalid whitelist pattern: {pattern}")
                    continue

        # Skip if domain is exactly the real brand domain
        for brand in monitored_brands:
            if registered == f"{brand}.com" or registered == f"{brand}.co.id" or registered == f"{brand}.org":
                return None

        score = 0
        matched_brand = None
        matched_pattern = None

        # Check against custom regex patterns first (highest priority, highest score)
        if custom_regex_patterns:
            for brand, regex_patterns in custom_regex_patterns.items():
                for regex_pattern in regex_patterns:
                    try:
                        if re.search(regex_pattern, domain, re.IGNORECASE):
                            # Store all regex matches (for testing)
                                score = max(score, 85)  # Regex matches get high score
                                matched_brand = brand
                                matched_pattern = f"Regex: {regex_pattern}"
                    except re.error:
                        # Invalid regex, skip this pattern
                        logger.warning(f"Invalid regex pattern for {brand}: {regex_pattern}")
                        continue

        # Check against custom patterns second
        if custom_patterns:
            for brand, patterns in custom_patterns.items():
                for pattern in patterns:
                    if pattern in main_domain and pattern != brand:
                        # Direct pattern match (but not the brand itself)
                        if main_domain != f"{brand}.com" and main_domain != f"{brand}.co.id":
                            score = max(score, 70)
                            matched_brand = brand
                            matched_pattern = f"Pattern: {pattern}"

        # Check against default patterns (from database or hardcoded fallback)
        # Use database default_patterns if provided, otherwise fall back to hardcoded
        patterns_to_check = default_patterns if default_patterns else StaticURLAnalyzer.TYPOSQUAT_PATTERNS
        for brand, patterns in patterns_to_check.items():
            if brand not in monitored_brands:
                continue
            for pattern in patterns:
                if pattern in main_domain and pattern != brand:
                    # Make sure it's not the real domain
                    if not registered.endswith(f"{brand}.com") and not registered.endswith(f"{brand}.co.id"):
                        score = max(score, 75)
                        if matched_brand is None:
                            matched_brand = brand
                        if matched_pattern is None:
                            matched_pattern = f"Typosquat: {pattern}"

        # Check for common typosquat techniques if no match yet
        if score == 0:
            for brand in monitored_brands:
                brand_lower = brand.lower()
                domain_lower = main_domain.lower()

                # Character substitution checks
                substitutions = {
                    '0': 'o', '1': 'i', '1': 'l', '2': 'z', '3': 'e',
                    '4': 'a', '5': 's', '7': 't', '8': 'b', '9': 'g'
                }

                # Check if domain contains brand with number substitutions
                for num, char in substitutions.items():
                    if brand_lower.replace(char, num) in domain_lower:
                        score = max(score, 65)
                        matched_brand = brand
                        matched_pattern = f"Number substitution: {char}->{num}"
                        break

                # Check for character omissions
                for i in range(len(brand_lower)):
                    omitted = brand_lower[:i] + brand_lower[i+1:]
                    if omitted in domain_lower and len(main_domain) < len(brand) + 5:
                        score = max(score, 60)
                        matched_brand = brand
                        matched_pattern = f"Character omission"
                        break

                # Check for character swaps (adjacent characters)
                for i in range(len(brand_lower) - 1):
                    swapped = brand_lower[:i] + brand_lower[i+1] + brand_lower[i] + brand_lower[i+2:]
                    if swapped in domain_lower and len(main_domain) < len(brand) + 5:
                        score = max(score, 55)
                        matched_brand = brand
                        matched_pattern = f"Character swap"
                        break

                # Check for double characters
                for i in range(len(brand_lower)):
                    doubled = brand_lower[:i] + brand_lower[i] * 2 + brand_lower[i+1:]
                    if doubled in domain_lower and len(main_domain) < len(brand) + 5:
                        score = max(score, 50)
                        matched_brand = brand
                        matched_pattern = f"Double character"
                        break

                if score > 0:
                    break

        # Only return if score meets threshold
        if score >= self.min_score_threshold:
            return matched_brand, matched_pattern, score

        return None

    async def _check_http_status(self, domain: str) -> Optional[int]:
        """Check HTTP status code for a domain.

        Args:
            domain: Domain to check

        Returns:
            HTTP status code or None if check failed
        """
        try:
            import httpx
            urls = [f"https://{domain}", f"http://{domain}"]

            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                for url in urls:
                    try:
                        response = await client.head(url, follow_redirects=False)
                        return response.status_code
                    except (httpx.ConnectError, httpx.ConnectTimeout):
                        continue
                    except Exception:
                        continue
            return None
        except Exception:
            return None

    async def _process_cert_entry(self, entry: dict, cert_index: int) -> Optional[DetectedDomain]:
        """Process a certificate entry for typosquat detection.

        Args:
            entry: Parsed certificate entry
            cert_index: Certificate index

        Returns:
            DetectedDomain if typosquat found, None otherwise
        """
        from uuid import uuid4

        all_domains = entry.get("all_domains", [])
        if not all_domains:
            return None

        logger.info(f"Processing cert with {len(all_domains)} domains: {all_domains[:3]}")

        # Get current monitoring configuration
        config = await self._get_monitoring_config()
        logger.info(f"Config loaded: {len(config.get('custom_brand_regex_patterns', {}))} regex brands")
        monitored_brands = config.get("monitored_brands", self.monitored_brands or [])
        custom_patterns = config.get("custom_brand_patterns", {})
        custom_regex_patterns = config.get("custom_brand_regex_patterns", {})
        default_patterns = config.get("default_brand_patterns", {})
        whitelist_patterns = config.get("whitelist_patterns", [])

        seen_at = entry.get("seen_at", now_utc().isoformat())
        if isinstance(seen_at, str):
            seen_at = datetime.fromisoformat(seen_at.replace('Z', '+00:00'))

        # Check each domain in the certificate
        for domain in all_domains:
            try:
                result = self._check_typosquat(domain.lower(), monitored_brands, custom_patterns, custom_regex_patterns, default_patterns, whitelist_patterns)

                if result:
                    matched_brand, matched_pattern, score = result

                    # Check if already exists
                    async with get_db_context() as db:
                        existing = await db.execute(
                            select(DetectedDomain).where(
                                DetectedDomain.domain == domain
                            ).order_by(DetectedDomain.cert_seen_at.desc())
                        )
                        existing = existing.scalar_one_or_none()

                        if existing:
                            # Update existing if newer
                            if existing.cert_seen_at < seen_at:
                                existing.cert_seen_at = seen_at
                                existing.detection_score = max(existing.detection_score, score)
                                existing.cert_data = entry
                                await db.commit()
                            continue

                        # Check HTTP status for the domain
                        http_status_code = await self._check_http_status(domain)

                        # Create new detected domain
                        detected = DetectedDomain(
                            domain=domain,
                            cert_data=entry,
                            matched_brand=matched_brand,
                            matched_pattern=matched_pattern,
                            detection_score=score,
                            cert_seen_at=seen_at,
                            http_status_code=http_status_code,
                            http_checked_at=now_utc() if http_status_code else None,
                            status="pending"
                        )
                        db.add(detected)
                        await db.commit()

                        self._stored_count += 1
                        logger.info(
                            f"Typosquat detected: {domain} "
                            f"(brand: {matched_brand}, score: {score})"
                        )

                        # Send alert if score is high enough
                        if score >= self.alert_threshold:
                            try:
                                send_typosquat_alert_sync(
                                    domain=domain,
                                    brand=matched_brand,
                                    score=score,
                                    cert_data=entry
                                )
                            except Exception as e:
                                logger.warning(f"Failed to send alert: {e}")

            except Exception as e:
                logger.error(f"Error processing domain {domain}: {e}", exc_info=True)

        return None

    async def _get_monitoring_config(self) -> dict:
        """Get current monitoring configuration from database.

        Returns:
            Dict with monitored_brands, custom_brand_patterns, custom_brand_regex_patterns,
            default_brand_patterns, and whitelist_patterns
        """
        async with get_db_context() as db:
            result = await db.execute(select(HuntingConfigModel))
            config = result.scalar_one_or_none()

            if config:
                brands = config.monitored_brands or []
                if isinstance(brands, str):
                    import json
                    brands = json.loads(brands)

                # Get default patterns from DB or fall back to hardcoded defaults
                default_patterns = config.default_brand_patterns if config.default_brand_patterns else {}
                if not default_patterns:
                    # Fall back to hardcoded patterns
                    from app.utils.analyzer import StaticURLAnalyzer
                    default_patterns = dict(StaticURLAnalyzer.TYPOSQUAT_PATTERNS)

                # Get whitelist from DB or fall back to hardcoded defaults
                whitelist = config.whitelist_patterns if config.whitelist_patterns else []
                if not whitelist:
                    # Fall back to hardcoded whitelist from typosquat_patterns
                    from app.utils.typosquat_patterns import WHITELIST
                    whitelist = WHITELIST

                return {
                    "monitored_brands": brands,
                    "custom_brand_patterns": config.custom_brand_patterns or {},
                    "custom_brand_regex_patterns": config.custom_brand_regex_patterns or {},
                    "default_brand_patterns": default_patterns,
                    "whitelist_patterns": whitelist,
                }

            # Return defaults if no config in database
            from app.utils.analyzer import StaticURLAnalyzer
            from app.utils.typosquat_patterns import WHITELIST

            return {
                "monitored_brands": self.monitored_brands or [],
                "custom_brand_patterns": {},
                "custom_brand_regex_patterns": {},
                "default_brand_patterns": dict(StaticURLAnalyzer.TYPOSQUAT_PATTERNS),
                "whitelist_patterns": list(WHITELIST),
            }

    async def monitor(self) -> None:
        """Monitor CT logs for new certificates.

        Uses CT Log Reader for direct CT log access.
        """
        self._running = True

        # Initialize heartbeat in database
        await self._update_heartbeat()

        # Skip certpatrol initialization - use CT Log Reader only
        use_certpatrol = False

        if self._ct_log_reader:
            logger.info("CT Log monitor started using CT Log Reader")
        else:
            logger.info("CT Log monitor started using crt.sh API fallback")

        check_interval = 60  # Check every minute
        heartbeat_interval = 30  # Update heartbeat every 30 seconds

        import asyncio
        last_heartbeat = asyncio.get_event_loop().time()

        while self._running:
            try:
                entries_processed = 0

                # Update heartbeat periodically
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat >= heartbeat_interval:
                    await self._update_heartbeat()
                    last_heartbeat = current_time

                # Use CT Log Reader (reliable, working)
                if self._ct_log_reader:
                    entries_processed = await self._fetch_from_sunlight_tiles()

                # Fall back to crt.sh if CT Log Reader returned no entries
                if entries_processed == 0:
                    logger.debug("No entries from CT Log Reader, trying crt.sh fallback")
                    entries_processed = await self._fetch_from_crtsh()

                if entries_processed > 0:
                    logger.info(
                        f"Certificate batch complete. "
                        f"Processed: {self._processed_count}, Stored: {self._stored_count}"
                    )

                    # Progress callback
                    if self._progress_callback:
                        try:
                            if asyncio.iscoroutinefunction(self._progress_callback):
                                await self._progress_callback(self._processed_count, self._stored_count)
                            else:
                                self._progress_callback(self._processed_count, self._stored_count)
                        except Exception:
                            pass

                if self._running:
                    await asyncio.sleep(check_interval)

            except Exception as e:
                logger.error(f"Error in CT log monitor: {e}")
                if self._running:
                    await asyncio.sleep(check_interval)

    async def _update_heartbeat(self) -> None:
        """Update the heartbeat timestamp in the database."""
        try:
            async with get_db_context() as db:
                result = await db.execute(select(HuntingConfigModel))
                config = result.scalar_one_or_none()

                if config:
                    config.monitor_last_heartbeat = now_utc()
                    config.monitor_is_running = True
                    config.certificates_processed = self._processed_count
                    config.domains_detected = self._stored_count
                    config.error_message = None
                else:
                    # Create config if it doesn't exist
                    config = HuntingConfigModel(
                        monitor_is_running=True,
                        monitor_enabled=True,
                        monitor_last_heartbeat=now_utc(),
                        monitor_started_at=now_utc(),
                        certificates_processed=self._processed_count,
                        domains_detected=self._stored_count,
                    )
                    db.add(config)

                await db.commit()
        except Exception as e:
            logger.debug(f"Failed to update heartbeat: {e}")

    async def stop(self) -> None:
        """Stop the monitor."""
        logger.info("Stopping CT Log monitor...")
        self._running = False

        if self._client:
            await self._client.aclose()

        if self._ct_log_reader:
            await self._ct_log_reader.close()

        logger.info(
            f"CT Log monitor stopped. "
            f"Processed {self._processed_count} certificates, "
            f"stored {self._stored_count} domains"
        )


@dataclass
class TyposquatResult:
    """Result of typosquat analysis."""
    is_match: bool
    brand: Optional[str] = None
    pattern: Optional[str] = None
    score: int = 0


async def run_ct_log_monitor(
    min_score_threshold: int = 50,
    alert_threshold: int = 80,
    monitored_brands: Optional[list[str]] = None,
    custom_brand_patterns: Optional[dict[str, list[str]]] = None,
    custom_brand_regex_patterns: Optional[dict[str, list[str]]] = None,
    progress_callback: Optional[callable] = None,
) -> None:
    """Run the CT log monitor."""
    monitor = CTLogMonitor(
        min_score_threshold=min_score_threshold,
        alert_threshold=alert_threshold,
        monitored_brands=monitored_brands,
        custom_brand_patterns=custom_brand_patterns,
        custom_brand_regex_patterns=custom_brand_regex_patterns,
        progress_callback=progress_callback,
    )

    try:
        await monitor.monitor()
    except asyncio.CancelledError:
        logger.info("CT Log monitor cancelled")
        await monitor.stop()
    except Exception as e:
        logger.error(f"CT Log monitor error: {e}")
        await monitor.stop()


__all__ = ["CTLogMonitor", "run_ct_log_monitor"]
