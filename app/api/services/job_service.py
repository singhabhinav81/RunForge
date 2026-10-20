from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.api.schemas.jobs import JobCreate, JobDeleteResponse, JobListResponse, JobResponse, JobUpdate
from app.api.exceptions.jobs import DuplicateJobNameException, JobHasRunsException, JobNotFoundException
from app.api.exceptions.team import TeamNotFoundException
from app.api.services.teams_service import get_team_by_id
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
        raise DuplicateJobNameException(job.team_id, job.name)
    new_job = Jobs(name=job.name, description=job.description, team_id=job.team_id, image=job.image, executor_type=job.executor_type)
    db.add(new_job)
    try:
        db.commit()
    except IntegrityError as exc:
        # A second concurrent request may insert the same (team_id, name) after our pre-check.
        db.rollback()
        if get_team_by_id(db, job.team_id) is None:
            raise TeamNotFoundException(job.team_id) from exc
        raise DuplicateJobNameException(job.team_id, job.name) from exc
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

def get_all_jobs(db: Session, team_id: int,  offset: int = 0, limit: int = 10) -> JobListResponse:
    """
    Get All Jobs
    """
    total_count = db.query(Jobs).filter(Jobs.team_id==team_id).count()
    get_team_name = get_team_by_id(db=db, team_id=team_id)
    # Avoid dereferencing None and turning a missing Team into a 500 response.
    if get_team_name is None:
        raise TeamNotFoundException(team_id)
    jobs = db.query(Jobs).filter(Jobs.team_id==team_id).offset(offset).limit(limit)
    response_list = [JobResponse(id=job.id, name=job.name, description=job.description, team_id=job.team_id, executor_type=job.executor_type, image=job.image, team_name=get_team_name.name) for job in jobs]
    # 3. Calculate current page safely
    page = (offset // limit) + 1 if limit > 0 else 1
    return JobListResponse(jobs=response_list, total=total_count, page=page, page_size=limit)


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
        # Keep execution history intact; callers receive a clear conflict instead of a database 500.
        if db.query(Jobs).filter(Jobs.job_id == job_id).first():
            raise JobHasRunsException(job_id)
        db.delete(job)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise JobHasRunsException(job_id) from exc
        return JobDeleteResponse(message=f"Job with ID {job_id} deleted successfully.")
    raise JobNotFoundException(job_id=job_id)

def update_job(db: Session, job_id: int, job: JobUpdate) -> JobResponse | None:
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
        # Only overwrite fields supplied by the client; omitted fields retain their stored values.
        for field in ("name", "description", "executor_type", "image"):
            if field in job.model_fields_set:
                setattr(existing_job, field, getattr(job, field))
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise DuplicateJobNameException(existing_job.team_id, job.name) from exc
        db.refresh(existing_job)
        return JobResponse(
            id=existing_job.id, name=existing_job.name, description=existing_job.description, 
            team_id=existing_job.team_id, image=existing_job.image, 
            executor_type=existing_job.executor_type
        )
    return None




