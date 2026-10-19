from sqlalchemy.orm import Session
from app.api.schemas.jobs import JobCreate, JobResponse, JobListResponse, JobDeleteResponse
from app.api.exceptions.jobs import JobNotFound
from app.api.services.teams_service import get_team_by_id
from fastapi.responses import JSONResponse
from app.db.models import Jobs

def create_job(db: Session, job: JobCreate) -> JobResponse:
    """
    Create a new job in the database.
    Args:
        db (Session): The database session.
        job (JobCreate): A JobCreate object containing the job details.

    Returns:
        JobResponse: A JobResponse object containing the created job details.
    """
    existing_job = db.query(Jobs).filter(Jobs.team_id==job.team_id, Jobs.name==job.name).first()
    if existing_job:
        return JSONResponse(status_code=409, content={"message":f"Job with Name '{job.name}' already exists."})
    new_job = Jobs(name=job.name, description=job.description, team_id=job.team_id, image=job.image, executor_type=job.executor_type)
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return JobResponse(id=new_job.id, name=new_job.name, description=new_job.description, team_id=new_job.team_id, image=new_job.image, executor_type=new_job.executor_type)
    

def get_job_by_id(db: Session, job_id) -> JobResponse | None:
    """
    Get Job by Id
    """
    job = db.query(Jobs).filter(Jobs.id == job_id).first()
    if job:
        get_team_name = get_team_by_id(db=db, team_id=job.team_id)
        return JobResponse(id=job.id, name=job.name, description=job.description, team_id=job.team_id, executor_type=job.executor_type, image=job.image, team_name=get_team_name.name)
    return None

def get_all_jobs(db: Session, team_id: int,  offset: int = 0, limit: int = 10) -> JobResponse:
    """
    Get All Jobs
    """
    total_count = db.query(Jobs).filter(Jobs.team_id==team_id).count()
    get_team_name = get_team_by_id(db=db, team_id=team_id)
    jobs = db.query(Jobs).filter(Jobs.team_id==team_id).offset(offset).limit(limit)
    response_list = [JobResponse(id=job.id, name=job.name, description=job.description, team_id=job.team_id, executor_type=job.executor_type, image=job.image, team_name=get_team_name.name) for job in jobs]
    return JobListResponse(jobs=response_list, total=total_count, page=(offset // limit) + 1, page_size=limit)


def delete_job(db: Session, job_id: int):
    """
    Delete a Job from the database by its ID.

    Args:
        db (Session): The database session.
        team_id (int): The ID of the team to delete.

    Returns:
        bool: True if the team was deleted, False if the team was not found.
    """
    job = db.query(Jobs).filter(Jobs.id==job_id).first()
    if job:
        db.delete(job)
        db.commit()
        return JobDeleteResponse(message=f"Job with ID {job_id} deleted successfully.")
    return JobNotFound(job_id=job_id)

def update_job(db: Session, job_id: int, job: JobCreate) -> JobResponse | None:
    """
    Update a job in the database by its ID.

    Args:
        db (Session): The database session.
        team_id (int): The ID of the team to update.
        team (TeamCreate): A JobCreate object containing the updated team details.

    Returns:
        TeamResponse | None: A JobResponse object containing the updated team details if found, otherwise None.
    """
    existing_job = db.query(Jobs).filter(Jobs.id == job_id).first()
    if existing_job:
        existing_job.name = job.name if job.name else existing_job.name
        existing_job.description = job.description if job.description else existing_job.description
        existing_job.executor_type = job.executor_type if job.executor_type else existing_job.executor_type
        existing_job.image = job.image if job.image else existing_job.image
        db.commit()
        db.refresh(existing_job)
        return JobResponse(
            id=existing_job.id, name=existing_job.name, description=existing_job.description, 
            team_id=existing_job.team_id, image=existing_job.image, 
            executor_type=existing_job.executor_type
        )
    return JSONResponse(status_code=404, content={"message":f"Job with Job Id {job_id} could not be found."})




