from datetime import date, timedelta
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    LessonTypeEnum,
    Price,
    ScheduledLesson,
    Schedule,
    Student,
    Subject,
    TeacherRate,
)
from app.schemas.schemas import (
    FinanceStudentRow,
    FinanceSummary,
    FinanceTeacherRow,
)


def calculate_lesson_price(
    db: Session,
    subject_id: int,
    lesson_type: LessonTypeEnum,
    participant_count: int,
) -> float:
    """Выручка центра с одного занятия (сумма оплат учеников)."""
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


def min_lesson_revenue(
    db: Session, subject_id: int, lesson_type: LessonTypeEnum
) -> float:
    """Минимальная выручка центра с занятия данного типа (самый ранний тариф)."""
    price_row = db.execute(
        select(Price)
        .where(
            and_(
                Price.subject_id == subject_id,
                Price.lesson_type == lesson_type,
            )
        )
        .order_by(Price.min_participants)
    ).scalars().first()

    if price_row is None:
        return 0.0
    return price_row.price_per_student * price_row.min_participants


def get_teacher_rate(
    db: Session,
    teacher_id: int,
    subject_id: int,
    lesson_type: LessonTypeEnum,
) -> float:
    """Ставка педагога за одно занятие: индивидуальная, иначе умолчание, иначе 0."""
    rows = db.execute(
        select(TeacherRate).where(
            TeacherRate.subject_id == subject_id,
            TeacherRate.lesson_type == lesson_type,
        )
    ).scalars().all()
    for r in rows:
        if r.teacher_id == teacher_id:
            return r.rate_per_lesson
    for r in rows:
        if r.teacher_id is None:
            return r.rate_per_lesson
    return 0.0


def validate_teacher_rate(
    db: Session,
    rate: float,
    subject_id: int,
    lesson_type: LessonTypeEnum,
) -> Optional[str]:
    """Возвращает текст ошибки, если ставка превышает выручку центра с занятия."""
    if lesson_type == LessonTypeEnum.both:
        lesson_type = LessonTypeEnum.individual
    allowed = min_lesson_revenue(db, subject_id, lesson_type)
    if allowed <= 0:
        return (
            "Не задана цена занятия для учеников. "
            "Сначала укажите стоимость занятия на вкладке «Тарифы учеников»."
        )
    if rate > allowed:
        return (
            f"Ставка педагога ({rate:g} ₽) превышает выручку центра с занятия "
            f"({allowed:g} ₽). Такая ситуация недопустима — оплата педагога "
            "должна быть не больше, чем центр зарабатывает на занятии."
        )
    return None


def _participant_count(sl: ScheduledLesson) -> int:
    if sl.lesson_type == LessonTypeEnum.group:
        return max(len(sl.participants), 1)
    return 1


