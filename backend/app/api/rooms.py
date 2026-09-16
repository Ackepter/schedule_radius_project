from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.entities import Room, Subject
from app.schemas.schemas import (
    DataResponse,
    ListResponse,
    MessageResponse,
    RoomBase,
    RoomCreate,
    RoomList,
    RoomUpdate,
)

router = APIRouter()


@router.get("", response_model=ListResponse[RoomList])
def list_rooms(
    subject_id: Optional[int] = Query(default=None),
    min_capacity: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = select(Room).options(selectinload(Room.allowed_subjects))
    if min_capacity is not None:
        q = q.where(Room.capacity >= min_capacity)
    if subject_id is not None:
        from app.models.entities import room_subjects

        q = q.join(room_subjects).where(
            room_subjects.c.subject_id == subject_id
        )
    q = q.order_by(Room.name)
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[RoomList.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("", response_model=DataResponse[RoomBase], status_code=201)
def create_room(body: RoomCreate, db: Session = Depends(get_db)):
    obj = Room(
        name=body.name,
        capacity=body.capacity,
        comment=body.comment,
    )
    if body.allowed_subject_ids:
        subjects = db.execute(
            select(Subject).where(Subject.id.in_(body.allowed_subject_ids))
        ).scalars().all()
        obj.allowed_subjects = list(subjects)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=RoomBase.model_validate(obj))


@router.get("/{room_id}", response_model=DataResponse[RoomBase])
def get_room(room_id: int, db: Session = Depends(get_db)):
    q = (
        select(Room)
        .options(selectinload(Room.allowed_subjects))
        .where(Room.id == room_id)
    )
    obj = db.execute(q).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Room not found")
    return DataResponse(data=RoomBase.model_validate(obj))


@router.put("/{room_id}", response_model=DataResponse[RoomBase])
def update_room(
    room_id: int, body: RoomUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Room, room_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Room not found")
    update_data = body.model_dump(exclude_unset=True)
    allowed_subject_ids = update_data.pop("allowed_subject_ids", None)
    for field, value in update_data.items():
        setattr(obj, field, value)
    if allowed_subject_ids is not None:
        subjects = db.execute(
            select(Subject).where(Subject.id.in_(allowed_subject_ids))
        ).scalars().all()
        obj.allowed_subjects = list(subjects)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=RoomBase.model_validate(obj))


@router.delete("/{room_id}", response_model=MessageResponse)
def delete_room(room_id: int, db: Session = Depends(get_db)):
    obj = db.get(Room, room_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Кабинет не найден")
    from app.models.entities import ScheduledLesson

    ref_lessons = (
        db.query(ScheduledLesson).filter(ScheduledLesson.room_id == room_id).count()
    )
    if ref_lessons:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Нельзя удалить кабинет: в расписании есть {ref_lessons} "
                "занятий в этом кабинете. Сначала удалите их из расписания."
            ),
        )
    try:
        db.delete(obj)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить кабинет: есть связанные данные. "
            "Удалите связанные записи и повторите.",
        ) from exc
    return MessageResponse(message="Кабинет удалён")
