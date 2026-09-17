from datetime import date, datetime, time
from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.models.entities import (
    EntityTypeEnum,
    LessonTypeEnum,
    RateTypeEnum,
    ScheduleStatusEnum,
)

T = TypeVar("T")


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------


class SubjectBase(SchemaBase):
    id: int
    name: str
    description: Optional[str] = None
    default_duration_minutes: int = Field(default=60, gt=0)
    is_active: bool = True


class SubjectCreate(SchemaBase):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    default_duration_minutes: int = Field(default=60, gt=0)
    is_active: bool = True


class SubjectUpdate(SchemaBase):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    default_duration_minutes: Optional[int] = Field(default=None, gt=0)
    is_active: Optional[bool] = None


class SubjectList(SubjectBase):
    pass


# ---------------------------------------------------------------------------
# Parent
# ---------------------------------------------------------------------------


class ParentBase(SchemaBase):
    id: int
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    comment: Optional[str] = None


class ParentCreate(SchemaBase):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=150)
    comment: Optional[str] = None


class ParentUpdate(SchemaBase):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=150)
    comment: Optional[str] = None


class ParentList(ParentBase):
    students: list["StudentBase"] = []


# ---------------------------------------------------------------------------
# Student
# ---------------------------------------------------------------------------


class StudentBase(SchemaBase):
    id: int
    first_name: str
    last_name: str
    birth_date: Optional[date] = None
    comment: Optional[str] = None
    is_active: bool = True
    parent_id: Optional[int] = None


class StudentCreate(SchemaBase):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    birth_date: Optional[date] = None
    comment: Optional[str] = None
    is_active: bool = True
    parent_id: Optional[int] = None


class StudentUpdate(SchemaBase):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    birth_date: Optional[date] = None
    comment: Optional[str] = None
    is_active: Optional[bool] = None
    parent_id: Optional[int] = None


class StudentList(StudentBase):
    parent: Optional[ParentBase] = None
    lesson_requests: list["LessonRequestBase"] = []


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------


class TeacherBase(SchemaBase):
    id: int
    first_name: str
    last_name: str
    comment: Optional[str] = None
    is_active: bool = True
    max_weekly_hours: Optional[int] = Field(default=None, ge=0)
    subjects: list[SubjectBase] = []


class TeacherCreate(SchemaBase):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    comment: Optional[str] = None
    is_active: bool = True
    max_weekly_hours: Optional[int] = Field(default=None, ge=0)
    subject_ids: list[int] = []


class TeacherUpdate(SchemaBase):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    comment: Optional[str] = None
    is_active: Optional[bool] = None
    max_weekly_hours: Optional[int] = Field(default=None, ge=0)
    subject_ids: Optional[list[int]] = None


class TeacherList(TeacherBase):
    pass


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------


class RoomBase(SchemaBase):
    id: int
    name: str
    capacity: int = Field(ge=1)
    comment: Optional[str] = None
    allowed_subjects: list[SubjectBase] = []


class RoomCreate(SchemaBase):
    name: str = Field(..., min_length=1, max_length=100)
    capacity: int = Field(..., ge=1)
    comment: Optional[str] = None
    allowed_subject_ids: list[int] = []


class RoomUpdate(SchemaBase):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    capacity: Optional[int] = Field(default=None, ge=1)
    comment: Optional[str] = None
    allowed_subject_ids: Optional[list[int]] = None


class RoomList(RoomBase):
    pass


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


class AvailabilityBase(SchemaBase):
    id: int
    entity_type: EntityTypeEnum
    entity_id: int
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time