def _lesson_duration_hours(sl: ScheduledLesson) -> float:
    return (sl.end_time.hour + sl.end_time.minute / 60.0) - (
        sl.start_time.hour + sl.start_time.minute / 60.0
    )


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
            selectinload(ScheduledLesson.teacher),
        )
        .where(ScheduledLesson.schedule_id == schedule_id)
    ).scalars().all()

    subject_names: dict[int, str] = {}
    for s in db.execute(select(Subject)).scalars():
        subject_names[s.id] = s.name

    total_revenue = 0.0
    teacher_pay_total = 0.0
    individual_count = 0
    group_count = 0
    total_student_hours = 0.0
    revenue_by_subject: dict[str, float] = {}
    revenue_by_type: dict[str, float] = {}
    warnings: list[str] = []

    teacher_pay_by_id: dict[int, dict] = {}
    student_paid_by_id: dict[int, dict] = {}

    for sl in lessons:
        duration_hours = _lesson_duration_hours(sl)
        subject_id = sl.lesson_request.subject_id if sl.lesson_request else None
        subject_name = subject_names.get(subject_id, "Unknown") if subject_id else "Unknown"

        participant_count = _participant_count(sl)
        lesson_revenue = calculate_lesson_price(
            db, subject_id or 0, sl.lesson_type, participant_count
        )
        if lesson_revenue == 0.0 and subject_id is not None:
            lesson_revenue = participant_count * 50.0
            warnings.append(
                f"«{subject_name}»: цена занятия не задана, применена заглушка "
                f"{50:g} ₽ × {participant_count} чел."
            )

        teacher_rate = 0.0
        if sl.teacher_id is not None and subject_id is not None:
            teacher_rate = get_teacher_rate(
                db, sl.teacher_id, subject_id, sl.lesson_type
            )
            if teacher_rate == 0.0:
                warnings.append(
                    f"«{subject_name}»: для педагога "
                    f"{sl.teacher.full_name if sl.teacher else '—'} не задана ставка, "
                    "оплата 0 ₽."
                )
            elif teacher_rate > lesson_revenue:
                warnings.append(
                    f"«{subject_name}»: оплата педагога "
                    f"{sl.teacher.full_name if sl.teacher else '—'} "
                    f"({teacher_rate:g} ₽) превышает выручку центра с занятия "
                    f"({lesson_revenue:g} ₽). Проверьте ставки."
                )

        total_revenue += lesson_revenue
        teacher_pay_total += teacher_rate
        total_student_hours += duration_hours * participant_count

        if sl.lesson_type == LessonTypeEnum.individual:
            individual_count += 1
        else:
            group_count += 1

        revenue_by_subject[subject_name] = (
            revenue_by_subject.get(subject_name, 0.0) + lesson_revenue
        )
        lesson_type_key = sl.lesson_type.value
        revenue_by_type[lesson_type_key] = (
            revenue_by_type.get(lesson_type_key, 0.0) + lesson_revenue
        )

        if sl.teacher_id is not None:
            rec = teacher_pay_by_id.setdefault(
                sl.teacher_id,
                {
                    "teacher_id": sl.teacher_id,
                    "teacher_name": sl.teacher.full_name if sl.teacher else "—",
                    "individual_lessons": 0,
                    "group_lessons": 0,
                    "total_pay": 0.0,
                },
            )
            if sl.lesson_type == LessonTypeEnum.individual:
                rec["individual_lessons"] += 1
            else:
                rec["group_lessons"] += 1
            rec["total_pay"] += teacher_rate

        per_student_payment = 0.0
        if sl.lesson_type == LessonTypeEnum.individual:
            per_student_payment = lesson_revenue
        else:
            price_row = db.execute(
                select(Price).where(
                    and_(
                        Price.subject_id == subject_id,
                        Price.lesson_type == sl.lesson_type,
                        Price.min_participants <= participant_count,
                        Price.max_participants >= participant_count,
                    )
                )
            ).scalar_one_or_none()
            per_student_payment = (
                price_row.price_per_student if price_row else 0.0
            )

        student_ids: list[int] = []
        if sl.lesson_type == LessonTypeEnum.group:
            student_ids = [p.student_id for p in sl.participants if p.student_id]
        elif sl.student_id is not None:
            student_ids = [sl.student_id]

        for sid in student_ids:
            rec = student_paid_by_id.setdefault(
                sid,
                {
                    "student_id": sid,
                    "student_name": f"Ученик #{sid}",
                    "individual_lessons": 0,
                    "group_lessons": 0,
                    "total_paid": 0.0,
                },
            )
            rec["total_paid"] += per_student_payment
            if sl.lesson_type == LessonTypeEnum.individual:
                rec["individual_lessons"] += 1
            else:
                rec["group_lessons"] += 1

    week_end = schedule.week_start + timedelta(days=6)
    total_lessons = individual_count + group_count

    if student_paid_by_id:
        students = db.execute(
            select(Student).where(Student.id.in_(student_paid_by_id.keys()))
        ).scalars().all()
        for st in students:
            rec = student_paid_by_id.get(st.id)
            if rec is not None:
                rec["student_name"] = st.full_name

    teacher_breakdown = [
        FinanceTeacherRow(
            teacher_id=r["teacher_id"],
            teacher_name=r["teacher_name"],
            individual_lessons=r["individual_lessons"],
            group_lessons=r["group_lessons"],
            total_lessons=r["individual_lessons"] + r["group_lessons"],
            total_pay=round(r["total_pay"], 2),
        )
        for r in teacher_pay_by_id.values()
    ]
    student_breakdown = [
        FinanceStudentRow(
            student_id=r["student_id"],
            student_name=r["student_name"],
            individual_lessons=r["individual_lessons"],
            group_lessons=r["group_lessons"],
            total_lessons=r["individual_lessons"] + r["group_lessons"],
            total_paid=round(r["total_paid"], 2),
        )
        for r in student_paid_by_id.values()
    ]

    return FinanceSummary(
        schedule_id=schedule_id,
        period_start=schedule.week_start,
        period_end=week_end,
        total_revenue=round(total_revenue, 2),
        teacher_pay_total=round(teacher_pay_total, 2),
        total_lessons=total_lessons,
        individual_lessons=individual_count,
        group_lessons=group_count,
        total_student_hours=round(total_student_hours, 2),
        average_lesson_price=(
            round(total_revenue / total_lessons, 2) if total_lessons > 0 else 0.0
        ),
        revenue_by_subject=revenue_by_subject,
        revenue_by_lesson_type=revenue_by_type,
        teacher_breakdown=teacher_breakdown,
        student_breakdown=student_breakdown,
        warnings=warnings,
    )