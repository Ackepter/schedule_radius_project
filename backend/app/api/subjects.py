from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import Subject
from app.schemas.schemas import (
    DataResponse,
    ListResponse,
    MessageResponse,
    SubjectBase,
    SubjectCreate,
    SubjectUpdate,
)

router = APIRouter()


@router.get("", response_model=ListResponse[SubjectBase])
def list_subjects(
    is_active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = select(Subject)
    if is_active is not None:
        q = q.where(Subject.is_active == is_active)
    q = q.order_by(Subject.name)
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[SubjectBase.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("", response_model=DataResponse[SubjectBase], status_code=201)
def create_subject(body: SubjectCreate, db: Session = Depends(get_db)):
    obj = Subject(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=SubjectBase.model_validate(obj))


@router.get("/{subject_id}", response_model=DataResponse[SubjectBase])
def get_subject(subject_id: int, db: Session = Depends(get_db)):
    obj = db.get(Subject, subject_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Subject not found")
    return DataResponse(data=SubjectBase.model_validate(obj))


@router.put("/{subject_id}", response_model=DataResponse[SubjectBase])
def update_subject(
    subject_id: int, body: SubjectUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Subject, subject_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Subject not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=SubjectBase.model_validate(obj))


@router.delete("/{subject_id}", response_model=MessageResponse)
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    obj = db.get(Subject, subject_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Subject not found")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="Subject deleted")
