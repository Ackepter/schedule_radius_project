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
    LessonRequest,
    LessonTypeEnum,
    Price,
    Room,
    Schedule,
    ScheduledLesson,
    Student,
    Subject,
    Teacher,
    TeacherRate,
    room_subjects,
    teacher_subjects,
)
from app.optimizer.scheduler import run_schedule_generation
from app.services.pricing_service import (
    calculate_schedule_revenue,
    get_teacher_rate,
    min_lesson_revenue,
    validate_teacher_rate,
)
from app.services.schedule_service import generate_schedule


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


def _group_request(db, students, subject, lessons=1, duration=60,
                   preferred_teacher=None, teacher_required=False):
    for st in students:
        _request(db, st, subject, lessons=lessons, duration=duration,
                 lesson_type=LessonTypeEnum.group,
                 preferred_teacher=preferred_teacher,
                 teacher_required=teacher_required)


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
#  Тест 5 — группа учитывает доступность всех участников
# ═══════════════════════════════════════════════════════════════════════════

def test_group_respects_all_participants_availability(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s], days=(1, 3))
    r = _room(db, 10, [s], days=(1, 3))
    st1 = _student(db, [1], name="Вт")  # только вт
    st2 = _student(db, [3], name="Чт")  # только чт — нет общего дня
    st3 = _student(db, [1], name="Вт2")

    # без общего свободного дня группа не формируется и не размещается
    _group_request(db, [st1, st2], s)
    db.commit()
    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    assert not any(l["lesson_type"] == "group" for l in res.scheduled), \
        "группа без общего дня не может быть размещена"
    assert any("не сформировано" in u.reason for u in res.unscheduled), \
        "одиночная групповая заявка должна попасть в отчёт в информационном виде"
    assert any(u.level == "info" for u in res.unscheduled), \
        "несформированная группа должна быть информационной, а не ошибкой"

    # контроль: двое с общим днём образуют группу
    _group_request(db, [st3], s)
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
    _group_request(db, students, s)
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
#  Тест 11 — индивидуальные и групповые занятия сосуществуют («всё сразу»)
# ═══════════════════════════════════════════════════════════════════════════

