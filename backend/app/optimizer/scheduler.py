"""Универсальный оптимизатор расписания на основе Google OR-Tools CP-SAT."""

from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional

from ortools.sat.python import cp_model
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    Availability,
    EntityTypeEnum,
    GroupLesson,
    LessonRequest,
    LessonTypeEnum,
    OptimizerSettings,
    Room,
    Student,
    Subject,
    Teacher,
    group_lesson_participants,
    room_subjects,
    teacher_subjects,
)

MINUTES_IN_DAY = 1440
SCALE = 100  # масштаб весов целевой функции -> целые коэффициенты


@dataclass
class TeacherCand:
    db_id: int
    name: str
    availability: dict[int, list[tuple[int, int]]] = field(default_factory=dict)
    has_any_availability: bool = False

    def fits(self, day: int, start_slot: int, dur_slots: int, slots_in_day: int) -> bool:
        if not self.has_any_availability:
            return 0 <= start_slot and start_slot + dur_slots <= slots_in_day
        return any(
            ivs <= start_slot and start_slot + dur_slots <= ive
            for (ivs, ive) in self.availability.get(day, [])
        )


@dataclass
class RoomCand:
    db_id: int
    name: str
    capacity: int
    availability: dict[int, list[tuple[int, int]]] = field(default_factory=dict)
    has_any_availability: bool = False

    def fits(self, day: int, start_slot: int, dur_slots: int, slots_in_day: int) -> bool:
        if not self.has_any_availability:
            return 0 <= start_slot and start_slot + dur_slots <= slots_in_day
        return any(
            ivs <= start_slot and start_slot + dur_slots <= ive
            for (ivs, ive) in self.availability.get(day, [])
        )


@dataclass
class StudentAvail:
    db_id: int
    name: str
    availability: dict[int, list[tuple[int, int]]] = field(default_factory=dict)

    def fits(self, day: int, start_slot: int, dur_slots: int) -> bool:
        return any(
            ivs <= start_slot and start_slot + dur_slots <= ive
            for (ivs, ive) in self.availability.get(day, [])
        )


@dataclass
class LessonOccurrence:
    """Одно вхождение занятия, которое нужно разместить в расписании."""

    id: str
    title: str
    lesson_type: LessonTypeEnum
    lesson_request_id: Optional[int] = None
    group_lesson_id: Optional[int] = None
    student_ids: list[int] = field(default_factory=list)
    subject_id: int = 0
    subject_name: str = ""
    duration_minutes: int = 60
    priority: int = 1
    preferred_teacher_id: Optional[int] = None
    teacher_is_required: bool = False
    notes: Optional[str] = None


@dataclass
class UnscheduledInfo:
    identifier: str
    name: str
    reason: str
    suggestions: list[str] = field(default_factory=list)


@dataclass
class ScheduleResult:
    success: bool
    message: str = ""
    scheduled: list[dict] = field(default_factory=list)
    unscheduled: list[UnscheduledInfo] = field(default_factory=list)
    total_lessons: int = 0
    solve_status: str = ""


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _to_slot(t: time, open_min: int) -> int:
    return (t.hour * 60 + t.minute - open_min) // 15


def _slot_to_minutes(slot: int, open_min: int) -> int:
    return open_min + slot * 15


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged: list[list[int]] = [list(intervals[0])]
    for s, e in intervals[1:]:
        if s <= merged[-1][1]:
            if e > merged[-1][1]:
                merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def load_availability(
    db: Session, entity_type: EntityTypeEnum, entity_id: int
) -> dict[int, list[tuple[int, int]]]:
    """Загружает доступность сущности: день -> список интервалов в слотах."""
    settings = get_settings()
    open_min = settings.center_open_hour * 60
    close_min = settings.center_close_hour * 60
    rows = db.scalars(
        select(Availability).where(
            Availability.entity_type == entity_type,
            Availability.entity_id == entity_id,
        )
    ).all()
    result: dict[int, list[tuple[int, int]]] = {}
    for r in rows:
        s = _to_slot(r.start_time, open_min)
        e = _to_slot(r.end_time, open_min)
        day_max = (close_min - open_min) // 15
        s = max(0, s)
        e = min(day_max, e)
        if e <= s:
            continue
        result.setdefault(r.day_of_week, []).append((s, e))
    for day in result:
        result[day] = _merge_intervals(result[day])
    return result


