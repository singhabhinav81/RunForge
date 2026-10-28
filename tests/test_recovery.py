from datetime import timedelta

from app.api.worker.worker import (
    recover_one_expired_run,
    utc_now,
)
from app.db.models import Team, Jobs, JobRuns, JobAttempts
from app.api.domain.run_status import JobRunStatus
from app.api.domain.attempt_status import AttemptStatus


def test_no_expired_runs_returns_false(db_session):
    result = recover_one_expired_run(db_session)

    assert result is False


def test_recovers_expired_run_and_creates_retry(db_session):
    # 1. Create team and job
    team = Team(name="Recovery Test Team")
    db_session.add(team)
    db_session.flush()

    job = Jobs(
        team_id=team.id,
        name="Recovery Test Job",
        executor_type="sample",
        image="alpine:latest",
    )
    db_session.add(job)
    db_session.flush()

    # 2. Create a RUNNING job run with an expired heartbeat
    expired_time = utc_now() - timedelta(seconds=120)

    run = JobRuns(
        job_id=job.id,
        status=JobRunStatus.RUNNING,
        worker_id="worker-A",
        heartbeat_at=expired_time,
    )
    db_session.add(run)
    db_session.flush()

    # 3. Create its RUNNING attempt
    attempt = JobAttempts(
        run_id=run.id,
        attempt_number=1,
        status=AttemptStatus.RUNNING,
    )
    db_session.add(attempt)
    db_session.commit()

    # 4. Execute recovery
    result = recover_one_expired_run(db_session)

    # 5. Verify recovery
    assert result is True

    db_session.refresh(run)
    db_session.refresh(attempt)

    assert run.status == JobRunStatus.QUEUED
    assert run.worker_id is None
    assert run.heartbeat_at is None

    assert attempt.status == AttemptStatus.FAILED
    assert attempt.finished_at is not None
    assert attempt.error is not None

    # 6. Verify the next attempt was created
    next_attempt = (
        db_session.query(JobAttempts)
        .filter(
            JobAttempts.run_id == run.id,
            JobAttempts.attempt_number == 2,
        )
        .first()
    )

    assert next_attempt is not None
    assert next_attempt.status == AttemptStatus.QUEUED


def test_expired_final_attempt_fails_run_without_retry(db_session):
    # 1. Create team and job
    team = Team(name="Recovery Test Team")
    db_session.add(team)
    db_session.flush()

    job = Jobs(
        team_id=team.id,
        name="Recovery Test Job",
        executor_type="sample",
        image="alpine:latest",
    )
    db_session.add(job)
    db_session.flush()

    # 2. Create a RUNNING job run with an expired heartbeat
    expired_time = utc_now() - timedelta(seconds=120)

    run = JobRuns(
        job_id=job.id,
        status=JobRunStatus.RUNNING,
        worker_id="worker-A",
        heartbeat_at=expired_time,
    )
    db_session.add(run)
    db_session.flush()

    # 3. Create its RUNNING attempt
    attempt = JobAttempts(
        run_id=run.id,
        attempt_number=3,
        status=AttemptStatus.RUNNING,
    )
    db_session.add(attempt)
    db_session.commit()

    # 4. Execute recovery
    result = recover_one_expired_run(db_session)

    # 5. Verify recovery
    assert result is True

    db_session.refresh(run)
    db_session.refresh(attempt)

    assert run.status == JobRunStatus.FAILED
    assert run.worker_id is None
    assert run.heartbeat_at is None

    assert attempt.status == AttemptStatus.FAILED
    assert attempt.finished_at is not None
    assert attempt.error is not None

    # 6. Verify the next attempt was created
    next_attempt = (
        db_session.query(JobAttempts)
        .filter(
            JobAttempts.run_id == run.id,
            JobAttempts.attempt_number == 4,
        )
        .first()
    )

    assert next_attempt is None
    assert run.status == JobRunStatus.FAILED


def test_expired_run_without_running_attempt_fails_run(db_session):
    team = Team(name="Missing Attempt Team")
    db_session.add(team)
    db_session.flush()

    job = Jobs(
        team_id=team.id,
        name="Missing Attempt Job",
        executor_type="sample",
        image="alpine:latest",
    )
    db_session.add(job)
    db_session.flush()

    run = JobRuns(
        job_id=job.id,
        status=JobRunStatus.RUNNING,
        worker_id="worker-A",
        heartbeat_at=utc_now() - timedelta(seconds=120),
    )
    db_session.add(run)
    db_session.commit()

    result = recover_one_expired_run(db_session)

    assert result is True

    db_session.refresh(run)

    assert run.status == JobRunStatus.FAILED
    assert run.finished_at is not None
    assert run.worker_id is None
    assert run.heartbeat_at is None

    assert db_session.query(JobAttempts).filter(
        JobAttempts.run_id == run.id
    ).count() == 0
