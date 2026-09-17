"""add rate_type to teacher rates

Revision ID: e7f8a9b0c1d2
Revises: c5d6e7f8a9b0
Create Date: 2026-09-17 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE ratetypeenum AS ENUM ('fixed', 'percent')")
    op.execute(
        "ALTER TABLE teacher_rates "
        "ADD COLUMN rate_type ratetypeenum DEFAULT 'fixed' NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("teacher_rates", "rate_type")
    op.execute("DROP TYPE IF EXISTS ratetypeenum")