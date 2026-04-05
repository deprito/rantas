"""Public API endpoints - no authentication required.

Provides public URL submission and analysis endpoints for external users.
"""
import re
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db_context
from app.models import PublicSubmission
from app.utils.analyzer import (
    RiskLevel,
    quick_analyze,
    StaticURLAnalyzer,
    URLSafetyAnalyzer,
)
from app.utils.ai_analyzer import ai_analyze_url
from app.utils.timezone import now_utc


router = APIRouter(prefix="/public", tags=["public"])


# ==================== Request/Response Schemas ====================


class AnalyzeRequest(BaseModel):
    """Request schema for URL analysis."""

    url: str = Field(..., description="URL to analyze", min_length=1, max_length=2048)
    deep: bool = Field(False, description="Perform deep analysis (DNS/HTTP checks)")
    use_ai: bool = Field(False, description="Use AI-powered content analysis (requires Ollama)")

    @field_validator("url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        """Normalize URL to ensure it has a scheme."""
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v


class QuickAnalysisResponse(BaseModel):
    """Response schema for quick URL analysis."""

    url: str
    risk_level: str  # 'safe' | 'low' | 'medium' | 'high' | 'critical'
    score: int  # 0-100
    can_submit: bool
    message: str
    quick_flags: list[str]
    analysis_id: Optional[str] = None
    ai_analysis: Optional[dict] = None  # AI analysis results if use_ai=True


class PublicSubmitRequest(BaseModel):
    """Request schema for public URL submission."""

    url: str = Field(..., description="URL to report", min_length=1, max_length=2048)
    email: str = Field(..., description="Submitter email (required)")
    notes: Optional[str] = Field(None, description="Additional notes about the submission", max_length=2000)

    @field_validator("url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        """Normalize URL to ensure it has a scheme."""
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v


class PublicSubmitResponse(BaseModel):
    """Response schema for public URL submission."""

    id: str
    url: str
    status: str
    created_at: datetime
    message: str


class CheckUrlRequest(BaseModel):
    """Request schema for URL classification check."""

    url: str = Field(..., description="URL to check", min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        """Normalize URL to ensure it has a scheme."""
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            v = "https://" + v
        return v


class CheckUrlResponse(BaseModel):
    """Response schema for URL classification check."""

    url: str
    domain: str
    classification: str  # 'not_suspicious' | 'suspicious' | 'high_risk'
    confidence: float
    reasons: list[str]
    details: dict
    can_submit: bool
    message: str


# ==================== Endpoints ====================


@router.post("/analyze", response_model=QuickAnalysisResponse)
async def analyze_url(
    request: Request,
    data: AnalyzeRequest,
) -> QuickAnalysisResponse:
    """Analyze a URL for security threats.

    Performs comprehensive URL safety analysis including:
    - Static analysis: URL structure, TLD checks, keyword detection
    - Deep analysis (if requested): DNS lookups, HTTP checks, domain intelligence
    - AI analysis (if requested): LLM-powered content analysis via Ollama

    Args:
        request: FastAPI request object
        data: Analysis request with URL, deep analysis flag, and AI flag

    Returns:
        QuickAnalysisResponse with risk score, level, and detected flags
    """
    try:
        # Run the base analysis
        result = await quick_analyze(data.url, deep=data.deep)

        # AI analysis if requested and enabled
        ai_analysis = None
        if data.use_ai and settings.OLLAMA_ENABLED:
            try:
                ai_score, ai_flags, ai_details = await ai_analyze_url(data.url)
                ai_analysis = {
                    "enabled": True,
                    "score": ai_score,
                    "flags": ai_flags,
                    "details": ai_details,
                }

                # Merge AI flags with rule-based flags
                if ai_flags and ai_details.get("is_phishing"):
                    result.quick_flags.extend([f"AI: {flag}" for flag in ai_flags])
                    # Boost score if AI detected phishing
                    if ai_score > result.score:
                        result.score = min(100, int((result.score + ai_score) / 2) + 10)

            except Exception as ai_error:
                print(f"AI analysis failed (non-fatal): {ai_error}")
                ai_analysis = {"enabled": True, "error": str(ai_error)}

        # Recalculate risk level and can_submit based on updated score
        analyzer = URLSafetyAnalyzer(enable_deep_analysis=False)
        new_risk_level = analyzer._get_risk_level(result.score, result.quick_flags)
        new_message = analyzer._generate_message(new_risk_level, result.quick_flags)
        result.risk_level = new_risk_level
        result.can_submit = new_risk_level in [RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        result.message = new_message

        return QuickAnalysisResponse(
            url=result.url,
            risk_level=result.risk_level.value,
            score=result.score,
            can_submit=result.can_submit,
            message=result.message,
            quick_flags=result.quick_flags,
            analysis_id=result.analysis_id,
            ai_analysis=ai_analysis,
        )

    except Exception as e:
        import traceback
        print(f"Error during URL analysis: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}",
        )


@router.post("/submit", response_model=PublicSubmitResponse, status_code=status.HTTP_201_CREATED)
async def public_submit_url(
    request: Request,
    data: PublicSubmitRequest,
) -> PublicSubmitResponse:
    """Submit a suspicious URL for investigation (public endpoint).

    This endpoint allows unauthenticated users to submit URLs for review.
    Submitted URLs are stored as PublicSubmission records for staff review.

    Args:
        request: FastAPI request object
        data: Submission request with URL, optional email, and notes

    Returns:
        PublicSubmitResponse with submission ID and status
    """
    # Validate corporate email domain
    corporate_email_pattern = r'^[^@]+@example\.com$'
    if not re.match(corporate_email_pattern, data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please use your corporate email to submit",
        )

    try:
        async with get_db_context() as db:
            # Check for duplicate URL in pending submissions
            existing_result = await db.execute(
                select(PublicSubmission).where(
                    PublicSubmission.url == data.url,
                    PublicSubmission.status == "pending"
                )
            )
            existing = existing_result.scalar_one_or_none()

            if existing:
                # Return existing submission instead of creating duplicate
                return PublicSubmitResponse(
                    id=str(existing.id),
                    url=existing.url,
                    status=existing.status,
                    created_at=existing.submitted_at,
                    message="This URL has already been submitted and is being reviewed.",
                )

            # Create new public submission
            new_submission = PublicSubmission(
                url=data.url,
                submitter_email=data.email,
                additional_notes=data.notes,
                ip_address=_get_client_ip(request),
                status="pending",
            )

            db.add(new_submission)
            await db.flush()
            await db.refresh(new_submission)

            # Convert to response before commit
            submission_id = str(new_submission.id)
            created_at = new_submission.submitted_at

            await db.commit()

            return PublicSubmitResponse(
                id=submission_id,
                url=new_submission.url,
                status=new_submission.status,
                created_at=created_at,
                message="Your submission has been received and will be reviewed by our team.",
            )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error during submission: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Submission failed: {str(e)}",
        )


@router.post("/check-url", response_model=CheckUrlResponse)
async def check_url(
    request: Request,
    data: CheckUrlRequest,
) -> CheckUrlResponse:
    """Check URL classification (legacy endpoint).

    This is a simplified URL check endpoint for backward compatibility.
    For detailed analysis, use the /analyze endpoint instead.

    Args:
        request: FastAPI request object
        data: Check request with URL

    Returns:
        CheckUrlResponse with classification and details
    """
    try:
        from app.utils.dns import get_registered_domain

        # Perform static analysis
        score, flags = StaticURLAnalyzer.analyze(data.url)

        # Use get_registered_domain for proper ccSLD handling
        domain_info = get_registered_domain(data.url)
        domain = domain_info["registered_domain"]
        tld = domain_info["suffix"]  # Now correctly returns "my.id" instead of "id"

        # Determine classification
        if score < 20:
            classification = "not_suspicious"
            can_submit = False
        elif score < 50:
            classification = "suspicious"
            can_submit = True
        else:
            classification = "high_risk"
            can_submit = True

        # Calculate confidence based on score
        confidence = min(score / 100 + 0.5, 1.0)

        # Generate message
        if classification == "not_suspicious":
            message = "This URL does not appear suspicious."
        elif classification == "suspicious":
            message = "This URL has some suspicious characteristics."
        else:
            message = "This URL exhibits multiple suspicious indicators."

        return CheckUrlResponse(
            url=data.url,
            domain=domain,
            classification=classification,
            confidence=confidence,
            reasons=flags,
            details={
                "domain": domain,
                "tld": tld,
                "is_standard_tld": tld in ["com", "org", "net", "edu", "gov"],
                "is_high_risk_tld": tld in StaticURLAnalyzer.SUSPICIOUS_TLDS,
                "risk_score": score,
            },
            can_submit=can_submit,
            message=message,
        )

    except Exception as e:
        import traceback
        print(f"Error during URL check: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"URL check failed: {str(e)}",
        )


@router.get("/submission/{submission_id}", response_model=PublicSubmitResponse)
async def get_public_submission_status(
    submission_id: UUID,
) -> PublicSubmitResponse:
    """Get the status of a public submission.

    Allows anyone with a submission ID to check its status.

    Args:
        submission_id: UUID of the submission

    Returns:
        PublicSubmitResponse with current status
    """
    try:
        async with get_db_context() as db:
            submission = await db.get(PublicSubmission, str(submission_id))

            if not submission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Submission not found",
                )

            # Generate appropriate message based on status
            status_messages = {
                "pending": "Your submission is pending review.",
                "approved": "Your submission has been approved and a case has been created.",
                "rejected": "Your submission has been reviewed and rejected.",
            }

            message = status_messages.get(submission.status, "Status unknown.")

            return PublicSubmitResponse(
                id=str(submission.id),
                url=submission.url,
                status=submission.status,
                created_at=submission.submitted_at,
                message=message,
            )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error getting submission status: {e}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get submission status: {str(e)}",
        )


# ==================== Helper Functions ====================


def _get_client_ip(request: Request) -> str:
    """Extract client IP address from request.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string
    """
    # Check for forwarded headers (reverse proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"


__all__ = ["router"]
