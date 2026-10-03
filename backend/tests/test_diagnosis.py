"""Тесты объяснения причин, почему занятие не попало в расписание."""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(
    _REPO_ROOT, "test_diagnosis.db"
).replace("\\", "/")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, time as dtime

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
from app.optimizer.scheduler import run_schedule_generation

client = TestClient(app)

DAYS = (0, 1, 2, 3, 4)


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


def _avail(entity_type, entity_id, days, start, end):
    for d in days:
        yield Availability(
            entity_type=entity_type,
            entity_id=entity_id,
            day_of_week=d,
            start_time=start,
            end_time=end,
        )


def _scenario(
    *,
    subject_name="Бочче",
    teacher_days=DAYS,
    teacher_hours=(10, 18),
    teacher_active=True,
    link_teacher=True,
    room_capacity=10,
    room_days=DAYS,
    room_hours=(10, 18),
    link_room=True,
    students=(("Данил", "Давлятшин"),),
    student_days=DAYS,
    student_hours=(10, 18),
    lessons_per_week=1,
    lesson_type=LessonTypeEnum.individual,
    duration=60,
    expect_exactly_one=True,
):
    """Собирает изолированный мир и возвращает разобранный отчёт."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        subject = Subject(name=subject_name)
        db.add(subject)
        db.flush()

        teacher = Teacher(
            first_name="Пётр",
            last_name="Иванов",
            is_active=teacher_active,
        )
        db.add(teacher)
        db.flush()
        if link_teacher:
            db.execute(
                teacher_subjects.insert().values(
                    teacher_id=teacher.id, subject_id=subject.id
                )
            )
        db.add_all(list(_avail(
            EntityTypeEnum.teacher, teacher.id, teacher_days,
            dtime(*teacher_hours[:1]), dtime(*teacher_hours[1:]),
        )))

        room = Room(name="Класс 1", capacity=room_capacity)
        db.add(room)
        db.flush()
        if link_room:
            db.execute(
                room_subjects.insert().values(room_id=room.id, subject_id=subject.id)
            )
        db.add_all(list(_avail(
            EntityTypeEnum.room, room.id, room_days,
            dtime(*room_hours[:1]), dtime(*room_hours[1:]),
        )))

        for first, last in students:
            student = Student(first_name=first, last_name=last)
            db.add(student)
            db.flush()
            db.add_all(list(_avail(
                EntityTypeEnum.student,
                student.id,
                student_days,
                dtime(*student_hours[:1]),
                dtime(*student_hours[1:]),
            )))
            for _ in range(lessons_per_week):
                db.add(
                    LessonRequest(
                        student_id=student.id,
                        subject_id=subject.id,
                        lesson_type=lesson_type,
                        lessons_per_week=1,
                        duration_minutes=duration,
                        priority=1,
                    )
                )
        db.commit()

        result = run_schedule_generation(db, "Тест", date.today())
        if expect_exactly_one:
            assert len(result.unscheduled) == 1, [
                (u.name, u.reason) for u in result.unscheduled
            ]
        else:
            assert result.unscheduled, "ожидались неразмещённые занятия"
        return result.unscheduled[0]
    finally:
        db.close()


# ── педагог ───────────────────────────────────────────────────────────────


def test_no_common_hours_with_teacher_is_explained():
    u = _scenario(student_hours=(14, 16), teacher_hours=(16, 18))
    assert "нет общих часов" in u.reason
    assert "Давлятшин Данил" in u.reason
    assert "Иванов Пётр" in u.reason
    joined = " ".join(u.details)
    assert "Часы ученика" in joined
    assert "14:00–16:00" in joined
    assert "Часы педагога" in joined
    assert "16:00–18:00" in joined
    assert u.suggestions


def test_teacher_available_on_other_day_is_explained():
    u = _scenario(student_days=(2,), teacher_days=(0,))
    assert "нет общих часов" in u.reason
    joined = " ".join(u.details)
    assert "среда 10:00–18:00" in joined
    assert "понедельник 10:00–18:00" in joined


def test_no_teacher_for_subject_is_explained():
    u = _scenario(link_teacher=False)
    assert "не назначен ни один педагог" in u.reason
    assert "Добавить педагога" in u.suggestions[0]


def test_inactive_teacher_is_explained():
    u = _scenario(teacher_active=False)
    assert "отключены" in u.reason
    assert "Иванов Пётр" in " ".join(u.details)


def test_teacher_overlap_shorter_than_lesson_is_explained():
    u = _scenario(teacher_hours=(10, 10) + (30,), duration=60)
    assert "короче занятия" in u.reason
    assert "максимум 30 мин" in u.reason
    assert any("Уменьшить длительность занятия до 30 мин" in s for s in u.suggestions)


# ── кабинет ───────────────────────────────────────────────────────────────


def test_no_room_allowed_for_subject_is_explained():
    u = _scenario(link_room=False)
    assert "ни один кабинет не разрешён" in u.reason
    assert "Разрешить кабинет" in u.suggestions[0]


def test_room_capacity_is_explained():
    u = _scenario(
        room_capacity=3,
        students=tuple((f"Уч{i}", "Имя") for i in range(5)),
        lesson_type=LessonTypeEnum.group,
    )
    assert "вместимостью не менее 5" in u.reason
    assert "максимальная вместимость" in u.reason
    assert "Класс 1 — 3 мест" in " ".join(u.details)


def test_room_overlap_shorter_than_lesson_is_explained():
    u = _scenario(room_hours=(10, 11), duration=120)
    assert "короче занятия" in u.reason
    assert "максимум 60 мин" in u.reason
    assert "Класс 1" in " ".join(u.details)


def test_room_not_overlapping_student_hours_is_explained():
    u = _scenario(student_hours=(14, 18), room_hours=(10, 13))
    assert "нет общих свободных часов" in u.reason
    joined = " ".join(u.details)
    assert "14:00–18:00" in joined
    assert "10:00–13:00" in joined


# ── перегрузка ────────────────────────────────────────────────────────────


def test_contention_reports_busy_windows():
    # 1 педагог + 1 кабинет, 60 слотов в неделю, 70 занятий
    u = _scenario(lessons_per_week=70, expect_exactly_one=False)
    assert "заняты" in u.reason
    joined = " ".join(u.details)
    assert "Иванов Пётр" in joined
    assert "уже занят" in joined
    assert "Класс 1" in joined


# ── отчёт в API ───────────────────────────────────────────────────────────


def test_unscheduled_report_is_returned_by_api_with_details():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # сброс таблиц удалил админа — создаём заново и логинимся
        from app.api.auth import login_limiter
        from app.services.user_service import create_user

        login_limiter.reset()
        create_user(db, "admin", "testpassword123")
        subject = Subject(name="Бочче")
        db.add(subject)
        db.flush()
        teacher = Teacher(first_name="Пётр", last_name="Иванов")
        db.add(teacher)
        db.flush()
        db.execute(
            teacher_subjects.insert().values(
                teacher_id=teacher.id, subject_id=subject.id
            )
        )
        room = Room(name="Класс 1", capacity=5)
        db.add(room)
        db.flush()
        db.execute(
            room_subjects.insert().values(room_id=room.id, subject_id=subject.id)
        )
        student = Student(first_name="Данил", last_name="Давлятшин")
        db.add(student)
        db.flush()
        db.add_all(list(_avail(
            EntityTypeEnum.student, student.id, (0,), dtime(14, 0), dtime(16, 0),
        )))
        db.add_all(list(_avail(
            EntityTypeEnum.teacher, teacher.id, (0,), dtime(17, 0), dtime(19, 0),
        )))
        db.add(
            LessonRequest(
                student_id=student.id,
                subject_id=subject.id,
                lesson_type=LessonTypeEnum.individual,
                lessons_per_week=1,
                duration_minutes=60,
                priority=1,
            )
        )
        db.commit()
    finally:
        db.close()

    r = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "testpassword123"},
    )
    assert r.status_code == 200, r.text

    gen = client.post("/api/schedules/generate")
    assert gen.status_code == 200, gen.text
    data = gen.json()["data"]
    assert data["unscheduled_count"] == 1, data

    entry = data["unscheduled"][0]
    assert "нет общих часов" in entry["reason"]
    assert entry["details"], "причина должна содержать детали"
    assert entry["suggestions"]
    assert entry["level"] == "error"
    assert "Давлятшин Данил" in entry["name"]

    # отчёт сохраняется в расписании
    stored = client.get(f"/api/schedules/{data['schedule_id']}")
    assert stored.status_code == 200, stored.text
    assert stored.json()["data"]["id"] == data["schedule_id"]


def test_optimizer_settings_available_before_first_generation():
    """Редактор должен знать рабочее окно до первой генерации расписания."""
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
    assert client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "testpassword123"},
    ).status_code == 200

    r = client.get("/api/optimizer-settings")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["early_hour"] == 9
    assert data["late_hour"] == 20


def test_student_without_availability_can_join_group():
    """Нет записей о доступности = свободен весь рабочий день, а не «нет часов»."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        subject = Subject(name="Бочче")
        db.add(subject)
        db.flush()
        teacher = Teacher(first_name="Пётр", last_name="Иванов")
        db.add(teacher)
        db.flush()
        db.execute(
            teacher_subjects.insert().values(
                teacher_id=teacher.id, subject_id=subject.id
            )
        )
        room = Room(name="Класс 1", capacity=5)
        db.add(room)
        db.flush()
        db.execute(
            room_subjects.insert().values(room_id=room.id, subject_id=subject.id)
        )
        # два ученика без единой записи об доступности
        for first, last in (("Данил", "Давлятшин"), ("Иван", "Петров")):
            student = Student(first_name=first, last_name=last)
            db.add(student)
            db.flush()
            db.add(
                LessonRequest(
                    student_id=student.id,
                    subject_id=subject.id,
                    lesson_type=LessonTypeEnum.group,
                    lessons_per_week=1,
                    duration_minutes=60,
                    priority=1,
                )
            )
        db.commit()

        result = run_schedule_generation(db, "Тест", date.today())
        assert result.unscheduled == []
        assert len(result.scheduled) == 1
    finally:
        db.close()