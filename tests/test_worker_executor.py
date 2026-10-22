"""Tests for the Worker (process_one_run) and Executor logic."""

import pytest
from unittest.mock import patch
from datetime import datetime, timezone

from app.db.models import Team, Jobs, JobRuns, JobAttempts
from app.api.domain.run_status import JobRunStatus
from app.api.domain.attempt_status import AttemptStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_team_and_job(db, *, executor_type="sample"):
    """Insert a Team + Job directly into the session for worker tests."""
    team = Team(name=f"WorkerTeam-{id(db)}", description="Worker testing")
    db.add(team)
    db.flush()

    job = Jobs(
        team_id=team.id,
        name=f"WorkerJob-{id(db)}",
        executor_type=executor_type,
        image="alpine:latest",
    )
    db.add(job)
    db.flush()
    return team, job


def _create_queued_run(db, job):
    """Create a QUEUED run + first QUEUED attempt."""
    run = JobRuns(job_id=job.id, status=JobRunStatus.QUEUED)
    db.add(run)
    db.flush()

    attempt = JobAttempts(
        run_id=run.id,
        attempt_number=1,
        status=AttemptStatus.QUEUED,
    )
    db.add(attempt)
    db.flush()
    return run, attempt


# =========================================================================
# Executor unit tests
# =========================================================================

class TestExecutor:
    """Tests for app.api.executors.executor functions."""

    def test_sample_job_returns_success(self):
        from app.api.executors.executor import sample_job

        with patch("app.api.executors.executor.time.sleep"):
            result = sample_job()
        assert "message" in result

    def test_execute_job_sample(self):
        from app.api.executors.executor import execute_job
        from types import SimpleNamespace

        job = SimpleNamespace(executor_type="sample")
        with patch("app.api.executors.executor.time.sleep"):
            result = execute_job(job)
        assert "message" in result

    def test_execute_job_unsupported_type(self):
        from app.api.executors.executor import execute_job
        from types import SimpleNamespace

        job = SimpleNamespace(executor_type="unknown_type")
        with pytest.raises(ValueError, match="Unsupported executor type"):
            execute_job(job)

    def test_failing_job_raises(self):
        from app.api.executors.executor import failing_job
        from types import SimpleNamespace

        job = SimpleNamespace(executor_type="failing")
        with patch("app.api.executors.executor.time.sleep"):
            with pytest.raises(ValueError, match="Failed job"):
                failing_job(job)


# =========================================================================
# Worker – process_one_run
# =========================================================================

class TestProcessOneRun:
    """Tests for app.api.worker.worker.process_one_run."""

    def test_no_queued_runs_returns_false(self, db_session):
        from app.api.worker.worker import process_one_run

        assert process_one_run(db_session) is False

    def test_successful_run(self, db_session):
        """A 'sample' job should transition run → SUCCESS and attempt → SUCCESS."""
        from app.api.worker.worker import process_one_run

        _team, job = _seed_team_and_job(db_session, executor_type="sample")
        run, attempt = _create_queued_run(db_session, job)
        db_session.commit()

        with patch("app.api.executors.executor.time.sleep"):
            result = process_one_run(db_session)

        assert result is True

        db_session.refresh(run)
        db_session.refresh(attempt)

        assert run.status == JobRunStatus.SUCCESS
        assert run.finished_at is not None
        assert attempt.status == AttemptStatus.SUCCESS
        assert attempt.finished_at is not None

    def test_failed_run_creates_retry_attempt(self, db_session):
        """A 'failing' job creates the next QUEUED attempt when attempts remain."""
        from app.api.worker.worker import process_one_run

        _team, job = _seed_team_and_job(db_session, executor_type="failing")
        run, attempt = _create_queued_run(db_session, job)
        db_session.commit()

        with patch("app.api.executors.executor.time.sleep"):
            result = process_one_run(db_session)

        assert result is True

        db_session.refresh(run)
        db_session.refresh(attempt)

        # First attempt failed
        assert attempt.status == AttemptStatus.FAILED
        assert attempt.error is not None

        # Run is re-queued for the next attempt
        assert run.status == JobRunStatus.QUEUED

        # A second attempt row was created
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

    def test_exhausted_retries_marks_run_failed(self, db_session):
        """After MAX_ATTEMPTS failures the run transitions to FAILED."""
        from app.api.worker.worker import process_one_run, MAX_ATTEMPTS

        _team, job = _seed_team_and_job(db_session, executor_type="failing")
        run, _attempt = _create_queued_run(db_session, job)
        db_session.commit()

        with patch("app.api.executors.executor.time.sleep"):
            for _ in range(MAX_ATTEMPTS):
                process_one_run(db_session)

        db_session.refresh(run)
        assert run.status == JobRunStatus.FAILED
        assert run.finished_at is not None

        # All attempts should be FAILED
        attempts = (
            db_session.query(JobAttempts)
            .filter(JobAttempts.run_id == run.id)
            .order_by(JobAttempts.attempt_number)
            .all()
        )
        assert len(attempts) == MAX_ATTEMPTS
        assert all(a.status == AttemptStatus.FAILED for a in attempts)

    def test_run_without_queued_attempt_returns_false(self, db_session):
        """A QUEUED run with no QUEUED attempt should be skipped gracefully."""
        from app.api.worker.worker import process_one_run

        _team, job = _seed_team_and_job(db_session, executor_type="sample")
        run = JobRuns(job_id=job.id, status=JobRunStatus.QUEUED)
        db_session.add(run)
        db_session.flush()
        # Deliberately do NOT create an attempt
        db_session.commit()

        result = process_one_run(db_session)
        assert result is False


# =========================================================================
# Domain enum tests
# =========================================================================

class TestDomainEnums:
    """Smoke tests for the status enums."""

    def test_job_run_status_values(self):
        assert JobRunStatus.QUEUED.value == "QUEUED"
        assert JobRunStatus.RUNNING.value == "RUNNING"
        assert JobRunStatus.SUCCESS.value == "SUCCESS"
        assert JobRunStatus.FAILED.value == "FAILED"

    def test_attempt_status_values(self):
        assert AttemptStatus.QUEUED.value == "QUEUED"
        assert AttemptStatus.RUNNING.value == "RUNNING"
        assert AttemptStatus.SUCCESS.value == "SUCCESS"
        assert AttemptStatus.FAILED.value == "FAILED"
        assert AttemptStatus.TIMED_OUT.value == "TIMED_OUT"
