import time


def sample_job() -> dict:
    """A predefined workload for testing the RunForge worker."""
    print("Sample job started")

    time.sleep(2)

    print("Sample job completed")

    return {"message": "Sample job completed successfully"}


def execute_job(job) -> dict:
    """Execute a supported workload based on its executor type."""

    if job.executor_type == "sample":
        return sample_job()

    raise ValueError(
        f"Unsupported executor type: {job.executor_type}"
    )
