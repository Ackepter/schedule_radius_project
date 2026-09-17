"""teacher rates (teacher pay per lesson)

Revision ID: c5d6e7f8a9b0
Revises: b0a1c2d3e4f7
Create Date: 2026-09-17 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b0a1c2d3e4f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE teacher_rates (
            id SERIAL PRIMARY KEY,
            teacher_id INTEGER REFERENCES teachers(id) ON DELETE CASCADE,
            subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
            lesson_type lessontypeenum NOT NULL,
            rate_per_lesson DOUBLE PRECISION NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.drop_table("teacher_rates")