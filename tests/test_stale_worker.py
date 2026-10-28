"""
Stale-worker scenario test.

Goal: Prove that Worker A cannot overwrite the database state after recovery
has given the job to Worker B.

Timeline
--------
1. Worker A claims Run, marks Attempt 1 as RUNNING.
2. Worker A "executes" (mocked) and returns — heartbeat thread stops.
3. **Worker A is paused** before its final DB update.
4. Recovery detects an expired heartbeat, marks Attempt 1 FAILED, queues Attempt 2.
5. Worker B claims Attempt 2, marks it RUNNING.
6. **Worker A resumes** — ownership check rejects the stale update.
7. We verify Worker B's state is untouched.

Implementation notes
--------------------
* Uses the real PostgreSQL database (not SQLite) because ``WITH FOR UPDATE``
  and ``skip_locked`` are PostgreSQL features.
* Each "worker" runs in its own thread with a patched ``WORKER_ID``.
* ``threading.Event`` gates enforce a deterministic execution order — no
  ``time.sleep`` guessing.
* The heartbeat loop and executor are mocked so the test completes in < 2 s.
"""

import os
import sys
import threading
from datetime import timedelta
from unittest.mock import patch

# Ensure repo root is on sys.path if run directly
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pytest

from app.db.database import SessionLocal
from app.db.models import Team, Jobs, JobRuns, JobAttempts
from app.api.domain.run_status import JobRunStatus
from app.api.domain.attempt_status import AttemptStatus

# Import worker module
from app.api.worker import worker as worker_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WORKER_A_ID = "test-worker-A"
WORKER_B_ID = "test-worker-B"


def _seed_run(db) -> tuple[int, int, int]:
    """Create Team → Job → QUEUED Run → QUEUED Attempt 1.  Returns (job_id, run_id, attempt_id)."""
    team = Team(name="StaleTest Team", description="stale-worker scenario")
    db.add(team)
    db.flush()

    job = Jobs(
        team_id=team.id,
        name="StaleTest Job",
        executor_type="sample",
        image="alpine:latest",
    )
    db.add(job)
    db.flush()

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

    db.commit()
    return job.id, run.id, attempt.id


def _db():
    """Shortcut for a fresh session."""
    return SessionLocal()


# ---------------------------------------------------------------------------
# The test
# ---------------------------------------------------------------------------