class AvailabilitySchema(AvailabilityBase):
    id: Optional[int] = None

    @model_validator(mode="after")
    def _check_times(self) -> "AvailabilitySchema":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class AvailabilityCreate(SchemaBase):
    entity_type: EntityTypeEnum
    entity_id: int = Field(..., ge=1)
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def _check_times(self) -> "AvailabilityCreate":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class AvailabilityUpdate(SchemaBase):
    entity_type: Optional[EntityTypeEnum] = None
    entity_id: Optional[int] = Field(default=None, ge=1)
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    @model_validator(mode="after")
    def _check_times(self) -> "AvailabilityUpdate":
        if self.start_time is not None and self.end_time is not None:
            if self.start_time >= self.end_time:
                raise ValueError("start_time must be earlier than end_time")
        return self


# ---------------------------------------------------------------------------
# LessonRequest
# ---------------------------------------------------------------------------


class LessonRequestBase(SchemaBase):
    id: int
    student_id: int
    subject_id: int
    lesson_type: LessonTypeEnum
    lessons_per_week: int = Field(default=1, ge=1)
    duration_minutes: int = Field(default=60, gt=0)
    preferred_teacher_id: Optional[int] = None
    teacher_is_required: bool = False
    priority: int = Field(default=1, ge=1, le=3)
    notes: Optional[str] = None
    subject: Optional[SubjectBase] = None
    preferred_teacher: Optional[TeacherBase] = None
    excluded_students: list["StudentBase"] = []


class LessonRequestCreate(SchemaBase):
    student_id: int = Field(..., ge=1)
    subject_id: int = Field(..., ge=1)
    lesson_type: LessonTypeEnum
    lessons_per_week: int = Field(default=1, ge=1)
    duration_minutes: int = Field(default=60, gt=0)
    preferred_teacher_id: Optional[int] = Field(default=None, ge=1)
    teacher_is_required: bool = False
    priority: int = Field(default=1, ge=1, le=3)
    notes: Optional[str] = None
    excluded_student_ids: list[int] = Field(default_factory=list)


class LessonRequestUpdate(SchemaBase):
    student_id: Optional[int] = Field(default=None, ge=1)
    subject_id: Optional[int] = Field(default=None, ge=1)
    lesson_type: Optional[LessonTypeEnum] = None
    lessons_per_week: Optional[int] = Field(default=None, ge=1)
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    preferred_teacher_id: Optional[int] = Field(default=None, ge=1)
    teacher_is_required: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=1, le=3)
    notes: Optional[str] = None
    excluded_student_ids: Optional[list[int]] = None


class LessonRequestList(LessonRequestBase):
    student: Optional[StudentBase] = None


# ---------------------------------------------------------------------------
# Price
# ---------------------------------------------------------------------------


class PriceBase(SchemaBase):
    id: int
    subject_id: int
    lesson_type: LessonTypeEnum
    min_participants: int = Field(ge=1)
    max_participants: int = Field(ge=1)
    price_per_student: float = Field(ge=0.0)
    subject: Optional[SubjectBase] = None


class PriceCreate(SchemaBase):
    subject_id: int = Field(..., ge=1)
    lesson_type: LessonTypeEnum
    min_participants: int = Field(..., ge=1)
    max_participants: int = Field(..., ge=1)
    price_per_student: float = Field(..., ge=0.0)

    @model_validator(mode="after")
    def _check_participants_range(self) -> "PriceCreate":
        if self.min_participants > self.max_participants:
            raise ValueError("min_participants must be <= max_participants")
        if self.lesson_type == LessonTypeEnum.individual:
            if self.min_participants != 1 or self.max_participants != 1:
                raise ValueError(
                    "Индивидуальное занятие — строго 1 участник"
                )
        return self


class PriceUpdate(SchemaBase):
    subject_id: Optional[int] = Field(default=None, ge=1)
    lesson_type: Optional[LessonTypeEnum] = None
    min_participants: Optional[int] = Field(default=None, ge=1)
    max_participants: Optional[int] = Field(default=None, ge=1)
    price_per_student: Optional[float] = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _check_participants_range(self) -> "PriceUpdate":
        if (
            self.min_participants is not None
            and self.max_participants is not None
            and self.min_participants > self.max_participants
        ):
            raise ValueError("min_participants must be <= max_participants")
        if self.lesson_type == LessonTypeEnum.individual:
            if (
                self.min_participants is not None
                and self.min_participants != 1
            ) or (
                self.max_participants is not None
                and self.max_participants != 1
            ):
                raise ValueError(
                    "Индивидуальное занятие — строго 1 участник"
                )
        return self


