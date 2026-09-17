"""Экспорт, импорт и полная очистка данных.

Формат JSON ориентирован на ручное (в т.ч. ИИ) составление:
все связи указываются по именам (направление, ФИО педагога,
ФИО ученика, название кабинета), а не по числовым id.
"""

from datetime import date, time, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    Availability,
    EntityTypeEnum,
    LessonRequest,
    LessonTypeEnum,
    OptimizerSettings,
    Parent,
    Price,
    RateTypeEnum,
    Room,
    Schedule,
    ScheduledLesson,
    Student,
    Subject,
    Teacher,
    TeacherRate,
)

WIPE_TABLES = (
    "scheduled_lesson_participants, scheduled_lessons, schedules, lesson_requests, "
    "lesson_request_excluded_students, availabilities, teacher_rates, prices, students, teachers, "
    "rooms, subjects, parents"
)

TIME_FMT = "%H:%M"


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------


def full_name(first: str, last: str) -> str:
    return f"{last} {first}".strip()


def _fmt_time(t: time) -> str:
    return t.strftime(TIME_FMT) if t else ""


def _fmt_date(d) -> str:
    return d.isoformat() if d else None


def _fmt_lesson_type(lt: LessonTypeEnum) -> str:
    return lt.value


def _parse_time(value) -> time | None:
    if value is None:
        return None
    if isinstance(value, time):
        return value
    try:
        return time.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _parse_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _parse_lesson_type(value) -> LessonTypeEnum:
    if isinstance(value, LessonTypeEnum):
        return value
    try:
        return LessonTypeEnum(str(value).strip().lower())
    except ValueError:
        return LessonTypeEnum.individual


def _parse_rate_type(value) -> RateTypeEnum:
    if isinstance(value, RateTypeEnum):
        return value
    try:
        return RateTypeEnum(str(value).strip().lower())
    except ValueError:
        return RateTypeEnum.fixed


def _parse_status(value) -> str:
    v = str(value or "draft").strip().lower()
    if v in ("active", "активный", "активное"):
        return "active"
    return "draft"


# ---------------------------------------------------------------------------
# Очистка данных
# ---------------------------------------------------------------------------


def wipe_all_data(db: Session) -> None:
    """Полностью очищает справочники и расписания (без настроек оптимизатора)."""
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        db.execute(text(f"TRUNCATE TABLE {WIPE_TABLES} RESTART IDENTITY CASCADE"))
    else:
        db.execute(text("DELETE FROM scheduled_lesson_participants"))
        db.execute(text("DELETE FROM scheduled_lessons"))
        db.execute(text("DELETE FROM schedules"))
        db.execute(text("DELETE FROM lesson_request_excluded_students"))
        db.execute(text("DELETE FROM lesson_requests"))
        db.execute(text("DELETE FROM availabilities"))
        db.execute(text("DELETE FROM teacher_rates"))
        db.execute(text("DELETE FROM prices"))
        db.execute(text("DELETE FROM students"))
        db.execute(text("DELETE FROM teacher_subjects"))
        db.execute(text("DELETE FROM room_subjects"))
        db.execute(text("DELETE FROM teachers"))
        db.execute(text("DELETE FROM rooms"))
        db.execute(text("DELETE FROM subjects"))
        db.execute(text("DELETE FROM parents"))
    db.flush()


def _add_availabilities(db: Session, entity_id: int, etype: EntityTypeEnum, items) -> None:
    """Добавляет доступности для сущности. items: [{day_of_week, start_time, end_time}, ...]"""
    if not items:
        return
    for a in items or []:
        day = a.get("day_of_week") if isinstance(a, dict) else a
        start = _parse_time(a.get("start_time"))
        end = _parse_time(a.get("end_time"))
        try:
            day_int = int(day)
        except (TypeError, ValueError):
            continue
        if start is None or end is None or start >= end or day_int < 0 or day_int > 6:
            continue
        db.add(
            Availability(
                entity_type=etype,
                entity_id=entity_id,
                day_of_week=day_int,
                start_time=start,
                end_time=end,
            )
        )


