from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.entities import Student
from app.schemas.schemas import (
    DataResponse,
    IdResponse,
    ListResponse,
    MessageResponse,
    StudentBase,
    StudentCreate,
    StudentList,
    StudentUpdate,
)

router = APIRouter()


@router.get("", response_model=ListResponse[StudentList])
def list_students(
    is_active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = select(Student).options(
        selectinload(Student.parent),
        selectinload(Student.lesson_requests),
    )
    if is_active is not None:
        q = q.where(Student.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            or_(
                Student.first_name.ilike(pattern),
                Student.last_name.ilike(pattern),
            )
        )
    q = q.order_by(Student.last_name, Student.first_name)
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[StudentList.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post("", response_model=DataResponse[StudentBase], status_code=201)
def create_student(body: StudentCreate, db: Session = Depends(get_db)):
    obj = Student(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=StudentBase.model_validate(obj))


@router.get("/{student_id}", response_model=DataResponse[StudentList])
def get_student(student_id: int, db: Session = Depends(get_db)):
    q = (
        select(Student)
        .options(
            selectinload(Student.parent),
            selectinload(Student.lesson_requests).selectinload("subject"),
        )
        .where(Student.id == student_id)
    )
    obj = db.execute(q).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Student not found")
    return DataResponse(data=StudentList.model_validate(obj))


@router.put("/{student_id}", response_model=DataResponse[StudentBase])
def update_student(
    student_id: int, body: StudentUpdate, db: Session = Depends(get_db)
):
    obj = db.get(Student, student_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Student not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=StudentBase.model_validate(obj))


@router.delete("/{student_id}", response_model=MessageResponse)
def delete_student(student_id: int, db: Session = Depends(get_db)):
    obj = db.get(Student, student_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Student not found")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="Student deleted")
