from datetime import time

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.entities import (
    Availability,
    EntityTypeEnum,
    Room,
    ScheduledLesson,
    Student,
    Subject,
    Teacher,
)
from app.schemas.schemas import ConflictDetail, ConflictType


def _times_overlap(s1: time, e1: time, s2: time, e2: time) -> bool:
    return s1 < e2 and s2 < e1


def _fmt(t: time) -> str:
    return f"{t.hour:02d}:{t.minute:02d}"


def _availability_overlaps(avail_rows, start: time, end: time) -> bool:
    """Интервал занятия целиком помещается в одну из записей доступности."""
    for a in avail_rows:
        if a.start_time <= start and end <= a.end_time:
            return True
    return False


def check_conflicts(
    db: Session,
    schedule_id: int,
    day_of_week: int,
    start_time: time,
    end_time: time,
    teacher_id: int,
    room_id: int,
    student_ids: list[int],
    exclude_lesson_id: int | None = None,
    subject_id: int | None = None,
) -> list[ConflictDetail]:
    conflicts: list[ConflictDetail] = []

    # ── Пересекающиеся занятия в расписании ──────────────────────────────
    q = select(ScheduledLesson).where(
        and_(
            ScheduledLesson.schedule_id == schedule_id,
            ScheduledLesson.day_of_week == day_of_week,
        )
    )
    if exclude_lesson_id is not None:
        q = q.where(ScheduledLesson.id != exclude_lesson_id)

    overlapping = [
        sl
        for sl in db.execute(q).scalars().all()
        if _times_overlap(sl.start_time, sl.end_time, start_time, end_time)
    ]

    names = {}

    def teacher_name(tid: int) -> str:
        if tid not in names:
            t = db.get(Teacher, tid)
            names[tid] = f"{t.last_name} {t.first_name}".strip() if t else f"#{tid}"
        return names[tid]

    for sl in overlapping:
        if sl.teacher_id == teacher_id:
            conflicts.append(
                ConflictDetail(
                    conflict_type=ConflictType.teacher_busy,
                    message=(
                        f"{teacher_name(teacher_id)} уже занят(а) "
                        f"{_fmt(sl.start_time)}–{_fmt(sl.end_time)} на другом занятии"
                    ),
                    conflicting_lesson_id=sl.id,
                )
            )
        if sl.room_id == room_id:
            room = db.get(Room, room_id)
            conflicts.append(
                ConflictDetail(
                    conflict_type=ConflictType.room_busy,
                    message=(
                        f"Кабинет {room.name if room else '№' + str(room_id)} уже занят "
                        f"{_fmt(sl.start_time)}–{_fmt(sl.end_time)}"
                    ),
                    conflicting_lesson_id=sl.id,
                )
            )
        # Проверка занятости каждого участника
        sl_student_ids: list[int] = []
        if sl.student_id is not None:
            sl_student_ids.append(sl.student_id)
        # Участники группового занятия (по запросам в join-таблице)
        sl_student_ids.extend(
            p.student_id
            for p in sl.participants
            if p.student_id is not None
        )
        for sid in student_ids:
            if sid in sl_student_ids:
                st = db.get(Student, sid)
                conflicts.append(
                    ConflictDetail(
                        conflict_type=ConflictType.student_busy,
                        message=(
                            f"Ребёнок {st.last_name + ' ' + st.first_name if st else sid} "
                            f"занят в это время"
                        ),
                        conflicting_lesson_id=sl.id,
                    )
                )

    # ── Проверка доступности ─────────────────────────────────────────────
    teacher_avail = db.execute(
        select(Availability).where(
            and_(
                Availability.entity_type == EntityTypeEnum.teacher,
                Availability.entity_id == teacher_id,
                Availability.day_of_week == day_of_week,
            )
        )
    ).scalars().all()
    if teacher_avail and not _availability_overlaps(teacher_avail, start_time, end_time):
        conflicts.append(
            ConflictDetail(
                conflict_type=ConflictType.teacher_required,
                message=f"{teacher_name(teacher_id)} работает только в другое время",
            )
        )

    room_avail = db.execute(
        select(Availability).where(
            and_(
                Availability.entity_type == EntityTypeEnum.room,
                Availability.entity_id == room_id,
                Availability.day_of_week == day_of_week,
            )
        )
    ).scalars().all()
    room = db.get(Room, room_id)
    room_label = room.name if room else f"№{room_id}"
    if room_avail and not _availability_overlaps(room_avail, start_time, end_time):
        conflicts.append(
            ConflictDetail(
                conflict_type=ConflictType.room_capacity,
                message=f"Кабинет {room_label} в это время недоступен",
            )
        )

    for sid in student_ids:
        stu_avail = db.execute(
            select(Availability).where(
                and_(
                    Availability.entity_type == EntityTypeEnum.student,
                    Availability.entity_id == sid,
                    Availability.day_of_week == day_of_week,
                )
            )
        ).scalars().all()
        if stu_avail and not _availability_overlaps(stu_avail, start_time, end_time):
            conflicts.append(
                ConflictDetail(
                    conflict_type=ConflictType.student_busy,
                    message=f"Ребёнок не может заниматься в это время (расписание/доступность)",
                )
            )

    # ── Вместимость кабинета ─────────────────────────────────────────────
    if room and len(student_ids) > room.capacity:
        conflicts.append(
            ConflictDetail(
                conflict_type=ConflictType.room_capacity,
                message=(
                    f"Вместимость кабинета {room_label} — {room.capacity} чел., "
                    f"а в занятии {len(student_ids)} участник(ов)"
                ),
            )
        )

    # ── Совместимость направления ────────────────────────────────────────
    if subject_id is not None:
        if room and room.allowed_subjects and subject_id not in [s.id for s in room.allowed_subjects]:
            subj = db.get(Subject, subject_id)
            conflicts.append(
                ConflictDetail(
                    conflict_type=ConflictType.subject_mismatch,
                    message=(
                        f"Кабинет {room_label} не предназначен для "
                        f"«{subj.name if subj else subject_id}»"
                    ),
                )
            )
        teacher = db.get(Teacher, teacher_id)
        if teacher and subject_id not in [s.id for s in teacher.subjects]:
            subj = db.get(Subject, subject_id)
            conflicts.append(
                ConflictDetail(
                    conflict_type=ConflictType.subject_mismatch,
                    message=(
                        f"{teacher_name(teacher_id)} не ведёт направление "
                        f"«{subj.name if subj else subject_id}»"
                    ),
                )
            )
        else:
            # Обязательный педагог задания
            if teacher is None:
                conflicts.append(
                    ConflictDetail(
                        conflict_type=ConflictType.teacher_required,
                        message="Педагог не найден",
                    )
                )

    return conflicts