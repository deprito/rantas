"""Browserless client for capturing screenshots."""
import hashlib
from typing import Optional
from pathlib import Path
from datetime import datetime

import httpx

from app.config import settings
from app.utils.timezone import now_utc


class BrowserlessClient:
    """Client for Browserless screenshot API."""

    def __init__(
        self,
        api_key: str,
        endpoint: str = "https://connected.browserless.io",
        viewport_width: int = 1440,
        viewport_height: int = 900,
        verify_ssl: bool = True,
    ):
        """Initialize the Browserless client.

        Args:
            api_key: Browserless API key
            endpoint: Browserless endpoint URL
            viewport_width: Viewport width in pixels (default: 1440 - MacBook standard)
            viewport_height: Viewport height in pixels (default: 900 - MacBook standard)
            verify_ssl: Whether to verify SSL certificates (default: True)
        """
        self.api_key = api_key
        self.endpoint = endpoint.rstrip("/")
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.verify_ssl = verify_ssl

    def get_screenshot_url(self) -> str:
        """Get the full screenshot endpoint URL."""
        return f"{self.endpoint}/screenshot"

    async def capture_screenshot(
        self,
        url: str,
        output_path: str,
        full_page: bool = True,
        wait_for: Optional[int] = None,
    ) -> dict:
        """Capture a screenshot of a URL using Browserless.

        Args:
            url: URL to capture
            output_path: Path where the screenshot will be saved
            full_page: Capture the full page or just the viewport
            wait_for: Optional milliseconds to wait before capturing

        Returns:
            Dictionary with capture results including file path and metadata
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Browserless API key not configured",
            }

        # Build query parameters with API key (production API only accepts token, blockAds, timeout)
        params = {
            "token": self.api_key,
            "blockAds": "false",
            "timeout": "60000",
        }

        # Build the screenshot request payload - production API only accepts URL in body
        payload = {
            "url": url,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0, verify=self.verify_ssl) as client:
                response = await client.post(
                    self.get_screenshot_url(),
                    params=params,
                    json=payload,
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Browserless returned status {response.status_code}: {response.text[:200]}",
                    }

                # Ensure output directory exists
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)

                # Write screenshot to file
                with open(output_path, "wb") as f:
                    f.write(response.content)

                # Calculate content hash for deduplication
                content_hash = hashlib.sha256(response.content).hexdigest()

                # Get file size
                file_size = len(response.content)

                return {
                    "success": True,
                    "file_path": output_path,
                    "content_hash": content_hash,
                    "file_size": file_size,
                    "viewport_width": self.viewport_width,
                    "viewport_height": self.viewport_height,
                    "full_page": full_page,
                    "captured_at": now_utc().isoformat(),
                }

        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "Screenshot capture timed out",
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": f"Request error: {str(e)}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
            }

    def capture_screenshot_sync(
        self,
        url: str,
        output_path: str,
        full_page: bool = True,
        wait_for: Optional[int] = None,
    ) -> dict:
        """Synchronous version of capture_screenshot for use in Celery tasks.

        Args:
            url: URL to capture
            output_path: Path where the screenshot will be saved
            full_page: Capture the full page or just the viewport
            wait_for: Optional milliseconds to wait before capturing

        Returns:
            Dictionary with capture results including file path and metadata
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Browserless API key not configured",
            }

        # Build query parameters with API key (production API only accepts token, blockAds, timeout)
        params = {
            "token": self.api_key,
            "blockAds": "false",
            "timeout": "60000",
        }

        # Build the screenshot request payload - production API only accepts URL in body
        payload = {
            "url": url,
        }

        try:
            with httpx.Client(timeout=60.0, verify=self.verify_ssl) as client:
                response = client.post(
                    self.get_screenshot_url(),
                    params=params,
                    json=payload,
                )

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Browserless returned status {response.status_code}: {response.text[:200]}",
                    }

                # Ensure output directory exists
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)

                # Write screenshot to file
                with open(output_path, "wb") as f:
                    f.write(response.content)

                # Calculate content hash for deduplication
                content_hash = hashlib.sha256(response.content).hexdigest()

                # Get file size
                file_size = len(response.content)

                return {
                    "success": True,
                    "file_path": output_path,
                    "content_hash": content_hash,
                    "file_size": file_size,
                    "viewport_width": self.viewport_width,
                    "viewport_height": self.viewport_height,
                    "full_page": full_page,
                    "captured_at": now_utc().isoformat(),
                }

        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "Screenshot capture timed out",
            }
        except httpx.RequestError as e:
            return {
                "success": False,
                "error": f"Request error: {str(e)}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
            }


__all__ = ["BrowserlessClient"]
