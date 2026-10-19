from pydantic import BaseModel

class TeamCreate(BaseModel):
    name: str
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


