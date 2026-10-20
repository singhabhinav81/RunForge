from app.api.exceptions.base import RunForgeException

class JobRunNotFoundException(RunForgeException):
    """Exception raised when JobRun is not Found"""
    status_code = 404
    def __init__(self, run_id: int):
        message = f"Job run with ID {run_id} not found."
        super().__init__(message)