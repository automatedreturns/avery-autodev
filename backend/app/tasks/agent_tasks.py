"""Celery tasks for agent processing."""

import logging
import traceback
from datetime import datetime
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


class AgentProcessingTask(Task):
    """
    Custom Celery task class with automatic retry logic and error handling.

    This class provides:
    - Automatic retries on failure with exponential backoff
    - Jitter to prevent thundering herd
    - Better error tracking and logging
    """
    autoretry_for = (Exception,)
    retry_kwargs = {
        'max_retries': 3,
        'countdown': 60,  # Wait 60 seconds before first retry
    }
    retry_backoff = True  # Exponential backoff (60s, 120s, 240s)
    retry_backoff_max = 600  # Max 10 minutes between retries
    retry_jitter = True  # Add random jitter to prevent thundering herd
    acks_late = True  # Only acknowledge task after it completes
    reject_on_worker_lost = True  # Requeue if worker crashes


@celery_app.task(base=AgentProcessingTask, bind=True, name="agent_tasks.process_agent_response")
def process_agent_response_task(
    self,
    workspace_id: int,
    task_id: int,
    user_message_id: int,
    token: str,
):
    """
    Celery task wrapper for agent response processing.

    This task:
    1. Creates an AgentJob record for tracking
    2. Delegates to the original _process_agent_response_async function
    3. Updates job status based on success/failure
    4. Provides retry logic on failure

    Args:
        self: Celery task instance (provided by bind=True)
        workspace_id: Workspace ID
        task_id: Workspace task ID
        user_message_id: User message ID that triggered this processing
        token: GitHub token for API operations
    """
    import asyncio
    from app.database import SessionLocal
    from app.models.agent_job import AgentJob
    from app.models.workspace_task import WorkspaceTask
    from app.api.v1.agent_chat import _process_agent_response_async

    db = SessionLocal()
    job = None

    try:
        # Create or get existing job record
        job = db.query(AgentJob).filter(
            AgentJob.celery_task_id == self.request.id
        ).first()

        if not job:
            job = AgentJob(
                celery_task_id=self.request.id,
                workspace_id=workspace_id,
                task_id=task_id,
                user_message_id=user_message_id,
                status="pending",
                retry_count=self.request.retries,
            )
            db.add(job)
            db.commit()
            db.refresh(job)

        # Update status to running
        job.update_status("running")
        db.commit()

        # Update workspace task status
        workspace_task = db.query(WorkspaceTask).filter(
            WorkspaceTask.id == task_id
        ).first()
        if workspace_task:
            workspace_task.agent_status = "running"
            workspace_task.agent_executed_at = datetime.utcnow()
            db.commit()

        logger.info(
            f"Starting agent processing: workspace={workspace_id}, "
            f"task={task_id}, celery_task={self.request.id}, "
            f"retry={self.request.retries}"
        )

        # Close the DB session before long-running operation
        db.close()

        # Execute the actual agent processing
        # This function handles its own DB sessions
        asyncio.run(_process_agent_response_async(
            workspace_id,
            task_id,
            user_message_id,
            token
        ))

        # Reopen DB session for final updates
        db = SessionLocal()
        job = db.query(AgentJob).filter(
            AgentJob.celery_task_id == self.request.id
        ).first()

        if job:
            job.update_status("completed")
            db.commit()

        # Update workspace task status
        workspace_task = db.query(WorkspaceTask).filter(
            WorkspaceTask.id == task_id
        ).first()
        if workspace_task:
            workspace_task.agent_status = "completed"
            db.commit()

        logger.info(
            f"Completed agent processing: workspace={workspace_id}, "
            f"task={task_id}, celery_task={self.request.id}"
        )

        return {
            "success": True,
            "workspace_id": workspace_id,
            "task_id": task_id,
            "job_id": job.id if job else None,
        }

    except SoftTimeLimitExceeded:
        # Handle soft time limit (task took too long)
        error_msg = "Agent processing exceeded time limit"
        logger.warning(
            f"{error_msg}: workspace={workspace_id}, task={task_id}, "
            f"celery_task={self.request.id}"
        )

        db = SessionLocal()
        job = db.query(AgentJob).filter(
            AgentJob.celery_task_id == self.request.id
        ).first()

        if job:
            job.update_status(
                "failed",
                error_message=error_msg,
                error_traceback="Soft time limit exceeded"
            )
            db.commit()

        workspace_task = db.query(WorkspaceTask).filter(
            WorkspaceTask.id == task_id
        ).first()
        if workspace_task:
            workspace_task.agent_status = "failed"
            workspace_task.agent_error = error_msg
            db.commit()

        db.close()
        raise  # Re-raise to trigger retry

    except Exception as exc:
        # Handle any other errors
        error_msg = str(exc)
        error_trace = traceback.format_exc()

        logger.error(
            f"Agent processing failed: workspace={workspace_id}, "
            f"task={task_id}, celery_task={self.request.id}, "
            f"error={error_msg}",
            exc_info=True
        )

        db = SessionLocal()
        job = db.query(AgentJob).filter(
            AgentJob.celery_task_id == self.request.id
        ).first()

        if job:
            # Determine if we'll retry or give up
            if self.request.retries >= self.max_retries:
                status = "failed"
            else:
                status = "retrying"

            job.update_status(
                status,
                error_message=error_msg[:1000],  # Truncate to avoid DB issues
                error_traceback=error_trace[:5000]
            )
            job.retry_count = self.request.retries + 1
            db.commit()

        # Update workspace task on final failure
        if self.request.retries >= self.max_retries:
            workspace_task = db.query(WorkspaceTask).filter(
                WorkspaceTask.id == task_id
            ).first()
            if workspace_task:
                workspace_task.agent_status = "failed"
                workspace_task.agent_error = error_msg[:500]
                db.commit()

        db.close()
        raise  # Re-raise to trigger retry

    finally:
        if db:
            db.close()


@celery_app.task(name="agent_tasks.cleanup_old_jobs")
def cleanup_old_jobs_task(days_old: int = 7):
    """
    Cleanup old completed agent jobs from the database.

    Args:
        days_old: Remove jobs older than this many days
    """
    from app.database import SessionLocal
    from app.models.agent_job import AgentJob
    from datetime import timedelta

    db = SessionLocal()

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        deleted_count = db.query(AgentJob).filter(
            AgentJob.status.in_(["completed", "failed"]),
            AgentJob.completed_at < cutoff_date
        ).delete(synchronize_session=False)

        db.commit()

        logger.info(f"Cleaned up {deleted_count} old agent jobs older than {days_old} days")

        return {
            "success": True,
            "deleted_count": deleted_count,
        }

    except Exception as e:
        logger.error(f"Failed to cleanup old jobs: {str(e)}")
        db.rollback()
        raise

    finally:
        db.close()