def test_individual_and_group_lessons_together(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    r = _room(db, 10, [s])
    st1 = _student(db, ALL_DAYS, name="A")
    st2 = _student(db, ALL_DAYS, name="B")
    # у st1 одновременно и индивидуальное, и групповое требование
    _request(db, st1, s, lessons=2)
    _group_request(db, [st1, st2], s)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    types = {l["lesson_type"] for l in res.scheduled}
    assert "individual" in types
    assert "group" in types
    st1_lessons = [l for l in res.scheduled if st1.id in (l.get("students") or [])]
    assert len(st1_lessons) >= 3, "у ребёнка должны быть и индивид., и групповые занятия"


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 12 — состав сформированной группы фиксирован (не меняется оптимизатором)
# ═══════════════════════════════════════════════════════════════════════════

def test_group_composition_preserved(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    r = _room(db, 10, [s])
    studs = [_student(db, ALL_DAYS, name=f"S{i}") for i in range(4)]
    original_ids = sorted(st.id for st in studs)
    _group_request(db, studs, s)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    placed = [l for l in res.scheduled if l["lesson_type"] == "group"]
    assert placed, "группа должна разместиться"
    for l in placed:
        assert sorted(l.get("students") or []) == original_ids


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 13 — одно требование типа «both» даёт и индивидуальное, и групповое
# ═══════════════════════════════════════════════════════════════════════════

def test_both_type_generates_individual_and_group(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    r = _room(db, 10, [s])
    st1 = _student(db, ALL_DAYS, name="A")
    st2 = _student(db, ALL_DAYS, name="B")
    _request(db, st1, s, lesson_type=LessonTypeEnum.both)
    _request(db, st2, s, lesson_type=LessonTypeEnum.group)
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    ind = [l for l in res.scheduled if l["lesson_type"] == "individual" and st1.id in (l.get("students") or [])]
    grp = [l for l in res.scheduled if l["lesson_type"] == "group" and st1.id in (l.get("students") or [])]
    assert ind, "по требованию 'both' должно появиться индивидуальное занятие"
    assert grp, "по требованию 'both' ученик должен попасть в группу"


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 14 — несовместимые дети не попадают в одну группу
# ═══════════════════════════════════════════════════════════════════════════

def test_incompatible_students_not_grouped_together(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    r = _room(db, 10, [s])
    a = _student(db, ALL_DAYS, name="A")
    b = _student(db, ALL_DAYS, name="B")
    c = _student(db, ALL_DAYS, name="C")
    lr_a = _request(db, a, s, lesson_type=LessonTypeEnum.group)
    lr_b = _request(db, b, s, lesson_type=LessonTypeEnum.group)
    lr_c = _request(db, c, s, lesson_type=LessonTypeEnum.group)
    lr_a.excluded_students = [b]
    db.commit()

    res = run_schedule_generation(db, "Неделя", date.today())
    assert res.success, res.message
    placed = [l for l in res.scheduled if l["lesson_type"] == "group"]
    assert placed, "совместимая пара должна образовать группу"
    for l in placed:
        member_ids = sorted(l.get("students") or [])
        assert a.id in member_ids and c.id in member_ids, f"неверный состав группы: {member_ids}"
        assert b.id not in member_ids, "исключённый ученик не должен попасть в группу"
    assert any("не сформировано" in u.reason for u in res.unscheduled), \
        "исключённый ученик должен остаться без группы и попасть в отчёт"


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 15 — финансовая разбивка: центр, педагоги, ученики
# ═══════════════════════════════════════════════════════════════════════════

def _price(db, subject, lesson_type, min_part, max_part, per_student):
    p = Price(
        subject_id=subject.id, lesson_type=lesson_type,
        min_participants=min_part, max_participants=max_part,
        price_per_student=per_student,
    )
    db.add(p)
    db.flush()
    return p


def test_finance_breakdown_all_participants(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    r = _room(db, 10, [s])
    st1 = _student(db, ALL_DAYS, name="Перв")
    st2 = _student(db, ALL_DAYS, name="Втор")
    _price(db, s, LessonTypeEnum.individual, 1, 1, 1000)
    _price(db, s, LessonTypeEnum.group, 2, 2, 800)
    _price(db, s, LessonTypeEnum.group, 3, 8, 700)
    db.add(TeacherRate(teacher_id=t.id, subject_id=s.id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=400))
    db.add(TeacherRate(teacher_id=None, subject_id=s.id, lesson_type=LessonTypeEnum.group, rate_per_lesson=900))
    _request(db, st1, s, lesson_type=LessonTypeEnum.individual)
    _group_request(db, [st1, st2], s)
    db.commit()

    sched_id = generate_schedule(db, "Неделя", date.today()).schedule_id
    assert sched_id is not None

    f = calculate_schedule_revenue(db, sched_id)
    assert f.total_lessons == 2, f.total_lessons
    assert f.individual_lessons == 1 and f.group_lessons == 1
    assert f.total_revenue == 1000 + 2 * 800 == 2600, f.total_revenue
    assert f.teacher_pay_total == 400 + 900 == 1300, f.teacher_pay_total
    assert f.net_revenue == 1300, f.net_revenue

    assert len(f.teacher_breakdown) == 1
    tb = f.teacher_breakdown[0]
    assert tb.teacher_name == "Пед О"
    assert tb.total_lessons == 2
    assert tb.total_pay == 1300

    names = {st.student_name: st for st in f.student_breakdown}
    assert len(names) == 2
    assert names["Перв"].total_paid == 1000 + 800 == 1800
    assert names["Втор"].total_paid == 800
    assert names["Перв"].total_lessons == 2
    assert names["Втор"].total_lessons == 1


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 16 — ставки педагога: индивидуальная переопределяет умолчание
# ═══════════════════════════════════════════════════════════════════════════

def test_teacher_rate_override_precedence(fresh_db):
    db = fresh_db
    s = _subject(db)
    t1 = _teacher(db, [s], name="Пед1")
    t2 = _teacher(db, [s], name="Пед2")
    db.add(TeacherRate(teacher_id=None, subject_id=s.id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=400))
    db.add(TeacherRate(teacher_id=t1.id, subject_id=s.id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=600))
    db.commit()

    r1 = get_teacher_rate(db, t1.id, s.id, LessonTypeEnum.individual)
    assert r1 is not None and r1.rate_per_lesson == 600
    r2 = get_teacher_rate(db, t2.id, s.id, LessonTypeEnum.individual)
    assert r2 is not None and r2.rate_per_lesson == 400
    assert get_teacher_rate(db, t2.id, s.id, LessonTypeEnum.group) is None


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 17 — валидация: оплата педагога не может превышать выручку центра
# ═══════════════════════════════════════════════════════════════════════════

def test_teacher_rate_overpay_rejected(fresh_db):
    db = fresh_db
    s = _subject(db)
    _price(db, s, LessonTypeEnum.individual, 1, 1, 1000)
    _price(db, s, LessonTypeEnum.group, 2, 2, 700)

    assert validate_teacher_rate(db, 999, s.id, LessonTypeEnum.individual) is None
    assert validate_teacher_rate(db, 1000, s.id, LessonTypeEnum.individual) is None
    err = validate_teacher_rate(db, 1001, s.id, LessonTypeEnum.individual)
    assert err is not None and "превышает" in err
    assert min_lesson_revenue(db, s.id, LessonTypeEnum.individual) == 1000

    assert validate_teacher_rate(db, 1400, s.id, LessonTypeEnum.group) is None
    err = validate_teacher_rate(db, 1500, s.id, LessonTypeEnum.group)
    assert err is not None

    # если цена не задана — ставку поставить нельзя
    s2 = _subject(db, name="Новое направление")
    err = validate_teacher_rate(db, 100, s2.id, LessonTypeEnum.individual)
    assert err is not None and "Сначала укажите" in err


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 18 — процентная ставка педагога (процент от выручки занятия)
# ═══════════════════════════════════════════════════════════════════════════

def test_teacher_rate_percent(fresh_db):
    from app.models.entities import RateTypeEnum
    from app.services.pricing_service import lesson_teacher_pay

    db = fresh_db
    s = _subject(db)
    _price(db, s, LessonTypeEnum.individual, 1, 1, 1000)
    _price(db, s, LessonTypeEnum.group, 2, 2, 700)

    # процент <= 100 разрешён, 0 и >100 отклоняются
    assert validate_teacher_rate(
        db, 100, s.id, LessonTypeEnum.group, RateTypeEnum.percent
    ) is None
    err = validate_teacher_rate(db, 0, s.id, LessonTypeEnum.group, RateTypeEnum.percent)
    assert err is not None and "больше 0" in err
    err = validate_teacher_rate(
        db, 100.5, s.id, LessonTypeEnum.group, RateTypeEnum.percent
    )
    assert err is not None and "превыша" in err

    # расчёт: 50% от выручки занятия 1400 (2×700) = 700
    rate = TeacherRate(
        teacher_id=None, subject_id=s.id, lesson_type=LessonTypeEnum.group,
        rate_type=RateTypeEnum.percent, rate_per_lesson=50,
    )
    db.add(rate)
    db.commit()
    assert lesson_teacher_pay(rate, 1400.0) == 700.0
    assert lesson_teacher_pay(rate, 997.13) == round(997.13 * 0.5, 2)


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 19 — ставка «индивидуальное и групповое» (оба типа сразу)
# ═══════════════════════════════════════════════════════════════════════════

def test_teacher_rate_both(fresh_db):
    db = fresh_db
    s = _subject(db)
    t1 = _teacher(db, [s], name="Пед1")
    _price(db, s, LessonTypeEnum.individual, 1, 1, 1000)
    _price(db, s, LessonTypeEnum.group, 2, 2, 700)

    # валидация: нужны цены обоих типов; лимит — самый дешёвый вариант (индивидуальная 1000)
    assert validate_teacher_rate(db, 700, s.id, LessonTypeEnum.both) is None
    assert validate_teacher_rate(db, 1000, s.id, LessonTypeEnum.both) is None
    err = validate_teacher_rate(db, 1001, s.id, LessonTypeEnum.both)
    assert err is not None and "превышает" in err

    s2 = _subject(db, name="Без группы")
    _price(db, s2, LessonTypeEnum.individual, 1, 1, 1000)
    err = validate_teacher_rate(db, 100, s2.id, LessonTypeEnum.both)
    assert err is not None and "обоих" in err

    # приоритет: индивидуальная ставка педагога > «оба» > умолчание > ...
    db.add(TeacherRate(teacher_id=None, subject_id=s.id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=400))
    db.add(TeacherRate(teacher_id=None, subject_id=s.id, lesson_type=LessonTypeEnum.both, rate_per_lesson=250))
    db.add(TeacherRate(teacher_id=t1.id, subject_id=s.id, lesson_type=LessonTypeEnum.both, rate_per_lesson=500))
    db.commit()

    # у Пед1 индивидуальное занятие — его «оба»-ставка (500) переопределяет умолчание
    r = get_teacher_rate(db, t1.id, s.id, LessonTypeEnum.individual)
    assert r is not None and r.rate_per_lesson == 500
    # у других индивидуальное — умолчание на точный тип (400) сильнее «оба»-умолчания
    r = get_teacher_rate(db, 9999, s.id, LessonTypeEnum.individual)
    assert r is not None and r.rate_per_lesson == 400
    # групповое занятие: точной групповой ставки нет → «оба»-ставка (500)
    r = get_teacher_rate(db, t1.id, s.id, LessonTypeEnum.group)
    assert r is not None and r.rate_per_lesson == 500
    r = get_teacher_rate(db, 9999, s.id, LessonTypeEnum.group)
    assert r is not None and r.rate_per_lesson == 250


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 20 — финансы за день: фильтр по дню недели и разбивка по дням
# ═══════════════════════════════════════════════════════════════════════════

def test_finance_day_filter(fresh_db):
    db = fresh_db
    s = _subject(db)
    t = _teacher(db, [s])
    r = _room(db, 10, [s])
    st1 = _student(db, ALL_DAYS, name="Перв")
    st2 = _student(db, ALL_DAYS, name="Втор")
    _price(db, s, LessonTypeEnum.individual, 1, 1, 1000)
    db.add(TeacherRate(teacher_id=None, subject_id=s.id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=400))
    _request(db, st1, s, lesson_type=LessonTypeEnum.individual)
    _request(db, st2, s, lesson_type=LessonTypeEnum.individual)
    db.commit()

    sched_id = generate_schedule(db, "Неделя", date.today()).schedule_id
    assert sched_id is not None

    week = calculate_schedule_revenue(db, sched_id)
    assert week.total_lessons == 2
    assert week.day_of_week is None
    assert len(week.days) == 7
    assert sum(d.total_lessons for d in week.days) == 2
    assert sum(d.total_revenue for d in week.days) == week.total_revenue

    used_days = [d.day_of_week for d in week.days if d.total_lessons > 0]
    assert len(used_days) >= 1

    day = calculate_schedule_revenue(db, sched_id, day_of_week=used_days[0])
    assert day.total_lessons >= 1
    assert day.day_of_week == used_days[0]
    assert day.net_revenue == round(day.total_revenue - day.teacher_pay_total, 2)

    empty_day = calculate_schedule_revenue(db, sched_id, day_of_week=(used_days[0] + 1) % 7)
    if all(d.total_lessons == 0 for d in [empty_day]):
        assert empty_day.total_revenue == 0.0
        assert empty_day.total_lessons == 0


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 21 — регрессия: предупреждения не роняют сводку (UnboundLocalError)
# ═══════════════════════════════════════════════════════════════════════════

def test_finance_missing_rate_warning(fresh_db):
    db = fresh_db
    s = _subject(db, name="Без ставки")
    t = _teacher(db, [s])
    r = _room(db, 10, [s])
    st = _student(db, ALL_DAYS)
    _price(db, s, LessonTypeEnum.individual, 1, 1, 1000)
    _request(db, st, s, lesson_type=LessonTypeEnum.individual)
    db.commit()

    sched_id = generate_schedule(db, "Неделя", date.today()).schedule_id
    assert sched_id is not None

    f = calculate_schedule_revenue(db, sched_id)
    assert f.total_lessons >= 1
    assert any("не задана ставка" in w for w in f.warnings)


# ═══════════════════════════════════════════════════════════════════════════
#  Тест 22 — индивидуальное занятие строго на 1 участника
# ═══════════════════════════════════════════════════════════════════════════

def test_price_individual_single_participant():
    from pydantic import ValidationError

    from app.schemas.schemas import PriceCreate, PriceUpdate

    ok = PriceCreate(
        subject_id=1,
        lesson_type=LessonTypeEnum.individual,
        min_participants=1,
        max_participants=1,
        price_per_student=500,
    )
    assert ok.max_participants == 1

    for bad in (
        dict(min_participants=1, max_participants=5),
        dict(min_participants=2, max_participants=2),
        dict(min_participants=3, max_participants=4),
    ):
        with pytest.raises(ValidationError):
            PriceCreate(
                subject_id=1,
                lesson_type=LessonTypeEnum.individual,
                **bad,
                price_per_student=500,
            )

    # время обновления: перевод existing-тарифа в индивидуальный с max>1 отклоняется
    with pytest.raises(ValidationError):
        PriceUpdate(lesson_type=LessonTypeEnum.individual, max_participants=3)

    # групповые тарифы не затронуты
    grp = PriceCreate(
        subject_id=1,
        lesson_type=LessonTypeEnum.group,
        min_participants=2,
        max_participants=8,
        price_per_student=600,
    )
    assert grp.min_participants == 2
