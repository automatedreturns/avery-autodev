"""Celery tasks for test generation processing."""

import logging
import traceback
from datetime import datetime

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


class TestGenerationTask(Task):
    """
    Custom Celery task class for test generation with retry logic.

    Features:
    - Automatic retries on failure with exponential backoff
    - Jitter to prevent thundering herd
    - Better error tracking and logging
    """
    autoretry_for = (Exception,)
    retry_kwargs = {
        'max_retries': 2,
        'countdown': 120,  # Wait 2 minutes before first retry
    }
    retry_backoff = True  # Exponential backoff
    retry_backoff_max = 600  # Max 10 minutes between retries
    retry_jitter = True
    acks_late = True
    reject_on_worker_lost = True
    soft_time_limit = 1800  # 30 minutes soft limit
    time_limit = 2100  # 35 minutes hard limit


@celery_app.task(
    base=TestGenerationTask,
    bind=True,
    name="test_generation_tasks.process_test_generation_job"
)
def process_test_generation_job_task(
    self,
    job_id: int,
    workspace_id: int,
    github_token: str,
):
    """
    Celery task for processing an AgentTestGeneration job.

    This task:
    1. Loads the AgentTestGeneration job from database
    2. Processes it using ClaudeSDKClient
    3. Updates job status based on success/failure
    4. Provides retry logic on failure

    Args:
        self: Celery task instance (provided by bind=True)
        job_id: AgentTestGeneration job ID
        workspace_id: Workspace ID
        github_token: GitHub token for git operations
    """
    from app.database import SessionLocal
    from app.models.agent_test_generation import AgentTestGeneration, TestGenerationStatus
    from app.models.workspace import Workspace
    from app.services.test_code_generator_service import (
        process_agent_test_generation,
        TestCodeGeneratorError,
    )

    db = SessionLocal()

    try:
        # Load the job
        job = db.query(AgentTestGeneration).filter(
            AgentTestGeneration.id == job_id
        ).first()

        if not job:
            logger.error(f"Test generation job {job_id} not found")
            return {
                "success": False,
                "error": f"Job {job_id} not found",
            }

        # Load workspace
        workspace = db.query(Workspace).filter(
            Workspace.id == workspace_id
        ).first()

        if not workspace:
            logger.error(f"Workspace {workspace_id} not found for job {job_id}")
            job.status = TestGenerationStatus.FAILED.value
            job.error_message = f"Workspace {workspace_id} not found"
            job.completed_at = datetime.utcnow()
            db.commit()
            return {
                "success": False,
                "error": f"Workspace {workspace_id} not found",
            }

        # Update retry count
        job.retry_count = self.request.retries
        db.commit()

        logger.info(
            f"Starting test generation: job={job_id}, workspace={workspace_id}, "
            f"celery_task={self.request.id}, retry={self.request.retries}"
        )

        # Process the job
        result = process_agent_test_generation(
            job=job,
            workspace=workspace,
            github_token=github_token,
            db=db,
        )

        logger.info(
            f"Completed test generation: job={job_id}, "
            f"tests={result.get('tests_generated_count', 0)}, "
            f"files={len(result.get('generated_files', []))}"
        )

        return {
            "success": True,
            "job_id": job_id,
            "workspace_id": workspace_id,
            **result,
        }

    except SoftTimeLimitExceeded:
        error_msg = "Test generation exceeded time limit"
        logger.warning(
            f"{error_msg}: job={job_id}, workspace={workspace_id}, "
            f"celery_task={self.request.id}"
        )

        db = SessionLocal()
        job = db.query(AgentTestGeneration).filter(
            AgentTestGeneration.id == job_id
        ).first()

        if job:
            job.status = TestGenerationStatus.FAILED.value
            job.error_message = error_msg
            job.completed_at = datetime.utcnow()
            db.commit()

        db.close()
        raise  # Re-raise to trigger retry

    except TestCodeGeneratorError as e:
        logger.error(
            f"Test generation failed: job={job_id}, error={str(e)}"
        )
        # Job status already updated in process_agent_test_generation
        raise  # Re-raise to trigger retry

    except Exception as exc:
        error_msg = str(exc)
        error_trace = traceback.format_exc()

        logger.error(
            f"Test generation failed: job={job_id}, "
            f"workspace={workspace_id}, error={error_msg}",
            exc_info=True
        )

        db = SessionLocal()
        job = db.query(AgentTestGeneration).filter(
            AgentTestGeneration.id == job_id
        ).first()

        if job:
            if self.request.retries >= self.max_retries:
                job.status = TestGenerationStatus.FAILED.value
            else:
                job.status = "retrying"

            job.error_message = error_msg[:1000]
            job.retry_count = self.request.retries + 1
            db.commit()

        db.close()
        raise  # Re-raise to trigger retry

    finally:
        if db:
            db.close()


