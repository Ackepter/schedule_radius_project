from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    LessonRequest,
    LessonTypeEnum,
    Price,
    ScheduledLesson,
    Schedule,
    Subject,
)
from app.schemas.schemas import FinanceSummary


def calculate_lesson_price(
    db: Session,
    subject_id: int,
    lesson_type: LessonTypeEnum,
    participant_count: int,
) -> float:
    price_row = db.execute(
        select(Price).where(
            and_(
                Price.subject_id == subject_id,
                Price.lesson_type == lesson_type,
                Price.min_participants <= participant_count,
                Price.max_participants >= participant_count,
            )
        )
    ).scalar_one_or_none()

    if price_row is None:
        return 0.0

    return price_row.price_per_student * participant_count


def calculate_schedule_revenue(
    db: Session, schedule_id: int
) -> FinanceSummary:
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        return FinanceSummary(
            schedule_id=schedule_id,
            period_start=date.today(),
            period_end=date.today(),
        )

    lessons = db.execute(
        select(ScheduledLesson)
        .options(
            selectinload(ScheduledLesson.lesson_request),
            selectinload(ScheduledLesson.student),
            selectinload(ScheduledLesson.participants),
        )
        .where(ScheduledLesson.schedule_id == schedule_id)
    ).scalars().all()

    total_revenue = 0.0
    individual_count = 0
    group_count = 0
    total_student_hours = 0.0
    revenue_by_subject: dict[str, float] = {}
    revenue_by_type: dict[str, float] = {}

    for sl in lessons:
        duration_hours = (
            sl.end_time.hour + sl.end_time.minute / 60.0
        ) - (sl.start_time.hour + sl.start_time.minute / 60.0)

        subject_id = None
        subject_name = "Unknown"
        if sl.lesson_request is not None:
            subject_id = sl.lesson_request.subject_id

        if subject_id is not None:
            subj = db.get(Subject, subject_id)
            if subj:
                subject_name = subj.name

        participant_count = 1
        if sl.lesson_type == LessonTypeEnum.group:
            participant_count = max(len(sl.participants), 1)
        elif sl.student_id is not None:
            participant_count = 1

        lesson_price = calculate_lesson_price(
            db, subject_id or 0, sl.lesson_type, participant_count
        )
        if lesson_price == 0.0 and subject_id is not None:
            lesson_price = participant_count * 50.0

        total_revenue += lesson_price
        total_student_hours += duration_hours * participant_count

        if sl.lesson_type == LessonTypeEnum.individual:
            individual_count += 1
        else:
            group_count += 1

        revenue_by_subject[subject_name] = (
            revenue_by_subject.get(subject_name, 0.0) + lesson_price
        )
        lesson_type_key = sl.lesson_type.value
        revenue_by_type[lesson_type_key] = (
            revenue_by_type.get(lesson_type_key, 0.0) + lesson_price
        )

    week_end = schedule.week_start
    from datetime import timedelta

    week_end = week_end + timedelta(days=6)

    total_lessons = individual_count + group_count

    return FinanceSummary(
        schedule_id=schedule_id,
        period_start=schedule.week_start,
        period_end=week_end,
        total_revenue=round(total_revenue, 2),
        total_lessons=total_lessons,
        individual_lessons=individual_count,
        group_lessons=group_count,
        total_student_hours=round(total_student_hours, 2),
        average_lesson_price=(
            round(total_revenue / total_lessons, 2)
            if total_lessons > 0
            else 0.0
        ),
        revenue_by_subject=revenue_by_subject,
        revenue_by_lesson_type=revenue_by_type,
    )
