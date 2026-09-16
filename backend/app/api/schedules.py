from datetime import date

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.entities import ScheduledLesson, Schedule
from app.schemas.schemas import (
    ConflictCheckRequest,
    ConflictCheckResponse,
    DataResponse,
    ListResponse,
    MessageResponse,
    ScheduleBase,
    ScheduleCreate,
    ScheduleGenerateResponse,
    ScheduleList,
    ScheduleUpdate,
    ScheduledLessonBase,
    ScheduledLessonCreate,
    ScheduledLessonDetail,
    ScheduledLessonUpdate,
)
from app.services.conflict_service import check_conflicts
from app.services.schedule_service import generate_schedule

router = APIRouter()


@router.post("/generate", response_model=DataResponse[ScheduleGenerateResponse])
def generate(db: Session = Depends(get_db)):
    """Автоматически составить расписание на текущую неделю."""
    try:
        result = generate_schedule(
            db,
            name=f"Неделя с {date.today().isoformat()}",
            week_start=date.today(),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DataResponse(data=result)


# ── Schedules ──────────────────────────────────────────────────────────────

@router.get("", response_model=ListResponse[ScheduleList])
def list_schedules(db: Session = Depends(get_db)):
    q = select(Schedule).options(
        selectinload(Schedule.lessons),
    ).order_by(Schedule.week_start.desc())
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[ScheduleList.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("", response_model=DataResponse[ScheduleBase], status_code=201)
def create_schedule(body: ScheduleCreate, db: Session = Depends(get_db)):
    obj = Schedule(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=ScheduleBase.model_validate(obj))


@router.get("/{schedule_id}", response_model=DataResponse[ScheduleList])
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    q = (
        select(Schedule)
        .options(selectinload(Schedule.lessons))
        .where(Schedule.id == schedule_id)
    )
    obj = db.execute(q).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return DataResponse(data=ScheduleList.model_validate(obj))


@router.put("/{schedule_id}", response_model=DataResponse[ScheduleBase])
def update_schedule(
    schedule_id: int, body: ScheduleUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Schedule, schedule_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Schedule not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=ScheduleBase.model_validate(obj))


@router.delete("/{schedule_id}", response_model=MessageResponse)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    obj = db.get(Schedule, schedule_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="Schedule deleted")


# ── Scheduled Lessons (filtered) ──────────────────────────────────────────

@router.post(
    "/{schedule_id}/lessons",
    response_model=DataResponse[ScheduledLessonDetail],
    status_code=201,
)
def create_scheduled_lesson(
    schedule_id: int,
    body: ScheduledLessonCreate,
    db: Session = Depends(get_db),
):
    if body.schedule_id != schedule_id:
        raise HTTPException(status_code=400, detail="schedule_id mismatch")
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    obj = ScheduledLesson(**body.model_dump())
    db.add(obj)
    db.flush()

    student_ids: list[int] = []
    subject_id = None
    if obj.student_id is not None:
        student_ids = [obj.student_id]
    if obj.lesson_request_id is not None:
        lr = obj.lesson_request
        if lr:
            subject_id = lr.subject_id
    if obj.group_lesson_id is not None:
        from app.models.entities import group_lesson_participants

        rows = db.execute(
            select(group_lesson_participants.c.student_id).where(
                group_lesson_participants.c.group_lesson_id == obj.group_lesson_id
            )
        ).scalars().all()
        student_ids = list(rows)
        gl = obj.group_lesson
        if gl:
            subject_id = gl.subject_id

    conflicts = check_conflicts(
        db=db,
        schedule_id=schedule_id,
        day_of_week=obj.day_of_week,
        start_time=obj.start_time,
        end_time=obj.end_time,
        teacher_id=obj.teacher_id,
        room_id=obj.room_id,
        student_ids=student_ids,
        exclude_lesson_id=obj.id,
        subject_id=subject_id,
    )
    if conflicts:
        from fastapi.responses import JSONResponse

        db.rollback()
        return JSONResponse(
            status_code=409,
            content=ConflictCheckResponse(
                has_conflicts=True, conflicts=conflicts
            ).model_dump(),
        )

    db.commit()
    db.refresh(obj)
    return DataResponse(data=ScheduledLessonDetail.model_validate(obj))


@router.get(
    "/{schedule_id}/lessons",
    response_model=ListResponse[ScheduledLessonDetail],
)
def list_scheduled_lessons(
    schedule_id: int,
    student_id: Optional[int] = Query(default=None),
    teacher_id: Optional[int] = Query(default=None),
    room_id: Optional[int] = Query(default=None),
    group_lesson_id: Optional[int] = Query(default=None),
    day_of_week: Optional[int] = Query(default=None, ge=0, le=6),
    db: Session = Depends(get_db),
):
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    q = (
        select(ScheduledLesson)
        .options(
            selectinload(ScheduledLesson.schedule),
            selectinload(ScheduledLesson.lesson_request),
            selectinload(ScheduledLesson.student),
            selectinload(ScheduledLesson.group_lesson),
            selectinload(ScheduledLesson.teacher),
            selectinload(ScheduledLesson.room),
        )
        .where(ScheduledLesson.schedule_id == schedule_id)
    )
    if student_id is not None:
        q = q.where(ScheduledLesson.student_id == student_id)
    if teacher_id is not None:
        q = q.where(ScheduledLesson.teacher_id == teacher_id)
    if room_id is not None:
        q = q.where(ScheduledLesson.room_id == room_id)
    if group_lesson_id is not None:
        q = q.where(ScheduledLesson.group_lesson_id == group_lesson_id)
    if day_of_week is not None:
        q = q.where(ScheduledLesson.day_of_week == day_of_week)

    q = q.order_by(ScheduledLesson.day_of_week, ScheduledLesson.start_time)
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[ScheduledLessonDetail.model_validate(r) for r in rows],
        total=len(rows),
    )


# ── Single Scheduled Lesson CRUD ──────────────────────────────────────────

@router.get(
    "/scheduled-lessons/{lesson_id}",
    response_model=DataResponse[ScheduledLessonDetail],
)
def get_scheduled_lesson(lesson_id: int, db: Session = Depends(get_db)):
    q = (
        select(ScheduledLesson)
        .options(
            selectinload(ScheduledLesson.schedule),
            selectinload(ScheduledLesson.lesson_request),
            selectinload(ScheduledLesson.student),
            selectinload(ScheduledLesson.group_lesson),
            selectinload(ScheduledLesson.teacher),
            selectinload(ScheduledLesson.room),
        )
        .where(ScheduledLesson.id == lesson_id)
    )
    obj = db.execute(q).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Scheduled lesson not found")
    return DataResponse(data=ScheduledLessonDetail.model_validate(obj))


@router.put(
    "/scheduled-lessons/{lesson_id}",
    response_model=DataResponse[ScheduledLessonDetail],
)
def update_scheduled_lesson(
    lesson_id: int,
    body: ScheduledLessonUpdate,
    db: Session = Depends(get_db),
):
    obj = db.get(ScheduledLesson, lesson_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Scheduled lesson not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(obj, field, value)

    db.flush()

    student_ids: list[int] = []
    subject_id = None
    if obj.lesson_request_id is not None and obj.lesson_request:
        subject_id = obj.lesson_request.subject_id
    if obj.group_lesson_id is not None and obj.group_lesson:
        subject_id = obj.group_lesson.subject_id
    if obj.student_id is not None:
        student_ids = [obj.student_id]
    if obj.group_lesson_id is not None:
        from app.models.entities import group_lesson_participants

        rows = db.execute(
            select(group_lesson_participants.c.student_id).where(
                group_lesson_participants.c.group_lesson_id == obj.group_lesson_id
            )
        ).scalars().all()
        student_ids = list(rows)

    conflicts = check_conflicts(
        db=db,
        schedule_id=obj.schedule_id,
        day_of_week=obj.day_of_week,
        start_time=obj.start_time,
        end_time=obj.end_time,
        teacher_id=obj.teacher_id,
        room_id=obj.room_id,
        student_ids=student_ids,
        exclude_lesson_id=obj.id,
        subject_id=subject_id,
    )
    if conflicts:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=409,
            content=ConflictCheckResponse(
                has_conflicts=True, conflicts=conflicts
            ).model_dump(),
        )

    db.commit()
    db.refresh(obj)
    return DataResponse(data=ScheduledLessonDetail.model_validate(obj))


@router.delete("/scheduled-lessons/{lesson_id}", response_model=MessageResponse)
def delete_scheduled_lesson(lesson_id: int, db: Session = Depends(get_db)):
    obj = db.get(ScheduledLesson, lesson_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Scheduled lesson not found")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="Scheduled lesson deleted")


# ── Conflict check endpoint ───────────────────────────────────────────────

@router.post(
    "/{schedule_id}/conflict-check",
    response_model=ConflictCheckResponse,
)
def conflict_check(
    schedule_id: int,
    body: ConflictCheckRequest,
    db: Session = Depends(get_db),
):
    student_ids: list[int] = []
    subject_id = None
    if body.student_id is not None:
        student_ids = [body.student_id]
    if body.group_lesson_id is not None:
        from sqlalchemy import select as sel
        from app.models.entities import group_lesson_participants, GroupLesson

        rows = db.execute(
            sel(group_lesson_participants.c.student_id).where(
                group_lesson_participants.c.group_lesson_id == body.group_lesson_id
            )
        ).scalars().all()
        student_ids = list(rows)
        gl = db.get(GroupLesson, body.group_lesson_id)
        if gl:
            subject_id = gl.subject_id
    if body.exclude_lesson_id is not None:
        existing = db.get(ScheduledLesson, body.exclude_lesson_id)
        if existing and existing.lesson_request_id:
            subject_id = (
                existing.lesson_request.subject_id
                if existing.lesson_request
                else None
            )
        if existing and existing.group_lesson_id and existing.group_lesson:
            subject_id = existing.group_lesson.subject_id

    conflicts = check_conflicts(
        db=db,
        schedule_id=schedule_id,
        day_of_week=body.day_of_week,
        start_time=body.start_time,
        end_time=body.end_time,
        teacher_id=body.teacher_id,
        room_id=body.room_id,
        student_ids=student_ids,
        exclude_lesson_id=body.exclude_lesson_id,
        subject_id=subject_id,
    )
    return ConflictCheckResponse(
        has_conflicts=len(conflicts) > 0,
        conflicts=conflicts,
    )