# ---------------------------------------------------------------------------
# Экспорт
# ---------------------------------------------------------------------------


def export_all(db: Session) -> dict:
    """Собирает все данные БД в JSON-совместимый словарь (для выгрузки/бэкапа)."""
    subjects = db.scalars(select(Subject).order_by(Subject.id)).all()
    teachers = db.scalars(
        select(Teacher).options(selectinload(Teacher.subjects)).order_by(Teacher.id)
    ).all()
    rooms = db.scalars(
        select(Room).options(selectinload(Room.allowed_subjects)).order_by(Room.id)
    ).all()
    parents = db.scalars(select(Parent).order_by(Parent.id)).all()
    students = db.scalars(
        select(Student).options(selectinload(Student.parent)).order_by(Student.id)
    ).all()
    requests = db.scalars(
        select(LessonRequest)
        .options(
            selectinload(LessonRequest.subject),
            selectinload(LessonRequest.preferred_teacher),
            selectinload(LessonRequest.excluded_students),
        )
        .order_by(LessonRequest.id)
    ).all()
    prices = db.scalars(
        select(Price).options(selectinload(Price.subject)).order_by(Price.id)
    ).all()
    teacher_rates = db.scalars(
        select(TeacherRate)
        .options(
            selectinload(TeacherRate.teacher), selectinload(TeacherRate.subject)
        )
        .order_by(TeacherRate.id)
    ).all()
    schedules = db.scalars(
        select(Schedule).options(selectinload(Schedule.lessons)).order_by(Schedule.id)
    ).all()
    lesson_rows = db.scalars(
        select(ScheduledLesson)
        .options(
            selectinload(ScheduledLesson.lesson_request).selectinload(LessonRequest.subject),
            selectinload(ScheduledLesson.participants).selectinload(LessonRequest.student),
            selectinload(ScheduledLesson.student),
            selectinload(ScheduledLesson.teacher),
            selectinload(ScheduledLesson.room),
        )
        .order_by(ScheduledLesson.id)
    ).all()
    availabilities = db.scalars(select(Availability).order_by(Availability.id)).all()
    settings = db.scalars(select(OptimizerSettings).order_by(OptimizerSettings.id)).all()

    avail_by_key: dict[tuple[str, int], list[dict]] = {}
    for a in availabilities:
        key = (a.entity_type.value, a.entity_id)
        avail_by_key.setdefault(key, []).append(
            {
                "day_of_week": a.day_of_week,
                "start_time": _fmt_time(a.start_time),
                "end_time": _fmt_time(a.end_time),
            }
        )

    subject_names: dict[int, str] = {s.id: s.name for s in subjects}
    teacher_names: dict[int, str] = {}
    teacher_by_id: dict[int, Teacher] = {}
    for t in teachers:
        teacher_names[t.id] = full_name(t.first_name, t.last_name)
        teacher_by_id[t.id] = t

    requests_by_student: dict[int, list[LessonRequest]] = {}
    for r in requests:
        requests_by_student.setdefault(r.student_id, []).append(r)

    payload = {
        "version": 1,
        "schema": "education-center-backup",
        "exported_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "subjects": [
            {
                "name": s.name,
                "description": s.description,
                "default_duration_minutes": s.default_duration_minutes,
                "is_active": s.is_active,
            }
            for s in subjects
        ],
        "teachers": [
            {
                "first_name": t.first_name,
                "last_name": t.last_name,
                "comment": t.comment,
                "is_active": t.is_active,
                "max_weekly_hours": t.max_weekly_hours,
                "subjects": [s.name for s in t.subjects],
                "availability": avail_by_key.get(
                    (EntityTypeEnum.teacher.value, t.id), []
                ),
            }
            for t in teachers
        ],
        "rooms": [
            {
                "name": r.name,
                "capacity": r.capacity,
                "comment": r.comment,
                "allowed_subjects": [s.name for s in r.allowed_subjects],
                "availability": avail_by_key.get((EntityTypeEnum.room.value, r.id), []),
            }
            for r in rooms
        ],
        "parents": [
            {
                "first_name": p.first_name,
                "last_name": p.last_name,
                "phone": p.phone,
                "email": p.email,
                "comment": p.comment,
            }
            for p in parents
        ],
        "students": [
            {
                "first_name": s.first_name,
                "last_name": s.last_name,
                "birth_date": _fmt_date(s.birth_date),
                "comment": s.comment,
                "is_active": s.is_active,
                "parent": (
                    full_name(s.parent.first_name, s.parent.last_name)
                    if s.parent
                    else None
                ),
                "availability": avail_by_key.get(
                    (EntityTypeEnum.student.value, s.id), []
                ),
                "lesson_requests": [
                    {
                        "subject": subject_names.get(r.subject_id),
                        "lesson_type": _fmt_lesson_type(r.lesson_type),
                        "lessons_per_week": r.lessons_per_week,
                        "duration_minutes": r.duration_minutes,
                        "preferred_teacher": (
                            teacher_names.get(r.preferred_teacher_id)
                            if r.preferred_teacher_id
                            else None
                        ),
                        "teacher_is_required": r.teacher_is_required,
                        "priority": r.priority,
                        "notes": r.notes,
                        "excluded_students": [
                            full_name(s.first_name, s.last_name)
                            for s in r.excluded_students
                        ],
                    }
                    for r in requests_by_student.get(s.id, [])
                ],
            }
            for s in students
        ],
        "prices": [
            {
                "subject": subject_names.get(p.subject_id),
                "lesson_type": _fmt_lesson_type(p.lesson_type),
                "min_participants": p.min_participants,
                "max_participants": p.max_participants,
                "price_per_student": p.price_per_student,
            }
            for p in prices
        ],
        "teacher_rates": [
            {
                "teacher": (
                    full_name(r.teacher.first_name, r.teacher.last_name)
                    if r.teacher is not None
                    else None
                ),
                "subject": subject_names.get(r.subject_id),
                "lesson_type": _fmt_lesson_type(r.lesson_type),
                "rate_type": r.rate_type.value if r.rate_type is not None else "fixed",
                "rate_per_lesson": r.rate_per_lesson,
            }
            for r in teacher_rates
        ],
        "optimizer_settings": (
            {
                "time_limit_seconds": settings[0].time_limit_seconds,
                "weight_presence": settings[0].weight_presence,
                "reward_preferred_teacher": settings[0].reward_preferred_teacher,
                "penalty_student_same_day": settings[0].penalty_student_same_day,
                "penalty_early_late": settings[0].penalty_early_late,
                "early_hour": settings[0].early_hour,
                "late_hour": settings[0].late_hour,
                "weight_teacher_balance": settings[0].weight_teacher_balance,
                "weight_room_balance": settings[0].weight_room_balance,
                "group_min_size": settings[0].group_min_size,
                "group_max_size": settings[0].group_max_size,
            }
            if settings
            else {}
        ),
        "schedules": [
            {
                "name": sch.name,
                "week_start": _fmt_date(sch.week_start),
                "status": sch.status.value,
                "unscheduled_report": sch.unscheduled_report,
                "lessons": [
                    {
                        "lesson_type": _fmt_lesson_type(l.lesson_type),
                        "student": (
                            full_name(l.student.first_name, l.student.last_name)
                            if l.student
                            else None
                        ),
                        "subject": (
                            subject_names.get(l.lesson_request.subject_id)
                            if l.lesson_request
                            else None
                        ),
                        "participants": [
                            (
                                f"{p.student.last_name} {p.student.first_name}".strip()
                                if p.student
                                else ""
                            )
                            for p in l.participants
                            if p.student
                        ],
                        "day_of_week": l.day_of_week,
                        "start_time": _fmt_time(l.start_time),
                        "end_time": _fmt_time(l.end_time),
                        "teacher": (
                            teacher_names.get(l.teacher_id) if l.teacher else None
                        ),
                        "room": l.room.name if l.room else None,
                    }
                    for l in lesson_rows
                    if l.schedule_id == sch.id
                ],
            }
            for sch in schedules
        ],
    }
    return payload