class PriceList(PriceBase):
    pass


class TeacherRateBase(SchemaBase):
    id: int
    teacher_id: Optional[int] = None
    subject_id: int
    lesson_type: LessonTypeEnum
    rate_type: RateTypeEnum = RateTypeEnum.fixed
    rate_per_lesson: float = Field(ge=0.0)
    is_default: bool = False
    teacher: Optional[TeacherBase] = None
    subject: Optional[SubjectBase] = None


class TeacherRateCreate(SchemaBase):
    teacher_id: Optional[int] = Field(default=None, ge=1)
    subject_id: int = Field(..., ge=1)
    lesson_type: LessonTypeEnum
    rate_type: RateTypeEnum = RateTypeEnum.fixed
    rate_per_lesson: float = Field(..., ge=0.0)


class TeacherRateUpdate(SchemaBase):
    teacher_id: Optional[int] = Field(default=None, ge=1)
    subject_id: Optional[int] = Field(default=None, ge=1)
    lesson_type: Optional[LessonTypeEnum] = None
    rate_type: Optional[RateTypeEnum] = None
    rate_per_lesson: Optional[float] = Field(default=None, ge=0.0)


class TeacherRateList(TeacherRateBase):
    pass


# ---------------------------------------------------------------------------
# Schedule + ScheduledLesson
# ---------------------------------------------------------------------------


class ScheduleBase(SchemaBase):
    id: int
    name: str
    week_start: date
    status: ScheduleStatusEnum = ScheduleStatusEnum.draft
    unscheduled_report: Optional[str] = None


class ScheduleCreate(SchemaBase):
    name: str = Field(..., min_length=1, max_length=200)
    week_start: date
    status: ScheduleStatusEnum = ScheduleStatusEnum.draft


class ScheduleUpdate(SchemaBase):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    week_start: Optional[date] = None
    status: Optional[ScheduleStatusEnum] = None
    unscheduled_report: Optional[str] = None


class ScheduledLessonBase(SchemaBase):
    id: int
    schedule_id: int
    lesson_type: LessonTypeEnum
    lesson_request_id: Optional[int] = None
    student_id: Optional[int] = None
    lesson_request_ids: list[int] = []
    day_of_week: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    teacher_id: int
    room_id: int


class ScheduledLessonParticipant(SchemaBase):
    lesson_request_id: int
    student: Optional[StudentBase] = None
    subject: Optional[SubjectBase] = None


class ScheduledLessonDetail(ScheduledLessonBase):
    schedule: Optional[ScheduleBase] = None
    lesson_request: Optional[LessonRequestBase] = None
    student: Optional[StudentBase] = None
    participants: list[ScheduledLessonParticipant] = []
    teacher: Optional[TeacherBase] = None
    room: Optional[RoomBase] = None


class ScheduledLessonCreate(SchemaBase):
    schedule_id: int = Field(..., ge=1)
    lesson_type: LessonTypeEnum
    lesson_request_id: Optional[int] = Field(default=None, ge=1)
    student_id: Optional[int] = Field(default=None, ge=1)
    lesson_request_ids: list[int] = Field(default_factory=list)
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    teacher_id: int = Field(..., ge=1)
    room_id: int = Field(..., ge=1)

    @model_validator(mode="after")
    def _check_times(self) -> "ScheduledLessonCreate":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class ScheduledLessonUpdate(SchemaBase):
    schedule_id: Optional[int] = Field(default=None, ge=1)
    lesson_type: Optional[LessonTypeEnum] = None
    lesson_request_id: Optional[int] = Field(default=None, ge=1)
    student_id: Optional[int] = Field(default=None, ge=1)
    lesson_request_ids: Optional[list[int]] = None
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    teacher_id: Optional[int] = Field(default=None, ge=1)
    room_id: Optional[int] = Field(default=None, ge=1)


