import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Jobs, JobRuns, JobAttempts
from app.api.domain.run_status import JobRunStatus
from app.api.domain.attempt_status import AttemptStatus
from app.api.executors.executor import execute_job


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
HEARTBEAT_INTERVAL_SECONDS = 15
LEASE_TIMEOUT_SECONDS = 60

# One stable identity per worker process.
WORKER_ID = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"

logger.info("RunForge worker started. Worker ID: %s", WORKER_ID)


def utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


def heartbeat_loop(run_id: int, stop_event: threading.Event, worker_id: str | None = None) -> None:
    """Refresh the run heartbeat while the executor is running."""
    wid = worker_id or WORKER_ID
    while not stop_event.wait(HEARTBEAT_INTERVAL_SECONDS):
        db = SessionLocal()

        try:
            run = (
                db.query(JobRuns)
                .filter(
                    JobRuns.id == run_id,
                    JobRuns.status == JobRunStatus.RUNNING,
                    JobRuns.worker_id == wid,
                )
                .with_for_update()
                .first()
            )

            if run is None:
                logger.warning(
                    "Heartbeat stopped: Run %s is no longer owned by worker %s",
                    run_id,
                    wid,
                )
                stop_event.set()
                return

            run.heartbeat_at = utc_now()
            db.commit()

            logger.debug("Heartbeat updated for JobRun %s", run_id)

        except Exception:
            db.rollback()
            logger.exception("Failed to update heartbeat for JobRun %s", run_id)
        finally:
            db.close()


def start_heartbeat(run_id: int, worker_id: str | None = None) -> tuple[threading.Event, threading.Thread]:
    """Start the background heartbeat thread for a running job."""
    stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        args=(run_id, stop_event, worker_id),
        daemon=True,
    )
    heartbeat_thread.start()
    return stop_event, heartbeat_thread



def recover_one_expired_run(db: Session) -> bool:
    """Recover one RUNNING job whose heartbeat lease has expired."""

    cutoff = utc_now() - timedelta(seconds=LEASE_TIMEOUT_SECONDS)

    run = (
        db.query(JobRuns)
        .filter(
            JobRuns.status == JobRunStatus.RUNNING,
            JobRuns.heartbeat_at.isnot(None),
            JobRuns.heartbeat_at < cutoff,
        )
        .order_by(JobRuns.heartbeat_at.asc(), JobRuns.id.asc())
        .with_for_update(skip_locked=True)
        .first()
    )

    if run is None:
        return False

    # Lock and find the currently running attempt.
    attempt = (
        db.query(JobAttempts)
        .filter(
            JobAttempts.run_id == run.id,
            JobAttempts.status == AttemptStatus.RUNNING,
        )
        .order_by(JobAttempts.attempt_number.desc())
        .with_for_update()
        .first()
    )

    now = utc_now()

    # Repair inconsistent state rather than leaving the run stuck forever.
    if attempt is None:
        logger.error(
            "Run %s has an expired lease but no RUNNING attempt",
            run.id,
        )
        run.status = JobRunStatus.FAILED
        run.finished_at = now
        run.worker_id = None
        run.heartbeat_at = None
        db.commit()
        return True

    run_id = run.id
    attempt_number = attempt.attempt_number

    attempt.status = AttemptStatus.FAILED
    attempt.error = (
        f"Worker lease expired after {LEASE_TIMEOUT_SECONDS} seconds. "
        "The worker did not report completion."
    )
    attempt.finished_at = now

    if attempt_number < MAX_ATTEMPTS:
        db.add(
            JobAttempts(
                run_id=run_id,
                attempt_number=attempt_number + 1,
                status=AttemptStatus.QUEUED,
            )
        )

        run.status = JobRunStatus.QUEUED
        run.finished_at = None

        logger.warning(
            "Recovered JobRun %s: attempt %s abandoned; "
            "queued attempt %s/%s",
            run_id,
            attempt_number,
            attempt_number + 1,
            MAX_ATTEMPTS,
        )
    else:
        run.status = JobRunStatus.FAILED
        run.finished_at = now

        logger.error(
            "JobRun %s failed: attempt %s exhausted the retry limit",
            run_id,
            attempt_number,
        )

    # Release the expired worker's lease.
    run.worker_id = None
    run.heartbeat_at = None

    # Commit run and attempt changes atomically.
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return True


