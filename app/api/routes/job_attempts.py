from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.schemas.job_attempts import (
    JobAttemptResponse,
    JobAttemptsListResponse,
)
from app.api.services.job_attempts_service import (
    get_job_attempt_by_id,
    get_job_attempts_by_run_id,
)
from app.db.deps import get_db

job_attempt_router = APIRouter()


@job_attempt_router.get("/attempts/{attempt_id}", response_model=JobAttemptResponse, status_code=status.HTTP_200_OK)
def get_job_attempt_endpoint(attempt_id: int, db: Session = Depends(get_db)):
    return get_job_attempt_by_id(attempt_id=attempt_id, db=db)

@job_attempt_router.get("/runs/{run_id}/attempts", response_model=JobAttemptsListResponse, status_code=status.HTTP_200_OK)
def get_job_attempts_endpoint(run_id: int, page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=100), db: Session = Depends(get_db)):
    offset = (page - 1) * page_size
    return get_job_attempts_by_run_id(run_id=run_id, db=db, offset=offset, limit=page_size, page=page, page_size=page_size)