# ---------------------------------------------------------------------------
# Загрузка данных
# ---------------------------------------------------------------------------


def _load_occurrences(db: Session) -> list[LessonOccurrence]:
    occs: list[LessonOccurrence] = []

    gl_rows = db.execute(
        select(GroupLesson, Subject.name).join(Subject, GroupLesson.subject_id == Subject.id)
    ).all()
    for gl, subj_name in gl_rows:
        student_ids = list(
            db.execute(
                select(group_lesson_participants.c.student_id).where(
                    group_lesson_participants.c.group_lesson_id == gl.id
                )
            ).scalars()
        )
        if not student_ids:
            continue
        for w_occ in range(gl.lessons_per_week):
            occs.append(
                LessonOccurrence(
                    id=f"gl_{gl.id}_{w_occ}",
                    title=gl.title or subj_name,
                    lesson_type=LessonTypeEnum.group,
                    group_lesson_id=gl.id,
                    student_ids=student_ids,
                    subject_id=gl.subject_id,
                    subject_name=subj_name,
                    duration_minutes=gl.duration_minutes or 60,
                    priority=3,
                    preferred_teacher_id=gl.teacher_id,
                    teacher_is_required=gl.teacher_is_required,
                    notes=gl.comment,
                )
            )

    lr_rows = db.execute(
        select(LessonRequest, Subject.name)
        .join(Subject, LessonRequest.subject_id == Subject.id)
        .where(LessonRequest.lesson_type == LessonTypeEnum.individual)
    ).all()
    for lr, subj_name in lr_rows:
        student = db.get(Student, lr.student_id)
        if student is None or not student.is_active:
            continue
        for o in range(lr.lessons_per_week):
            occs.append(
                LessonOccurrence(
                    id=f"lr_{lr.id}_{o}",
                    title=subj_name,
                    lesson_type=LessonTypeEnum.individual,
                    lesson_request_id=lr.id,
                    student_ids=[lr.student_id],
                    subject_id=lr.subject_id,
                    subject_name=subj_name,
                    duration_minutes=lr.duration_minutes or 60,
                    priority=lr.priority or 1,
                    preferred_teacher_id=lr.preferred_teacher_id,
                    teacher_is_required=lr.teacher_is_required,
                    notes=lr.notes,
                )
            )
    return occs


def _teachers_for_subject(db: Session, subject_id: int) -> set[int]:
    return set(
        db.execute(
            select(teacher_subjects.c.teacher_id).where(
                teacher_subjects.c.subject_id == subject_id
            )
        ).scalars()
    )


def _rooms_for_subject(db: Session, subject_id: int) -> set[int]:
    return set(
        db.execute(
            select(room_subjects.c.room_id).where(room_subjects.c.subject_id == subject_id)
        ).scalars()
    )


# ---------------------------------------------------------------------------
# Основная оптимизация
# ---------------------------------------------------------------------------


