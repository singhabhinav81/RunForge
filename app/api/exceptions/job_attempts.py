from app.api.exceptions.base import RunForgeException

class JobAttemptNotFoundException(RunForgeException):
    """Exception raised when JobAttempt is not Found"""
    status_code = 404
    def __init__(self, attempt_id: int):
        message = f"Job attempt with ID {attempt_id} not found."
        super().__init__(message)    