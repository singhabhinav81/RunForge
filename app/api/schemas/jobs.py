from pydantic import BaseModel

class JobCreate(BaseModel):
    team_id: int
    name: str
    description: str | None = None
    executor_type: str
    image: str


class JobResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    team_id: int
    team_name: str | None = None
    executor_type: str
    image: str
    created_at: str | None = None
    updated_at: str | None = None


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int


class JobDeleteResponse(BaseModel):
    message: str