from app.api.exceptions.base import RunForgeException

class TeamNotFoundException(RunForgeException):
    """Exception raised when a team is not found."""
    def __init__(self, team_id: int):
        message = f"Team with ID {team_id} not found."
        super().__init__(message)

class DuplicateTeamNameException(RunForgeException):
    """Exception raised when a team with the same name already exists."""
    def __init__(self, team_name: str):
        message = f"Team with name '{team_name}' already exists."
        super().__init__(message)


class UnauthorizedTeamAccessException(RunForgeException):
    """Exception raised when a user tries to access a team they are not authorized to."""
    def __init__(self, team_id: int):
        message = f"You are not authorized to access team with ID {team_id}."
        super().__init__(message)

