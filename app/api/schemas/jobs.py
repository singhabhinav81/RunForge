from pydantic import BaseModel, Field

class JobCreate(BaseModel):
    team_id: int
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    executor_type: str = Field(min_length=1, max_length=50)
    image: str = Field(min_length=1, max_length=500)


class JobUpdate(BaseModel):
    # team_id is deliberately excluded; moving a Job needs explicit business rules later.
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    executor_type: str | None = Field(default=None, min_length=1, max_length=50)
    image: str | None = Field(default=None, min_length=1, max_length=500)


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
