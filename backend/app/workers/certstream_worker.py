"""Celery worker for running the hunting monitor as a Celery task.

This module provides a Celery task that runs the CT Log monitor
in the background, continuously processing Certificate Transparency logs
to detect typosquat domains.
"""
import asyncio
import logging
import threading

from celery import shared_task, signals

from app.database import async_session_factory
from app.models import HuntingConfig
from app.services.ct_log_monitor import CTLogMonitor
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Global flag to check if we should be running
_SHOULD_RUN = True

# Thread storage for running monitor
_monitor_thread = None
_stop_event = threading.Event()


async def _get_hunting_config_from_db() -> dict:
    """Load hunting configuration from database.

    Returns:
        dict with keys: min_score_threshold, alert_threshold, monitored_brands,
                       custom_brand_patterns, custom_brand_regex_patterns
    """
    async with async_session_factory() as db:
        result = await db.execute(select(HuntingConfig))
        config = result.scalar_one_or_none()

        if config:
            return {
                "min_score_threshold": config.min_score_threshold,
                "alert_threshold": config.alert_threshold,
                "monitored_brands": config.monitored_brands or [],
                "custom_brand_patterns": config.custom_brand_patterns or {},
                "custom_brand_regex_patterns": config.custom_brand_regex_patterns or {},
            }

        # Return defaults if no config in database
        return {
            "min_score_threshold": 50,
            "alert_threshold": 80,
            "monitored_brands": ["example", "testcorp"],
            "custom_brand_patterns": {},
            "custom_brand_regex_patterns": {},
        }


@signals.worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Worker ready callback - auto-start monitor after a delay."""
    logger.info("CT Log worker ready")

    # Auto-start monitor after a delay (worker needs to be fully ready first)
    try:
        import threading
        import time

        def _delayed_start():
            time.sleep(5)  # Wait for worker to be fully ready
            try:
                logger.info("Auto-starting CT Log monitor...")
                from celery import current_app
                # Just send the task - monitor checks enabled status internally
                current_app.send_task("ctlog.run_monitor", queue="phishtrack.hunting")
                logger.info("CT Log monitor start task sent")
            except Exception as e:
                logger.error(f"Error auto-starting monitor: {e}", exc_info=True)

        # Start in a background thread
        threading.Thread(target=_delayed_start, daemon=True).start()
    except Exception as e:
        logger.error(f"Error setting up auto-start: {e}")


def _run_monitor_in_thread():
    """Run the monitor in a dedicated thread with its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    monitor = None

    async def _run():
        nonlocal monitor

        # Load config from database
        config = await _get_hunting_config_from_db()

        try:
            monitor = CTLogMonitor(
                min_score_threshold=config["min_score_threshold"],
                alert_threshold=config["alert_threshold"],
                monitored_brands=config["monitored_brands"],
                custom_brand_patterns=config["custom_brand_patterns"],
                custom_brand_regex_patterns=config["custom_brand_regex_patterns"],
            )
            logger.info(
                f"CT Log monitor started with {len(config.get('custom_brand_regex_patterns', {}))} "
                f"regex pattern brands"
            )
            await monitor.monitor()
        except asyncio.CancelledError:
            logger.info("CT Log monitor cancelled")
        except Exception as e:
            logger.error(f"CT Log monitor error: {e}", exc_info=True)
        finally:
            if monitor:
                await monitor.stop()
            logger.info("CT Log monitor ended")

    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


@shared_task(
    name="ctlog.run_monitor",
    bind=True,
    max_retries=0,
    autoretry_for=(),
    queue="phishtrack.hunting",
)
def run_ct_log_monitor_task(self) -> dict:
    """Run the CT Log monitor as a Celery task in continuous mode."""
    logger.info("Starting CT Log monitor task (continuous mode)...")

    global _monitor_thread, _stop_event

    # Check if already running
    if _monitor_thread and _monitor_thread.is_alive():
        logger.info("CT Log monitor is already running")
        return {"status": "already_running"}

    _stop_event.clear()

    # Start monitor in a daemon thread (config loaded from DB inside thread)
    _monitor_thread = threading.Thread(
        target=_run_monitor_in_thread,
        daemon=True,
    )
    _monitor_thread.start()

    return {"status": "started", "message": "CT Log monitor started in background thread"}


@shared_task(
    name="ctlog.health_check",
    bind=True,
    queue="phishtrack.hunting",
)
def ctlog_health_check() -> dict:
    """Health check for the CT Log monitor."""
    is_running = _monitor_thread and _monitor_thread.is_alive()
    return {
        "status": "running" if is_running else "stopped",
        "message": "CT Log monitor health check",
    }


__all__ = [
    "run_ct_log_monitor_task",
    "ctlog_health_check",
]
