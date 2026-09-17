import json
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    LessonRequest,
    Schedule,
    ScheduleStatusEnum,
    ScheduledLesson,
)
from app.optimizer.scheduler import (
    ScheduleResult,
    run_schedule_generation,
)
from app.schemas.schemas import ScheduleGenerateResponse, UnscheduledLessonReport


def generate_schedule(db: Session, name: str, week_start: date) -> ScheduleGenerateResponse:
    result: ScheduleResult = run_schedule_generation(db, name, week_start)

    if not result.success:
        raise RuntimeError(result.message)

    # Создаём расписание и сохраняем уроки
    schedule = Schedule(
        name=name,
        week_start=week_start,
        status=ScheduleStatusEnum.draft,
    )
    db.add(schedule)
    db.flush()

    for item in result.scheduled:
        lesson_request_ids = item.get("lesson_request_ids") or []
        participants = (
            db.execute(
                select(LessonRequest).where(
                    LessonRequest.id.in_(lesson_request_ids)
                )
            ).scalars().all()
            if lesson_request_ids
            else []
        )
        sl = ScheduledLesson(
            schedule_id=schedule.id,
            lesson_type=item["lesson_type"],
            lesson_request_id=item.get("lesson_request_id"),
            student_id=item.get("student_id"),
            day_of_week=item["day_of_week"],
            start_time=item["start_time"],
            end_time=item["end_time"],
            teacher_id=item["teacher_id"],
            room_id=item["room_id"],
            participants=participants,
        )
        db.add(sl)

    # Сохраняем отчёт о неразмещённых занятиях
    report_payload = {
        "scheduled_count": len(result.scheduled),
        "unscheduled_count": len(result.unscheduled),
        "unscheduled": [
            {
                "identifier": u.identifier,
                "name": u.name,
                "reason": u.reason,
                "suggestions": u.suggestions,
                "level": u.level,
            }
            for u in result.unscheduled
        ],
    }
    schedule.unscheduled_report = json.dumps(report_payload, ensure_ascii=False)
    db.commit()
    db.refresh(schedule)

    return ScheduleGenerateResponse(
        schedule_id=schedule.id,
        status=schedule.status,
        generated_at=datetime.utcnow(),
        total_lessons=result.total_lessons,
        scheduled_count=len(result.scheduled),
        unscheduled_count=len(result.unscheduled),
        unscheduled_report=json.dumps(report_payload, ensure_ascii=False),
        unscheduled=[
            UnscheduledLessonReport(
                identifier=u.identifier, name=u.name, reason=u.reason, suggestions=u.suggestions, level=u.level
            )
            for u in result.unscheduled
        ],
    )