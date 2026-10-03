from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import Availability, EntityTypeEnum
from app.schemas.schemas import (
    AvailabilityBase,
    AvailabilityBulkCreate,
    AvailabilityBulkResult,
    AvailabilityCreate,
    AvailabilityUpdate,
    DataResponse,
    ListResponse,
    MessageResponse,
)

router = APIRouter()


@router.get("", response_model=ListResponse[AvailabilityBase])
def list_availabilities(
    entity_type: Optional[EntityTypeEnum] = Query(default=None),
    entity_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = select(Availability)
    if entity_type is not None:
        q = q.where(Availability.entity_type == entity_type)
    if entity_id is not None:
        q = q.where(Availability.entity_id == entity_id)
    q = q.order_by(Availability.day_of_week, Availability.start_time)
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[AvailabilityBase.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post(
    "", response_model=DataResponse[AvailabilityBase], status_code=201
)
def create_availability(
    body: AvailabilityCreate, db: Session = Depends(get_db)
):
    obj = Availability(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=AvailabilityBase.model_validate(obj))


@router.put("/{avail_id}", response_model=DataResponse[AvailabilityBase])
def update_availability(
    avail_id: int, body: AvailabilityUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Availability, avail_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Availability not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=AvailabilityBase.model_validate(obj))


@router.delete("/bulk", response_model=MessageResponse)
def bulk_delete_availabilities(
    entity_type: EntityTypeEnum = Query(...),
    entity_id: int = Query(...),
    db: Session = Depends(get_db),
):
    stmt = select(Availability).where(
        and_(
            Availability.entity_type == entity_type,
            Availability.entity_id == entity_id,
        )
    )
    rows = db.execute(stmt).scalars().all()
    count = len(rows)
    for row in rows:
        db.delete(row)
    db.commit()
    return MessageResponse(message=f"Deleted {count} availabilities")


@router.post(
    "/bulk", response_model=DataResponse[AvailabilityBulkResult], status_code=201
)
def bulk_create_availabilities(
    body: AvailabilityBulkCreate, db: Session = Depends(get_db)
):
    """Создаёт один и тот же интервал доступности сразу на выбранные дни недели.

    Точные дубликаты (день + начало + конец) пропускаются, чтобы не плодить
    пересекающиеся интервалы при повторном нажатии «Добавить».
    """
    days = body.unique_days

    removed = 0
    if body.replace:
        stmt = select(Availability).where(
            and_(
                Availability.entity_type == body.entity_type,
                Availability.entity_id == body.entity_id,
            )
        )
        for row in db.execute(stmt).scalars().all():
            db.delete(row)
            removed += 1
        db.flush()

    existing = set(
        db.execute(
            select(Availability.day_of_week, Availability.start_time, Availability.end_time).where(
                and_(
                    Availability.entity_type == body.entity_type,
                    Availability.entity_id == body.entity_id,
                )
            )
        ).all()
    )

    created: list[Availability] = []
    skipped = 0
    for day in days:
        key = (day, body.start_time, body.end_time)
        if key in existing:
            skipped += 1
            continue
        obj = Availability(
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            day_of_week=day,
            start_time=body.start_time,
            end_time=body.end_time,
        )
        db.add(obj)
        created.append(obj)
        existing.add(key)

    db.commit()
    for obj in created:
        db.refresh(obj)

    return DataResponse(
        data=AvailabilityBulkResult(
            created=len(created),
            skipped=skipped,
            removed=removed,
            items=[AvailabilityBase.model_validate(o) for o in created],
        )
    )


@router.delete("/{avail_id}", response_model=MessageResponse)
def delete_availability(avail_id: int, db: Session = Depends(get_db)):
    obj = db.get(Availability, avail_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Availability not found")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="Availability deleted")
