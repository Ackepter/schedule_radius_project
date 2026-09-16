from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.entities import LessonTypeEnum, Price
from app.schemas.schemas import (
    DataResponse,
    ListResponse,
    MessageResponse,
    PriceBase,
    PriceCreate,
    PriceUpdate,
)

router = APIRouter()


@router.get("", response_model=ListResponse[PriceBase])
def list_prices(
    subject_id: Optional[int] = Query(default=None),
    lesson_type: Optional[LessonTypeEnum] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = select(Price).options(selectinload(Price.subject))
    if subject_id is not None:
        q = q.where(Price.subject_id == subject_id)
    if lesson_type is not None:
        q = q.where(Price.lesson_type == lesson_type)
    q = q.order_by(Price.subject_id, Price.min_participants)
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[PriceBase.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("", response_model=DataResponse[PriceBase], status_code=201)
def create_price(body: PriceCreate, db: Session = Depends(get_db)):
    obj = Price(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=PriceBase.model_validate(obj))


@router.put("/{price_id}", response_model=DataResponse[PriceBase])
def update_price(
    price_id: int, body: PriceUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Price, price_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Price not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=PriceBase.model_validate(obj))


@router.delete("/{price_id}", response_model=MessageResponse)
def delete_price(price_id: int, db: Session = Depends(get_db)):
    obj = db.get(Price, price_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Price not found")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="Price deleted")