class TestStaleWorkerScenario:
    """
    End-to-end stale-worker test against PostgreSQL.

    Step 1 – Worker A claims the run.
    Step 2 – We artificially expire the heartbeat.
    Step 3 – Recovery marks Attempt 1 FAILED and queues Attempt 2.
    Step 4 – Worker B claims Attempt 2.
    Step 5 – Worker A resumes and tries to finalize — should be REJECTED.
    Step 6 – We verify Worker B's state is intact.
    """

    # ------------------------------------------------------------------ #
    # Fixtures
    # ------------------------------------------------------------------ #

    @pytest.fixture(autouse=True)
    def _setup_and_teardown(self):
        """Seed the run and clean up after the test."""
        db = _db()
        try:
            self.job_id, self.run_id, self.attempt1_id = _seed_run(db)
        finally:
            db.close()

        yield  # ← run the test

        # Cleanup: delete the rows we created (reverse FK order).
        db = _db()
        try:
            db.query(JobAttempts).filter(
                JobAttempts.run_id == self.run_id,
            ).delete()
            db.query(JobRuns).filter(JobRuns.id == self.run_id).delete()
            db.query(Jobs).filter(Jobs.id == self.job_id).delete()
            db.query(Team).filter(Team.name == "StaleTest Team").delete()
            db.commit()
        finally:
            db.close()

    # ------------------------------------------------------------------ #
    # The scenario
    # ------------------------------------------------------------------ #

    def test_stale_worker_a_rejected_after_recovery(self):
        """Worker A's finalization is rejected; Worker B's state is intact."""

        # Synchronisation gates ------------------------------------------------
        worker_a_paused = threading.Event()   # A signals: "I finished executing, pausing now."
        worker_a_resume = threading.Event()   # Main thread signals: "Recovery is done, resume A."
        worker_b_claimed = threading.Event()  # B signals: "I claimed Attempt 2."
        worker_b_release = threading.Event()  # Main thread signals: "A has resumed, you may finish."

        worker_a_result = {}
        worker_b_result = {}

        def _dummy_heartbeat(run_id, worker_id=None):
            stop_ev = threading.Event()
            th = threading.Thread(target=lambda: None)
            th.start()
            return stop_ev, th

        # -- Worker A thread --------------------------------------------------
        def worker_a_fn():
            """
            Runs process_one_run with worker_id = WORKER_A_ID.
            We inject a pause between execution and the final DB update.

            IMPORTANT: We use manual patcher.start()/stop() so we can stop
            patches BEFORE signalling Worker B.  This avoids overlapping
            patch lifetimes on the same module attribute, which would leave
            worker_mod.execute_job permanently mocked after both threads
            exit their patches in the wrong order.
            """
            db = _db()
            patcher_hb = patch.object(worker_mod, "start_heartbeat", side_effect=_dummy_heartbeat)
            patcher_exec = patch.object(worker_mod, "execute_job", return_value={"msg": "ok"})

            try:
                patcher_hb.start()
                patcher_exec.start()

                original_expire_all = db.expire_all

                def _expire_all_with_pause():
                    # execute_job and start_heartbeat have already been called
                    # by process_one_run.  Stop the patches NOW, before we
                    # signal the main thread, so Worker B can safely create
                    # its own non-overlapping patches.
                    patcher_exec.stop()
                    patcher_hb.stop()

                    original_expire_all()
                    # Signal: "I've finished executing."
                    worker_a_paused.set()
                    # Block until recovery + Worker B claim are done.
                    worker_a_resume.wait(timeout=15)

                db.expire_all = _expire_all_with_pause
                result = worker_mod.process_one_run(db, worker_id=WORKER_A_ID)
                worker_a_result["returned"] = result

            except Exception as exc:
                worker_a_result["error"] = str(exc)
            finally:
                db.close()

        # -- Worker B thread --------------------------------------------------
        def worker_b_fn():
            """
            After recovery queues Attempt 2, Worker B claims it with worker_id = WORKER_B_ID.
            It stays "running" until released by the main thread.
            """
            db = _db()
            try:
                def _blocking_execute(job):
                    worker_b_claimed.set()
                    worker_b_release.wait(timeout=15)
                    return {"msg": "ok from B"}

                with patch.object(worker_mod, "start_heartbeat", side_effect=_dummy_heartbeat):
                    with patch.object(worker_mod, "execute_job", side_effect=_blocking_execute):
                        result = worker_mod.process_one_run(db, worker_id=WORKER_B_ID)
                        worker_b_result["returned"] = result

            except Exception as exc:
                worker_b_result["error"] = str(exc)
            finally:
                db.close()


        # ==================================================================
        # Orchestrate the scenario
        # ==================================================================

        # ---- Step 1: Worker A claims the run -----------------------------
        thread_a = threading.Thread(target=worker_a_fn, name="WorkerA")
        thread_a.start()

        # Wait until Worker A has executed and is paused before finalization.
        assert worker_a_paused.wait(timeout=15), "Worker A did not reach the pause point"

        # Verify Step 1: run should be RUNNING, owned by Worker A.
        db = _db()
        try:
            run = db.query(JobRuns).filter(JobRuns.id == self.run_id).first()
            assert run.status == JobRunStatus.RUNNING, f"Expected RUNNING, got {run.status}"
            assert run.worker_id == WORKER_A_ID
            attempt1 = db.query(JobAttempts).filter(JobAttempts.id == self.attempt1_id).first()
            assert attempt1.status == AttemptStatus.RUNNING
        finally:
            db.close()

        # ---- Step 2: Simulate an expired heartbeat -----------------------
        db = _db()
        try:
            run = db.query(JobRuns).filter(JobRuns.id == self.run_id).first()
            # Push heartbeat_at back by 2× the lease timeout.
            run.heartbeat_at = worker_mod.utc_now() - timedelta(
                seconds=worker_mod.LEASE_TIMEOUT_SECONDS * 2,
            )
            db.commit()
        finally:
            db.close()

        # ---- Step 3: Recovery picks up the expired run -------------------
        db = _db()
        try:
            recovered = worker_mod.recover_one_expired_run(db)
            assert recovered, "Recovery did not find the expired run"
        finally:
            db.close()

        # Verify Step 3: Attempt 1 → FAILED, Attempt 2 → QUEUED, Run → QUEUED.
        db = _db()
        try:
            run = db.query(JobRuns).filter(JobRuns.id == self.run_id).first()
            assert run.status == JobRunStatus.QUEUED, f"Expected QUEUED after recovery, got {run.status}"
            assert run.worker_id is None

            attempt1 = db.query(JobAttempts).filter(JobAttempts.id == self.attempt1_id).first()
            assert attempt1.status == AttemptStatus.FAILED

            attempt2 = (
                db.query(JobAttempts)
                .filter(
                    JobAttempts.run_id == self.run_id,
                    JobAttempts.attempt_number == 2,
                )
                .first()
            )
            assert attempt2 is not None, "Recovery did not create Attempt 2"
            assert attempt2.status == AttemptStatus.QUEUED
            self.attempt2_id = attempt2.id
        finally:
            db.close()

        # ---- Step 4: Worker B claims Attempt 2 ---------------------------
        thread_b = threading.Thread(target=worker_b_fn, name="WorkerB")
        thread_b.start()

        assert worker_b_claimed.wait(timeout=15), "Worker B did not claim the run"

        # Verify Step 4: run → RUNNING owned by B, Attempt 2 → RUNNING.
        db = _db()
        try:
            run = db.query(JobRuns).filter(JobRuns.id == self.run_id).first()
            assert run.status == JobRunStatus.RUNNING
            assert run.worker_id == WORKER_B_ID

            attempt2 = db.query(JobAttempts).filter(JobAttempts.id == self.attempt2_id).first()
            assert attempt2.status == AttemptStatus.RUNNING
        finally:
            db.close()

        # ---- Step 5: Resume Worker A — it should be REJECTED -------------
        worker_a_resume.set()
        thread_a.join(timeout=15)

        assert "error" not in worker_a_result, f"Worker A raised: {worker_a_result.get('error')}"
        # process_one_run returns True even when ownership is lost (it's a "handled" case).
        assert worker_a_result.get("returned") is True

        # ---- Step 6: Verify Worker B's state is UNTOUCHED ----------------
        db = _db()
        try:
            run = db.query(JobRuns).filter(JobRuns.id == self.run_id).first()
            assert run.status == JobRunStatus.RUNNING, (
                f"Worker A corrupted the run! Expected RUNNING, got {run.status}"
            )
            assert run.worker_id == WORKER_B_ID, (
                f"Worker A overwrote worker_id! Expected {WORKER_B_ID}, got {run.worker_id}"
            )

            attempt1 = db.query(JobAttempts).filter(JobAttempts.id == self.attempt1_id).first()
            assert attempt1.status == AttemptStatus.FAILED, (
                f"Worker A overwrote Attempt 1! Expected FAILED, got {attempt1.status}"
            )

            attempt2 = db.query(JobAttempts).filter(JobAttempts.id == self.attempt2_id).first()
            assert attempt2.status == AttemptStatus.RUNNING, (
                f"Worker A corrupted Attempt 2! Expected RUNNING, got {attempt2.status}"
            )
        finally:
            db.close()

        # ---- Release Worker B so it can finish ---------------------------
        worker_b_release.set()
        thread_b.join(timeout=15)

        assert "error" not in worker_b_result, f"Worker B raised: {worker_b_result.get('error')}"

        # Final state: run → SUCCESS, Attempt 2 → SUCCESS, Worker B done.
        db = _db()
        try:
            run = db.query(JobRuns).filter(JobRuns.id == self.run_id).first()
            assert run.status == JobRunStatus.SUCCESS, (
                f"Worker B didn't finalize! Expected SUCCESS, got {run.status}"
            )
            assert run.worker_id is None  # lease cleared

            attempt2 = db.query(JobAttempts).filter(JobAttempts.id == self.attempt2_id).first()
            assert attempt2.status == AttemptStatus.SUCCESS
        finally:
            db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
