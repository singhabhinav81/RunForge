from datetime import datetime
from sqlalchemy import (
    DateTime,
    Integer,
    String,
    ForeignKey,
    Text,
    func,
)

from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base
from app.api.domain.run_status import JobRunStatus
from app.api.domain.attempt_status import AttemptStatus
from sqlalchemy import Enum, UniqueConstraint, CheckConstraint


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    first_name: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    last_name: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), 
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False
    )

class TeamMember(Base):
    __tablename__ = "team_members"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="viewer",
    )


class Jobs(Base):
    __tablename__ = "jobs"

    __table_args__ = (
        # Service checks improve the error message; this constraint prevents races from creating duplicates.
        UniqueConstraint("team_id", "name", name="uq_jobs_team_name"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    team_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("teams.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    executor_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    image: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), 
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False
    )


class JobRuns(Base):
    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    job_id: Mapped[int] = mapped_column(
            Integer, ForeignKey("jobs.id"), nullable=False
    )
    status: Mapped[JobRunStatus] = mapped_column(
        Enum(JobRunStatus, name="job_run_status"),
        nullable=False,
        default=JobRunStatus.QUEUED
    )
    started_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True),
    nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
                    DateTime(timezone=True),
                    server_default=func.now(),
                    nullable=False,
    )

class JobAttempts(Base):
    __tablename__ = "job_attempts"

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "attempt_number",
            name="uq_job_attempt_run_number",
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name="ck_job_attempt_number_positive",
        ),
    )
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("job_runs.id"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    status: Mapped[AttemptStatus] = mapped_column(
        Enum(AttemptStatus, name="attempt_status"),
        nullable=False,
        default=AttemptStatus.QUEUED,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )



