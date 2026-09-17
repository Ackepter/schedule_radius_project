from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.entities import LessonTypeEnum, TeacherRate
from app.schemas.schemas import (
    DataResponse,
    ListResponse,
    MessageResponse,
    TeacherRateBase,
    TeacherRateCreate,
    TeacherRateList,
    TeacherRateUpdate,
)
from app.services.pricing_service import validate_teacher_rate

router = APIRouter()


def _to_base(r: TeacherRate) -> TeacherRateList:
    return TeacherRateList(
        id=r.id,
        teacher_id=r.teacher_id,
        subject_id=r.subject_id,
        lesson_type=r.lesson_type,
        rate_per_lesson=r.rate_per_lesson,
        is_default=r.is_default,
        teacher=r.teacher,
        subject=r.subject,
    )


def _check_rate(body, db: Session) -> None:
    error = validate_teacher_rate(
        db, body.rate_per_lesson, body.subject_id, body.lesson_type
    )
    if error:
        raise HTTPException(status_code=400, detail=error)


@router.get("", response_model=ListResponse[TeacherRateBase])
def list_teacher_rates(
    subject_id: Optional[int] = Query(default=None),
    lesson_type: Optional[LessonTypeEnum] = Query(default=None),
    teacher_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = select(TeacherRate).options(
        selectinload(TeacherRate.teacher), selectinload(TeacherRate.subject)
    )
    if subject_id is not None:
        q = q.where(TeacherRate.subject_id == subject_id)
    if lesson_type is not None:
        q = q.where(TeacherRate.lesson_type == lesson_type)
    if teacher_id is not None:
        q = q.where(TeacherRate.teacher_id == teacher_id)
    q = q.order_by(TeacherRate.subject_id, TeacherRate.lesson_type, TeacherRate.teacher_id)
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[_to_base(r) for r in rows],
        total=len(rows),
    )


@router.post("", response_model=DataResponse[TeacherRateBase], status_code=201)
def create_teacher_rate(body: TeacherRateCreate, db: Session = Depends(get_db)):
    _check_rate(body, db)
    if body.teacher_id is not None:
        existing = db.execute(
            select(TeacherRate).where(
                TeacherRate.teacher_id == body.teacher_id,
                TeacherRate.subject_id == body.subject_id,
                TeacherRate.lesson_type == body.lesson_type,
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Для этого педагога уже задана ставка по данному направлению. Отредактируйте её.",
            )
    obj = TeacherRate(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=_to_base(obj))


@router.put("/{rate_id}", response_model=DataResponse[TeacherRateBase])
def update_teacher_rate(
    rate_id: int, body: TeacherRateUpdate, db: Session = Depends(get_db)
):
    obj = db.get(TeacherRate, rate_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Ставка не найдена")
    data = body.model_dump(exclude_unset=True)
    if "rate_per_lesson" in data:
        error = validate_teacher_rate(
            db,
            data["rate_per_lesson"],
            data.get("subject_id") or obj.subject_id,
            data.get("lesson_type") or obj.lesson_type,
        )
        if error:
            raise HTTPException(status_code=400, detail=error)
    for field, value in data.items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=_to_base(obj))


@router.delete("/{rate_id}", response_model=MessageResponse)
def delete_teacher_rate(rate_id: int, db: Session = Depends(get_db)):
    obj = db.get(TeacherRate, rate_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Ставка не найдена")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="Ставка удалена")