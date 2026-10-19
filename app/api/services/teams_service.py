from app.api.schemas.teams import TeamCreate, TeamResponse, TeamListResponse, TeamDeleteResponse
from sqlalchemy.orm import Session
from app.api.exceptions.team import TeamNotFoundException, DuplicateTeamNameException

from app.db.models import Team


def create_team(db:Session, team: TeamCreate) -> TeamResponse:
    """
    Create a new team in the database.

    Args:
        db (Session): The database session.
        team (TeamCreate): A TeamCreate object containing the team details.

    Returns:
        TeamResponse: A TeamResponse object containing the created team details.
    """
    existing_team = (
        db.query(Team)
        .filter(Team.name == team.name)
        .first()
    )

    if existing_team:
        raise DuplicateTeamNameException(team.name)
    
    new_team = Team(name=team.name, description=team.description)
    db.add(new_team)
    db.commit()
    db.refresh(new_team)
    return TeamResponse(id=new_team.id, name=new_team.name, description=new_team.description)


def get_team_by_id(db: Session, team_id: int) -> TeamResponse | None:
    """
    Retrieve a team from the database by its ID.

    Args:
        db (Session): The database session.
        team_id (int): The ID of the team to retrieve.

    Returns:
        TeamResponse | None: A TeamResponse object containing the team details if found, otherwise None.
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    if team:
        return TeamResponse(id=team.id, name=team.name, description=team.description)
    return None

def get_all_teams(db: Session, offset: int = 0, limit: int = 10) -> TeamListResponse:
    """
    Retrieve all teams from the database.

    Args:
        db (Session): The database session.
        offset (int): The number of teams to skip.
        limit (int): The maximum number of teams to retrieve.

    Returns:
        TeamListResponse: A TeamListResponse object containing the list of teams and pagination information.
    """
    total_teams = db.query(Team).count()
    teams = db.query(Team).offset(offset).limit(limit).all()
    team_list = [TeamResponse(id=team.id, name=team.name, description=team.description) for team in teams]
    return TeamListResponse(teams=team_list, total=total_teams, page=(offset // limit) + 1, page_size=limit)

def delete_team(db: Session, team_id: int) -> bool:
    """
    Delete a team from the database by its ID.

    Args:
        db (Session): The database session.
        team_id (int): The ID of the team to delete.

    Returns:
        bool: True if the team was deleted, False if the team was not found.
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    if team: 
        db.delete(team)
        db.commit()
        return TeamDeleteResponse(message=f"Team with ID {team_id} deleted successfully.")
    raise TeamNotFoundException(team_id)

def update_team(db: Session, team_id: int, team: TeamCreate) -> TeamResponse | None:
    """
    Update a team in the database by its ID.

    Args:
        db (Session): The database session.
        team_id (int): The ID of the team to update.
        team (TeamCreate): A TeamCreate object containing the updated team details.

    Returns:
        TeamResponse | None: A TeamResponse object containing the updated team details if found, otherwise None.
    """
    existing_team = db.query(Team).filter(Team.id == team_id).first()
    if existing_team:
        existing_team.name = team.name if team.name else existing_team.name
        existing_team.description = team.description if team.description else existing_team.description
        db.commit()
        db.refresh(existing_team)
        return TeamResponse(id=existing_team.id, name=existing_team.name, description=existing_team.description)
    return None

