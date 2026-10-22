from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.api.domain.attempt_status import AttemptStatus


class JobAttemptResponse(BaseModel):
    id: int
    run_id: int
    attempt_number: int
    status: AttemptStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None

    model_config = ConfigDict(from_attributes=True)


class JobAttemptsListResponse(BaseModel):
    items: list[JobAttemptResponse]
    total: int
    page: int
    page_size: int