class ScheduleList(ScheduleBase):
    lessons: list[ScheduledLessonBase] = []


# ---------------------------------------------------------------------------
# OptimizerSettings
# ---------------------------------------------------------------------------


class OptimizerSettingsBase(SchemaBase):
    id: int
    time_limit_seconds: int = Field(default=30, gt=0)
    weight_presence: float = Field(default=1000.0, ge=0.0)
    reward_preferred_teacher: float = Field(default=100.0, ge=0.0)
    penalty_student_same_day: float = Field(default=50.0, ge=0.0)
    penalty_early_late: float = Field(default=20.0, ge=0.0)
    early_hour: int = Field(default=9, ge=0, le=23)
    late_hour: int = Field(default=20, ge=0, le=23)
    weight_teacher_balance: float = Field(default=30.0, ge=0.0)
    weight_room_balance: float = Field(default=10.0, ge=0.0)
    group_min_size: int = Field(default=2, ge=2)
    group_max_size: int = Field(default=8, ge=2)

    @model_validator(mode="after")
    def _check_hours(self) -> "OptimizerSettingsBase":
        if self.early_hour >= self.late_hour:
            raise ValueError("early_hour must be earlier than late_hour")
        if self.group_min_size > self.group_max_size:
            raise ValueError("group_min_size must be <= group_max_size")
        return self


class OptimizerSettingsCreate(SchemaBase):
    time_limit_seconds: int = Field(default=30, gt=0)
    weight_presence: float = Field(default=1000.0, ge=0.0)
    reward_preferred_teacher: float = Field(default=100.0, ge=0.0)
    penalty_student_same_day: float = Field(default=50.0, ge=0.0)
    penalty_early_late: float = Field(default=20.0, ge=0.0)
    early_hour: int = Field(default=9, ge=0, le=23)
    late_hour: int = Field(default=20, ge=0, le=23)
    weight_teacher_balance: float = Field(default=30.0, ge=0.0)
    weight_room_balance: float = Field(default=10.0, ge=0.0)
    group_min_size: int = Field(default=2, ge=2)
    group_max_size: int = Field(default=8, ge=2)

    @model_validator(mode="after")
    def _check_hours(self) -> "OptimizerSettingsCreate":
        if self.early_hour >= self.late_hour:
            raise ValueError("early_hour must be earlier than late_hour")
        if self.group_min_size > self.group_max_size:
            raise ValueError("group_min_size must be <= group_max_size")
        return self


class OptimizerSettingsUpdate(SchemaBase):
    time_limit_seconds: Optional[int] = Field(default=None, gt=0)
    weight_presence: Optional[float] = Field(default=None, ge=0.0)
    reward_preferred_teacher: Optional[float] = Field(default=None, ge=0.0)
    penalty_student_same_day: Optional[float] = Field(default=None, ge=0.0)
    penalty_early_late: Optional[float] = Field(default=None, ge=0.0)
    early_hour: Optional[int] = Field(default=None, ge=0, le=23)
    late_hour: Optional[int] = Field(default=None, ge=0, le=23)
    weight_teacher_balance: Optional[float] = Field(default=None, ge=0.0)
    weight_room_balance: Optional[float] = Field(default=None, ge=0.0)
    group_min_size: Optional[int] = Field(default=None, ge=2)
    group_max_size: Optional[int] = Field(default=None, ge=2)


# ---------------------------------------------------------------------------
# Request / Response wrappers
# ---------------------------------------------------------------------------


class RequestWrapper(SchemaBase, Generic[T]):
    data: T


class DataResponse(SchemaBase, Generic[T]):
    data: T


class ListResponse(SchemaBase, Generic[T]):
    items: list[T]
    total: int


class IdResponse(SchemaBase):
    id: int


