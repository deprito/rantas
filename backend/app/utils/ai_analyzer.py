"""AI-powered URL analyzer using Ollama for phishing detection.

Provides LLM-based content analysis including:
- Social engineering detection
- Brand impersonation analysis
- Psychological manipulation tactics
- Content-based threat assessment
"""
import asyncio
import httpx
import json
from typing import Optional, Tuple
from urllib.parse import urlparse

from app.config import settings


class AIPhishingAnalyzer:
    """AI-powered phishing analyzer using Ollama LLM."""

    # System prompt for phishing analysis
    SYSTEM_PROMPT = """You are a cybersecurity expert specializing in phishing detection. Analyze the provided webpage content and URL for signs of phishing, fraud, or malicious intent.

Your analysis should consider:
1. **Brand Impersonation**: Does the content mimic a legitimate company, bank, or service?
2. **Social Engineering**: Are there urgency tactics, threats, or too-good-to-be-true offers?
3. **Credential Harvesting**: Does the page ask for passwords, credit cards, or sensitive data?
4. **Suspicious Patterns**: Poor grammar, mismatched branding, fake security badges?
5. **URL Analysis**: Does the URL match the claimed brand or service?

Respond in JSON format with this exact structure:
{
    "is_phishing": boolean,
    "confidence": number (0-100),
    "risk_level": "safe" | "low" | "medium" | "high" | "critical",
    "threat_types": ["list", "of", "detected", "threats"],
    "analysis": "detailed explanation of findings",
    "recommendation": "clear recommendation for the user"
}

Be strict in your analysis - false negatives are more dangerous than false positives."""

    # User prompt template
    USER_PROMPT_TEMPLATE = """Analyze this URL and webpage content for phishing indicators:

**URL**: {url}

**Page Title**: {title}

**Meta Description**: {meta_description}

**Page Content** (text extracted):
{content}

**HTTP Headers**:
{headers}

Provide your security analysis in JSON format."""

    @classmethod
    async def analyze(
        cls,
        url: str,
        html_content: Optional[str] = None,
        timeout: int = None
    ) -> Tuple[int, list[str], dict]:
        """Perform AI-powered phishing analysis.

        Args:
            url: URL to analyze
            html_content: Optional pre-fetched HTML content
            timeout: Request timeout in seconds

        Returns:
            Tuple of (ai_risk_score, list_of_flags, ai_analysis_dict)
        """
        if not settings.OLLAMA_ENABLED:
            return 0, ["AI analysis disabled"], {}

        timeout = timeout or settings.OLLAMA_TIMEOUT

        try:
            # Fetch webpage content if not provided
            if not html_content:
                html_content = await cls._fetch_page_content(url, timeout)

            # Extract text content from HTML
            text_content = cls._extract_text_from_html(html_content)

            # Parse URL for context
            parsed = urlparse(url)

            # Build the prompt
            user_prompt = cls.USER_PROMPT_TEMPLATE.format(
                url=url,
                title=cls._extract_title(html_content),
                meta_description=cls._extract_meta_description(html_content),
                content=text_content[:3000],  # Limit content length
                headers=f"Host: {parsed.netloc}"
            )

            # Call Ollama API
            ai_response = await cls._call_ollama(user_prompt, timeout)

            # Parse AI response
            analysis = cls._parse_ai_response(ai_response)

            # Convert to risk score and flags
            score = analysis.get("confidence", 0) if analysis.get("is_phishing") else 0
            flags = analysis.get("threat_types", [])

            return min(score, 100), flags, analysis

        except Exception as e:
            import traceback
            print(f"AI analysis error: {e}")
            traceback.print_exc()
            return 0, ["AI analysis failed"], {}

    @classmethod
    async def _fetch_page_content(
        cls,
        url: str,
        timeout: int
    ) -> str:
        """Fetch webpage HTML content."""
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            verify=False,  # Allow invalid SSL for analysis
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    @classmethod
    def _extract_text_from_html(cls, html: str) -> str:
        """Extract readable text from HTML content."""
        import re
        from html import unescape

        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)

        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)

        # Decode HTML entities
        text = unescape(text)

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text

    @classmethod
    def _extract_title(cls, html: str) -> str:
        """Extract page title from HTML."""
        import re
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    @classmethod
    def _extract_meta_description(cls, html: str) -> str:
        """Extract meta description from HTML."""
        import re
        match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        return ""

    @classmethod
    async def _call_ollama(cls, user_prompt: str, timeout: int) -> str:
        """Call Ollama Cloud API for analysis.

        Uses the OpenAI-compatible /api/chat endpoint.
        """
        # Ollama Cloud API endpoint
        ollama_url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/chat"

        headers = {
            "Content-Type": "application/json",
        }
        if settings.OLLAMA_API_KEY:
            headers["Authorization"] = f"Bearer {settings.OLLAMA_API_KEY}"

        # Use Ollama chat format
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": cls.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            }
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                ollama_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            # Extract content from Ollama chat response
            return result.get("message", {}).get("content", "")

    @classmethod
    def _parse_ai_response(cls, ai_response: str) -> dict:
        """Parse JSON response from AI."""
        import re

        # Try to extract JSON from response
        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # Fallback: try to parse the entire response
        try:
            return json.loads(ai_response)
        except json.JSONDecodeError:
            # Return safe default
            return {
                "is_phishing": False,
                "confidence": 0,
                "risk_level": "safe",
                "threat_types": ["Failed to parse AI response"],
                "analysis": "AI analysis encountered an error parsing the response.",
                "recommendation": "Manual review recommended."
            }


async def ai_analyze_url(url: str, html_content: Optional[str] = None) -> Tuple[int, list[str], dict]:
    """Convenience function for AI-powered URL analysis.

    Args:
        url: URL to analyze
        html_content: Optional pre-fetched HTML content

    Returns:
        Tuple of (risk_score, flags, analysis_dict)
    """
    return await AIPhishingAnalyzer.analyze(url, html_content)


__all__ = [
    "AIPhishingAnalyzer",
    "ai_analyze_url",
]
