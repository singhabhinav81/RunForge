class RunForgeException(Exception):
    """Base exception for all RunForge application errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
        