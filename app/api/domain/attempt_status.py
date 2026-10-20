import enum


class AttemptStatus(enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
