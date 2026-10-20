from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.schemas.job_runs import JobRunsListResponse
from app.api.services.job_runs_service import create_job_run, get_job_run_by_id, get_all_job_runs
from app.db.deps import get_db
from app.db.models import JobRunStatus

job_run_router = APIRouter()

@job_run_router.post("/jobs/{job_id}/run", status_code=status.HTTP_201_CREATED, description="Request a new execution")
def create_job_execution_endpoint(job_id: int, db: Session = Depends(get_db)):
    return create_job_run(job_id=job_id, db=db)


@job_run_router.get("/runs/{run_id}", status_code=status.HTTP_200_OK, description="Get job runs by job id")
def get_job_runs_endpoint(run_id: int, db: Session = Depends(get_db)):
    return get_job_run_by_id(run_id=run_id, db=db)


@job_run_router.get(
    "/jobs/{job_id}/runs",
    response_model=JobRunsListResponse,
    status_code=status.HTTP_200_OK,
    description="Get all job runs by job id",
)
def get_all_job_runs_endpoint(
    job_id: int, 
    db: Session = Depends(get_db),
    status: Optional[JobRunStatus] = Query(default=None, description="Filter runs by status"), 
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Items per page"),
):
    offset = (page - 1) * page_size
    return get_all_job_runs(db=db, job_id=job_id, status=status, offset=offset, limit=page_size)
    

@job_run_router.post("/runs/{run_id}/cancel", status_code=status.HTTP_200_OK, description="Cancel a job run by its run id")
def cancel_job_run_endpoint(run_id: int, db: Session = Depends(get_db)):
    pass
