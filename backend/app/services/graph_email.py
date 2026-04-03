"""Microsoft Graph API email service."""
import base64
from pathlib import Path
from azure.identity import ClientSecretCredential
from typing import Dict, List, Optional
import httpx

from app.config import settings


def send_graph_email(
    to_email: str,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    cc: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    inline_images: Optional[Dict[str, str]] = None,
) -> dict:
    """Send email via Microsoft Graph API.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Plain text email body
        html_body: Optional HTML email body
        cc: Optional CC email addresses (comma-separated)
        attachments: Optional list of file paths to attach
        inline_images: Optional dict mapping content_id to file_path for inline images

    Returns:
        Dictionary with send status
    """
    if not settings.GRAPH_ENABLED:
        return {
            "success": False,
            "error": "Graph API is disabled in configuration",
        }

    if not all([settings.GRAPH_TENANT_ID, settings.GRAPH_CLIENT_ID, settings.GRAPH_CLIENT_SECRET]):
        return {
            "success": False,
            "error": "Graph API credentials not configured",
        }

    try:
        # Get access token using client credentials
        credential = ClientSecretCredential(
            tenant_id=settings.GRAPH_TENANT_ID,
            client_id=settings.GRAPH_CLIENT_ID,
            client_secret=settings.GRAPH_CLIENT_SECRET,
        )

        # Get token for Graph API
        token = credential.get_token("https://graph.microsoft.com/.default")

        # Build email payload
        email_payload = {
            "message": {
                "subject": subject,
                "from": {
                    "emailAddress": {
                        "address": settings.GRAPH_FROM_EMAIL,
                        "name": settings.SMTP_FROM_NAME or "PhishTrack"
                    }
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email
                        }
                    }
                ],
                "body": {
                    "contentType": "HTML" if html_body else "Text",
                    "content": html_body or body
                }
            }
        }

        # Add CC recipients if provided
        if cc:
            cc_recipients = [
                {"emailAddress": {"address": email.strip()}}
                for email in cc.split(',')
                if email.strip()
            ]
            if cc_recipients:
                email_payload["message"]["ccRecipients"] = cc_recipients

        # Add attachments if provided
        attachment_list = []

        if attachments:
            for attachment_path in attachments:
                path = Path(attachment_path)
                if not path.exists():
                    continue

                # Read file and encode as base64
                with open(path, "rb") as f:
                    content_bytes = f.read()

                # Determine content type
                content_type = "application/octet-stream"
                if path.suffix == ".json":
                    content_type = "application/json"
                elif path.suffix == ".pdf":
                    content_type = "application/pdf"
                elif path.suffix in (".png", ".jpg", ".jpeg"):
                    content_type = f"image/{path.suffix[1:]}"
                elif path.suffix == ".txt":
                    content_type = "text/plain"

                # Graph API requires base64-encoded content without headers
                content_b64 = base64.b64encode(content_bytes).decode("utf-8")

                attachment_list.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": path.name,
                    "contentType": content_type,
                    "contentBytes": content_b64
                })

        # Add inline images if provided
        if inline_images:
            for content_id, image_path in inline_images.items():
                path = Path(image_path)
                if not path.exists():
                    continue

                # Read file and encode as base64
                with open(path, "rb") as f:
                    content_bytes = f.read()

                # Determine content type
                content_type = "image/png"
                if path.suffix == ".jpg" or path.suffix == ".jpeg":
                    content_type = "image/jpeg"
                elif path.suffix == ".gif":
                    content_type = "image/gif"
                elif path.suffix == ".webp":
                    content_type = "image/webp"

                # Graph API requires base64-encoded content without headers
                content_b64 = base64.b64encode(content_bytes).decode("utf-8")

                # Inline attachment with isInline=true and contentId
                attachment_list.append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": path.name,
                    "contentType": content_type,
                    "contentBytes": content_b64,
                    "isInline": True,
                    "contentId": content_id
                })

        if attachment_list:
            email_payload["message"]["attachments"] = attachment_list

        # Send email using Graph API REST endpoint
        # The URL path determines which mailbox sends the email
        url = f"https://graph.microsoft.com/v1.0/users/{settings.GRAPH_FROM_EMAIL}/sendMail"

        headers = {
            "Authorization": f"Bearer {token.token}",
            "Content-Type": "application/json",
        }

        with httpx.Client() as client:
            response = client.post(url, json=email_payload, headers=headers)

            if response.status_code == 202:
                return {
                    "success": True,
                    "to": to_email,
                    "cc": cc,
                    "attachments": [Path(p).name for p in attachments] if attachments else [],
                    "method": "graph_api",
                }
            else:
                return {
                    "success": False,
                    "error": f"Graph API returned {response.status_code}: {response.text}",
                }

    except Exception as e:
        return {
            "success": False,
            "error": f"Graph API error: {str(e)}",
        }
