"""add unique job name per team

Revision ID: c4e1a7b9d2f0
Revises: ec9e7f4a3290
Create Date: 2026-10-19
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c4e1a7b9d2f0"
down_revision: Union[str, Sequence[str], None] = "ec9e7f4a3290"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enforce the same uniqueness rule at the database level, including concurrent requests.
    op.create_unique_constraint("uq_jobs_team_name", "jobs", ["team_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_jobs_team_name", "jobs", type_="unique")
