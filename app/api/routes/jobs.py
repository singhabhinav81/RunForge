from fastapi import APIRouter, Depends, Query, status
from app.api.schemas.jobs import JobCreate, JobUpdate
from app.api.services.job_service import create_job, get_job_by_id, get_all_jobs, delete_job, update_job
from app.api.services.teams_service import get_team_by_id
from app.api.exceptions.jobs import JobNotFoundException
from app.api.exceptions.team import TeamNotFoundException
from sqlalchemy.orm import Session

from app.db.deps import get_db

job_router = APIRouter()


@job_router.post("/jobs", status_code=status.HTTP_201_CREATED, description="Create a new job")
def create_job_endpoint(job: JobCreate, db: Session = Depends(get_db)):
    # Implement the logic to create a new job in the database
    # For now, we will return a placeholder response
    get_team_id = get_team_by_id(db, job.team_id)
    if get_team_id is None:
        raise TeamNotFoundException(job.team_id)
    return create_job(db, job)        


@job_router.get("/jobs/{job_id}", status_code=status.HTTP_200_OK, description="Get Job by id")
def get_job_endpoint(job_id: int, db: Session = Depends(get_db)):
    job = get_job_by_id(db=db, job_id=job_id)
    if not job:
        raise JobNotFoundException(job_id)
    return job


@job_router.get("/jobs", status_code=status.HTTP_200_OK, description="Get all jobs")
def get_all_jobs_endpoint(
    # A Job list is scoped to a Team; ge=1 rejects invalid identifiers before querying.
    team_id: int = Query(..., ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size
    return get_all_jobs(db=db, team_id=team_id, offset=offset, limit=page_size)

@job_router.delete("/jobs/{job_id}", description="Delete a job by its ID")
def delete_job_endpoint(job_id:int, db: Session = Depends(get_db)):
    job = get_job_by_id(db, job_id=job_id)
    if not job:
        raise JobNotFoundException(job_id)
    return delete_job(db, job_id)

@job_router.put("/jobs/{job_id}", description="Update a job by its ID")
def update_job_endpoint(job_id: int, job: JobUpdate, db: Session = Depends(get_db)):
    existing_team = get_job_by_id(db, job_id)
    if not existing_team:
        raise JobNotFoundException(job_id)
    return update_job(db, job_id, job)
