"""Celery tasks for report generation (PDF exports, etc.)."""
from app.services.pdf_generator import generate_stats_pdf_task

__all__ = ["generate_stats_pdf_task"]
