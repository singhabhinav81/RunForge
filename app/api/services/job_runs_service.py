from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.api.exceptions.job_runs import JobRunNotFoundException
from app.api.exceptions.jobs import JobNotFoundException
from app.api.schemas.job_runs import JobRunResponse, JobRunsListResponse
from app.api.services.job_service import get_job_by_id
from app.db.models import JobRuns, JobAttempts
from app.api.domain.run_status import JobRunStatus
from app.api.domain.attempt_status import AttemptStatus


def create_job_run(job_id: int, db: Session) -> JobRunResponse:
    """Create a job run and its first attempt atomically."""

    job = get_job_by_id(db=db, job_id=job_id)

    if job is None:
        raise JobNotFoundException(job_id=job_id)

    try:
        # 1. Create the JobRun
        new_job_run = JobRuns(
            job_id=job.id,
            status=JobRunStatus.QUEUED,
        )
        db.add(new_job_run)

        # 2. Generate the JobRun ID without committing
        db.flush()

        # 3. Create the first JobAttempt
        first_attempt = JobAttempts(
            run_id=new_job_run.id,
            attempt_number=1,
            status=AttemptStatus.QUEUED,
        )
        db.add(first_attempt)

        # 4. Commit both records in one transaction
        db.commit()
        db.refresh(new_job_run)

    except Exception:
        db.rollback()
        raise

    return JobRunResponse.model_validate(new_job_run)   


def get_job_run_by_id(db: Session, run_id: int) -> JobRunResponse:
    # 1. Verify that the job run exists
    job_run = db.query(JobRuns).filter(JobRuns.id == run_id).first()
    if job_run is None:
        raise JobRunNotFoundException(run_id=run_id)
    
    # 2. Return the response
    return JobRunResponse.model_validate(job_run)


def get_all_job_runs(
    db: Session,
    job_id: int,
    status: Optional[JobRunStatus] = None,
    offset: int = 0,
    limit: int = 10,
) -> JobRunsListResponse:
    # 1. Verify that the job exists
    job = get_job_by_id(db=db, job_id=job_id)
    if job is None:
        raise JobNotFoundException(job_id=job_id)
    
    # 2. Build query for job runs with optional status filter
    query = db.query(JobRuns).filter(JobRuns.job_id == job_id)
    if status is not None:
        if isinstance(status, str):
            try:
                status = JobRunStatus(status)
            except ValueError:
                pass
        query = query.filter(JobRuns.status == status)

    total_count = query.count()
    job_runs = query.order_by(JobRuns.created_at.desc()).offset(offset).limit(limit).all()

    # 3. Calculate current page safely
    page = (offset // limit) + 1 if limit > 0 else 1

    # 4. Return the response
    return JobRunsListResponse(
        job_runs=[JobRunResponse.model_validate(job_run) for job_run in job_runs],
        total=total_count,
        page=page,
        page_size=limit,
    )

def delete_job_run(db: Session, run_id: int) -> None:
    # 1. Verify that the job run exists
    job_run = db.query(JobRuns).filter(JobRuns.id == run_id).first()
    if job_run is None:
        raise JobRunNotFoundException(run_id=run_id)
    
    # 2. Delete the job run
    db.delete(job_run)
    db.commit()
    # 3. Return the response
    return JobRunResponse.model_validate(job_run)