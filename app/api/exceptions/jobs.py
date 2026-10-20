from app.api.exceptions.base import RunForgeException

class JobNotFoundException(RunForgeException):
    """Exception raised when Job is not Found"""
    status_code = 404
    def __init__(self, job_id: int):
        message = f"Job with ID {job_id} not found."
        super().__init__(message)


class TeamNotFoundException(RunForgeException):
    """Exception raiesed when Team is not found"""
    def __init__(self, team_id: int):
        message = f"Team with ID {team_id} not found."
        super().__init__(message)


class DuplicateJobNameException(RunForgeException):
    """Exception raised when a team already has a job with this name."""
    status_code = 409

    def __init__(self, team_id: int, job_name: str):
        super().__init__(f"Job with name '{job_name}' already exists for team with ID {team_id}.")


class JobHasRunsException(RunForgeException):
    """Exception raised when deleting a job with execution history."""
    status_code = 409

    def __init__(self, job_id: int):
        super().__init__(f"Job with ID {job_id} cannot be deleted because it has runs.")


