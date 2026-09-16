"""Тесты оптимизатора расписания (сценарии 1–12 из ТЗ)."""

import os
import sys
from datetime import date, time

os.environ["DATABASE_URL"] = "sqlite:///C:/Users/Ackepter/Desktop/work_project2/test_pytest.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy import insert

from app.core.database import Base, SessionLocal, engine
from app.models.entities import (
    Availability,
    EntityTypeEnum,
    GroupLesson,
    LessonRequest,
    LessonTypeEnum,
    Room,
    Student,
    Subject,
    Teacher,
    group_lesson_participants,
    room_subjects,
    teacher_subjects,
)
from app.optimizer.scheduler import run_schedule_generation


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


# ── helpers ───────────────────────────────────────────────────────────────

def _avail(db, etype, eid, day, start, end):
    db.add(Availability(
        entity_type=etype, entity_id=eid,
        day_of_week=day,
        start_time=time(*start), end_time=time(*end),
    ))


def _subject(db, name="Математика"):
    s = Subject(name=name, default_duration_minutes=60)
    db.add(s)
    db.flush()
    return s


def _teacher(db, subjects, days=(0, 1, 2, 3, 4, 5), start=(10, 0), end=(20, 0), name="Пед"):
    t = Teacher(first_name="О", last_name=name)
    db.add(t)
    db.flush()
    for s in subjects:
        db.execute(teacher_subjects.insert().values(teacher_id=t.id, subject_id=s.id))
    for d in days:
        _avail(db, EntityTypeEnum.teacher, t.id, d, start, end)
    return t


def _student(db, days, start=(10, 0), end=(20, 0), name="Уч"):
    s = Student(first_name="", last_name=name)
    db.add(s)
    db.flush()
    for d in days if isinstance(days, list) else [days]:
        _avail(db, EntityTypeEnum.student, s.id, d, start, end)
    return s


def _room(db, capacity, subjects, days=(0, 1, 2, 3, 4, 5), start=(10, 0), end=(20, 0), name="Каб"):
    r = Room(name=name, capacity=capacity)
    db.add(r)
    db.flush()
    for s in subjects:
        db.execute(room_subjects.insert().values(room_id=r.id, subject_id=s.id))
    for d in days:
        _avail(db, EntityTypeEnum.room, r.id, d, start, end)
    return r


def _request(db, student, subject, lessons=1, duration=60,
             lesson_type=LessonTypeEnum.individual, preferred_teacher=None,
             teacher_required=False):
    lr = LessonRequest(
        student_id=student.id, subject_id=subject.id,
        lesson_type=lesson_type,
        lessons_per_week=lessons,
        duration_minutes=duration,
        preferred_teacher_id=preferred_teacher.id if preferred_teacher else None,
        teacher_is_required=teacher_required,
    )
    db.add(lr)
    db.flush()
    return lr


def _group(db, name, subject, teacher, student_ids):
    g = GroupLesson(title=name, subject_id=subject.id,
                    teacher_id=teacher.id, lessons_per_week=1)
    db.add(g)
    db.flush()
    for sid in student_ids:
        db.execute(group_lesson_participants.insert().values(
            group_lesson_id=g.id, student_id=sid
        ))
    return g


ALL_DAYS = list(range(6))
STD = ((10, 0), (20, 0))


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 1 — два индивидуальных занятия одного ребёнка не пересекаются
# ═══════════════════════════════════════════════════════════════════════════

