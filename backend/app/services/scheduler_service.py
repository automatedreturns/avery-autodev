"""Background scheduler for periodic tasks."""

import asyncio
import logging
import threading
from datetime import datetime

from app.database import SessionLocal
from app.services.issue_poller_service import poll_all_workspaces

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    """Background scheduler for running periodic tasks."""

    def __init__(self, poll_interval_minutes: int = 5):
        """
        Initialize the background scheduler.

        Args:
            poll_interval_minutes: How often to poll for new issues (default: 5 minutes)
        """
        self.poll_interval_minutes = poll_interval_minutes
        self.poll_interval_seconds = poll_interval_minutes * 60
        self.running = False
        self.thread = None

    def _poll_issues_task(self):
        """Background task to poll for new issues."""
        while self.running:
            try:
                logger.info("Starting issue polling task...")

                # Create database session
                db = SessionLocal()

                try:
                    # Poll all workspaces
                    result = poll_all_workspaces(db)

                    if result["success"]:
                        logger.info(
                            f"Issue polling complete: "
                            f"{result['workspaces_polled']} workspaces polled, "
                            f"{result['total_issues_linked']} issues auto-linked"
                        )

                        if result["errors"]:
                            logger.warning(f"Polling errors: {result['errors']}")
                    else:
                        logger.error(f"Issue polling failed: {result['errors']}")

                finally:
                    db.close()

            except Exception as e:
                logger.error(f"Error in polling task: {str(e)}")

            # Wait for next poll interval
            if self.running:
                logger.info(f"Next poll in {self.poll_interval_minutes} minutes")
                for _ in range(self.poll_interval_seconds):
                    if not self.running:
                        break
                    threading.Event().wait(1)

    def start(self):
        """Start the background scheduler."""
        if self.running:
            logger.warning("Scheduler is already running")
            return

        logger.info(
            f"Starting background scheduler (poll interval: {self.poll_interval_minutes} minutes)"
        )
        self.running = True
        self.thread = threading.Thread(target=self._poll_issues_task, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the background scheduler."""
        if not self.running:
            logger.warning("Scheduler is not running")
            return

        logger.info("Stopping background scheduler...")
        self.running = False

        if self.thread:
            self.thread.join(timeout=5)

        logger.info("Background scheduler stopped")


# Global scheduler instance
_scheduler = None


def get_scheduler(poll_interval_minutes: int = 5) -> BackgroundScheduler:
    """
    Get the global scheduler instance.

    Args:
        poll_interval_minutes: Poll interval in minutes (only used on first call)

    Returns:
        BackgroundScheduler instance
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(poll_interval_minutes)
    return _scheduler


def start_scheduler(poll_interval_minutes: int = 5):
    """Start the global background scheduler."""
    scheduler = get_scheduler(poll_interval_minutes)
    scheduler.start()


def stop_scheduler():
    """Stop the global background scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