def build_and_solve(
    db: Session,
    occurrences: list[LessonOccurrence],
    settings: OptimizerSettings,
) -> ScheduleResult:
    result = ScheduleResult(success=False)
    result.total_lessons = len(occurrences)
    if not occurrences:
        result.success = True
        return result

    open_min = settings.early_hour * 60
    close_min = settings.late_hour * 60
    slots_in_day = (close_min - open_min) // 15
    if slots_in_day <= 0:
        return ScheduleResult(
            success=False,
            message="Не удалось составить расписание: некорректные границы рабочего времени (начало >= конец). Настройте рабочие часы центра в настройках оптимизатора."
        )

    teachers = _load_teachers(db)
    rooms = _load_rooms(db)
    students = _load_students(db)
    all_teachers = list(teachers.values())
    all_rooms = list(rooms.values())

    model = cp_model.CpModel()

    # --- предрасчёт кандидатов по каждому вхождению ---
    occs_data: list[dict] = []
    for occ in occurrences:
        dur_slots = max(1, (occ.duration_minutes + 14) // 15)
        dur_min = dur_slots * 15

        positions: list[tuple[int, int]] = []
        for d in range(7):
            for s in range(0, slots_in_day - dur_slots + 1):
                ok = True
                for sid in occ.student_ids:
                    st = students.get(sid)
                    if st is None or not st.fits(d, s, dur_slots):
                        ok = False
                        break
                if ok:
                    positions.append((d, s))

        t_ids = _teachers_for_subject(db, occ.subject_id)
        t_cands = [t for t in all_teachers if t.db_id in t_ids]
        if occ.preferred_teacher_id is not None and occ.teacher_is_required:
            t_cands = [t for t in t_cands if t.db_id == occ.preferred_teacher_id]

        r_ids = _rooms_for_subject(db, occ.subject_id)
        n_participants = len(occ.student_ids) or 1
        r_cands = [r for r in all_rooms if r.db_id in r_ids and r.capacity >= n_participants]

        occs_data.append(
            {
                "occ": occ,
                "dur_slots": dur_slots,
                "dur_min": dur_min,
                "positions": positions,
                "teachers": t_cands,
                "rooms": r_cands,
            }
        )

    # --- существует ли валидная комбинация вообще ---
    for od in occs_data:
        od["has_valid"] = False
        for (d, s) in od["positions"]:
            any_t = any(t.fits(d, s, od["dur_slots"], slots_in_day) for t in od["teachers"])
            any_r = any(r.fits(d, s, od["dur_slots"], slots_in_day) for r in od["rooms"])
            if any_t and any_r:
                od["has_valid"] = True
                break

    # --- переменные ---
    PRESENT: dict[int, object] = {}
    POS_VAR: dict[int, object] = {}
    DAY_VAR: dict[int, object] = {}
    SLOT_VAR: dict[int, object] = {}
    ABS_START: dict[int, object] = {}
    teacher_sel: dict[int, dict[int, object]] = {}
    room_sel: dict[int, dict[int, object]] = {}
    teacher_interval: dict[int, dict[int, object]] = {}
    room_interval: dict[int, dict[int, object]] = {}
    student_interval: dict[int, dict[int, object]] = {}

    def pos_abs_min(day: int, slot: int) -> int:
        return day * MINUTES_IN_DAY + open_min + slot * 15

    for oi, od in enumerate(occs_data):
        occ = od["occ"]
        if not od["has_valid"] or not od["teachers"] or not od["rooms"]:
            continue

        PRESENT[oi] = model.NewBoolVar(f"pres_{occ.id}")
        positions = od["positions"]
        pos_len = len(positions)

        POS_VAR[oi] = model.NewIntVar(0, pos_len - 1, f"pos_{occ.id}")
        DAY_VAR[oi] = model.NewIntVar(0, 6, f"day_{occ.id}")
        SLOT_VAR[oi] = model.NewIntVar(0, slots_in_day - 1, f"slot_{occ.id}")

        day_vals = [d for (d, s) in positions]
        slot_vals = [s for (d, s) in positions]
        abs_vals = [pos_abs_min(d, s) for (d, s) in positions]
        ABS_START[oi] = model.NewIntVar(min(abs_vals), max(abs_vals), f"abs_{occ.id}")

        model.AddElement(POS_VAR[oi], day_vals, DAY_VAR[oi])
        model.AddElement(POS_VAR[oi], slot_vals, SLOT_VAR[oi])
        model.AddElement(POS_VAR[oi], abs_vals, ABS_START[oi])

        dur_min = od["dur_min"]
        teacher_sel[oi] = {}
        teacher_interval[oi] = {}
        for ti, tc in enumerate(od["teachers"]):
            b = model.NewBoolVar(f"tsel_{occ.id}_t{ti}")
            teacher_sel[oi][ti] = b
            teacher_interval[oi][ti] = model.NewOptionalIntervalVar(
                ABS_START[oi], dur_min, ABS_START[oi] + dur_min, b, f"tint_{occ.id}_t{ti}"
            )
        model.Add(sum(teacher_sel[oi].values()) == PRESENT[oi])

        room_sel[oi] = {}
        room_interval[oi] = {}
        for ri, rc in enumerate(od["rooms"]):
            b = model.NewBoolVar(f"rsel_{occ.id}_r{ri}")
            room_sel[oi][ri] = b
            room_interval[oi][ri] = model.NewOptionalIntervalVar(
                ABS_START[oi], dur_min, ABS_START[oi] + dur_min, b, f"rint_{occ.id}_r{ri}"
            )
        model.Add(sum(room_sel[oi].values()) == PRESENT[oi])

        student_interval[oi] = {}
        for sid in occ.student_ids:
            student_interval[oi][sid] = model.NewOptionalIntervalVar(
                ABS_START[oi], dur_min, ABS_START[oi] + dur_min,
                PRESENT[oi], f"sint_{occ.id}_st{sid}",
            )

    # --- жёсткие ограничения: ресурсы не пересекаются ---
    for tc in all_teachers:
        intervals = []
        for oi, od in enumerate(occs_data):
            for ti, itv in teacher_interval.get(oi, {}).items():
                if od["teachers"][ti].db_id == tc.db_id:
                    intervals.append(itv)
        if intervals:
            model.AddNoOverlap(intervals)

    for rc in all_rooms:
        intervals = []
        for oi, od in enumerate(occs_data):
            for ri, itv in room_interval.get(oi, {}).items():
                if od["rooms"][ri].db_id == rc.db_id:
                    intervals.append(itv)
        if intervals:
            model.AddNoOverlap(intervals)

    for st in students.values():
        intervals = []
        for oi in student_interval:
            if st.db_id in student_interval[oi]:
                intervals.append(student_interval[oi][st.db_id])
        if intervals:
            model.AddNoOverlap(intervals)

    # --- доступность педагога/кабинета привязана к позиции ---
    for oi, od in enumerate(occs_data):
        if oi not in POS_VAR:
            continue
        for ti, tc in enumerate(od["teachers"]):
            pairs = [(d, s, 0) for (d, s) in od["positions"]]
            pairs += [
                (d, s, 1)
                for (d, s) in od["positions"]
                if tc.fits(d, s, od["dur_slots"], slots_in_day)
            ]
            model.AddAllowedAssignments(
                (DAY_VAR[oi], SLOT_VAR[oi], teacher_sel[oi][ti]), pairs
            )
        for ri, rc in enumerate(od["rooms"]):
            pairs = [(d, s, 0) for (d, s) in od["positions"]]
            pairs += [
                (d, s, 1)
                for (d, s) in od["positions"]
                if rc.fits(d, s, od["dur_slots"], slots_in_day)
            ]
            model.AddAllowedAssignments(
                (DAY_VAR[oi], SLOT_VAR[oi], room_sel[oi][ri]), pairs
            )

    # --- целевая функция (только целые коэффициенты) ---
    objective_terms: list[object] = []

    # 1. количество размещённых занятий с учётом приоритета
    for oi, od in enumerate(occs_data):
        occ = od["occ"]
        if oi in PRESENT:
            coef = int(round(settings.weight_presence * (1.0 + 0.5 * (occ.priority - 1)) * SCALE))
            objective_terms.append(coef * PRESENT[oi])

    # 2. предпочтительный педагог
    if settings.reward_preferred_teacher > 0:
        for oi, od in enumerate(occs_data):
            occ = od["occ"]
            if oi not in teacher_sel:
                continue
            if occ.preferred_teacher_id is None or occ.teacher_is_required:
                continue
            for ti, tc in enumerate(od["teachers"]):
                if tc.db_id == occ.preferred_teacher_id:
                    objective_terms.append(
                        int(round(settings.reward_preferred_teacher * SCALE)) * teacher_sel[oi][ti]
                    )
                    break

    # 3. занятия одного ребёнка не должны скапливаться в один день
    if settings.penalty_student_same_day > 0:
        for sid in students:
            for d in range(7):
                terms = []
                for oi, od in enumerate(occs_data):
                    if oi not in DAY_VAR:
                        continue
                    if sid not in od["occ"].student_ids:
                        continue
                    b = model.NewBoolVar(f"sday_{oi}_{sid}_{d}")
                    model.Add(DAY_VAR[oi] == d).OnlyEnforceIf(b)
                    model.Add(DAY_VAR[oi] != d).OnlyEnforceIf(b.Not())
                    terms.append(b)
                if not terms:
                    continue
                count_var = model.NewIntVar(0, len(terms), f"sday_count_{sid}_{d}")
                model.Add(count_var == sum(terms))
                extra = model.NewIntVar(0, len(terms), f"sday_extra_{sid}_{d}")
                model.AddMaxEquality(extra, [count_var - 1, 0])
                objective_terms.append(-int(round(settings.penalty_student_same_day * SCALE)) * extra)

    # 4. ранние/поздние занятия
    if settings.penalty_early_late > 0:
        for oi, od in enumerate(occs_data):
            if oi not in POS_VAR:
                continue
            penalty_vals = []
            for (d, s) in od["positions"]:
                start_min = _slot_to_minutes(s, open_min)
                delta_minutes = 0
                if start_min < settings.early_hour * 60:
                    delta_minutes += settings.early_hour * 60 - start_min
                if start_min > settings.late_hour * 60 - 15:
                    delta_minutes += start_min - (settings.late_hour * 60 - 15)
                units = delta_minutes / 15
                penalty_vals.append(int(round(settings.penalty_early_late * units)))
            if not penalty_vals:
                continue
            pv = model.NewIntVar(0, max(penalty_vals), f"pen_el_{od['occ'].id}")
            model.AddElement(POS_VAR[oi], penalty_vals, pv)
            objective_terms.append(-pv)

    # 5. баланс нагрузки педагогов (в 15-минутных слотах)
    if settings.weight_teacher_balance > 0:
        loads = []
        for tc in all_teachers:
            terms = []
            for oi, od in enumerate(occs_data):
                if oi not in teacher_sel:
                    continue
                for ti, tce in enumerate(od["teachers"]):
                    if tce.db_id == tc.db_id:
                        terms.append(teacher_sel[oi][ti] * od["dur_slots"])
            load = model.NewIntVar(0, 200000, f"tload_{tc.db_id}")
            model.Add(load == sum(terms))
            loads.append(load)
        if loads:
            mx = model.NewIntVar(0, 200000, "t_load_max")
            mn = model.NewIntVar(0, 200000, "t_load_min")
            model.AddMaxEquality(mx, loads)
            model.AddMinEquality(mn, loads)
            objective_terms.append(-int(round(settings.weight_teacher_balance * SCALE)) * (mx - mn))

    # 6. баланс использования кабинетов
    if settings.weight_room_balance > 0:
        loads = []
        for rc in all_rooms:
            terms = []
            for oi, od in enumerate(occs_data):
                if oi not in room_sel:
                    continue
                for ri, rce in enumerate(od["rooms"]):
                    if rce.db_id == rc.db_id:
                        terms.append(room_sel[oi][ri] * od["dur_slots"])
            load = model.NewIntVar(0, 200000, f"rload_{rc.db_id}")
            model.Add(load == sum(terms))
            loads.append(load)
        if loads:
            mx = model.NewIntVar(0, 200000, "r_load_max")
            mn = model.NewIntVar(0, 200000, "r_load_min")
            model.AddMaxEquality(mx, loads)
            model.AddMinEquality(mn, loads)
            objective_terms.append(-int(round(settings.weight_room_balance * SCALE)) * (mx - mn))

    model.Maximize(sum(objective_terms) if objective_terms else 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = settings.time_limit_seconds
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    result.solve_status = solver.StatusName(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        result.success = False
        result.message = (
            f"Не удалось составить расписание: {solver.StatusName(status)}. "
            f"Проверьте доступность учеников, педагогов и кабинетов, "
            f"а также рабочие часы центра."
        )
        return result

    result.success = True
    for oi, od in enumerate(occs_data):
        occ = od["occ"]
        if oi not in PRESENT:
            # Нет переменных — вообще нет валидных комбинаций (студенты/педагоги/кабинеты не пересекаются)
            student_names = ", ".join(students[sid].name for sid in occ.student_ids if sid in students)
            student_part = f" ({student_names})" if student_names else ""
            result.unscheduled.append(
                UnscheduledInfo(
                    identifier=occ.id,
                    name=occ.title,
                    reason=(
                        f"Нет ни одного слота, где свободны и ученик{student_part}, "
                        f"и педагог, и кабинет одновременно."
                    ),
                    suggestions=["Добавить педагога", "Добавить кабинет", "Расширить доступность детей"],
                )
            )
            continue
        if not solver.Value(PRESENT[oi]):
            diag = _diagnose(db, occ, od, slots_in_day, students)
            result.unscheduled.append(
                UnscheduledInfo(
                    identifier=occ.id, name=occ.title,
                    reason=diag["reason"], suggestions=diag["suggestions"],
                )
            )
            continue
        d = solver.Value(DAY_VAR[oi])
        s = solver.Value(SLOT_VAR[oi])
        start_min = _slot_to_minutes(s, open_min)
        ti = next(ti for ti in teacher_sel[oi] if solver.Value(teacher_sel[oi][ti]))
        ri = next(ri for ri in room_sel[oi] if solver.Value(room_sel[oi][ri]))
        h1, m1 = divmod(start_min, 60)
        end_min = start_min + od["dur_min"]
        h2, m2 = divmod(end_min, 60)
        result.scheduled.append(
            {
                "lesson_type": occ.lesson_type.value,
                "lesson_request_id": occ.lesson_request_id,
                "group_lesson_id": occ.group_lesson_id,
                "student_id": occ.student_ids[0] if occ.student_ids else None,
                "students": occ.student_ids,
                "day_of_week": d,
                "start_time": time(hour=h1, minute=m1),
                "end_time": time(hour=h2, minute=m2),
                "teacher_id": od["teachers"][ti].db_id,
                "room_id": od["rooms"][ri].db_id,
            }
        )

    return result


def _diagnose(
    db: Session,
    occ: LessonOccurrence,
    od: dict,
    slots_in_day: int,
    students: dict[int, StudentAvail],
) -> dict:
    reasons: list[str] = []
    suggestions: list[str] = []

    student_names = ", ".join(students[sid].name for sid in occ.student_ids if sid in students)
    student_desc = f" (ученики: {student_names})" if student_names else ""

    if not od["teachers"]:
        if occ.preferred_teacher_id is not None and occ.teacher_is_required:
            reasons.append(
                f"У занятия «{occ.subject_name}»{student_desc} обязательный педагог не ведёт это направление или недоступен."
            )
            suggestions.append("Назначить другого обязательного педагога или снять флаг «обязательный»")
        else:
            reasons.append(f"По направлению «{occ.subject_name}»{student_desc} нет активных педагогов.")
            suggestions.append("Добавить педагога на это направление")

    if not od["rooms"]:
        n = len(occ.student_ids) or 1
        reasons.append(
            f"Нет кабинета для направления «{occ.subject_name}»{student_desc} вместимостью не менее {n}."
        )
        suggestions.append("Добавить кабинет подходящей вместимости")

    if not od["positions"]:
        reasons.append(
            f"У ученика(ов){student_desc} нет пересекающихся свободных интервалов длительностью {occ.duration_minutes} мин."
        )
        suggestions.append("Расширить доступность детей")

    free = busy = 0
    t_only_busy = 0
    r_only_busy = 0
    for (d, s) in od["positions"][:200]:
        has_t = any(t.fits(d, s, od["dur_slots"], slots_in_day) for t in od["teachers"])
        has_r = any(r.fits(d, s, od["dur_slots"], slots_in_day) for r in od["rooms"])
        if has_t and has_r:
            free += 1
        else:
            busy += 1
            if not has_t and has_r:
                t_only_busy += 1
            elif has_t and not has_r:
                r_only_busy += 1

    if free > 0:
        reasons.append(
            "Есть свободные слоты, но занятие не размещено — вероятен конфликт за педагога или кабинет с другими занятиями."
        )
        suggestions.append("Увеличить количество педагогов/кабинетов или сократить кол-во занятий")

    if free == 0 and busy > 0:
        parts = []
        if t_only_busy:
            parts.append(f"педагогов не хватает в {t_only_busy} из {len(od['positions'][:200])} проверенных слотов")
        if r_only_busy:
            parts.append(f"кабинетов не хватает в {r_only_busy} из {len(od['positions'][:200])} проверенных слотов")
        if parts:
            reasons.append("В доступное детям время " + ", ".join(parts) + ".")
        else:
            reasons.append("В доступное детям время педагоги и кабинеты заняты.")
        suggestions.append("Расширить рабочие часы педагогов")
        suggestions.append("Добавить кабинет")

    suggestions += ["Изменить время занятия", "Уменьшить количество занятий"]
    reason = " ".join(dict.fromkeys(reasons)) or "Занятие не удалось разместить."
    return {"reason": reason, "suggestions": list(dict.fromkeys(suggestions))[:5]}


def run_schedule_generation(db: Session, schedule_name: str, week_start: date) -> ScheduleResult:
    """Полный цикл: загрузка данных и оптимизация с проверкой результата."""
    occurrences = _load_occurrences(db)
    if not occurrences:
        return ScheduleResult(
            success=False,
            message="Нет занятий для составления расписания. Добавьте индивидуальные требования учеников (активные, с типом 'individual') или групповые занятия с участниками."
        )

    opt_settings = db.scalars(select(OptimizerSettings).limit(1)).first()
    if opt_settings is None:
        opt_settings = OptimizerSettings()
        db.add(opt_settings)
        db.commit()
        db.refresh(opt_settings)

    result = build_and_solve(db, occurrences, opt_settings)
    if not result.success:
        return result

    # самопроверка: никакие назначения не должны пересекаться
    conflicts = _pairwise_conflicts(result.scheduled)
    if conflicts:
        result.success = False
        result.message = "Внутренняя ошибка оптимизатора: " + conflicts
        return result
    return result


def _pairwise_conflicts(scheduled: list[dict]) -> str:
    for i in range(len(scheduled)):
        for j in range(i + 1, len(scheduled)):
            a, b = scheduled[i], scheduled[j]
            if a["day_of_week"] != b["day_of_week"]:
                continue
            sta = a["start_time"].hour * 60 + a["start_time"].minute
            ena = a["end_time"].hour * 60 + a["end_time"].minute
            stb = b["start_time"].hour * 60 + b["start_time"].minute
            enb = b["end_time"].hour * 60 + b["end_time"].minute
            if not (sta < enb and stb < ena):
                continue
            if a["teacher_id"] == b["teacher_id"]:
                return f"Педагог ID {a['teacher_id']} имеет пересечение занятий"
            if a["room_id"] == b["room_id"]:
                return f"Кабинет ID {a['room_id']} имеет пересечение занятий"
            a_students = set(a.get("students") or [])
            b_students = set(b.get("students") or [])
            if a_students & b_students:
                return f"Ученик ID {next(iter(a_students & b_students))} имеет пересечение занятий"
    return ""


def _load_teachers(db: Session) -> dict[int, TeacherCand]:
    teachers = db.scalars(select(Teacher).where(Teacher.is_active)).all()
    result: dict[int, TeacherCand] = {}
    for t in teachers:
        av = load_availability(db, EntityTypeEnum.teacher, t.id)
        result[t.id] = TeacherCand(
            db_id=t.id,
            name=f"{t.last_name} {t.first_name}".strip(),
            availability=av,
            has_any_availability=bool(av),
        )
    return result


def _load_rooms(db: Session) -> dict[int, RoomCand]:
    rooms = db.scalars(select(Room)).all()
    result: dict[int, RoomCand] = {}
    for r in rooms:
        av = load_availability(db, EntityTypeEnum.room, r.id)
        result[r.id] = RoomCand(
            db_id=r.id,
            name=r.name,
            capacity=r.capacity,
            availability=av,
            has_any_availability=bool(av),
        )
    return result


def _load_students(db: Session) -> dict[int, StudentAvail]:
    students = db.scalars(select(Student).where(Student.is_active)).all()
    result: dict[int, StudentAvail] = {}
    for s in students:
        av = load_availability(db, EntityTypeEnum.student, s.id)
        result[s.id] = StudentAvail(
            db_id=s.id,
            name=f"{s.last_name} {s.first_name}".strip(),
            availability=av,
        )
    return result