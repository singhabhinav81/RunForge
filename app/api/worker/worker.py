
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


def process_one_run(db: Session) -> bool:
    """Process one queued JobRun. Return False if none is available."""

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
        logger.error(
            "JobRun %s is queued but has no queued attempt",
            run.id,
        )
        return False

    job = db.query(Jobs).filter(Jobs.id == run.job_id).first()

    if job is None:
        logger.error("Job %s does not exist", run.job_id)
        return False

    # Mark both records as running before executing the workload.
    now = datetime.now(timezone.utc)
    run.status = JobRunStatus.RUNNING
    run.started_at = now
    attempt.status = AttemptStatus.RUNNING
    attempt.started_at = now

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    logger.info(
        "Started JobRun %s, attempt %s",
        run.id,
        attempt.attempt_number,
    )

    try:
        result = execute_job(job)

        run.status = JobRunStatus.SUCCESS
        attempt.status = AttemptStatus.SUCCESS

        logger.info(
            "JobRun %s completed: %s",
            run.id,
            result,
        )

    except Exception as exc:
        run.status = JobRunStatus.FAILED
        attempt.status = AttemptStatus.FAILED
        attempt.error = str(exc)

        logger.exception("JobRun %s failed", run.id)

    finally:
        finished_at = datetime.now(timezone.utc)
        run.finished_at = finished_at
        attempt.finished_at = finished_at

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
