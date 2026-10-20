from pydantic import BaseModel, Field

class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class TeamUpdate(BaseModel):
    # Update fields are optional so clients can change one field without resending the whole Team.
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None

class TeamResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    

class TeamListResponse(BaseModel):
    teams: list[TeamResponse]
    total: int
    page: int
    page_size: int


class TeamDeleteResponse(BaseModel):
    message: str