def process_one_run(db: Session, worker_id: str | None = None) -> bool:
    """Claim and process one queued run, retrying failures up to MAX_ATTEMPTS."""
    wid = worker_id or WORKER_ID

    run = (
        db.query(JobRuns)
        .filter(JobRuns.status == JobRunStatus.QUEUED)
        .order_by(JobRuns.created_at.asc(), JobRuns.id.asc())
        .with_for_update(skip_locked=True)
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

    run_id = run.id
    attempt_id = attempt.id
    attempt_number = attempt.attempt_number
    now = utc_now()

    run.status = JobRunStatus.RUNNING
    run.worker_id = wid
    run.heartbeat_at = now

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
        "Worker %s claimed JobRun %s, attempt %s/%s",
        wid,
        run_id,
        attempt_number,
        MAX_ATTEMPTS,
    )

    # time.sleep(60)

    # Execute outside the claim transaction. Keep heartbeats in their
    # own sessions so they don't interfere with this session.
    stop_event, heartbeat_thread = start_heartbeat(run_id, wid)

    execution_error = None
    result = None

    try:
        result = execute_job(job)
    except Exception as exc:
        execution_error = exc
    finally:
        stop_event.set()
        heartbeat_thread.join()

    # Refresh ORM objects because heartbeat_loop uses a separate session.
    
    db.expire_all()

    # Lock the run row while validating ownership and finalizing it.
    run = (
        db.query(JobRuns)
        .filter(JobRuns.id == run_id)
        .with_for_update()
        .first()
    )

    attempt = (
        db.query(JobAttempts)
        .filter(JobAttempts.id == attempt_id)
        .with_for_update()
        .first()
    )

    if (
        run is None
        or attempt is None
        or run.status != JobRunStatus.RUNNING
        or run.worker_id != wid
        or attempt.status != AttemptStatus.RUNNING
    ):
        logger.warning(
            "Worker %s no longer owns JobRun %s, attempt %s. "
            "Skipping final status update.",
            wid,
            run_id,
            attempt_number,
        )
        db.rollback()
        return True

    finished_at = utc_now()

    if execution_error is not None:
        attempt.status = AttemptStatus.FAILED
        attempt.error = str(execution_error)
        attempt.finished_at = finished_at

        if attempt_number < MAX_ATTEMPTS:
            db.add(
                JobAttempts(
                    run_id=run_id,
                    attempt_number=attempt_number + 1,
                    status=AttemptStatus.QUEUED,
                )
            )
            run.status = JobRunStatus.QUEUED
            run.finished_at = None

            logger.warning(
                "Attempt %s failed for JobRun %s. Queuing attempt %s/%s. Error: %s",
                attempt_number,
                run_id,
                attempt_number + 1,
                MAX_ATTEMPTS,
                execution_error,
            )
        else:
            run.status = JobRunStatus.FAILED
            run.finished_at = finished_at

            logger.error(
                "JobRun %s failed after %s attempts",
                run_id,
                MAX_ATTEMPTS,
            )
    else:
        attempt.status = AttemptStatus.SUCCESS
        attempt.finished_at = finished_at

        run.status = JobRunStatus.SUCCESS
        run.finished_at = finished_at

        logger.info(
            "JobRun %s succeeded on attempt %s: %s",
            run_id,
            attempt_number,
            result,
        )

    # Clear the lease/ownership once this worker has finished.
    run.worker_id = None
    run.heartbeat_at = None

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return True


def main() -> None:
    """Continuously recover expired runs and process queued runs."""

    logger.info("RunForge worker started: %s", WORKER_ID)

    while True:
        db = SessionLocal()

        try:
            recovered = recover_one_expired_run(db)

            if recovered:
                continue

            processed = process_one_run(db)

        except Exception:
            db.rollback()
            logger.exception("Worker encountered an error")
            processed = False

        finally:
            db.close()

        if not processed:
            time.sleep(3)

if __name__ == "__main__":
    main()
