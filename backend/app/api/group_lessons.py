from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.entities import GroupLesson, Student
from app.schemas.schemas import (
    DataResponse,
    GroupLessonBase,
    GroupLessonCreate,
    GroupLessonList,
    GroupLessonUpdate,
    ListResponse,
    MessageResponse,
)

router = APIRouter()


@router.get("", response_model=ListResponse[GroupLessonList])
def list_group_lessons(db: Session = Depends(get_db)):
    q = (
        select(GroupLesson)
        .options(
            selectinload(GroupLesson.subject),
            selectinload(GroupLesson.teacher),
            selectinload(GroupLesson.participants),
        )
        .order_by(GroupLesson.id)
    )
    rows = db.execute(q).scalars().all()
    return ListResponse(
        items=[GroupLessonList.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.post(
    "", response_model=DataResponse[GroupLessonBase], status_code=201
)
def create_group_lesson(
    body: GroupLessonCreate, db: Session = Depends(get_db)
):
    obj = GroupLesson(
        title=body.title,
        subject_id=body.subject_id,
        teacher_id=body.teacher_id,
        teacher_is_required=body.teacher_is_required,
        duration_minutes=body.duration_minutes,
        lessons_per_week=body.lessons_per_week,
        max_size=body.max_size,
        comment=body.comment,
    )
    if body.participant_ids:
        students = db.execute(
            select(Student).where(Student.id.in_(body.participant_ids))
        ).scalars().all()
        obj.participants = list(students)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=GroupLessonBase.model_validate(obj))


@router.get("/{gl_id}", response_model=DataResponse[GroupLessonBase])
def get_group_lesson(gl_id: int, db: Session = Depends(get_db)):
    q = (
        select(GroupLesson)
        .options(
            selectinload(GroupLesson.subject),
            selectinload(GroupLesson.teacher),
            selectinload(GroupLesson.participants),
        )
        .where(GroupLesson.id == gl_id)
    )
    obj = db.execute(q).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Group lesson not found")
    return DataResponse(data=GroupLessonBase.model_validate(obj))


@router.put("/{gl_id}", response_model=DataResponse[GroupLessonBase])
def update_group_lesson(
    gl_id: int, body: GroupLessonUpdate, db: Session = Depends(get_db)
):
    obj = db.get(GroupLesson, gl_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Group lesson not found")
    update_data = body.model_dump(exclude_unset=True)
    participant_ids = update_data.pop("participant_ids", None)
    for field, value in update_data.items():
        setattr(obj, field, value)
    if participant_ids is not None:
        students = db.execute(
            select(Student).where(Student.id.in_(participant_ids))
        ).scalars().all()
        obj.participants = list(students)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=GroupLessonBase.model_validate(obj))


@router.delete("/{gl_id}", response_model=MessageResponse)
def delete_group_lesson(gl_id: int, db: Session = Depends(get_db)):
    obj = db.get(GroupLesson, gl_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Group lesson not found")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="Group lesson deleted")