def test_no_overlap_for_one_child(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    r = _room(db, 5, [s])
    st = _student(db, ALL_DAYS)
    for _ in range(2):
        _request(db, st, s, lessons=2)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    slots = [(l["day_of_week"], l["start_time"], l["end_time"])
             for l in res.scheduled
             if l["lesson_type"] == "individual"]
    assert len(slots) == 4
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            a, b = slots[i], slots[j]
            if a[0] == b[0]:
                assert not (a[1] < b[2] and b[1] < a[2])


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 2 — один педагог не ведёт два занятия одновременно
# ═══════════════════════════════════════════════════════════════════════════

def test_no_teacher_double_booking(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    r = _room(db, 5, [s])
    st1 = _student(db, ALL_DAYS, name="A")
    st2 = _student(db, ALL_DAYS, name="B")
    for st in (st1, st2):
        _request(db, st, s)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    slots = [(l["day_of_week"], l["start_time"], l["end_time"])
             for l in res.scheduled if l["teacher_id"] == t.id]
    assert len(slots) == 2
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            a, b = slots[i], slots[j]
            if a[0] == b[0]:
                assert not (a[1] < b[2] and b[1] < a[2])


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 3 — один кабинет не используется одновременно
# ═══════════════════════════════════════════════════════════════════════════

def test_no_room_double_booking(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    r = _room(db, 5, [s])
    for i in range(3):
        _request(db, _student(db, ALL_DAYS, name=str(i)), s)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    slots = [(l["day_of_week"], l["start_time"], l["end_time"])
             for l in res.scheduled if l["room_id"] == r.id]
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            a, b = slots[i], slots[j]
            if a[0] == b[0]:
                assert not (a[1] < b[2] and b[1] < a[2])


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 4 — ребёнок не имеет двух занятий одновременно
# ═══════════════════════════════════════════════════════════════════════════

def test_no_student_double_booking(fresh_db):
    db = fresh_db
    sa = _subject(db, "Математика")
    sb = _subject(db, "Русский")
    ta = _teacher(db, [sa], name="A")
    tb = _teacher(db, [sb], name="B")
    ra = _room(db, 5, [sa], name="MA")
    rb = _room(db, 5, [sb], name="RB")
    st = _student(db, ALL_DAYS)
    _request(db, st, sa, lessons=2)
    _request(db, st, sb, lessons=2)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    slots = [(l["day_of_week"], l["start_time"], l["end_time"])
             for l in res.scheduled if l["student_id"] == st.id]
    assert len(slots) == 4
    for i in range(len(slots)):
        for j in range(i + 1, len(slots)):
            a, b = slots[i], slots[j]
            if a[0] == b[0]:
                assert not (a[1] < b[2] and b[1] < a[2])


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 5 — групповое занятие учитывает доступность всех участников
# ═══════════════════════════════════════════════════════════════════════════

def test_group_respects_all_participants_availability(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s], days=(1, 3))
    r = _room(db, 10, [s], days=(1, 3))
    st1 = _student(db, [1], name="Вт")  # только вт
    st2 = _student(db, [3], name="Чт")  # только чт — нет общего дня
    st3 = _student(db, [1], name="Вт2")

    _group(db, "Нет общего", s, t, [st1.id, st2.id])
    db.commit()
    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    assert not any(l["lesson_type"] == "group" for l in res.scheduled), \
        "группа без общего дня не может быть размещена"

    # контроль: двое с общим днём
    _group(db, "Есть общий", s, t, [st1.id, st3.id])
    db.commit()
    res2 = run_schedule_generation(db, "Неделя2", date.today())
    assert res2.success, res2.message
    groups = [l for l in res2.scheduled if l["lesson_type"] == "group"]
    assert groups, "доступная группа должна разместиться"
    assert all(l["day_of_week"] in (1,) for l in groups)


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 6 — групповое занятие нельзя назначить в малый кабинет
# ═══════════════════════════════════════════════════════════════════════════

def test_group_not_in_undersized_room(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    small = _room(db, 2, [s], name="Мал")
    big = _room(db, 10, [s], name="Бол")
    students = [_student(db, ALL_DAYS, name=f"S{i}") for i in range(5)]
    _group(db, "Пятеро", s, t, [s.id for s in students])
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    placed = [l for l in res.scheduled if l["lesson_type"] == "group"]
    assert placed, "группа должна разместиться в большом кабинете"
    assert all(l["room_id"] == big.id for l in placed)


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 7 — педагог не ведёт предмет, который не преподаёт
# ═══════════════════════════════════════════════════════════════════════════

def test_teacher_not_teaching_foreign_subject(fresh_db):
    db = fresh_db
    math = _subject(db, "Математика")
    rus = _subject(db, "Русский")
    teach_rus = _teacher(db, [rus], name="Р")
    r = _room(db, 10, [math, rus])
    st = _student(db, ALL_DAYS)
    _request(db, st, math, preferred_teacher=teach_rus, teacher_required=True)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    placed = [l for l in res.scheduled if l["lesson_type"] == "individual"]
    assert not placed, "обязательный непрофильный педагог не должен попасть в расписание"


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 8 — кабинет нельзя использовать для запрещённого направления
# ═══════════════════════════════════════════════════════════════════════════

def test_room_not_forbidden_subject(fresh_db):
    db = fresh_db
    math = _subject(db, "Математика")
    t = _teacher(db, [math])
    room_math = _room(db, 10, [math], name="М")
    room_other = _room(db, 10, [], name="Д")  # не для математики
    st = _student(db, ALL_DAYS)
    _request(db, st, math)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    placed = [l for l in res.scheduled if l["lesson_type"] == "individual"]
    assert placed, "занятие должно быть размещено"
    assert all(l["room_id"] == room_math.id for l in placed)


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 9 — занятие не выходит за пределы доступности
# ═══════════════════════════════════════════════════════════════════════════

def test_lesson_within_availability_bounds(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s], days=(2,), start=(15, 0), end=(18, 0))
    r = _room(db, 5, [s], days=(2,), start=(10, 0), end=(20, 0))
    st = _student(db, [2], start=(15, 0), end=(18, 0))
    _request(db, st, s)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    assert res.scheduled
    l = res.scheduled[0]
    assert l["day_of_week"] == 2
    assert l["start_time"] >= time(15, 0)
    assert l["end_time"]   <= time(18, 0)


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 10 — если расписание невозможно — сообщение, не конфликт
# ═══════════════════════════════════════════════════════════════════════════

def test_infeasible_schedule_reports_conflict_free(fresh_db):
    db = fresh_db
    s = _subject(db)
    # педагог доступен 1 час во вт; двое учеников просят по 2 занятия
    t = _teacher(db, [s], days=(1,), start=(10, 0), end=(11, 0))
    r = _room(db, 5, [s], days=(0, 1), start=(10, 0), end=(20, 0))
    st1 = _student(db, ALL_DAYS, start=(10, 0), end=(20, 0), name="A")
    st2 = _student(db, ALL_DAYS, start=(10, 0), end=(20, 0), name="B")
    _request(db, st1, s, lessons=2)
    _request(db, st2, s, lessons=2)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    assert res.unscheduled, "есть неразмещённые занятия"
    # конфликтов быть не должно
    for i in range(len(res.scheduled)):
        for j in range(i + 1, len(res.scheduled)):
            a, b = res.scheduled[i], res.scheduled[j]
            if a["day_of_week"] != b["day_of_week"]:
                continue
            a_s = a["start_time"].hour * 60 + a["start_time"].minute
            a_e = a["end_time"].hour * 60 + a["end_time"].minute
            b_s = b["start_time"].hour * 60 + b["start_time"].minute
            b_e = b["end_time"].hour * 60 + b["end_time"].minute
            assert a_s >= b_e or b_s >= a_e, "обнаружен конфликт"


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 11 — индивидуальные и групповые занятия сосуществуют
# ═══════════════════════════════════════════════════════════════════════════

def test_individual_and_group_lessons_together(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    r = _room(db, 10, [s])
    st1 = _student(db, ALL_DAYS, name="A")
    st2 = _student(db, ALL_DAYS, name="B")
    _request(db, st1, s, lessons=2)
    _group(db, "Группа", s, t, [st1.id, st2.id])
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    types = {l["lesson_type"] for l in res.scheduled}
    assert "individual" in types
    assert "group" in types


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 12 — алгоритм не изменяет состав групп
# ═══════════════════════════════════════════════════════════════════════════

def test_group_composition_preserved(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    r = _room(db, 10, [s])
    studs = [_student(db, ALL_DAYS, name=f"S{i}") for i in range(4)]
    original_ids = sorted(st.id for st in studs)
    g = _group(db, "Группа", s, t, original_ids)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    placed = [l for l in res.scheduled if l["group_lesson_id"] == g.id]
    assert placed, "группа должна разместиться"
    for l in placed:
        assert sorted(l.get("students") or []) == original_ids
