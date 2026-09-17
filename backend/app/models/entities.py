import enum
from datetime import date, time
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Time,
    Date,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

# --- промежуточные таблицы ---

teacher_subjects = Table(
    "teacher_subjects",
    Base.metadata,
    Column("teacher_id", Integer, ForeignKey("teachers.id", ondelete="CASCADE"), primary_key=True),
    Column("subject_id", Integer, ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True),
)

room_subjects = Table(
    "room_subjects",
    Base.metadata,
    Column("room_id", Integer, ForeignKey("rooms.id", ondelete="CASCADE"), primary_key=True),
    Column("subject_id", Integer, ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True),
)

scheduled_lesson_participants = Table(
    "scheduled_lesson_participants",
    Base.metadata,
    Column(
        "scheduled_lesson_id",
        Integer,
        ForeignKey("scheduled_lessons.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "lesson_request_id",
        Integer,
        ForeignKey("lesson_requests.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

lesson_request_excluded_students = Table(
    "lesson_request_excluded_students",
    Base.metadata,
    Column(
        "lesson_request_id",
        Integer,
        ForeignKey("lesson_requests.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "student_id",
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ---------- Enums ----------

class LessonTypeEnum(str, enum.Enum):
    individual = "individual"
    group = "group"
    both = "both"


class ScheduleStatusEnum(str, enum.Enum):
    draft = "draft"
    active = "active"


class EntityTypeEnum(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    room = "room"
    lesson_request = "lesson_request"


# ---------- Models ----------

class Parent(Base):
    __tablename__ = "parents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(50))
    email = Column(String(150))
    comment = Column(Text)

    students: Mapped[list["Student"]] = relationship("Student", back_populates="parent")


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    birth_date = Column(Date)
    comment = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    parent_id = Column(Integer, ForeignKey("parents.id", ondelete="SET NULL"))

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name}".strip()

    parent: Mapped[Optional["Parent"]] = relationship("Parent", back_populates="students")
    lesson_requests: Mapped[list["LessonRequest"]] = relationship(
        "LessonRequest", back_populates="student", cascade="all, delete-orphan"
    )


class Subject(Base, TimestampMixin):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    default_duration_minutes = Column(Integer, default=60)
    is_active = Column(Boolean, default=True, nullable=False)


class Teacher(Base, TimestampMixin):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    comment = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    max_weekly_hours = Column(Integer)

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name}".strip()

    subjects: Mapped[list["Subject"]] = relationship(
        "Subject", secondary=teacher_subjects, backref="teachers"
    )


class Room(Base, TimestampMixin):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    capacity = Column(Integer, nullable=False)
    comment = Column(Text)

    allowed_subjects: Mapped[list["Subject"]] = relationship(
        "Subject", secondary=room_subjects, backref="rooms"
    )


class Availability(Base):
    __tablename__ = "availabilities"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="check_avail_time"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(Enum(EntityTypeEnum), nullable=False)
    entity_id = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)


class LessonRequest(Base, TimestampMixin):
    __tablename__ = "lesson_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    subject_id = Column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    lesson_type = Column(Enum(LessonTypeEnum), nullable=False)
    lessons_per_week = Column(Integer, default=1, nullable=False)
    duration_minutes = Column(Integer, default=60, nullable=False)
    preferred_teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="SET NULL"))
    teacher_is_required = Column(Boolean, default=False, nullable=False)
    priority = Column(Integer, default=1, nullable=False)
    notes = Column(Text)

    student: Mapped["Student"] = relationship("Student", back_populates="lesson_requests")
    subject: Mapped["Subject"] = relationship("Subject")
    preferred_teacher: Mapped[Optional["Teacher"]] = relationship("Teacher")
    scheduled_lessons: Mapped[list["ScheduledLesson"]] = relationship(
        "ScheduledLesson",
        secondary=scheduled_lesson_participants,
        back_populates="participants",
    )
    excluded_students: Mapped[list["Student"]] = relationship(
        "Student",
        secondary=lesson_request_excluded_students,
        backref="excluded_from_requests",
    )

    @property
    def lesson_request_id(self) -> int:
        return self.id


class Schedule(Base, TimestampMixin):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    week_start = Column(Date, nullable=False)
    status = Column(
        Enum(ScheduleStatusEnum), default=ScheduleStatusEnum.draft, nullable=False
    )
    unscheduled_report = Column(Text)

    lessons: Mapped[list["ScheduledLesson"]] = relationship(
        "ScheduledLesson", back_populates="schedule", cascade="all, delete-orphan"
    )


class ScheduledLesson(Base, TimestampMixin):
    __tablename__ = "scheduled_lessons"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="check_sched_time"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(
        Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    lesson_type = Column(Enum(LessonTypeEnum), nullable=False)
    lesson_request_id = Column(
        Integer, ForeignKey("lesson_requests.id", ondelete="SET NULL")
    )
    student_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"))
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    teacher_id = Column(
        Integer, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=False
    )
    room_id = Column(
        Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=False
    )

    schedule: Mapped["Schedule"] = relationship("Schedule", back_populates="lessons")
    lesson_request: Mapped[Optional["LessonRequest"]] = relationship("LessonRequest")
    student: Mapped[Optional["Student"]] = relationship("Student")
    participants: Mapped[list["LessonRequest"]] = relationship(
        "LessonRequest",
        secondary=scheduled_lesson_participants,
        back_populates="scheduled_lessons",
    )
    teacher: Mapped["Teacher"] = relationship("Teacher")
    room: Mapped["Room"] = relationship("Room")

    @property
    def lesson_request_ids(self) -> list[int]:
        return [p.id for p in self.participants]


class Price(Base):
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    lesson_type = Column(Enum(LessonTypeEnum), nullable=False)
    min_participants = Column(Integer, nullable=False)
    max_participants = Column(Integer, nullable=False)
    price_per_student = Column(Float, nullable=False)

    subject: Mapped["Subject"] = relationship("Subject")


class TeacherRate(Base):
    """Оплата педагогу за одно занятие.

    teacher_id = NULL — ставка по умолчанию для пары (subject, lesson_type).
    teacher_id задан — индивидуальная ставка конкретного педагога (переопределяет умолчание).
    """

    __tablename__ = "teacher_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    teacher_id = Column(
        Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=True
    )
    subject_id = Column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    lesson_type = Column(Enum(LessonTypeEnum), nullable=False)
    rate_per_lesson = Column(Float, nullable=False)

    teacher: Mapped[Optional["Teacher"]] = relationship("Teacher")
    subject: Mapped["Subject"] = relationship("Subject")

    @property
    def is_default(self) -> bool:
        return self.teacher_id is None


class OptimizerSettings(Base):
    __tablename__ = "optimizer_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time_limit_seconds = Column(Integer, default=30, nullable=False)
    weight_presence = Column(Float, default=1000.0, nullable=False)
    reward_preferred_teacher = Column(Float, default=100.0, nullable=False)
    penalty_student_same_day = Column(Float, default=50.0, nullable=False)
    penalty_early_late = Column(Float, default=20.0, nullable=False)
    early_hour = Column(Integer, default=9, nullable=False)
    late_hour = Column(Integer, default=20, nullable=False)
    weight_teacher_balance = Column(Float, default=30.0, nullable=False)
    weight_room_balance = Column(Float, default=10.0, nullable=False)
    group_min_size = Column(Integer, default=2, nullable=False)
    group_max_size = Column(Integer, default=8, nullable=False)