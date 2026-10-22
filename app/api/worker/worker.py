
import time
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Jobs, JobRuns, JobAttempts
from app.api.domain.run_status import JobRunStatus
from app.api.domain.attempt_status import AttemptStatus
from app.api.executors.executor import execute_job

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3

def process_one_run(db: Session) -> bool:
    """Process one queued run, retrying failures up to MAX_ATTEMPTS."""

    run = (
        db.query(JobRuns)
        .filter(JobRuns.status == JobRunStatus.QUEUED)
        .order_by(JobRuns.created_at.asc(), JobRuns.id.asc())
        .first()
    )

    if run is None:
        return False

    attempt = (
        db.query(JobAttempts)
        .filter(
            JobAttempts.run_id == run.id,
            JobAttempts.status == AttemptStatus.QUEUED,
        )
        .order_by(JobAttempts.attempt_number.asc())
        .first()
    )

    if attempt is None:
        logger.error("Queued JobRun %s has no queued attempt", run.id)
        return False

    job = db.query(Jobs).filter(Jobs.id == run.job_id).first()

    if job is None:
        logger.error("Job %s does not exist", run.job_id)
        return False

    # Mark the current attempt as running.
    now = datetime.now(timezone.utc)
    run.status = JobRunStatus.RUNNING

    if run.started_at is None:
        run.started_at = now

    attempt.status = AttemptStatus.RUNNING
    attempt.started_at = now

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info(
        "Running JobRun %s, attempt %s/%s",
        run.id,
        attempt.attempt_number,
        MAX_ATTEMPTS,
    )

    try:
        result = execute_job(job)

    except Exception as exc:
        finished_at = datetime.now(timezone.utc)

        attempt.status = AttemptStatus.FAILED
        attempt.error = str(exc)
        attempt.finished_at = finished_at

        if attempt.attempt_number < MAX_ATTEMPTS:
            # Schedule another attempt for the SAME run.
            next_attempt = JobAttempts(
                run_id=run.id,
                attempt_number=attempt.attempt_number + 1,
                status=AttemptStatus.QUEUED,
            )

            db.add(next_attempt)

            # The run is eligible for processing again.
            run.status = JobRunStatus.QUEUED
            run.finished_at = None

            logger.warning(
                "Attempt %s failed for JobRun %s. "
                "Queueing attempt %s/%s. Error: %s",
                attempt.attempt_number,
                run.id,
                next_attempt.attempt_number,
                MAX_ATTEMPTS,
                exc,
            )
        
        else:
            # No attempts remain.
            run.status = JobRunStatus.FAILED
            run.finished_at = finished_at

            logger.error(
                "JobRun %s failed after %s attempts",
                run.id,
                MAX_ATTEMPTS,
            )

    else:
        # Execution succeeded.
        finished_at = datetime.now(timezone.utc)

        attempt.status = AttemptStatus.SUCCESS
        attempt.finished_at = finished_at

        run.status = JobRunStatus.SUCCESS
        run.finished_at = finished_at

        logger.info(
            "JobRun %s succeeded on attempt %s: %s",
            run.id,
            attempt.attempt_number,
            result,
        )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return True


def main() -> None:
    """Continuously poll for queued runs."""

    logger.info("RunForge worker started")

    while True:
        db = SessionLocal()

        try:
            processed = process_one_run(db)
        except Exception:
            logger.exception("Worker encountered an error")
            processed = False
        finally:
            db.close()

        if not processed:
            time.sleep(3)


if __name__ == "__main__":
    main()