class MessageResponse(SchemaBase):
    message: str


# ---------------------------------------------------------------------------
# Schedule generation
# ---------------------------------------------------------------------------


class ScheduleGenerateRequest(SchemaBase):
    pass


class UnscheduledLessonReport(SchemaBase):
    identifier: str
    name: Optional[str] = None
    reason: str
    suggestions: list[str] = []
    level: str = "error"


class ScheduleGenerateResponse(SchemaBase):
    schedule_id: int
    status: ScheduleStatusEnum
    generated_at: datetime
    total_lessons: int
    scheduled_count: int
    unscheduled_count: int
    unscheduled_report: Optional[str] = None
    unscheduled: list[UnscheduledLessonReport] = []


class ExportFormat(str, Enum):
    png = "png"
    pdf = "pdf"
    xlsx = "xlsx"


class ExportRequest(SchemaBase):
    schedule_id: int = Field(..., ge=1)
    format: ExportFormat = ExportFormat.xlsx


# ---------------------------------------------------------------------------
# Manual editing + conflicts
# ---------------------------------------------------------------------------


class ConflictCheckRequest(SchemaBase):
    schedule_id: int = Field(..., ge=1)
    day_of_week: int = Field(..., ge=0, le=6)
    start_time: time
    end_time: time
    teacher_id: int = Field(..., ge=1)
    room_id: int = Field(..., ge=1)
    student_id: Optional[int] = Field(default=None, ge=1)
    lesson_request_ids: list[int] = Field(default_factory=list)
    exclude_lesson_id: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _check_times(self) -> "ConflictCheckRequest":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be earlier than end_time")
        return self


class ConflictType(str, Enum):
    teacher_busy = "teacher_busy"
    room_busy = "room_busy"
    student_busy = "student_busy"
    teacher_required = "teacher_required"
    room_capacity = "room_capacity"
    subject_mismatch = "subject_mismatch"


class ConflictDetail(SchemaBase):
    conflict_type: ConflictType
    message: str
    conflicting_lesson_id: Optional[int] = None


class ConflictCheckResponse(SchemaBase):
    has_conflicts: bool
    conflicts: list[ConflictDetail] = []


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------


class FinanceTeacherRow(SchemaBase):
    teacher_id: int
    teacher_name: str
    individual_lessons: int = 0
    group_lessons: int = 0
    total_lessons: int = 0
    total_pay: float = 0.0


class FinanceStudentRow(SchemaBase):
    student_id: int
    student_name: str
    individual_lessons: int = 0
    group_lessons: int = 0
    total_lessons: int = 0
    total_paid: float = 0.0


class FinanceDayRow(SchemaBase):
    """Финансы за один день недели (day_of_week: 0 = Пн, ..., 6 = Вс)."""
    day_of_week: int
    label: str
    individual_lessons: int = 0
    group_lessons: int = 0
    total_lessons: int = 0
    total_revenue: float = 0.0
    teacher_pay_total: float = 0.0


class FinanceSummary(SchemaBase):
    schedule_id: Optional[int] = None
    period_start: date
    period_end: date
    day_of_week: Optional[int] = None
    total_revenue: float = 0.0
    teacher_pay_total: float = 0.0
    net_revenue: float = 0.0
    total_lessons: int = 0
    individual_lessons: int = 0
    group_lessons: int = 0
    total_student_hours: float = 0.0
    average_lesson_price: float = 0.0
    revenue_by_subject: dict[str, float] = {}
    revenue_by_lesson_type: dict[str, float] = {}
    days: list[FinanceDayRow] = []
    teacher_breakdown: list[FinanceTeacherRow] = []
    student_breakdown: list[FinanceStudentRow] = []
    warnings: list[str] = []

    def model_post_init(self, __context) -> None:
        if self.total_lessons > 0:
            self.average_lesson_price = self.total_revenue / self.total_lessons
        self.net_revenue = round(self.total_revenue - self.teacher_pay_total, 2)