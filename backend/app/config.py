"""Configuration settings for PhishTrack backend."""
import os
import json
from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Application
    APP_NAME: str = "RANTAS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://phishtrack:phishtrack@db:5432/phishtrack"
    DATABASE_ECHO: bool = False

    # Redis (for Celery broker and result backend)
    REDIS_URL: str = "redis://redis:6379/0"

    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 30 * 60  # 30 minutes

    # Monitoring intervals (in seconds)
    MONITOR_INTERVAL_DEFAULT: int = 6 * 60 * 60  # 6 hours
    MONITOR_INTERVAL_MIN: int = 30 * 60  # 30 minutes
    MONITOR_INTERVAL_MAX: int = 24 * 60 * 60  # 24 hours

    # HTTP Client
    HTTP_TIMEOUT: int = 10  # seconds
    HTTP_USER_AGENT: str = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    HTTP_MAX_REDIRECTS: int = 5

    # Email / SMTP
    SMTP_ENABLED: bool = False
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "abuse@phishtrack.local")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "PhishTrack Abuse Reporting")
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT: int = 30

    # Microsoft Graph API (alternative to SMTP)
    GRAPH_ENABLED: bool = os.getenv("GRAPH_ENABLED", "true").lower() == "true"
    GRAPH_TENANT_ID: str = os.getenv("GRAPH_TENANT_ID", "")
    GRAPH_CLIENT_ID: str = os.getenv("GRAPH_CLIENT_ID", "")
    GRAPH_CLIENT_SECRET: str = os.getenv("GRAPH_CLIENT_SECRET", "")
    GRAPH_FROM_EMAIL: str = os.getenv("GRAPH_FROM_EMAIL", SMTP_FROM_EMAIL)

    # Email webhook
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "change-this-secret-in-production")

    # CORS - parse from environment variable
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://frontend:3000",
        "http://127.0.0.1:3000",
    ]

    # Brand impacted - list of brands for dropdown in reports
    BRAND_IMPACTED: List[str] = [
        "Example Corp",
        "Test Corp",
        "Corporate Website",
        "Subsidiary",
        "Others",
    ]

    @field_validator('CORS_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # Fallback: split by comma
                return [origin.strip() for origin in v.split(',')]
        return v

    @field_validator('BRAND_IMPACTED', mode='before')
    @classmethod
    def parse_brand_impacted(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # Fallback: split by comma
                return [brand.strip() for brand in v.split(',')]
        return v

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-this-secret-key-in-production-use-openssl-rand-hex-32")
    SESSION_TIMEOUT_MINUTES: int = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

    @field_validator('SESSION_TIMEOUT_MINUTES')
    @classmethod
    def validate_session_timeout(cls, v):
        if v < 5:
            raise ValueError('SESSION_TIMEOUT_MINUTES must be at least 5 minutes')
        if v > 1440:
            raise ValueError('SESSION_TIMEOUT_MINUTES must be at most 1440 minutes (24 hours)')
        return v

    # Case defaults
    DEFAULT_MONITOR_INTERVAL: int = 6 * 60 * 60  # 6 hours in seconds

    # Evidence Storage
    EVIDENCE_STORAGE_PATH: str = "./evidence"

    # Timezone
    TIMEZONE: str = "Asia/Jakarta"

    # Browserless Screenshot Service
    BROWSERLESS_API_KEY: str = ""
    BROWSERLESS_ENDPOINT: str = "https://connected.browserless.io"
    BROWSERLESS_VIEWPORT_WIDTH: int = 1440  # MacBook standard
    BROWSERLESS_VIEWPORT_HEIGHT: int = 900  # MacBook standard
    BROWSERLESS_FULL_PAGE: bool = True
    BROWSERLESS_VERIFY_SSL: bool = os.getenv("BROWSERLESS_VERIFY_SSL", "true").lower() == "true"

    # XARF (eXtended Abuse Reporting Format) Configuration
    XARF_REPORTER_ORG: str = os.getenv("XARF_REPORTER_ORG", "PhishTrack")
    XARF_REPORTER_CONTACT: str = os.getenv("XARF_REPORTER_CONTACT", "abuse@yourdomain.com")
    XARF_REPORTER_DOMAIN: str = os.getenv("XARF_REPORTER_DOMAIN", "yourdomain.com")
    XARF_STORAGE_PATH: str = os.getenv("XARF_STORAGE_PATH", "./xarf_reports")

    # Microsoft Teams Webhook (for case resolution notifications)
    TEAMS_WEBHOOK_URL: str = os.getenv("TEAMS_WEBHOOK_URL", "")

    # Base URL (for generating download links)
    BASE_URL: str = os.getenv("BASE_URL", "http://localhost:8000")

    # Hunting (CertStream) Configuration
    HUNTING_MIN_SCORE: int = int(os.getenv("HUNTING_MIN_SCORE", "50"))  # Minimum score to store
    HUNTING_ALERT_SCORE: int = int(os.getenv("HUNTING_ALERT_SCORE", "80"))  # Minimum score for Teams alert
    HUNTING_RETENTION_DAYS: int = int(os.getenv("HUNTING_RETENTION_DAYS", "90"))  # Days to keep detections
    RAW_LOG_RETENTION_DAYS: int = int(os.getenv("RAW_LOG_RETENTION_DAYS", "3"))  # Days to keep raw CT log entries in Redis

    # CT Log / Sunlight Configuration (secondary data source for hunting)
    # Enable fetching from public CT logs as secondary data source
    SUNLIGHT_ENABLED: bool = os.getenv("SUNLIGHT_ENABLED", "true").lower() == "true"
    # Number of entries to fetch per CT log scan
    SUNLIGHT_ENTRIES_PER_LOG: int = int(os.getenv("SUNLIGHT_ENTRIES_PER_LOG", "50"))
    # Public CT log endpoints (comma-separated URLs)
    # These are used as fallback/secondary source when certpatrol is unavailable
    SUNLIGHT_PUBLIC_LOGS: List[str] = [
        "https://ct.googleapis.com/logs/us1/argon2026h1/",
        "https://ct.googleapis.com/logs/us1/argon2026h2/",
        "https://ct.cloudflare.com/logs/nimbus2026/",
        "https://wyvern.ct.digicert.com/2026h1/",
        "https://sphinx.ct.digicert.com/2026h1/",
    ]
    # Override with env var if provided
    _sunlight_logs_override = os.getenv("SUNLIGHT_PUBLIC_LOGS", "")
    if _sunlight_logs_override:
        SUNLIGHT_PUBLIC_LOGS = [log.strip() for log in _sunlight_logs_override.split(",") if log.strip()]

    # Redis host/port for direct access (used by services)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # Ollama AI Configuration
    OLLAMA_ENABLED: bool = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/api")
    OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY", "")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "60"))

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
