"""lesson request both types + excluded students

Revision ID: b0a1c2d3e4f7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-17 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b0a1c2d3e4f7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Дети, с которыми ученик не может заниматься в групповых занятиях
    op.create_table(
        "lesson_request_excluded_students",
        sa.Column("lesson_request_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["lesson_request_id"], ["lesson_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("lesson_request_id", "student_id"),
    )

    # Тип требования «индивидуально и в группе одновременно»
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE lessontypeenum ADD VALUE IF NOT EXISTS 'both'")


def downgrade() -> None:
    op.drop_table("lesson_request_excluded_students")
    # Удаление значения из Postgres enum ALTER TYPE не поддерживает;
    # 'both' просто игнорируется старым кодом.