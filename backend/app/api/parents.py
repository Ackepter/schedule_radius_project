from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.entities import Parent
from app.schemas.schemas import (
    DataResponse,
    ListResponse,
    MessageResponse,
    ParentBase,
    ParentCreate,
    ParentList,
    ParentUpdate,
)

router = APIRouter()


@router.get("", response_model=ListResponse[ParentList])
def list_parents(db: Session = Depends(get_db)):
    q = select(Parent).options(
        selectinload(Parent.students),
    ).order_by(Parent.last_name, Parent.first_name)
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[ParentList.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("", response_model=DataResponse[ParentBase], status_code=201)
def create_parent(body: ParentCreate, db: Session = Depends(get_db)):
    obj = Parent(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=ParentBase.model_validate(obj))


@router.get("/{parent_id}", response_model=DataResponse[ParentList])
def get_parent(parent_id: int, db: Session = Depends(get_db)):
    q = (
        select(Parent)
        .options(selectinload(Parent.students))
        .where(Parent.id == parent_id)
    )
    obj = db.execute(q).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Parent not found")
    return DataResponse(data=ParentList.model_validate(obj))


@router.put("/{parent_id}", response_model=DataResponse[ParentBase])
def update_parent(
    parent_id: int, body: ParentUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Parent, parent_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Parent not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=ParentBase.model_validate(obj))


@router.delete("/{parent_id}", response_model=MessageResponse)
def delete_parent(parent_id: int, db: Session = Depends(get_db)):
    obj = db.get(Parent, parent_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Parent not found")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="Parent deleted")
