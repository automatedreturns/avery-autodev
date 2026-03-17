"""Celery application configuration for asynchronous task processing."""

from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
from app.core.config import settings

# Initialize Celery application
celery_app = Celery(
    "avery_agent",
    broker=getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=getattr(settings, "CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task tracking
    task_track_started=True,
    task_send_sent_event=True,

    # Time limits
    task_time_limit=7200,  # 2 hours hard limit
    task_soft_time_limit=6600,  # 1 hour 50 minutes soft limit

    # Worker configuration
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
    worker_disable_rate_limits=False,

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store additional task metadata

    # Task routing
    task_routes={
        "agent_tasks.*": {"queue": "agent_processing"},
        "github_tasks.*": {"queue": "github_operations"},
    },

    # Retry configuration
    task_acks_late=True,  # Acknowledge tasks after completion
    task_reject_on_worker_lost=True,  # Requeue tasks if worker crashes

    # Logging
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)

# Autodiscover tasks from the tasks module
celery_app.autodiscover_tasks(["app.tasks"])


# Signal handlers for better observability
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra_kwargs):
    """Handler called before task execution."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Starting task: {task.name}[{task_id}]")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extra_kwargs):
    """Handler called after task execution."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Completed task: {task.name}[{task_id}] - State: {state}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **extra_kwargs):
    """Handler called when task fails."""
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Task failed: {sender.name}[{task_id}] - Exception: {exception}", exc_info=einfo)
