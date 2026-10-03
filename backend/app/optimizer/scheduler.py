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
    LessonRequest,
    LessonTypeEnum,
    OptimizerSettings,
    Room,
    Student,
    Subject,
    Teacher,
    room_subjects,
    teacher_subjects,
)
from app.optimizer.diagnosis import (
    Diagnosis,
    Placement,
    UnplacedLesson,
    diagnose,
)
from app.optimizer.grouping import FailedGroup, form_groups

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
    has_any_availability: bool = False

    def fits(
        self, day: int, start_slot: int, dur_slots: int, slots_in_day: int = 0
    ) -> bool:
        # Доступность не задана — ученик свободен весь рабочий день,
        # как педагог и кабинет (TeacherCand.fits / RoomCand.fits).
        if not self.has_any_availability:
            return 0 <= start_slot and start_slot + dur_slots <= slots_in_day
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
    lesson_request_ids: list[int] = field(default_factory=list)
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
    level: str = "error"  # "error" — не размещено, "info" — возможность / рекомендация
    details: list[str] = field(default_factory=list)


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


def _load_occurrences(
    db: Session,
) -> tuple[list[LessonOccurrence], list[FailedGroup]]:
    occs: list[LessonOccurrence] = []
    failed_groups: list[FailedGroup] = []

    subject_names: dict[int, str] = {}
    for s in db.execute(select(Subject)).scalars():
        subject_names[s.id] = s.name

    lr_rows = db.execute(
        select(LessonRequest, Subject.name)
        .join(Subject, LessonRequest.subject_id == Subject.id)
        .where(
            LessonRequest.lesson_type.in_(
                [LessonTypeEnum.individual, LessonTypeEnum.both]
            )
        )
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
                    lesson_request_ids=[lr.id],
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

    opt_settings = db.scalars(select(OptimizerSettings).limit(1)).first()
    if opt_settings is None:
        opt_settings = OptimizerSettings()
        db.add(opt_settings)
        db.flush()

    group_reqs = db.execute(
        select(LessonRequest)
        .where(
            LessonRequest.lesson_type.in_(
                [LessonTypeEnum.group, LessonTypeEnum.both]
            )
        )
    ).scalars().all()
    formed, failed_groups = form_groups(
        db,
        list(group_reqs),
        min_size=opt_settings.group_min_size or 2,
        max_size=opt_settings.group_max_size or 8,
        subject_names=subject_names,
    )
    for g in formed:
        anchor = g.lesson_request_ids[0]
        for o in range(g.lessons_per_week):
            occs.append(
                LessonOccurrence(
                    id=f"gp_{'_'.join(str(i) for i in g.lesson_request_ids)}_{o}",
                    title=g.subject_name,
                    lesson_type=LessonTypeEnum.group,
                    lesson_request_id=anchor,
                    lesson_request_ids=list(g.lesson_request_ids),
                    student_ids=list(g.student_ids),
                    subject_id=g.subject_id,
                    subject_name=g.subject_name,
                    duration_minutes=g.duration_minutes,
                    priority=g.priority,
                    preferred_teacher_id=g.preferred_teacher_id,
                    teacher_is_required=g.teacher_is_required,
                )
            )

    return occs, failed_groups


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
                    if st is None or not st.fits(d, s, dur_slots, slots_in_day):
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
        all_r_cands = [r for r in all_rooms if r.db_id in r_ids]
        r_cands = [r for r in all_r_cands if r.capacity >= n_participants]

        occs_data.append(
            {
                "occ": occ,
                "dur_slots": dur_slots,
                "dur_min": dur_min,
                "positions": positions,
                "teachers": t_cands,
                "rooms": r_cands,
                "all_rooms": all_r_cands,
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
    placement_by_oi: dict[int, Placement] = {}
    for oi, od in enumerate(occs_data):
        if oi not in PRESENT or not solver.Value(PRESENT[oi]):
            continue
        d = solver.Value(DAY_VAR[oi])
        s = solver.Value(SLOT_VAR[oi])
        start_min = _slot_to_minutes(s, open_min)
        end_min = start_min + od["dur_min"]
        ti = next(ti for ti in teacher_sel[oi] if solver.Value(teacher_sel[oi][ti]))
        ri = next(ri for ri in room_sel[oi] if solver.Value(room_sel[oi][ri]))
        occ = od["occ"]
        placement_by_oi[oi] = Placement(
            teacher_id=od["teachers"][ti].db_id,
            room_id=od["rooms"][ri].db_id,
            day=d,
            start_min=start_min,
            end_min=end_min,
            student_ids=tuple(occ.student_ids),
            title=occ.subject_name,
        )
        h1, m1 = divmod(start_min, 60)
        h2, m2 = divmod(end_min, 60)
        result.scheduled.append(
            {
                "lesson_type": occ.lesson_type.value,
                "lesson_request_id": occ.lesson_request_id,
                "lesson_request_ids": list(occ.lesson_request_ids),
                "student_id": occ.student_ids[0] if occ.student_ids else None,
                "students": occ.student_ids,
                "day_of_week": d,
                "start_time": time(hour=h1, minute=m1),
                "end_time": time(hour=h2, minute=m2),
                "teacher_id": od["teachers"][ti].db_id,
                "room_id": od["rooms"][ri].db_id,
            }
        )

    placements = list(placement_by_oi.values())
    # Нет записей о доступности — человек свободен весь рабочий день (как в TeacherCand.fits)
    whole_day = {d: [(0, slots_in_day * 15)] for d in range(7)}
    teacher_windows = {
        tc.db_id: (tc.availability if tc.has_any_availability else whole_day)
        for tc in all_teachers
    }
    room_windows = {
        rc.db_id: (rc.availability if rc.has_any_availability else whole_day)
        for rc in all_rooms
    }

    for oi, od in enumerate(occs_data):
        if oi in placement_by_oi:
            continue
        occ = od["occ"]
        title = _occurrence_title(occ, students)
        diag = _diagnose(
            db=db,
            occ=occ,
            od=od,
            slots_in_day=slots_in_day,
            open_min=open_min,
            dur_slots=od["dur_slots"],
            students=students,
            teachers=teachers,
            rooms=rooms,
            placements=placements,
            teacher_windows=teacher_windows,
            room_windows=room_windows,
        )
        result.unscheduled.append(
            UnscheduledInfo(
                identifier=occ.id,
                name=title,
                reason=diag.reason,
                suggestions=diag.suggestions,
                details=diag.details,
            )
        )

    return result


def _occurrence_title(occ: LessonOccurrence, students: dict[int, StudentAvail]) -> str:
    """Человеческое название занятия для отчёта: предмет + участники."""
    if len(occ.student_ids) <= 1:
        names = [students[sid].name for sid in occ.student_ids if sid in students]
        who = names[0] if names else ""
        kind = "Групповое" if occ.lesson_type == LessonTypeEnum.group else "Индивидуальное"
        return f"{kind}: {occ.subject_name}" + (f" — {who}" if who else "")
    names = [students[sid].name for sid in occ.student_ids if sid in students]
    kind = "Групповое"
    return f"{kind}: {occ.subject_name} — " + ", ".join(names)


def _abs_minutes(windows: dict[int, list[tuple[int, int]]], open_min: int) -> dict[int, list[tuple[int, int]]]:
    """Переводит слоты в минуты от полуночи — так их видит человек."""
    return {
        day: [(open_min + s * 15, open_min + e * 15) for (s, e) in ivs]
        for day, ivs in windows.items()
    }


def _inactive_teachers_for_subject(db: Session, subject_id: int) -> list[Teacher]:
    return list(
        db.scalars(
            select(Teacher)
            .join(teacher_subjects, teacher_subjects.c.teacher_id == Teacher.id)
            .where(
                teacher_subjects.c.subject_id == subject_id,
                Teacher.is_active.is_(False),
            )
        ).all()
    )


def _diagnose(
    db: Session,
    occ: LessonOccurrence,
    od: dict,
    slots_in_day: int,
    open_min: int,
    dur_slots: int,
    students: dict[int, StudentAvail],
    teachers: dict[int, TeacherCand],
    rooms: dict[int, RoomCand],
    placements: list[Placement],
    teacher_windows: dict[int, dict[int, list[tuple[int, int]]]],
    room_windows: dict[int, dict[int, list[tuple[int, int]]]],
) -> Diagnosis:
    """Делает `od` пригодным для diagnosis.diagnose и зовёт его."""
    slot_positions: list[tuple[int, int]] = [
        (d, open_min + s * 15)
        for (d, s) in od["positions"]
        if s + dur_slots <= slots_in_day
    ]

    n_participants = len(occ.student_ids) or 1
    lesson = UnplacedLesson(
        subject_name=occ.subject_name,
        duration_minutes=od["dur_min"],
        participants=n_participants,
        student_names=[students[sid].name for sid in occ.student_ids if sid in students],
        lesson_type=occ.lesson_type.value,
        teacher_candidates=[(t.db_id, t.name) for t in od["teachers"]],
        # кабинеты, проходящие по вместимости — именно их оптимизатор использовал
        room_candidates=[
            (r.db_id, r.name, r.capacity)
            for r in od["all_rooms"]
            if r.capacity >= n_participants
        ],
        # а это все кабинеты, разрешённые для направления: нужны, чтобы объяснить
        # нехватку вместимости, а не «занятость»
        subject_rooms=[(r.db_id, r.name, r.capacity) for r in od["all_rooms"]],
        preferred_teacher=(
            (occ.preferred_teacher_id, teachers[occ.preferred_teacher_id].name)
            if occ.preferred_teacher_id in teachers
            else None
        ),
        teacher_required=occ.teacher_is_required,
        inactive_teachers=[
            f"{t.last_name} {t.first_name}".strip()
            for t in _inactive_teachers_for_subject(db, occ.subject_id)
        ],
    )

    student_windows: list[tuple[str, dict[int, list[tuple[int, int]]]]] = []
    for sid in occ.student_ids:
        st = students.get(sid)
        if st is None:
            continue
        if not st.availability:
            # доступность не задана — человек считает доступным всё рабочее время
            whole = {d: [(open_min, open_min + slots_in_day * 15)] for d in range(7)}
            student_windows.append((st.name, whole))
        else:
            student_windows.append((st.name, _abs_minutes(st.availability, open_min)))

    return diagnose(
        lesson=lesson,
        placements=placements,
        slots=slot_positions,
        student_windows=student_windows,
        teacher_windows={tid: _abs_minutes(w, open_min) for tid, w in teacher_windows.items()},
        room_windows={rid: _abs_minutes(w, open_min) for rid, w in room_windows.items()},
        teacher_labels={tid: tc.name for tid, tc in teachers.items()},
        room_labels={rid: rc.name for rid, rc in rooms.items()},
        teacher_exists=bool(od["teachers"]),
        room_exists=bool(od["all_rooms"]),
    )


def run_schedule_generation(db: Session, schedule_name: str, week_start: date) -> ScheduleResult:
    """Полный цикл: загрузка данных и оптимизация с проверкой результата."""
    occurrences, failed_groups = _load_occurrences(db)
    if not occurrences and not failed_groups:
        return ScheduleResult(
            success=False,
            message="Нет занятий для составления расписания. Добавьте активные требования учеников с типом 'individual', 'group' или 'both'."
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

    students = _load_students(db)
    for fg in failed_groups:
        student_name = students[fg.student_id].name if fg.student_id in students else ""
        who = f" ({student_name})" if student_name else ""
        result.unscheduled.insert(
            0,
            UnscheduledInfo(
                identifier=f"gr_{fg.lesson_request_id}",
                name=f"Групповое: {fg.subject_name}" + who,
                reason=fg.reason,
                suggestions=[
                    "Добавить ещё одного ученика на это направление с теми же часами",
                    "Снизить минимальный размер группы в настройках оптимизатора",
                ],
                details=[
                    f"Минимальный размер группы — {fg.min_size} чел., "
                    f"максимальный — {fg.max_size}.",
                    f"Длительность занятия: {fg.duration_minutes} мин.",
                ],
                level="info",
            ),
        )

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
            has_any_availability=bool(av),
        )
    return result