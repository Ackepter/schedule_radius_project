"""auto group lessons

Revision ID: a1b2c3d4e5f6
Revises: e3497b83862a
Create Date: 2026-09-17 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e3497b83862a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # Существующие ручные группы конвертируем в групповые требования учеников,
    # чтобы алгоритм мог автоматически переформировать группы.
    op.execute(
        sa.text(
            """
            INSERT INTO lesson_requests
                (student_id, subject_id, lesson_type, lessons_per_week,
                 duration_minutes, preferred_teacher_id, teacher_is_required,
                 priority, notes)
            SELECT p.student_id, gl.subject_id, 'group', gl.lessons_per_week,
                   gl.duration_minutes, gl.teacher_id, gl.teacher_is_required,
                   1, 'Конвертировано из ручной группы при обновлении'
            FROM group_lesson_participants p
            JOIN group_lessons gl ON gl.id = p.group_lesson_id
            WHERE p.student_id IS NOT NULL
            """
        )
    )

    # Join-таблица участников занятий расписания
    op.create_table(
        "scheduled_lesson_participants",
        sa.Column("scheduled_lesson_id", sa.Integer(), nullable=False),
        sa.Column("lesson_request_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scheduled_lesson_id"], ["scheduled_lessons.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["lesson_request_id"], ["lesson_requests.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("scheduled_lesson_id", "lesson_request_id"),
    )

    # Минимальный/максимальный размер автоматически формируемой группы
    op.add_column(
        "optimizer_settings",
        sa.Column("group_min_size", sa.Integer(), server_default="2", nullable=False),
    )
    op.add_column(
        "optimizer_settings",
        sa.Column("group_max_size", sa.Integer(), server_default="8", nullable=False),
    )

    # Удаляем ручные группы и связь с ними в расписании
    op.drop_column("scheduled_lessons", "group_lesson_id")
    op.drop_table("group_lesson_participants")
    op.drop_table("group_lessons")

    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE entitytypeenum RENAME TO entitytypeenum_old")
        op.execute(
            "CREATE TYPE entitytypeenum AS ENUM "
            "('student', 'teacher', 'room', 'lesson_request')"
        )
        op.execute(
            "ALTER TABLE availabilities ALTER COLUMN entity_type "
            "TYPE entitytypeenum USING entity_type::text::entitytypeenum"
        )
        op.execute("DROP TYPE entitytypeenum_old")


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_table("scheduled_lesson_participants")
    op.drop_column("optimizer_settings", "group_max_size")
    op.drop_column("optimizer_settings", "group_min_size")

    op.create_table(
        "group_lessons",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=True),
        sa.Column("teacher_is_required", sa.Boolean(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("lessons_per_week", sa.Integer(), nullable=False),
        sa.Column("max_size", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "group_lesson_participants",
        sa.Column("group_lesson_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_lesson_id"], ["group_lessons.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("group_lesson_id", "student_id"),
    )
    op.add_column(
        "scheduled_lessons",
        sa.Column("group_lesson_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_scheduled_lessons_group_lesson_id",
        "scheduled_lessons",
        "group_lessons",
        ["group_lesson_id"],
        ["id"],
        ondelete="SET NULL",
    )

    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE entitytypeenum RENAME TO entitytypeenum_old")
        op.execute(
            "CREATE TYPE entitytypeenum AS ENUM "
            "('student', 'teacher', 'room', 'lesson_request', 'group_lesson')"
        )
        op.execute(
            "ALTER TABLE availabilities ALTER COLUMN entity_type "
            "TYPE entitytypeenum USING entity_type::text::entitytypeenum"
        )
        op.execute("DROP TYPE entitytypeenum_old")