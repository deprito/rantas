"""API endpoints for webhooks."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr

from app.config import settings
from app.schemas import WebhookResponse
from app.tasks.email import process_email_webhook_task

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class EmailWebhookData(BaseModel):
    """Schema for incoming email webhook data."""

    from_email: EmailStr
    to_email: EmailStr
    subject: str
    body: str
    headers: dict = {}
    timestamp: Optional[str] = None


@router.post("/email", response_model=WebhookResponse)
async def email_webhook(
    data: EmailWebhookData,
    request: Request,
    x_webhook_secret: Optional[str] = Header(None),
) -> WebhookResponse:
    """Handle incoming email webhook for abuse report replies.

    This endpoint receives notifications when abuse contacts reply to
    takedown emails. It extracts the case ID from the subject line
    and updates the case history.

    Case ID format in subject: [Case-ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx]

    Args:
        data: Email webhook data
        request: FastAPI request object
        x_webhook_secret: Webhook secret for verification

    Returns:
        WebhookResponse with processing result
    """
    # Verify webhook secret if configured
    if settings.WEBHOOK_SECRET and settings.WEBHOOK_SECRET != "change-this-secret-in-production":
        if x_webhook_secret != settings.WEBHOOK_SECRET:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook secret",
            )

    try:
        # Process the webhook asynchronously
        result = process_email_webhook_task.delay(
            from_email=str(data.from_email),
            subject=data.subject,
            body=data.body,
            headers=data.headers,
        )

        return WebhookResponse(
            success=True,
            message="Email webhook accepted for processing",
            case_id=result.id,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process email webhook: {str(e)}",
        )


@router.post("/email/test", response_model=WebhookResponse)
async def test_email_webhook(
    data: EmailWebhookData,
) -> WebhookResponse:
    """Test endpoint for email webhook processing.

    This endpoint processes the webhook synchronously for testing purposes.

    Args:
        data: Email webhook data

    Returns:
        WebhookResponse with processing result
    """
    try:
        # Import the async function directly
        from app.tasks.email import _process_webhook_async
        import asyncio

        result = await asyncio.run(_process_webhook_async(
            from_email=str(data.from_email),
            subject=data.subject,
            body=data.body,
            headers=data.headers,
        ))

        if result.get("success"):
            return WebhookResponse(
                success=True,
                message="Email processed successfully",
                case_id=UUID(result["case_id"]) if result.get("case_id") else None,
            )
        else:
            return WebhookResponse(
                success=False,
                message=result.get("error", "Processing failed"),
            )

    except Exception as e:
        return WebhookResponse(
            success=False,
            message=f"Failed to process: {str(e)}",
        )


@router.post("/health", response_model=dict)
async def webhook_health() -> dict:
    """Health check endpoint for webhook service.

    Returns:
        Health status
    """
    return {
        "status": "healthy",
        "service": "webhooks",
        "timestamp": "ok",
    }


@router.post("/verify", response_model=dict)
async def verify_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(None),
) -> dict:
    """Verify webhook configuration.

    Args:
        request: FastAPI request object
        x_webhook_secret: Webhook secret for verification

    Returns:
        Verification status
    """
    is_valid = (
        not settings.WEBHOOK_SECRET or
        settings.WEBHOOK_SECRET == "change-this-secret-in-production" or
        x_webhook_secret == settings.WEBHOOK_SECRET
    )

    return {
        "valid": is_valid,
        "configured": bool(settings.WEBHOOK_SECRET and settings.WEBHOOK_SECRET != "change-this-secret-in-production"),
    }


__all__ = ["router"]
