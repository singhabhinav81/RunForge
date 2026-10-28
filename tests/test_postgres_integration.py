
import os
import threading
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.domain.attempt_status import AttemptStatus
from app.api.domain.run_status import JobRunStatus
from app.api.worker import worker as worker_mod
from app.api.worker.worker import recover_one_expired_run, utc_now
from app.db.models import Team, Jobs, JobRuns, JobAttempts


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_POSTGRES_URL"),
    reason="TEST_POSTGRES_URL is not configured",
)


def _postgres_engine():
    """Create an engine used only by independently-connected test workers."""
    return create_engine(os.environ["TEST_POSTGRES_URL"])


def _seed_queued_runs(engine, count: int) -> tuple[int, int, list[int]]:
    """Commit data visible to all worker sessions and return cleanup ids."""
    suffix = uuid4().hex[:8]
    with Session(engine) as db:
        team = Team(name=f"PG Worker Team {suffix}")
        db.add(team)
        db.flush()

        job = Jobs(
            team_id=team.id,
            name=f"PG Worker Job {suffix}",
            executor_type="sample",
            image="alpine:latest",
        )
        db.add(job)
        db.flush()

        run_ids = []
        for _ in range(count):
            run = JobRuns(job_id=job.id, status=JobRunStatus.QUEUED)
            db.add(run)
            db.flush()
            db.add(
                JobAttempts(
                    run_id=run.id,
                    attempt_number=1,
                    status=AttemptStatus.QUEUED,
                )
            )
            run_ids.append(run.id)

        db.commit()
        return team.id, job.id, run_ids


def _cleanup_seeded_runs(engine, team_id: int, job_id: int, run_ids: list[int]) -> None:
    """Remove committed PostgreSQL fixture rows in foreign-key order."""
    with engine.begin() as connection:
        connection.execute(JobAttempts.__table__.delete().where(JobAttempts.run_id.in_(run_ids)))
        connection.execute(JobRuns.__table__.delete().where(JobRuns.id.in_(run_ids)))
        connection.execute(Jobs.__table__.delete().where(Jobs.id == job_id))
        connection.execute(Team.__table__.delete().where(Team.id == team_id))


def _no_op_heartbeat(*_args, **_kwargs):
    """Avoid background database activity while preserving worker lifecycle calls."""
    stop_event = threading.Event()
    thread = threading.Thread(target=lambda: None)
    thread.start()
    return stop_event, thread


def test_postgres_two_workers_claim_one_run_once():
    """Only one real worker can claim and finalize a single queued run."""
    engine = _postgres_engine()
    team_id, job_id, run_ids = _seed_queued_runs(engine, count=1)
    run_id = run_ids[0]

    start = threading.Barrier(2)
    executor_entered = threading.Event()
    competing_worker_finished = threading.Event()
    allow_completion = threading.Event()
    results: dict[str, bool] = {}
    errors: list[BaseException] = []
    results_lock = threading.Lock()

    def blocking_execute(_job):
        executor_entered.set()
        assert allow_completion.wait(timeout=10), "test did not release the claimed worker"
        return {"message": "completed by test worker"}

    def run_worker(worker_id: str) -> None:
        db = Session(engine)
        try:
            start.wait(timeout=10)
            result = worker_mod.process_one_run(db, worker_id=worker_id)
            with results_lock:
                results[worker_id] = result
            if not result:
                competing_worker_finished.set()
        except BaseException as exc:  # Surface thread failures in the test thread.
            with results_lock:
                errors.append(exc)
        finally:
            db.close()

    workers = [
        threading.Thread(target=run_worker, args=(f"pg-worker-{index}",))
        for index in range(2)
    ]

    try:
        # These module attributes are patched once for the whole test, before
        # either worker starts, so no thread sees a partially-applied patch.
        with patch.object(worker_mod, "start_heartbeat", side_effect=_no_op_heartbeat), patch.object(
            worker_mod, "execute_job", side_effect=blocking_execute
        ):
            for thread in workers:
                thread.start()

            assert executor_entered.wait(timeout=10), "no worker claimed the queued run"

            # The claimant stays RUNNING while its peer executes the actual
            # SKIP LOCKED query through process_one_run.
            assert competing_worker_finished.wait(timeout=10), (
                "the competing worker did not finish its claim attempt"
            )

            allow_completion.set()
            for thread in workers:
                thread.join(timeout=10)

        assert not errors
        assert sorted(results.values()) == [False, True]

        with Session(engine) as db:
            run = db.get(JobRuns, run_id)
            attempts = (
                db.query(JobAttempts)
                .filter(JobAttempts.run_id == run_id)
                .order_by(JobAttempts.attempt_number)
                .all()
            )

            assert run.status == JobRunStatus.SUCCESS
            assert run.worker_id is None
            assert len(attempts) == 1
            assert attempts[0].status == AttemptStatus.SUCCESS
    finally:
        allow_completion.set()
        for thread in workers:
            thread.join(timeout=10)
        _cleanup_seeded_runs(engine, team_id, job_id, run_ids)
        engine.dispose()


