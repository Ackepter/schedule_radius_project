from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.entities import LessonRequest, LessonTypeEnum
from app.schemas.schemas import (
    DataResponse,
    ListResponse,
    MessageResponse,
    LessonRequestBase,
    LessonRequestCreate,
    LessonRequestList,
    LessonRequestUpdate,
)

router = APIRouter()


@router.get("", response_model=ListResponse[LessonRequestList])
def list_lesson_requests(
    student_id: Optional[int] = Query(default=None),
    subject_id: Optional[int] = Query(default=None),
    lesson_type: Optional[LessonTypeEnum] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = select(LessonRequest).options(
        selectinload(LessonRequest.student),
        selectinload(LessonRequest.subject),
        selectinload(LessonRequest.preferred_teacher),
    )
    if student_id is not None:
        q = q.where(LessonRequest.student_id == student_id)
    if subject_id is not None:
        q = q.where(LessonRequest.subject_id == subject_id)
    if lesson_type is not None:
        q = q.where(LessonRequest.lesson_type == lesson_type)
    q = q.order_by(LessonRequest.id)
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[LessonRequestList.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post(
    "", response_model=DataResponse[LessonRequestBase], status_code=201
)
def create_lesson_request(
    body: LessonRequestCreate, db: Session = Depends(get_db)
):
    obj = LessonRequest(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=LessonRequestBase.model_validate(obj))


@router.get("/{lr_id}", response_model=DataResponse[LessonRequestList])
def get_lesson_request(lr_id: int, db: Session = Depends(get_db)):
    q = (
        select(LessonRequest)
        .options(
            selectinload(LessonRequest.student),
            selectinload(LessonRequest.subject),
            selectinload(LessonRequest.preferred_teacher),
        )
        .where(LessonRequest.id == lr_id)
    )
    obj = db.execute(q).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Lesson request not found")
    return DataResponse(data=LessonRequestList.model_validate(obj))


@router.put("/{lr_id}", response_model=DataResponse[LessonRequestBase])
def update_lesson_request(
    lr_id: int, body: LessonRequestUpdate, db: Session = Depends(get_db)
):
    obj = db.get(LessonRequest, lr_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Lesson request not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=LessonRequestBase.model_validate(obj))


@router.delete("/{lr_id}", response_model=MessageResponse)
def delete_lesson_request(lr_id: int, db: Session = Depends(get_db)):
    obj = db.get(LessonRequest, lr_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Lesson request not found")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="Lesson request deleted")
