from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from app.api.schemas.teams import TeamCreate
from app.api.services.teams_service import create_team, get_team_by_id, get_all_teams, delete_team, update_team
from sqlalchemy.orm import Session
from app.api.exceptions.team import TeamNotFoundException, DuplicateTeamNameException, UnauthorizedTeamAccessException

from app.db.deps import get_db


team_router = APIRouter()

@team_router.post("/teams", status_code=status.HTTP_201_CREATED, description="Create a new team")
def create_team_endpoint(team: TeamCreate, db: Session = Depends(get_db)):
    return create_team(db, team)


@team_router.post("/teams/bulk", status_code=status.HTTP_201_CREATED, description="Create multiple teams")
def create_teams_endpoint(teams: list[TeamCreate], db: Session = Depends(get_db)):
    return [create_team(db, team) for team in teams]


@team_router.get("/teams/{team_id}", status_code=status.HTTP_200_OK, description="Retrieve a team by its ID")
def get_team_endpoint(team_id: int, db: Session = Depends(get_db)):
    team = get_team_by_id(db, team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


@team_router.get("/teams", status_code=status.HTTP_200_OK, description="Retrieve all teams")
def get_all_teams_endpoint(page: int = 1, page_size: int = 10, db: Session = Depends(get_db)):
    offset = (page - 1) * page_size
    teams = get_all_teams(db, offset=offset, limit=page_size)
    return teams


@team_router.delete("/teams/{team_id}", description="Delete a team by its ID")
def delete_team_endpoint(team_id: int, db: Session = Depends(get_db)):
    team = get_team_by_id(db, team_id)
    if not team:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Team not found"})
    return delete_team(db, team_id)
    
    
@team_router.put("/teams/{team_id}", description="Update a team by its ID")
def update_team_endpoint(team_id: int, team: TeamCreate, db: Session = Depends(get_db)):
    existing_team = get_team_by_id(db, team_id)
    if not existing_team:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": "Team not found"})
    return update_team(db, team_id, team)
