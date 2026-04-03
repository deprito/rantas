# Dockerfile for PhishTrack Backend
# syntax=docker/dockerfile:1.4

FROM python:3.11-slim-bookworm AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies in a separate layer (cached unless base image changes)
FROM base AS deps
RUN for i in 1 2 3; do \
    apt-get update && \
    apt-get install -y --no-install-recommends gcc whois && \
    rm -rf /var/lib/apt/lists/* && exit 0; \
    echo "Retrying... ($i/3)"; \
    sleep 5; \
    done

# Install Python dependencies with pip cache
FROM deps AS python-deps
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Final stage - start from base (without gcc) to minimize size
FROM base AS runner
WORKDIR /app

# Install runtime dependencies only (whois binary needed for OSINT)
RUN apt-get update && \
    apt-get install -y --no-install-recommends whois && \
    rm -rf /var/lib/apt/lists/*

# Copy shared libraries from deps (needed for Python C extensions)
COPY --from=deps /usr/lib /usr/lib
COPY --from=deps /usr/local/lib /usr/local/lib

# Copy Python packages from python-deps
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Copy application code (changes most frequently - last layer)
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/xarf_reports && \
    chown -R appuser:appuser /app/xarf_reports
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)" || exit 1

# Set entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
