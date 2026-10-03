"""Тесты массового заполнения доступности (несколько дней одними часами)."""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    _REPO_ROOT, "test_availability.db"
).replace("\\", "/")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import time as dtime

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.entities import (
    Availability,
    EntityTypeEnum,
    LessonRequest,
    LessonTypeEnum,
    Room,
    Student,
    Subject,
    Teacher,
    room_subjects,
    teacher_subjects,
)

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        from app.api.auth import login_limiter
        from app.services.user_service import create_user

        login_limiter.reset()
        create_user(db, "admin", "testpassword123")
    finally:
        db.close()
    r = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "testpassword123"},
    )
    assert r.status_code == 200, r.text
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def teacher_id():
    db = SessionLocal()
    try:
        t = Teacher(first_name="Пётр", last_name="Тестовый")
        db.add(t)
        db.commit()
        db.refresh(t)
        return t.id
    finally:
        db.close()


def _bulk(entity_type: str, entity_id: int, days, start: str, end: str, **extra):
    return client.post(
        "/api/availabilities/bulk",
        json={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "days": days,
            "start_time": start,
            "end_time": end,
            **extra,
        },
    )


def _list_avail(entity_type: str, entity_id: int):
    return client.get(
        "/api/availabilities",
        params={"entity_type": entity_type, "entity_id": entity_id},
    ).json()["items"]


# ── API: массовое создание ────────────────────────────────────────────────


def test_bulk_creates_same_window_for_many_days(_db, teacher_id):
    r = _bulk("teacher", teacher_id, [0, 1, 2, 3, 4], "09:00", "19:00")
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["created"] == 5
    assert data["skipped"] == 0
    assert {i["day_of_week"] for i in data["items"]} == {0, 1, 2, 3, 4}

    listed = _list_avail("teacher", teacher_id)
    assert len(listed) == 5
    assert all(i["start_time"] == "09:00:00" for i in listed)
    assert all(i["end_time"] == "19:00:00" for i in listed)


def test_bulk_is_idempotent(_db, teacher_id):
    assert _bulk("teacher", teacher_id, [0, 1, 2, 3, 4], "09:00", "19:00").json()["data"][
        "created"
    ] == 5
    second = _bulk("teacher", teacher_id, [0, 1, 2, 3, 4], "09:00", "19:00").json()["data"]
    assert second["created"] == 0
    assert second["skipped"] == 5
    assert len(_list_avail("teacher", teacher_id)) == 5


def test_bulk_keeps_extra_window_of_same_day(_db, teacher_id):
    _bulk("teacher", teacher_id, [0], "09:00", "13:00")
    _bulk("teacher", teacher_id, [0], "14:00", "18:00")
    listed = _list_avail("teacher", teacher_id)
    assert len(listed) == 2
    assert {i["start_time"] for i in listed} == {"09:00:00", "14:00:00"}


def test_bulk_deduplicates_days_in_request(_db, teacher_id):
    r = _bulk("teacher", teacher_id, [1, 1, 2], "10:00", "12:00")
    assert r.status_code == 201, r.text
    assert r.json()["data"]["created"] == 2


def test_bulk_replace_clears_previous(_db, teacher_id):
    _bulk("teacher", teacher_id, [0, 1], "09:00", "14:00")
    r = _bulk("teacher", teacher_id, [2, 3], "09:00", "19:00", replace=True)
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["removed"] == 2
    assert data["created"] == 2

    listed = _list_avail("teacher", teacher_id)
    assert {i["day_of_week"] for i in listed} == {2, 3}


def test_bulk_validates_input(_db, teacher_id):
    assert _bulk("teacher", teacher_id, [0, 9], "09:00", "19:00").status_code == 422
    assert _bulk("teacher", teacher_id, [-1], "09:00", "19:00").status_code == 422
    assert _bulk("teacher", teacher_id, [0], "19:00", "09:00").status_code == 422
    assert _bulk("teacher", teacher_id, [], "09:00", "19:00").status_code == 422


def test_bulk_touches_only_one_entity(_db, teacher_id):
    db = SessionLocal()
    try:
        other = Teacher(first_name="Пётр", last_name="Другой")
        db.add(other)
        db.commit()
        db.refresh(other)
        other_id = other.id
    finally:
        db.close()

    _bulk("teacher", teacher_id, [0, 1, 2, 3, 4], "09:00", "19:00")
    assert _list_avail("teacher", other_id) == []


# ── Влияние на оптимизатор ───────────────────────────────────────────────


def test_bulk_weekday_window_lets_lesson_be_placed(_db):
    """Педагог с Пн–Пт одним интервалом должен получить занятие в будний день."""
    db = SessionLocal()
    try:
        subject = Subject(name="Робототехника", default_duration_minutes=60)
        db.add(subject)
        db.flush()

        teacher = Teacher(first_name="Иван", last_name="Иванов")
        db.add(teacher)
        db.flush()
        db.execute(
            teacher_subjects.insert().values(
                teacher_id=teacher.id, subject_id=subject.id
            )
        )

        room = Room(name="Кабинет Бот", capacity=5)
        db.add(room)
        db.flush()
        db.execute(room_subjects.insert().values(room_id=room.id, subject_id=subject.id))

        student = Student(first_name="Данил", last_name="Давлятшин")
        db.add(student)
        db.flush()

        # ученик доступен только в понедельник
        db.add(
            Availability(
                entity_type=EntityTypeEnum.student,
                entity_id=student.id,
                day_of_week=0,
                start_time=dtime(9, 0),
                end_time=dtime(19, 0),
            )
        )
        db.add(
            LessonRequest(
                student_id=student.id,
                subject_id=subject.id,
                lesson_type=LessonTypeEnum.individual,
                lessons_per_week=1,
                duration_minutes=60,
            )
        )
        db.commit()
        teacher_pk = teacher.id
    finally:
        db.close()

    r = _bulk("teacher", teacher_pk, [0, 1, 2, 3, 4], "09:00", "19:00")
    assert r.status_code == 201, r.text

    gen = client.post("/api/schedules/generate")
    assert gen.status_code == 200, gen.text
    data = gen.json()["data"]
    assert data["unscheduled_count"] == 0, data["unscheduled"]

    lessons = client.get(f"/api/schedules/{data['schedule_id']}/lessons").json()["items"]
    assert len(lessons) == 1
    assert lessons[0]["day_of_week"] == 0
    assert lessons[0]["teacher_id"] == teacher_pk