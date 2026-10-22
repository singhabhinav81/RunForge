import time


def sample_job() -> dict:
    """A predefined workload for testing the RunForge worker."""
    print("Sample job started")

    time.sleep(2)

    return {"message": "Sample job completed successfully"}


def execute_job(job) -> dict:
    """Execute a supported workload based on its executor type."""

    if job.executor_type == "sample":
        return sample_job()

    if job.executor_type == "failing":
        return failing_job(job)

    if job.executor_type == "flaky":
        return flaky_job(job)

    raise ValueError(
        f"Unsupported executor type: {job.executor_type}"
    )

def failing_job(job) -> dict:
    """A predefined workload for testing the RunForge worker."""

    time.sleep(2)

    raise ValueError(
        f"Failed job for testing"
    )
    

def flaky_job(job) -> dict:
    """Fail on the first execution, succeed on the second."""

    # Temporary in-memory counter for testing only
    if not hasattr(flaky_job, "execution_count"):
        flaky_job.execution_count = 0

    flaky_job.execution_count += 1

    print(f"Flaky job execution #{flaky_job.execution_count}")

    time.sleep(2)

    if flaky_job.execution_count == 1:
        raise ValueError("Intentional failure on first attempt")

    print("Flaky job completed successfully")

    return {"message": "Job succeeded after retry"}