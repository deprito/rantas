"""XARF (eXtended Abuse Reporting Format) v4 Generator Service.

This service generates XARF-compliant JSON reports for abuse reporting.
XARF v4 is a comprehensive, JSON-based format for structured abuse reporting
used by providers like DigitalOcean Abuse.

Specification: https://xarf.org/docs/specification/
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from app.config import settings
from app.models import Case


class XARFGenerator:
    """Generator for XARF v4 format abuse reports."""

    # XARF v4 specification version
    XARF_VERSION = "4.0.0"

    # Default category and type for phishing reports
    DEFAULT_CATEGORY = "content"
    DEFAULT_TYPE = "phishing"

    def __init__(self, case: Case, settings_override: Optional[dict[str, Any]] = None):
        """Initialize the XARF generator.

        Args:
            case: The Case object to generate a report for
            settings_override: Optional settings override for testing
        """
        self.case = case
        self.settings = settings_override or {
            "XARF_REPORTER_ORG": settings.XARF_REPORTER_ORG if hasattr(settings, 'XARF_REPORTER_ORG') else settings.APP_NAME,
            "XARF_REPORTER_CONTACT": settings.XARF_REPORTER_CONTACT if hasattr(settings, 'XARF_REPORTER_CONTACT') else settings.SMTP_FROM_EMAIL,
            "XARF_REPORTER_DOMAIN": settings.XARF_REPORTER_DOMAIN if hasattr(settings, 'XARF_REPORTER_DOMAIN') else settings.SMTP_FROM_EMAIL.split('@')[-1] if settings.SMTP_FROM_EMAIL and '@' in settings.SMTP_FROM_EMAIL else "phishtrack.local",
            "XARF_STORAGE_PATH": settings.XARF_STORAGE_PATH if hasattr(settings, 'XARF_STORAGE_PATH') else "./xarf_reports",
        }

    def _extract_target_brand(self) -> Optional[str]:
        """Extract the target brand from the case URL or domain info.

        Attempts to identify the brand being impersonated by the phishing site.
        This is a best-effort extraction based on common patterns.

        Returns:
            The brand name or None if not identifiable
        """
        domain_info = self.case.domain_info or {}
        url = self.case.url or ""

        # Check if domain_info has a target_brand field
        if "target_brand" in domain_info:
            return domain_info["target_brand"]

        # Try to extract from URL patterns
        # Common brands that are frequently impersonated
        common_brands = [
            "paypal", "apple", "amazon", "google", "microsoft",
            "facebook", "instagram", "netflix", "bank", "chase",
            "wellsfargo", "citibank", "steam", "ebay", "walmart",
            "dropbox", "adobe", "intuit", "turbotax", "hmrctax",
        ]

        url_lower = url.lower()
        for brand in common_brands:
            if brand in url_lower:
                return brand.capitalize()

        return None

    def _get_source_identifier(self) -> str:
        """Get the source identifier (IP or domain) from the case.

        Returns:
            The IP address or domain as the source identifier
        """
        domain_info = self.case.domain_info or {}

        # Prefer IP address as it's more specific
        ip = domain_info.get("ip")
        if ip:
            return ip

        # Fall back to domain
        domain = domain_info.get("domain", "")
        if domain:
            return domain

        # Last resort: extract domain from URL
        from urllib.parse import urlparse
        try:
            parsed = urlparse(self.case.url or "")
            return parsed.netloc or parsed.path
        except Exception:
            return "unknown"

    def _get_reporter_entity(self) -> dict[str, str]:
        """Build the reporter/sender entity for XARF.

        Returns:
            Dictionary with org, contact, and domain
        """
        return {
            "org": self.settings["XARF_REPORTER_ORG"],
            "contact": self.settings["XARF_REPORTER_CONTACT"],
            "domain": self.settings["XARF_REPORTER_DOMAIN"],
        }

    def generate(self) -> dict[str, Any]:
        """Generate XARF v4 JSON for phishing report.

        Returns:
            XARF-compliant dictionary
        """
        domain_info = self.case.domain_info or {}

        xarf_report = {
            # XARF specification version
            "xarf_version": self.XARF_VERSION,

            # Unique report identifier (use case ID)
            "report_id": str(self.case.id),

            # Report timestamp (use case creation time)
            "timestamp": self.case.created_at.isoformat() if self.case.created_at else datetime.utcnow().isoformat() + "Z",

            # Report classification
            "category": self.DEFAULT_CATEGORY,
            "type": self.DEFAULT_TYPE,

            # Reporter information
            "reporter": self._get_reporter_entity(),

            # Sender information (same as reporter for automated reports)
            "sender": self._get_reporter_entity(),

            # Source of the abuse (IP or domain)
            "source_identifier": self._get_source_identifier(),

            # The phishing URL
            "url": self.case.url or "",

            # Optional: The brand being impersonated
            "target_brand": self._extract_target_brand(),

            # Evidence source
            "evidence_source": "automated_scan",

            # Confidence level (0.0 to 1.0)
            "confidence": 0.95,
        }

        # Add optional domain information if available
        if domain_info.get("domain"):
            xarf_report["domain"] = domain_info["domain"]

        if domain_info.get("ip"):
            xarf_report["ip"] = domain_info["ip"]

        # Add optional registrar information
        if domain_info.get("registrar"):
            xarf_report["registrar"] = {
                "name": domain_info["registrar"],
            }

        # Add optional notes/history
        if self.case.history:
            # Add recent history entries as notes
            recent_history = list(self.case.history)[-3:] if isinstance(self.case.history, list) else []
            if recent_history:
                xarf_report["notes"] = [
                    f"{entry.get('type', 'system')}: {entry.get('message', '')}"
                    for entry in recent_history
                ]

        return xarf_report

    def to_json(self, pretty: bool = True) -> str:
        """Convert XARF report to JSON string.

        Args:
            pretty: Whether to pretty-print the JSON

        Returns:
            JSON string representation of the XARF report
        """
        if pretty:
            return json.dumps(self.generate(), indent=2, default=str)
        return json.dumps(self.generate(), default=str)

    def to_json_file(self) -> str:
        """Save XARF JSON to file and return the path.

        Creates the storage directory if it doesn't exist.
        Uses the case ID for the filename.
        Falls back to /tmp if the configured path is not writable.

        Returns:
            Path to the created XARF JSON file
        """
        import tempfile

        storage_path = Path(self.settings["XARF_STORAGE_PATH"])

        # Try to create the directory and write file
        # Fall back to temp directory if permission denied
        try:
            storage_path.mkdir(parents=True, exist_ok=True)
            # Test if we can write to this directory
            test_file = storage_path / ".write_test"
            test_file.touch()
            test_file.unlink()
            use_storage_path = True
        except (OSError, PermissionError):
            # Fall back to temp directory
            storage_path = Path(tempfile.gettempdir()) / "xarf_reports"
            storage_path.mkdir(parents=True, exist_ok=True)
            use_storage_path = False

        # Create filename with case ID and timestamp
        filename = f"xarf_{self.case.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = storage_path / filename

        # Write XARF JSON to file
        with open(file_path, 'w') as f:
            f.write(self.to_json(pretty=True))

        return str(file_path)

    def validate(self) -> list[str]:
        """Validate the XARF report against mandatory fields.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        report = self.generate()

        # Mandatory fields according to XARF v4 spec
        mandatory_fields = [
            "xarf_version",
            "report_id",
            "timestamp",
            "category",
            "type",
            "reporter",
            "sender",
            "source_identifier",
            "url",
        ]

        for field in mandatory_fields:
            if field not in report or not report[field]:
                errors.append(f"Missing mandatory field: {field}")

        # Validate reporter/sender structure
        for entity_name in ["reporter", "sender"]:
            entity = report.get(entity_name, {})
            if not isinstance(entity, dict):
                errors.append(f"{entity_name} must be an object")
                continue

            for entity_field in ["org", "contact", "domain"]:
                if not entity.get(entity_field):
                    errors.append(f"Missing {entity_name}.{entity_field}")

        return errors


__all__ = ["XARFGenerator"]
