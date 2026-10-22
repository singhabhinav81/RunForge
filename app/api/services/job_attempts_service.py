
from sqlalchemy.orm import Session

from app.db.models import JobAttempts, JobRuns
from app.api.exceptions.job_runs import JobRunNotFoundException
from app.api.exceptions.job_attempts import JobAttemptNotFoundException
from app.api.schemas.job_attempts import (
    JobAttemptResponse,
    JobAttemptsListResponse,
)


def get_job_attempt_by_id(
    attempt_id: int,
    db: Session,
) -> JobAttemptResponse:
    attempt = (
        db.query(JobAttempts)
        .filter(JobAttempts.id == attempt_id)
        .first()
    )

    if attempt is None:
        raise JobAttemptNotFoundException(attempt_id=attempt_id)

    return JobAttemptResponse.model_validate(attempt)


def get_job_attempts_by_run_id(
    run_id: int,
    db: Session,
    offset: int,
    limit: int,
    page: int,
    page_size: int,
) -> JobAttemptsListResponse:
    # Confirm that the parent run exists.
    run = db.query(JobRuns).filter(JobRuns.id == run_id).first()

    if run is None:
        raise JobRunNotFoundException(run_id=run_id)

    query = db.query(JobAttempts).filter(JobAttempts.run_id == run_id)

    total = query.count()

    attempts = (
        query
        .order_by(JobAttempts.attempt_number.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return JobAttemptsListResponse(
        items=[
            JobAttemptResponse.model_validate(attempt)
            for attempt in attempts
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
