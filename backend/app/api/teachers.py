from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.entities import Subject, Teacher, teacher_subjects
from app.schemas.schemas import (
    DataResponse,
    ListResponse,
    MessageResponse,
    TeacherBase,
    TeacherCreate,
    TeacherList,
    TeacherUpdate,
)

router = APIRouter()


@router.get("", response_model=ListResponse[TeacherList])
def list_teachers(
    subject_id: Optional[int] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = select(Teacher).options(selectinload(Teacher.subjects))
    if is_active is not None:
        q = q.where(Teacher.is_active == is_active)
    if subject_id is not None:
        q = q.join(teacher_subjects).where(
            teacher_subjects.c.subject_id == subject_id
        )
    q = q.order_by(Teacher.last_name, Teacher.first_name)
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[TeacherList.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("", response_model=DataResponse[TeacherBase], status_code=201)
def create_teacher(body: TeacherCreate, db: Session = Depends(get_db)):
    obj = Teacher(
        first_name=body.first_name,
        last_name=body.last_name,
        comment=body.comment,
        is_active=body.is_active,
        max_weekly_hours=body.max_weekly_hours,
    )
    if body.subject_ids:
        subjects = db.execute(
            select(Subject).where(Subject.id.in_(body.subject_ids))
        ).scalars().all()
        obj.subjects = list(subjects)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=TeacherBase.model_validate(obj))


@router.get("/{teacher_id}", response_model=DataResponse[TeacherBase])
def get_teacher(teacher_id: int, db: Session = Depends(get_db)):
    q = (
        select(Teacher)
        .options(selectinload(Teacher.subjects))
        .where(Teacher.id == teacher_id)
    )
    obj = db.execute(q).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Teacher not found")
    return DataResponse(data=TeacherBase.model_validate(obj))


@router.put("/{teacher_id}", response_model=DataResponse[TeacherBase])
def update_teacher(
    teacher_id: int, body: TeacherUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Teacher, teacher_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Teacher not found")
    update_data = body.model_dump(exclude_unset=True)
    subject_ids = update_data.pop("subject_ids", None)
    for field, value in update_data.items():
        setattr(obj, field, value)
    if subject_ids is not None:
        subjects = db.execute(
            select(Subject).where(Subject.id.in_(subject_ids))
        ).scalars().all()
        obj.subjects = list(subjects)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=TeacherBase.model_validate(obj))


@router.delete("/{teacher_id}", response_model=MessageResponse)
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    obj = db.get(Teacher, teacher_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Teacher not found")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="Teacher deleted")
