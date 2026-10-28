
import sys
import time
import logging
from threading import Barrier, Thread

from app.db.database import SessionLocal
from app.db.models import JobRuns
from app.api.domain.run_status import JobRunStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reset_run(run_id: int) -> None:
    """Reset a disposable test run to QUEUED."""
    with SessionLocal() as db:
        run = db.query(JobRuns).filter(
            JobRuns.id == run_id
        ).first()

        if run is None:
            raise ValueError(f"JobRun {run_id} not found")

        run.status = JobRunStatus.QUEUED
        db.commit()


def unsafe_worker(
    worker_name: str,
    run_id: int,
    barrier: Barrier,
    claims: list[str],
) -> None:
    """Demonstrate the race condition without row locking."""
    with SessionLocal() as db:
        run = (
            db.query(JobRuns)
            .filter(
                JobRuns.id == run_id,
                JobRuns.status == JobRunStatus.QUEUED,
            )
            .first()
        )

        if run is None:
            logger.info("%s found no queued run", worker_name)
            barrier.wait()
            return

        logger.info("%s read run %s as QUEUED", worker_name, run_id)

        # Force both workers to read before either updates.
        barrier.wait()

        run.status = JobRunStatus.RUNNING
        db.commit()

        claims.append(worker_name)
        logger.info("%s claimed run %s", worker_name, run_id)


def safe_worker(
    worker_name: str,
    run_id: int,
    barrier: Barrier,
    claims: list[str],
) -> None:
    """Claim a run using PostgreSQL row locking."""
    with SessionLocal() as db:
        # Start both workers at approximately the same time.
        barrier.wait()

        run = (
            db.query(JobRuns)
            .filter(
                JobRuns.id == run_id,
                JobRuns.status == JobRunStatus.QUEUED,
            )
            .order_by(JobRuns.id.asc())
            .with_for_update(skip_locked=True)
            .first()
        )

        if run is None:
            logger.info(
                "%s skipped the locked run or found no queued run",
                worker_name,
            )
            return

        run.status = JobRunStatus.RUNNING

        # Hold the transaction briefly so the other worker
        # has an opportunity to encounter the locked row.
        time.sleep(1)

        db.commit()

        claims.append(worker_name)
        logger.info("%s claimed run %s", worker_name, run_id)


def run_experiment(run_id: int, safe: bool) -> int:
    """Run two competing workers and return the claim count."""
    reset_run(run_id)

    claims: list[str] = []
    barrier = Barrier(2)

    worker_function = safe_worker if safe else unsafe_worker

    workers = [
        Thread(
            target=worker_function,
            args=(f"Worker-{i}", run_id, barrier, claims),
        )
        for i in (1, 2)
    ]

    for worker in workers:
        worker.start()

    for worker in workers:
        worker.join()

    return len(claims)


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage: python -m scripts.test_worker_concurrency <run_id>"
        )
        sys.exit(1)

    run_id = int(sys.argv[1])

    # run_id = 10
    # Confirm this is a disposable, queued test run.
    with SessionLocal() as db:
        run = db.query(JobRuns).filter(
            JobRuns.id == run_id
        ).first()

        if run is None:
            raise ValueError(f"JobRun {run_id} not found")

        if run.status != JobRunStatus.QUEUED:
            raise ValueError(
                "Use a disposable JobRun whose status is QUEUED"
            )

    try:
        print("\n=== UNSAFE: No row locking ===")
        unsafe_claims = run_experiment(run_id, safe=False)
        print(f"Number of claims: {unsafe_claims}")

        print("\n=== SAFE: FOR UPDATE SKIP LOCKED ===")
        safe_claims = run_experiment(run_id, safe=True)
        print(f"Number of claims: {safe_claims}")

        print("\n=== RESULTS ===")
        print(f"Unsafe claims: {unsafe_claims}")
        print(f"Safe claims:   {safe_claims}")

        if unsafe_claims == 2 and safe_claims == 1:
            print("SUCCESS: The race condition was reproduced and prevented.")
        else:
            print(
                "Unexpected result. Inspect the logs and ensure "
                "PostgreSQL is being used."
            )

    finally:
        # Restore the test run so it can be inspected or reused.
        reset_run(run_id)


if __name__ == "__main__":
    main()