@celery_app.task(name="test_generation_tasks.process_pending_jobs")
def process_pending_test_generation_jobs_task(limit: int = 5):
    """
    Periodic task to process pending AgentTestGeneration jobs.

    This task finds pending jobs and queues them for processing.

    Args:
        limit: Maximum number of jobs to process in this batch
    """
    from app.database import SessionLocal
    from app.models.agent_test_generation import AgentTestGeneration, TestGenerationStatus
    from app.models.workspace import Workspace
    from app.models.workspace_member import WorkspaceMember
    from app.services.github_service import get_github_token_for_workspace

    db = SessionLocal()
    queued_count = 0

    try:
        # Find pending jobs
        pending_jobs = db.query(AgentTestGeneration).filter(
            AgentTestGeneration.status == TestGenerationStatus.PENDING.value
        ).order_by(
            AgentTestGeneration.created_at.asc()
        ).limit(limit).all()

        logger.info(f"Found {len(pending_jobs)} pending test generation jobs")

        for job in pending_jobs:
            try:
                # Get workspace
                workspace = db.query(Workspace).filter(
                    Workspace.id == job.workspace_id
                ).first()

                if not workspace:
                    logger.warning(f"Workspace not found for job {job.id}")
                    job.status = TestGenerationStatus.FAILED.value
                    job.error_message = "Workspace not found"
                    job.completed_at = datetime.utcnow()
                    db.commit()
                    continue

                # Get GitHub token (from workspace owner or first admin)
                github_token = get_github_token_for_workspace(workspace.id, db)

                if not github_token:
                    logger.warning(f"No GitHub token available for workspace {workspace.id}")
                    job.status = TestGenerationStatus.FAILED.value
                    job.error_message = "No GitHub token available"
                    job.completed_at = datetime.utcnow()
                    db.commit()
                    continue

                # Queue the job for processing
                process_test_generation_job_task.delay(
                    job_id=job.id,
                    workspace_id=workspace.id,
                    github_token=github_token,
                )

                # Mark as queued (in progress)
                job.status = TestGenerationStatus.IN_PROGRESS.value
                db.commit()

                queued_count += 1
                logger.info(f"Queued test generation job {job.id} for workspace {workspace.id}")

            except Exception as e:
                logger.error(f"Failed to queue job {job.id}: {e}")
                job.status = TestGenerationStatus.FAILED.value
                job.error_message = f"Failed to queue: {str(e)}"
                job.completed_at = datetime.utcnow()
                db.commit()

        return {
            "success": True,
            "pending_found": len(pending_jobs),
            "queued": queued_count,
        }

    except Exception as e:
        logger.error(f"Failed to process pending jobs: {e}")
        return {
            "success": False,
            "error": str(e),
        }

    finally:
        db.close()


@celery_app.task(name="test_generation_tasks.cleanup_old_jobs")
def cleanup_old_test_generation_jobs_task(days_old: int = 30):
    """
    Cleanup old completed/failed test generation jobs.

    Args:
        days_old: Remove jobs older than this many days
    """
    from datetime import timedelta
    from app.database import SessionLocal
    from app.models.agent_test_generation import AgentTestGeneration, TestGenerationStatus

    db = SessionLocal()

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        deleted_count = db.query(AgentTestGeneration).filter(
            AgentTestGeneration.status.in_([
                TestGenerationStatus.COMPLETED.value,
                TestGenerationStatus.FAILED.value
            ]),
            AgentTestGeneration.completed_at < cutoff_date
        ).delete(synchronize_session=False)

        db.commit()

        logger.info(f"Cleaned up {deleted_count} old test generation jobs older than {days_old} days")

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