def test_postgres_two_workers_process_two_runs():
    """Two workers make progress concurrently without sharing an attempt."""
    engine = _postgres_engine()
    team_id, job_id, run_ids = _seed_queued_runs(engine, count=2)

    start = threading.Barrier(2)
    both_executing = threading.Event()
    allow_completion = threading.Event()
    execution_count = 0
    count_lock = threading.Lock()
    results: dict[str, bool] = {}
    errors: list[BaseException] = []

    def blocking_execute(_job):
        nonlocal execution_count
        with count_lock:
            execution_count += 1
            if execution_count == 2:
                both_executing.set()
        assert allow_completion.wait(timeout=10), "test did not release both workers"
        return {"message": "completed by test worker"}

    def run_worker(worker_id: str) -> None:
        db = Session(engine)
        try:
            start.wait(timeout=10)
            results[worker_id] = worker_mod.process_one_run(db, worker_id=worker_id)
        except BaseException as exc:
            errors.append(exc)
        finally:
            db.close()

    workers = [
        threading.Thread(target=run_worker, args=(f"pg-worker-{index}",))
        for index in range(2)
    ]

    try:
        with patch.object(worker_mod, "start_heartbeat", side_effect=_no_op_heartbeat), patch.object(
            worker_mod, "execute_job", side_effect=blocking_execute
        ):
            for thread in workers:
                thread.start()

            assert both_executing.wait(timeout=10), "both queued runs were not claimed"

            # At this synchronization point both workers are executing and
            # the database is the source of truth for their independent claims.
            with Session(engine) as db:
                running_runs = db.query(JobRuns).filter(JobRuns.id.in_(run_ids)).all()
                running_attempts = (
                    db.query(JobAttempts)
                    .filter(JobAttempts.run_id.in_(run_ids))
                    .all()
                )
                assert {run.worker_id for run in running_runs} == {"pg-worker-0", "pg-worker-1"}
                assert all(run.status == JobRunStatus.RUNNING for run in running_runs)
                assert all(attempt.status == AttemptStatus.RUNNING for attempt in running_attempts)

            allow_completion.set()
            for thread in workers:
                thread.join(timeout=10)

        assert not errors
        assert results == {"pg-worker-0": True, "pg-worker-1": True}

        with Session(engine) as db:
            runs = db.query(JobRuns).filter(JobRuns.id.in_(run_ids)).all()
            attempts = db.query(JobAttempts).filter(JobAttempts.run_id.in_(run_ids)).all()
            assert all(run.status == JobRunStatus.SUCCESS and run.worker_id is None for run in runs)
            assert all(attempt.status == AttemptStatus.SUCCESS for attempt in attempts)
    finally:
        allow_completion.set()
        for thread in workers:
            thread.join(timeout=10)
        _cleanup_seeded_runs(engine, team_id, job_id, run_ids)
        engine.dispose()


def test_postgres_worker_pool_processes_runs_without_duplicate_attempts():
    """A worker pool claims each run at most once while processing a backlog."""
    worker_count = 3
    run_count = 5
    engine = _postgres_engine()
    team_id, job_id, run_ids = _seed_queued_runs(engine, count=run_count)

    start = threading.Barrier(worker_count)
    initial_claims_ready = threading.Event()
    allow_completion = threading.Event()
    execution_count = 0
    count_lock = threading.Lock()
    results: dict[str, list[bool]] = {}
    errors: list[BaseException] = []
    result_lock = threading.Lock()

    def execute_after_initial_claims(_job):
        nonlocal execution_count
        with count_lock:
            execution_count += 1
            if execution_count == worker_count:
                initial_claims_ready.set()
        assert allow_completion.wait(timeout=10), "test did not release worker pool"
        return {"message": "completed by test worker"}

    def drain_worker(worker_id: str) -> None:
        db = Session(engine)
        processed: list[bool] = []
        try:
            start.wait(timeout=10)
            while True:
                handled = worker_mod.process_one_run(db, worker_id=worker_id)
                processed.append(handled)
                if not handled:
                    break
            with result_lock:
                results[worker_id] = processed
        except BaseException as exc:
            with result_lock:
                errors.append(exc)
        finally:
            db.close()

    workers = [
        threading.Thread(target=drain_worker, args=(f"pg-pool-worker-{index}",))
        for index in range(worker_count)
    ]

    try:
        with patch.object(worker_mod, "start_heartbeat", side_effect=_no_op_heartbeat), patch.object(
            worker_mod, "execute_job", side_effect=execute_after_initial_claims
        ):
            for thread in workers:
                thread.start()

            assert initial_claims_ready.wait(timeout=10), "worker pool did not claim concurrently"
            with Session(engine) as db:
                runs = db.query(JobRuns).filter(JobRuns.id.in_(run_ids)).all()
                attempts = db.query(JobAttempts).filter(JobAttempts.run_id.in_(run_ids)).all()
                assert sum(run.status == JobRunStatus.RUNNING for run in runs) == worker_count
                assert sum(run.status == JobRunStatus.QUEUED for run in runs) == run_count - worker_count
                assert len({run.worker_id for run in runs if run.status == JobRunStatus.RUNNING}) == worker_count
                assert sum(attempt.status == AttemptStatus.RUNNING for attempt in attempts) == worker_count

            allow_completion.set()
            for thread in workers:
                thread.join(timeout=10)

        assert not errors
        assert sum(result.count(True) for result in results.values()) == run_count

        with Session(engine) as db:
            runs = db.query(JobRuns).filter(JobRuns.id.in_(run_ids)).all()
            attempts = db.query(JobAttempts).filter(JobAttempts.run_id.in_(run_ids)).all()
            assert all(run.status == JobRunStatus.SUCCESS and run.worker_id is None for run in runs)
            assert len(attempts) == run_count
            assert all(attempt.status == AttemptStatus.SUCCESS for attempt in attempts)
            assert len({(attempt.run_id, attempt.attempt_number) for attempt in attempts}) == run_count
    finally:
        allow_completion.set()
        for thread in workers:
            thread.join(timeout=10)
        _cleanup_seeded_runs(engine, team_id, job_id, run_ids)
        engine.dispose()


