from app.api.exceptions.base import RunForgeException

class JobNotFound(RunForgeException):
    """Exception raised when Job is not Found"""
    def __init__(self, job_id: int):
        message = f"Job with ID {job_id} not found."
        super().__init__(message)


class TeamNotFound(RunForgeException):
    """Exception raiesed when Team is not found"""
    def __init__(self, team_id: int):
        message = f"Team with ID {team_id} not found."
        super().__init__(message)


