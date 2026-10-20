from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.db.models import JobRunStatus

class JobRunResponse(BaseModel):
    id: int
    job_id: int
    status: JobRunStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)    
    
class JobRunsListResponse(BaseModel):
    job_runs: list[JobRunResponse]
    total: int
    page: int
    page_size: int