def test_postgres_recovers_expired_run(postgres_db_session):
    db = postgres_db_session

    team = Team(name="PG Recovery Team")
    db.add(team)
    db.flush()

    job = Jobs(
        team_id=team.id,
        name="PG Recovery Job",
        executor_type="sample",
        image="alpine:latest",
    )
    db.add(job)
    db.flush()

    run = JobRuns(
        job_id=job.id,
        status=JobRunStatus.RUNNING,
        worker_id="worker-A",
        heartbeat_at=utc_now() - timedelta(seconds=120),
    )
    db.add(run)
    db.flush()

    attempt = JobAttempts(
        run_id=run.id,
        attempt_number=1,
        status=AttemptStatus.RUNNING,
    )
    db.add(attempt)
    db.commit()

    result = recover_one_expired_run(db)

    assert result is True

    db.refresh(run)
    db.refresh(attempt)

    assert run.status == JobRunStatus.QUEUED
    assert run.worker_id is None
    assert run.heartbeat_at is None
    assert attempt.status == AttemptStatus.FAILED

    retry = (
        db.query(JobAttempts)
        .filter(
            JobAttempts.run_id == run.id,
            JobAttempts.attempt_number == 2,
        )
        .one_or_none()
    )

    assert retry is not None
    assert retry.status == AttemptStatus.QUEUED


def test_postgres_skip_locked_skips_locked_run():
    engine = create_engine(os.environ["TEST_POSTGRES_URL"])
    suffix = uuid4().hex[:8]

    team_id = None
    job_id = None
    run_id = None

    try:
        # Create and commit data so both worker connections can see it.
        with Session(engine) as db:
            team = Team(name=f"Locking Team {suffix}")
            db.add(team)
            db.flush()

            job = Jobs(
                team_id=team.id,
                name=f"Locking Job {suffix}",
                executor_type="sample",
                image="alpine:latest",
            )
            db.add(job)
            db.flush()

            run = JobRuns(
                job_id=job.id,
                status=JobRunStatus.QUEUED,
            )
            db.add(run)
            db.flush()

            team_id = team.id
            job_id = job.id
            run_id = run.id

            db.commit()

        # Two independent connections represent two workers.
        with engine.connect() as worker_a, engine.connect() as worker_b:
            with worker_a.begin():
                locked_run = worker_a.execute(
                    select(JobRuns.id)
                    .where(JobRuns.id == run_id)
                    .with_for_update(skip_locked=True)
                ).first()

                assert locked_run is not None

                with worker_b.begin():
                    skipped_run = worker_b.execute(
                        select(JobRuns.id)
                        .where(JobRuns.id == run_id)
                        .with_for_update(skip_locked=True)
                    ).first()

                    assert skipped_run is None

    finally:
        # Remove committed test data, respecting foreign-key dependencies.
        with engine.begin() as connection:
            if run_id is not None:
                connection.execute(
                    JobRuns.__table__.delete().where(
                        JobRuns.id == run_id
                    )
                )
            if job_id is not None:
                connection.execute(
                    Jobs.__table__.delete().where(
                        Jobs.id == job_id
                    )
                )
            if team_id is not None:
                connection.execute(
                    Team.__table__.delete().where(
                        Team.id == team_id
                    )
                )