# ---------------------------------------------------------------------------
# Импорт
# ---------------------------------------------------------------------------


def import_all(db: Session, payload: dict) -> dict:
    """Загружает данные из JSON (формат export_all). Старые данные удаляются."""
    if not isinstance(payload, dict):
        raise ValueError("Корневой элемент должен быть JSON-объектом")

    wipe_all_data(db)
    warnings: list[str] = []

    # 1. Направления
    subject_map: dict[str, Subject] = {}
    for s in payload.get("subjects", []) or []:
        name = str(s.get("name") or "").strip()
        if not name:
            continue
        obj = Subject(
            name=name,
            description=s.get("description"),
            default_duration_minutes=int(s.get("default_duration_minutes") or 60),
            is_active=bool(s.get("is_active", True)),
        )
        db.add(obj)
        db.flush()
        subject_map[name] = obj

    # 2. Педагоги
    teacher_map: dict[str, Teacher] = {}
    for t in payload.get("teachers", []) or []:
        first = str(t.get("first_name") or "").strip()
        last = str(t.get("last_name") or "").strip()
        if not first or not last:
            continue
        obj = Teacher(
            first_name=first,
            last_name=last,
            comment=t.get("comment"),
            is_active=bool(t.get("is_active", True)),
            max_weekly_hours=t.get("max_weekly_hours"),
        )
        db.add(obj)
        db.flush()
        for sname in t.get("subjects", []) or []:
            subj = subject_map.get(str(sname).strip())
            if subj is not None:
                obj.subjects.append(subj)
            else:
                warnings.append(f"Педагог {full_name(first, last)}: направление «{sname}» не найдено")
        _add_availabilities(db, obj.id, EntityTypeEnum.teacher, t.get("availability"))
        teacher_map[full_name(first, last)] = obj

    # 3. Кабинеты
    room_map: dict[str, Room] = {}
    for r in payload.get("rooms", []) or []:
        name = str(r.get("name") or "").strip()
        if not name:
            continue
        obj = Room(
            name=name,
            capacity=int(r.get("capacity") or 1),
            comment=r.get("comment"),
        )
        db.add(obj)
        db.flush()
        for sname in r.get("allowed_subjects", []) or []:
            subj = subject_map.get(str(sname).strip())
            if subj is not None:
                obj.allowed_subjects.append(subj)
            else:
                warnings.append(f"Кабинет {name}: направление «{sname}» не найдено")
        _add_availabilities(db, obj.id, EntityTypeEnum.room, r.get("availability"))
        room_map[name] = obj

    # 4. Родители
    parent_map: dict[str, Parent] = {}
    for p in payload.get("parents", []) or []:
        first = str(p.get("first_name") or "").strip()
        last = str(p.get("last_name") or "").strip()
        if not first or not last:
            continue
        key = full_name(first, last)
        if key in parent_map:
            continue
        obj = Parent(
            first_name=first,
            last_name=last,
            phone=p.get("phone"),
            email=p.get("email"),
            comment=p.get("comment"),
        )
        db.add(obj)
        db.flush()
        parent_map[key] = obj

    # 5. Ученики и их требования
    student_map: dict[str, Student] = {}
    pending_exclusions: list[tuple[LessonRequest, list[str]]] = []
    # (student_id, subject_id, lesson_type) -> id требования
    request_lookup: dict[tuple[int, int, LessonTypeEnum | str], int] = {}
    for st in payload.get("students", []) or []:
        first = str(st.get("first_name") or "").strip()
        last = str(st.get("last_name") or "").strip()
        if not first or not last:
            continue
        parent_name = st.get("parent")
        parent_obj = (
            parent_map.get(str(parent_name).strip()) if parent_name else None
        )
        obj = Student(
            first_name=first,
            last_name=last,
            birth_date=_parse_date(st.get("birth_date")),
            comment=st.get("comment"),
            is_active=bool(st.get("is_active", True)),
            parent_id=parent_obj.id if parent_obj else None,
        )
        db.add(obj)
        db.flush()
        _add_availabilities(db, obj.id, EntityTypeEnum.student, st.get("availability"))
        student_map[full_name(first, last)] = obj

        for lr in st.get("lesson_requests", []) or []:
            subj_name = str(lr.get("subject") or "").strip()
            subj = subject_map.get(subj_name) if subj_name else None
            if subj is None:
                warnings.append(f"Ученик {full_name(first, last)}: направление «{subj_name}» не найдено — требование пропущено")
                continue
            teacher_name = lr.get("preferred_teacher")
            teacher_obj = (
                teacher_map.get(str(teacher_name).strip())
                if teacher_name
                else None
            )
            req = LessonRequest(
                student_id=obj.id,
                subject_id=subj.id,
                lesson_type=_parse_lesson_type(lr.get("lesson_type")),
                lessons_per_week=int(lr.get("lessons_per_week") or 1),
                duration_minutes=int(lr.get("duration_minutes") or 60),
                preferred_teacher_id=teacher_obj.id if teacher_obj else None,
                teacher_is_required=bool(lr.get("teacher_is_required") or False),
                priority=int(lr.get("priority") or 1),
                notes=lr.get("notes"),
            )
            db.add(req)
            db.flush()
            request_lookup.setdefault(
                (req.student_id, req.subject_id, req.lesson_type), req.id
            )
            pending_exclusions.append((req, lr.get("excluded_students") or []))

    # 5.1. Исключения: дети, с которыми нельзя заниматься в группе
    for req, names in pending_exclusions:
        for name in names:
            excl = student_map.get(str(name).strip())
            if excl is None or excl.id == req.student_id:
                warnings.append(
                    f"Ученик {req.student.full_name}: исключение «{name}» не найдено"
                )
                continue
            req.excluded_students.append(excl)

    # 6. Цены
    for p in payload.get("prices", []) or []:
        subj_name = str(p.get("subject") or "").strip()
        subj = subject_map.get(subj_name) if subj_name else None
        if subj is None:
            warnings.append(f"Цена: направление «{subj_name}» не найдено")
            continue
        min_part = int(p.get("min_participants") or 1)
        max_part = int(p.get("max_participants") or min_part)
        db.add(
            Price(
                subject_id=subj.id,
                lesson_type=_parse_lesson_type(p.get("lesson_type")),
                min_participants=min_part,
                max_participants=max(max_part, min_part),
                price_per_student=float(p.get("price_per_student") or 0),
            )
        )

    # 7. Ставки педагогов
    for rr in payload.get("teacher_rates", []) or []:
        subj_name = str(rr.get("subject") or "").strip()
        subj = subject_map.get(subj_name) if subj_name else None
        if subj is None:
            warnings.append(f"Ставка педагога: направление «{subj_name}» не найдено")
            continue
        teacher_name = rr.get("teacher")
        teacher_obj = (
            teacher_map.get(str(teacher_name).strip()) if teacher_name else None
        )
        if teacher_name and teacher_obj is None:
            warnings.append(
                f"Ставка педагога: педагог «{teacher_name}» не найден, ставка пропущена"
            )
            continue
        db.add(
            TeacherRate(
                teacher_id=teacher_obj.id if teacher_obj else None,
                subject_id=subj.id,
                lesson_type=_parse_lesson_type(rr.get("lesson_type")),
                rate_type=_parse_rate_type(rr.get("rate_type")),
                rate_per_lesson=float(rr.get("rate_per_lesson") or 0),
            )
        )

    # 8. Настройки оптимизатора
    opt = db.scalars(select(OptimizerSettings).limit(1)).first()
    if opt is None:
        opt = OptimizerSettings()
        db.add(opt)
    oset = payload.get("optimizer_settings") or {}
    for field in (
        "time_limit_seconds",
        "weight_presence",
        "reward_preferred_teacher",
        "penalty_student_same_day",
        "penalty_early_late",
        "early_hour",
        "late_hour",
        "weight_teacher_balance",
        "weight_room_balance",
        "group_min_size",
        "group_max_size",
    ):
        if field in oset and oset[field] is not None:
            setattr(opt, field, oset[field])

    # 9. Расписания
    for sch in payload.get("schedules", []) or []:
        name = str(sch.get("name") or "").strip()
        if not name:
            continue
        week_start = _parse_date(sch.get("week_start")) or date.today()
        sched = Schedule(
            name=name,
            week_start=week_start,
            status=_parse_status(sch.get("status")),
            unscheduled_report=sch.get("unscheduled_report"),
        )
        db.add(sched)
        db.flush()
        for ls in sch.get("lessons", []) or []:
            lesson_type = _parse_lesson_type(ls.get("lesson_type"))
            teacher_name = ls.get("teacher")
            teacher_obj = teacher_map.get(str(teacher_name).strip()) if teacher_name else None
            room_name = ls.get("room")
            room_obj = room_map.get(str(room_name).strip()) if room_name else None
            if teacher_obj is None or room_obj is None:
                warnings.append(
                    f"Расписание {name}: занятие без педагога/кабинета пропущено"
                )
                continue
            subject_name = ls.get("subject")
            subject_obj = subject_map.get(str(subject_name).strip()) if subject_name else None
            participant_names = ls.get("participants") or []
            if not participant_names and ls.get("student"):
                participant_names = [ls.get("student")]
            participant_requests: list[LessonRequest] = []
            for pname in participant_names:
                st_obj = student_map.get(str(pname).strip())
                if st_obj is None or subject_obj is None:
                    continue
                req_id = request_lookup.get((st_obj.id, subject_obj.id, lesson_type))
                if req_id is not None:
                    req = db.get(LessonRequest, req_id)
                    if req is not None:
                        participant_requests.append(req)
            anchor = participant_requests[0] if participant_requests else None
            anchor_student_id = None
            if anchor is not None:
                anchor_student_id = anchor.student_id
            else:
                student_name = ls.get("student")
                st_obj = (
                    student_map.get(str(student_name).strip()) if student_name else None
                )
                anchor_student_id = st_obj.id if st_obj else None
            db.add(
                ScheduledLesson(
                    schedule_id=sched.id,
                    lesson_type=lesson_type,
                    lesson_request_id=anchor.id if anchor else None,
                    student_id=anchor_student_id,
                    day_of_week=int(ls.get("day_of_week") or 0),
                    start_time=_parse_time(ls.get("start_time")) or time(9),
                    end_time=_parse_time(ls.get("end_time")) or time(10),
                    teacher_id=teacher_obj.id,
                    room_id=room_obj.id,
                    participants=participant_requests,
                )
            )

    db.commit()
    return {
        "subjects": len(subject_map),
        "teachers": len(teacher_map),
        "rooms": len(room_map),
        "parents": len(parent_map),
        "students": len(student_map),
        "prices": len(payload.get("prices", []) or []),
        "teacher_rates": len(payload.get("teacher_rates", []) or []),
        "schedules": len(payload.get("schedules", []) or []),
        "warnings": warnings,
    }