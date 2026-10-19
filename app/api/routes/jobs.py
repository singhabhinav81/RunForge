from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from app.api.schemas.jobs import JobCreate, JobResponse
from app.api.services.job_service import create_job, get_job_by_id, get_all_jobs, delete_job, update_job
from app.api.services.teams_service import get_team_by_id
from sqlalchemy.orm import Session

from app.db.deps import get_db

job_router = APIRouter()


@job_router.post("/jobs", status_code=status.HTTP_201_CREATED, description="Create a new job")
def create_job_endpoint(job: JobCreate, db: Session = Depends(get_db)):
    # Implement the logic to create a new job in the database
    # For now, we will return a placeholder response
    get_team_id = get_team_by_id(db, job.team_id)
    if get_team_id is None:
        return JSONResponse(status_code=404, content={"detail": "Team not found"})
    return create_job(db, job)        


@job_router.get("/jobs/{job_id}", status_code=status.HTTP_200_OK, description="Get Job by id")
def get_job_endpoint(job_id: int, db: Session = Depends(get_db)):
    job = get_job_by_id(db=db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@job_router.get("/jobs", status_code=status.HTTP_200_OK, description="Get all jobs")
def get_all_jobs_endpoint(page:int = 1, page_size:int = 10, team_id: int = None, db: Session = Depends(get_db)):
    if team_id is None:
        return JSONResponse(status_code=400, content={"detail": "Team not found"})
    offset = (page - 1) * page_size
    return get_all_jobs(db=db, team_id=team_id, offset=offset, limit=page_size)

@job_router.delete("/jobs/{job_id}", description="Delete a job by its ID")
def delete_job_endpoint(job_id:int, db: Session = Depends(get_db)):
    job = get_job_by_id(db, job_id=job_id)
    if not job:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Job not found"})
    return delete_job(db, job_id)

@job_router.put("/jobs/{job_id}", description="Update a job by its ID")
def update_job_endpoint(job_id: int, job: JobCreate, db: Session = Depends(get_db)):
    existing_team = get_job_by_id(db, job_id)
    if not existing_team:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Job not found"})
    return update_job(db, job_id, job)
