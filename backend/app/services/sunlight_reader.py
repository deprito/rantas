"""CT Log reader for public Certificate Transparency logs.

This module provides a simple HTTP client to read certificate data from
public CT logs that use the standard CT Log API (RFC 6962).
"""
import asyncio
import base64
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class CTLogReader:
    """Read CT log data from public CT logs using standard JSON API.

    This reader connects to public CT logs (Google, Cloudflare, DigiCert, etc.)
    and fetches certificate entries using the standard CT Log protocol:
    - get-sth: Get current tree head (tree size)
    - get-entries: Fetch entries by index range

    This provides a reliable secondary data source for the hunting feature.
    """

    # Public CT logs that support standard CT Log API
    PUBLIC_LOGS = [
        {
            "name": "Google_Argon2026h1",
            "url": "https://ct.googleapis.com/logs/us1/argon2026h1/",
            "description": "Google Argon 2026 H1 (US)",
        },
        {
            "name": "Google_Argon2026h2",
            "url": "https://ct.googleapis.com/logs/us1/argon2026h2/",
            "description": "Google Argon 2026 H2 (US)",
        },
        {
            "name": "Cloudflare_Nimbus2026",
            "url": "https://ct.cloudflare.com/logs/nimbus2026/",
            "description": "Cloudflare Nimbus 2026",
        },
        {
            "name": "DigiCert_Wyvern2026h1",
            "url": "https://wyvern.ct.digicert.com/2026h1/",
            "description": "DigiCert Wyvern 2026 H1",
        },
        {
            "name": "DigiCert_Sphinx2026h1",
            "url": "https://sphinx.ct.digicert.com/2026h1/",
            "description": "DigiCert Sphinx 2026 H1",
        },
    ]

    def __init__(self, client_timeout: float = 30.0):
        """Initialize the CT Log reader.

        Args:
            client_timeout: HTTP client timeout in seconds
        """
        self.client_timeout = client_timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.client_timeout,
                headers={"User-Agent": "AbuseChecker-CTLogReader/1.0"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_tree_size(self, log_url: str) -> Optional[int]:
        """Get current tree size from a CT log's STH.

        Args:
            log_url: Base URL of the CT log

        Returns:
            Current tree size, or None if request failed
        """
        client = await self._get_client()

        try:
            url = f"{log_url}ct/v1/get-sth"
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()
            tree_size = data.get("tree_size")

            if tree_size is not None:
                logger.debug(f"{log_url}: tree size = {tree_size}")
                return tree_size

        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error fetching STH from {log_url}: {e}")
        except Exception as e:
            logger.warning(f"Error fetching STH from {log_url}: {e}")

        return None

    async def get_entries(
        self,
        log_url: str,
        start: int,
        end: int,
    ) -> list[dict]:
        """Fetch entries from a CT log by index range.

        Args:
            log_url: Base URL of the CT log
            start: Starting index (inclusive)
            end: Ending index (inclusive)

        Returns:
            List of parsed certificate entries with domains
        """
        client = await self._get_client()

        try:
            url = f"{log_url}ct/v1/get-entries"
            params = {"start": start, "end": end}

            response = await client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            entries = data.get("entries", [])

            parsed = []
            for entry in entries:
                parsed_entry = self._parse_entry(entry)
                if parsed_entry:
                    parsed.append(parsed_entry)

            return parsed

        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error fetching entries from {log_url}: {e}")
        except Exception as e:
            logger.warning(f"Error fetching entries from {log_url}: {e}")

        return []

    def _parse_entry(self, entry: dict) -> Optional[dict]:
        """Parse a CT log entry to extract certificate domains.

        Args:
            entry: Raw CT log entry with leaf_input and extra_data

        Returns:
            Parsed entry with 'all_domains' list, or None
        """
        try:
            # Parse leaf_input to get certificate data
            leaf_input = entry.get("leaf_input", "")
            if not leaf_input:
                # Try extra_data as fallback
                leaf_input = entry.get("extra_data", "")

            if not leaf_input:
                return None

            # The leaf_input is base64-encoded
            leaf_bytes = base64.b64decode(leaf_input)

            # Try to extract domains from the certificate
            domains = self._extract_domains_from_der(leaf_bytes)

            if domains:
                return {
                    "all_domains": domains,
                    "leaf_input": leaf_input[:100] if len(leaf_input) > 100 else leaf_input,
                }

        except Exception as e:
            logger.debug(f"Failed to parse entry: {e}")

        return None

    def _extract_domains_from_der(self, der_bytes: bytes) -> Optional[list[str]]:
        """Extract domains from DER-encoded certificate or CT log leaf.

        CT Log leaf_input contains a MerkleTreeLeaf structure that wraps the
        actual certificate. This method parses that structure and extracts
        the Subject Alternative Names (SANs) and Common Name (CN) from the cert.

        Args:
            der_bytes: DER-encoded certificate bytes or CT log leaf

        Returns:
            List of domain names found in certificate
        """
        # Try certpatrol first if available
        try:
            import certpatrol
            try:
                domains = certpatrol.extract_domains_from_der(der_bytes)
                if domains:
                    return list(domains)
            except Exception:
                pass  # Fall through to custom parsing
        except ImportError:
            pass  # certpatrol not available

        # Use cryptography library for proper X.509 parsing
        try:
            from cryptography.x509 import load_der_x509_certificate
            from cryptography.hazmat.backends import default_backend

            # Parse CT Log MerkleTreeLeaf structure to find the actual certificate
            cert_bytes = self._extract_cert_from_ct_leaf(der_bytes)
            if cert_bytes:
                cert = load_der_x509_certificate(cert_bytes, default_backend())
                domains = self._get_domains_from_cert(cert)
                if domains:
                    return domains

        except ImportError:
            logger.debug("cryptography library not available, using heuristic parsing")
        except Exception as e:
            logger.debug(f"Certificate parsing failed: {e}")

        # Fallback to heuristic parsing
        return self._extract_domains_heuristic(der_bytes)

    def _extract_cert_from_ct_leaf(self, leaf_bytes: bytes) -> Optional[bytes]:
        """Extract X.509 certificate from CT log MerkleTreeLeaf.

        CT Log entry format (RFC 6962):
        - MerkleTreeLeaf.version (2 bytes)
        - MerkleTreeLeaf.timestamp (8 bytes)
        - MerkleTreeLeaf.entry_type (1 byte) - 0 for X509Entry
        - MerkleTreeLeaf.entry (variable)
          - For X509Entry: 3-byte TLS length prefix + DER-encoded certificate

        The X.509 certificate itself starts with ASN.1 SEQUENCE tag (0x30).

        Args:
            leaf_bytes: Raw CT log leaf bytes

        Returns:
            DER-encoded X.509 certificate bytes, or None
        """
        try:
            # Look for X.509 SEQUENCE tag (0x30) after the CT log header
            # CT Log header is 14 bytes (version 2 + timestamp 8 + entry_type 1 + cert_len 3)
            # Start looking for X.509 SEQUENCE tag after the header
            for i in range(14, min(30, len(leaf_bytes) - 20)):
                if leaf_bytes[i:i+1] == b'\x30':
                    # Found potential ASN.1 SEQUENCE tag
                    # Check if next byte indicates long form length (0x82)
                    if i + 1 < len(leaf_bytes) and leaf_bytes[i+1:i+2] == b'\x82':
                        # Long form length - next 2 bytes are the length
                        if i + 3 < len(leaf_bytes):
                            cert_len = int.from_bytes(leaf_bytes[i+2:i+4], 'big')
                            cert_end = i + 4 + cert_len
                            if cert_end <= len(leaf_bytes):
                                # Return just the certificate bytes
                                return leaf_bytes[i:cert_end]
                            else:
                                # Return what we have (might be partial)
                                return leaf_bytes[i:]
                    else:
                        # Short form or other format - try to extract
                        return leaf_bytes[i:]

        except Exception as e:
            logger.debug(f"CT leaf parsing failed: {e}")

        return None

    def _get_domains_from_cert(self, cert) -> list[str]:
        """Extract domains from a parsed X.509 certificate.

        Args:
            cert: cryptography.x509.Certificate object

        Returns:
            List of domain names
        """
        from cryptography.x509 import DNSName, ExtensionNotFound, SubjectAlternativeName
        from cryptography.x509 import NameOID
        import re

        domains = []

        try:
            # Get Subject Alternative Names
            san_ext = cert.extensions.get_extension_for_class(SubjectAlternativeName)
            if san_ext:
                for name in san_ext.value:
                    if isinstance(name, DNSName):
                        value = name.value.lower()
                        # Clean any control characters
                        value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
                        if value and '.' in value:
                            domains.append(value)
        except ExtensionNotFound:
            pass

        # Fallback to Common Name
        if not domains:
            try:
                cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
                if cn_attrs:
                    cn_value = cn_attrs[0].value
                    if '.' in cn_value:
                        value = cn_value.lower()
                        # Clean any control characters
                        value = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
                        if value:
                            domains.append(value)
            except Exception:
                pass

        return domains

    def _extract_domains_heuristic(self, der_bytes: bytes) -> Optional[list[str]]:
        """Fallback heuristic domain extraction.

        Args:
            der_bytes: Raw certificate bytes

        Returns:
            List of domain names, or None
        """
        import re

        try:
            # Look for X.509 certificate start marker
            cert_start = -1
            for i in range(len(der_bytes) - 20):
                if der_bytes[i:i+2] == b'\x30\x82':
                    cert_start = i
                    break

            if cert_start < 0:
                return None

            cert_bytes = der_bytes[cert_start:]
            domains = []

            # Look for SAN extension (OID 2.5.29.17 = 55 1D 11)
            san_pattern = rb'\x55\x1d\x11'
            san_match = re.search(san_pattern, cert_bytes)

            if san_match:
                san_start = san_match.end() + 4
                i = san_start
                while i < len(cert_bytes) - 10:
                    # DNS name tag in SAN can be \x82 (context-specific) or just the name
                    if cert_bytes[i:i+1] == b'\x82':  # DNS name tag with length
                        if i + 2 < len(cert_bytes):
                            name_len = int.from_bytes(cert_bytes[i+1:i+3], 'big')
                            if i + 3 + name_len <= len(cert_bytes):
                                raw_domain = cert_bytes[i+3:i+3+name_len]
                                # Decode and clean - remove non-ASCII/control characters
                                domain = raw_domain.decode('ascii', errors='ignore')
                                # Strip any control characters or non-domain characters
                                domain = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', domain)
                                if domain and '.' in domain and all(c.isalnum() or c in '.-' for c in domain):
                                    # Validate: only alphanumeric, dots, hyphens
                                    domains.append(domain.lower())
                                i += 3 + name_len
                                continue
                    i += 1
                    if i - san_start > 1000:
                        break

            if domains:
                return domains

        except Exception as e:
            logger.debug(f"Heuristic parsing failed: {e}")

        return None

    async def get_recent_entries(
        self,
        log_url: str,
        count: int = 100,
    ) -> list[dict]:
        """Fetch the most recent entries from a CT log.

        Args:
            log_url: Base URL of the CT log
            count: Number of recent entries to fetch

        Returns:
            List of parsed certificate entries
        """
        tree_size = await self.get_tree_size(log_url)

        if tree_size is None:
            return []

        # Calculate start index (count entries back from current head)
        start = max(0, tree_size - count)
        end = tree_size - 1

        logger.info(f"Fetching entries {start}-{end} from {log_url}")
        return await self.get_entries(log_url, start, end)

    async def scan_all_logs(
        self,
        entries_per_log: int = 50,
    ) -> dict[str, list[dict]]:
        """Scan all configured public CT logs for recent entries.

        Args:
            entries_per_log: Number of entries to fetch from each log

        Returns:
            Dict mapping log names to their entries
        """
        results = {}

        tasks = []
        for log_config in self.PUBLIC_LOGS:
            tasks.append(self._scan_log(log_config, entries_per_log))

        # Run scans concurrently
        scan_results = await asyncio.gather(*tasks, return_exceptions=True)

        for log_config, result in zip(self.PUBLIC_LOGS, scan_results):
            if isinstance(result, Exception):
                logger.warning(f"Error scanning {log_config['name']}: {result}")
            elif result:
                results[log_config["name"]] = result
                logger.info(f"{log_config['name']}: found {len(result)} entries")

        return results

    async def _scan_log(
        self,
        log_config: dict,
        entries_per_log: int,
    ) -> list[dict]:
        """Scan a single CT log.

        Args:
            log_config: Log configuration dict
            entries_per_log: Number of entries to fetch

        Returns:
            List of parsed entries
        """
        try:
            return await self.get_recent_entries(
                log_config["url"],
                entries_per_log,
            )
        except Exception as e:
            logger.warning(f"Error scanning {log_config['name']}: {e}")
            return []


class SunlightTileReader:
    """Reader for Sunlight-format static CT log tiles.

    Sunlight (by FiloSottile/Let's Encrypt) serves CT log data as static
    JSON tiles. This class provides compatibility with that format.

    Note: Most public CT logs now use the standard JSON API rather than
    Sunlight tiles. Use CTLogReader for general CT log access.
    """

    # Example Sunlight-format endpoints (if any become publicly available)
    PUBLIC_LOGS = []

    async def get_tree_size(self, log_url: str) -> Optional[int]:
        """Get current tree size from Sunlight checkpoint.

        Args:
            log_url: Base URL of the Sunlight log

        Returns:
            Current tree size, or None
        """
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{log_url}/checkpoint")
                if resp.status_code == 200:
                    return int(resp.text.strip())
            except Exception as e:
                logger.debug(f"Failed to get Sunlight checkpoint: {e}")

        return None

    async def get_tile(self, log_url: str, tile_index: int) -> list[dict]:
        """Fetch a Sunlight tile (256 entries).

        Args:
            log_url: Base URL of the Sunlight log
            tile_index: Tile number (each tile has 256 entries)

        Returns:
            List of entries from the tile
        """
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{log_url}/tile_{tile_index}.json")
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("entries", [])
            except Exception as e:
                logger.debug(f"Failed to get Sunlight tile {tile_index}: {e}")

        return []

    async def get_entries(
        self,
        log_url: str,
        start: int,
        limit: int = 256,
    ) -> list[dict]:
        """Get entries starting from index.

        Args:
            log_url: Base URL of the Sunlight log
            start: Starting entry index
            limit: Maximum entries to return

        Returns:
            List of certificate entries
        """
        tile_index = start // 256
        entries = await self.get_tile(log_url, tile_index)

        if not entries:
            return []

        offset_in_tile = start % 256
        return entries[offset_in_tile:offset_in_tile + limit]


# Convenience function for quick access
async def get_recent_certificates(
    count: int = 100,
) -> dict[str, list[dict]]:
    """Get recent certificates from all public CT logs.

    Args:
        count: Number of entries to fetch per log

    Returns:
        Dict mapping log names to their entries
    """
    reader = CTLogReader()
    try:
        return await reader.scan_all_logs(entries_per_log=count)
    finally:
        await reader.close()


__all__ = [
    "CTLogReader",
    "SunlightTileReader",
    "get_recent_certificates",
]
