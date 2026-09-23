import random
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

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

DAYS = [0, 1, 2, 3, 4, 5]  # Пн..Сб


def _merge_avail(a: list[tuple[int, time, time]]) -> list[tuple[int, time, time]]:
    return a


def seed_database(db: Session, *, force: bool = False) -> dict:
    """Заполняет базу демонстрационными данными.

    По умолчанию не затирает существующие данные: если база уже содержит
    направления — сидинг пропускается. force=True принудительно очищает
    и заполняет базу (используется только вручную/в тестах).
    """
    from sqlalchemy import func

    from app.services.backup_service import wipe_all_data

    if not force:
        existing = db.scalar(select(func.count()).select_from(Subject))
        if existing:
            return {"skipped": True, "reason": "database already contains data"}

    wipe_all_data(db)

    # Направления
    subjects = {
        "math": Subject(name="Математика", description="Подготовка по математике", default_duration_minutes=60),
        "eng": Subject(name="Английский язык", description="Английский для детей", default_duration_minutes=45),
        "rus": Subject(name="Русский язык", description="Русский язык и литература", default_duration_minutes=60),
        "robots": Subject(name="Робототехника", description="Сборка и программирование роботов", default_duration_minutes=90),
        "prog": Subject(name="Программирование", description="Питон и Scratch", default_duration_minutes=60),
        "art": Subject(name="Рисование", description="Изобразительное искусство", default_duration_minutes=90),
    }
    db.add_all(subjects.values())
    db.flush()

    # Педагоги (5 человек)
    teachers = [
        Teacher(first_name="Анна", last_name="Петрова", comment="Математика, физика", subjects=[subjects["math"], subjects["rus"], subjects["prog"]], max_weekly_hours=20),
        Teacher(first_name="Ольга", last_name="Смирнова", comment="Английский язык", subjects=[subjects["eng"], subjects["art"]], max_weekly_hours=18),
        Teacher(first_name="Дмитрий", last_name="Кузнецов", comment="Робототехника", subjects=[subjects["robots"], subjects["prog"]], max_weekly_hours=16),
        Teacher(first_name="Мария", last_name="Иванова", comment="Начальная школа", subjects=[subjects["rus"]], max_weekly_hours=14),
        Teacher(first_name="Сергей", last_name="Волков", comment="Программирование", subjects=[subjects["prog"]], max_weekly_hours=20),
    ]
    db.add_all(teachers)
    db.flush()

    # Доступность педагогов: Пн, Ср, Пт 14:00-19:00, Вт/Чт/Сб 10:00-17:00
    for t in teachers:
        db.add_all([
            Availability(entity_type=EntityTypeEnum.teacher, entity_id=t.id, day_of_week=0, start_time=time(14), end_time=time(19)),
            Availability(entity_type=EntityTypeEnum.teacher, entity_id=t.id, day_of_week=2, start_time=time(14), end_time=time(19)),
            Availability(entity_type=EntityTypeEnum.teacher, entity_id=t.id, day_of_week=4, start_time=time(15), end_time=time(19)),
            Availability(entity_type=EntityTypeEnum.teacher, entity_id=t.id, day_of_week=1, start_time=time(10), end_time=time(17)),
            Availability(entity_type=EntityTypeEnum.teacher, entity_id=t.id, day_of_week=3, start_time=time(10), end_time=time(17)),
            Availability(entity_type=EntityTypeEnum.teacher, entity_id=t.id, day_of_week=5, start_time=time(10), end_time=time(14)),
        ])

    # Кабинеты (5 комнат)
    rooms = [
        Room(name="Кабинет №1", capacity=8, comment="Универсальный класс", allowed_subjects=[subjects["math"], subjects["rus"], subjects["eng"]]),
        Room(name="Кабинет №2", capacity=2, comment="Индивидуальные занятия", allowed_subjects=[subjects["math"], subjects["eng"], subjects["rus"], subjects["art"]]),
        Room(name="Кабинет №3", capacity=10, comment="Групповой класс", allowed_subjects=[subjects["eng"], subjects["rus"], subjects["math"]]),
        Room(name="Лаборатория робототехники", capacity=8, comment="С оборудованием", allowed_subjects=[subjects["robots"], subjects["prog"]]),
        Room(name="Компьютерный класс", capacity=6, comment="ПК для программирования", allowed_subjects=[subjects["prog"], subjects["robots"]]),
    ]
    db.add_all(rooms)
    db.flush()

    for r in rooms:
        db.add_all([
            Availability(entity_type=EntityTypeEnum.room, entity_id=r.id, day_of_week=d, start_time=time(9), end_time=time(21))
            for d in DAYS
        ])

    # Родители
    parents = [
        Parent(first_name="Елена", last_name="Иванова", phone="+7 (900) 111-11-11", email="e.ivanova@mail.ru"),
        Parent(first_name="Павел", last_name="Петров", phone="+7 (900) 222-22-22", email="p.petrov@mail.ru"),
        Parent(first_name="Александр", last_name="Сидоров", phone="+7 (900) 333-33-33"),
        Parent(first_name="Наталья", last_name="Смирнова", phone="+7 (900) 444-44-44"),
    ]
    db.add_all(parents)
    db.flush()

    # Дети (10)
    student_data = [
        ("Иван", "Иванов", date(2014, 3, 12), parents[0]),
        ("Петр", "Петров", date(2013, 7, 1), parents[1]),
        ("Алексей", "Сидоров", date(2015, 1, 25), parents[2]),
        ("Анна", "Смирнова", date(2014, 11, 3), parents[3]),
        ("Максим", "Кузнецов", date(2013, 6, 19), None),
        ("Софья", "Козлова", date(2015, 8, 30), None),
        ("Дмитрий", "Новиков", date(2012, 4, 15), None),
        ("Мария", "Морозова", date(2014, 2, 7), None),
        ("Кирилл", "Волков", date(2013, 9, 22), None),
        ("Алиса", "Соколова", date(2015, 5, 10), None),
    ]
    students = [
        Student(first_name=fn, last_name=ln, birth_date=bd, parent_id=(p.id if p else None))
        for fn, ln, bd, p in student_data
    ]
    db.add_all(students)
    db.flush()

    # Доступность детей: разные слоты
    child_avail = {
        # (times patterns) Пн/Ср/Пт или Вт/Чт
        "week_aft": [(0, time(15), time(19)), (2, time(15), time(19)), (4, time(16), time(20))],
        "week_mid": [(0, time(14), time(18)), (3, time(15), time(19)), (5, time(10), time(14))],
        "all_ev": [(0, time(16), time(20)), (1, time(16), time(20)), (2, time(16), time(20)), (3, time(16), time(20))],
        "saturday": [(5, time(10), time(15)), (0, time(12), time(18))],
        "morning_wd": [(0, time(10), time(13)), (2, time(10), time(13)), (4, time(10), time(13))],
    }
    av_patterns = ["week_aft", "week_mid", "all_ev", "saturday", "morning_wd", "week_aft", "all_ev", "week_mid", "saturday", "morning_wd"]
    for i, st in enumerate(students):
        for d, s, e in child_avail[av_patterns[i]]:
            db.add(Availability(entity_type=EntityTypeEnum.student, entity_id=st.id, day_of_week=d, start_time=s, end_time=e))

    db.flush()

    # Цены
    db.add_all([
        Price(subject_id=subjects["math"].id, lesson_type=LessonTypeEnum.individual, min_participants=1, max_participants=1, price_per_student=1000),
        Price(subject_id=subjects["eng"].id, lesson_type=LessonTypeEnum.individual, min_participants=1, max_participants=1, price_per_student=900),
        Price(subject_id=subjects["rus"].id, lesson_type=LessonTypeEnum.individual, min_participants=1, max_participants=1, price_per_student=800),
        Price(subject_id=subjects["robots"].id, lesson_type=LessonTypeEnum.individual, min_participants=1, max_participants=1, price_per_student=1200),
        Price(subject_id=subjects["prog"].id, lesson_type=LessonTypeEnum.individual, min_participants=1, max_participants=1, price_per_student=1100),
        Price(subject_id=subjects["art"].id, lesson_type=LessonTypeEnum.individual, min_participants=1, max_participants=1, price_per_student=800),
        # Групповые тарифы по количеству участников
        Price(subject_id=subjects["math"].id, lesson_type=LessonTypeEnum.group, min_participants=2, max_participants=2, price_per_student=800),
        Price(subject_id=subjects["math"].id, lesson_type=LessonTypeEnum.group, min_participants=3, max_participants=4, price_per_student=700),
        Price(subject_id=subjects["math"].id, lesson_type=LessonTypeEnum.group, min_participants=5, max_participants=8, price_per_student=550),
        Price(subject_id=subjects["eng"].id, lesson_type=LessonTypeEnum.group, min_participants=2, max_participants=2, price_per_student=700),
        Price(subject_id=subjects["eng"].id, lesson_type=LessonTypeEnum.group, min_participants=3, max_participants=5, price_per_student=600),
        Price(subject_id=subjects["eng"].id, lesson_type=LessonTypeEnum.group, min_participants=6, max_participants=10, price_per_student=500),
        Price(subject_id=subjects["robots"].id, lesson_type=LessonTypeEnum.group, min_participants=2, max_participants=4, price_per_student=900),
        Price(subject_id=subjects["robots"].id, lesson_type=LessonTypeEnum.group, min_participants=5, max_participants=8, price_per_student=750),
        Price(subject_id=subjects["art"].id, lesson_type=LessonTypeEnum.group, min_participants=2, max_participants=8, price_per_student=600),
    ])

    # Ставки педагогам (по умолчанию и индивидуальные)
    db.add_all([
        # Умолчания по предметам/типам (teacher_id=NULL)
        TeacherRate(teacher_id=None, subject_id=subjects["math"].id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=500),
        TeacherRate(teacher_id=None, subject_id=subjects["eng"].id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=450),
        TeacherRate(teacher_id=None, subject_id=subjects["rus"].id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=400),
        TeacherRate(teacher_id=None, subject_id=subjects["robots"].id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=600),
        TeacherRate(teacher_id=None, subject_id=subjects["prog"].id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=550),
        TeacherRate(teacher_id=None, subject_id=subjects["art"].id, lesson_type=LessonTypeEnum.both, rate_per_lesson=400),
        TeacherRate(teacher_id=None, subject_id=subjects["math"].id, lesson_type=LessonTypeEnum.group, rate_per_lesson=1200),
        TeacherRate(teacher_id=None, subject_id=subjects["eng"].id, lesson_type=LessonTypeEnum.group, rate_per_lesson=1000),
        TeacherRate(teacher_id=None, subject_id=subjects["robots"].id, lesson_type=LessonTypeEnum.group, rate_per_lesson=1400),
        # Процентная ставка: 40% от выручки занятия (напр. групповое рисование)
        TeacherRate(teacher_id=None, subject_id=subjects["art"].id, lesson_type=LessonTypeEnum.group, rate_type=RateTypeEnum.percent, rate_per_lesson=40),
        # Индивидуальные ставки отдельных педагогов
        TeacherRate(teacher_id=teachers[0].id, subject_id=subjects["math"].id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=600),
        TeacherRate(teacher_id=teachers[4].id, subject_id=subjects["prog"].id, lesson_type=LessonTypeEnum.individual, rate_per_lesson=700),
    ])

    # Индивидуальные требования (10-15)
    requests = [
        (students[0], subjects["math"], 2, 60, teachers[0], False),
        (students[1], subjects["eng"], 2, 45, teachers[1], False),
        (students[2], subjects["prog"], 1, 60, teachers[2], False),
        (students[3], subjects["art"], 2, 90, teachers[1], False),
        (students[4], subjects["robots"], 1, 90, teachers[2], True),
        (students[5], subjects["rus"], 2, 60, teachers[3], False),
        (students[6], subjects["math"], 1, 60, teachers[0], False),
        (students[7], subjects["eng"], 2, 45, teachers[1], False),
        (students[8], subjects["prog"], 2, 60, teachers[4], False),
        (students[9], subjects["art"], 1, 90, None, False),
        (students[2], subjects["math"], 2, 60, teachers[0], False),
        (students[4], subjects["prog"], 1, 60, teachers[4], False),
    ]
    for st, subj, n, dur, pref, req in requests:
        lr = LessonRequest(
            student_id=st.id, subject_id=subj.id, lesson_type=LessonTypeEnum.individual,
            lessons_per_week=n, duration_minutes=dur,
            preferred_teacher_id=(pref.id if pref else None),
            teacher_is_required=req, priority=2, notes="Предпочтение вечернее время",
        )
        db.add(lr)

    db.flush()

    # Групповые требования (группы формируются автоматически из общих слотов)
    # Формат: (ученик, предмет, занятий/нед., длительность, педагог, обязательный, тип)
    group_requests = [
        (students[0], subjects["math"], 1, 60, None, False, LessonTypeEnum.group),
        (students[1], subjects["math"], 1, 60, None, False, LessonTypeEnum.both),
        (students[2], subjects["math"], 1, 60, None, False, LessonTypeEnum.group),
        (students[2], subjects["robots"], 1, 90, None, False, LessonTypeEnum.group),
        (students[6], subjects["robots"], 1, 90, None, False, LessonTypeEnum.group),
        (students[0], subjects["art"], 1, 90, None, False, LessonTypeEnum.group),
        (students[1], subjects["art"], 1, 90, None, False, LessonTypeEnum.group),
        (students[3], subjects["eng"], 1, 45, None, False, LessonTypeEnum.group),
        (students[5], subjects["eng"], 1, 45, None, False, LessonTypeEnum.group),
        (students[6], subjects["eng"], 1, 45, None, False, LessonTypeEnum.group),
        (students[4], subjects["prog"], 1, 60, None, False, LessonTypeEnum.group),
        (students[8], subjects["prog"], 1, 60, None, False, LessonTypeEnum.group),
        (students[9], subjects["prog"], 1, 60, None, False, LessonTypeEnum.group),
    ]
    for st, subj, n, dur, pref, req, lt in group_requests:
        db.add(
            LessonRequest(
                student_id=st.id, subject_id=subj.id,
                lesson_type=lt,
                lessons_per_week=n, duration_minutes=dur,
                preferred_teacher_id=(pref.id if pref else None),
                teacher_is_required=req, priority=1,
                notes=(
                    "Индивидуально и в группе. Группа формируется автоматически"
                    if lt == LessonTypeEnum.both
                    else "Групповое занятие. Группа формируется автоматически"
                ),
            )
        )

    db.flush()

    # Исключения: Кузнецов Максим не может заниматься в группе по программированию
    # вместе с Волковым Кириллом (автогруппа формируется из остальных учеников).
    prog_exclusions = db.scalars(
        select(LessonRequest).where(
            LessonRequest.student_id == students[4].id,
            LessonRequest.subject_id == subjects["prog"].id,
        )
    ).all()
    for prog_req in prog_exclusions:
        prog_req.excluded_students.append(students[8])

    db.flush()

    # Настройки оптимизатора
    opt = db.scalars(select(OptimizerSettings).limit(1)).first()
    if opt is None:
        opt = OptimizerSettings()
        db.add(opt)
    opt.time_limit_seconds = 30
    opt.weight_presence = 1000.0
    opt.reward_preferred_teacher = 100.0
    opt.penalty_student_same_day = 50.0
    opt.penalty_early_late = 20.0
    opt.early_hour = 9
    opt.late_hour = 20
    opt.weight_teacher_balance = 30.0
    opt.weight_room_balance = 10.0
    opt.group_min_size = 2
    opt.group_max_size = 8
    db.commit()

    return {
        "subjects": len(subjects),
        "teachers": len(teachers),
        "rooms": len(rooms),
        "students": len(students),
        "parents": len(parents),
        "lesson_requests": len(requests) + len(group_requests),
    }