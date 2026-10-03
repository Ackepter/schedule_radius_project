"""Пояснение причин, по которым занятие не попало в расписание.

Модуль не влияет на результат оптимизации: он получает уже принятое решение
(что и куда размещено) и объясняет, что именно мешает поставить конкретное
занятие, опираясь на доступность участников и на уже занятые ресурсы.
"""

from dataclasses import dataclass, field
from typing import Iterable, Optional

DAY_NAMES = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]
DAY_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

# Окна выводятся в минутах от полуночи внутри окна оптимизатора:
# слот 0 == open_min. Так проще не путать со сдвигом дня.
MAX_WINDOWS_IN_TEXT = 6


@dataclass
class Placement:
    """Уже размещённое занятие — источник конкуренции за ресурсы."""

    teacher_id: int
    room_id: int
    day: int
    start_min: int
    end_min: int
    student_ids: tuple[int, ...] = ()
    title: str = ""


@dataclass
class UnplacedLesson:
    """Занятие, которое оптимизатор не смог разместить."""

    subject_name: str
    duration_minutes: int
    participants: int = 1
    student_names: list[str] = field(default_factory=list)
    lesson_type: str = "individual"
    teacher_candidates: list[tuple[int, str]] = field(default_factory=list)
    room_candidates: list[tuple[int, str, int]] = field(default_factory=list)
    # Все кабинеты, разрешённые для направления, независимо от вместимости.
    subject_rooms: list[tuple[int, str, int]] = field(default_factory=list)
    preferred_teacher: Optional[tuple[int, str]] = None
    teacher_required: bool = False
    # Педагоги, которые ведут направление, но отключены (is_active=False).
    inactive_teachers: list[str] = field(default_factory=list)


@dataclass
class Diagnosis:
    reason: str
    details: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def fmt_clock(minute: int) -> str:
    """Минуты от полуночи -> «14:30»."""
    minute = max(0, minute)
    return f"{minute // 60:02d}:{minute % 60:02d}"


def fmt_day(day: int) -> str:
    if 0 <= day < len(DAY_NAMES):
        return DAY_NAMES[day]
    return f"день недели {day}"


def describe_windows(windows: dict[int, list[tuple[int, int]]]) -> str:
    """«понедельник 10:00–13:00, среда 16:00–19:00»."""
    parts: list[str] = []
    for day in sorted(windows):
        day_parts = []
        for s, e in windows[day]:
            day_parts.append(f"{fmt_clock(s)}–{fmt_clock(e)}")
        parts.append(f"{fmt_day(day)} " + ", ".join(day_parts))
    return "; ".join(parts)


def _intersect(
    a: dict[int, list[tuple[int, int]]], b: dict[int, list[tuple[int, int]]]
) -> dict[int, list[tuple[int, int]]]:
    result: dict[int, list[tuple[int, int]]] = {}
    for day in sorted(set(a) & set(b)):
        merged: list[list[int]] = []
        for s1, e1 in a[day]:
            for s2, e2 in b[day]:
                s, e = max(s1, s2), min(e1, e2)
                if e <= s:
                    continue
                if merged and s <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], e)
                else:
                    merged.append([s, e])
        if merged:
            result[day] = [(s, e) for s, e in merged]
    return result


def _cut(
    windows: dict[int, list[tuple[int, int]]], limit: int
) -> dict[int, list[tuple[int, int]]]:
    """Оставляет отрезки длиной не меньше limit."""
    result: dict[int, list[tuple[int, int]]] = {}
    for day, ivs in windows.items():
        kept = [(s, e) for (s, e) in ivs if e - s >= limit]
        if kept:
            result[day] = kept
    return result


def _minutes_total(windows: dict[int, list[tuple[int, int]]]) -> int:
    return sum(e - s for ivs in windows.values() for (s, e) in ivs)


def _longest(windows: dict[int, list[tuple[int, int]]]) -> int:
    return max((e - s for ivs in windows.values() for (s, e) in ivs), default=0)


def _overlaps(
    a_day: int, a_start: int, a_end: int, b_day: int, b_start: int, b_end: int
) -> bool:
    return a_day == b_day and a_start < b_end and b_start < a_end


class _Resource:
    """Уже занятые интервалы одного педагога / кабинета / ученика."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.blocks: dict[tuple[int, int], int] = {}

    def hit(self, day: int, start: int, end: int) -> int:
        return self.blocks.get((day, start), 0) + (1 if (day, end) in self.blocks else 0)

    def blocked_by(self, placements: Iterable[Placement]) -> "_Resource":
        for p in placements:
            self.blocks.setdefault((p.day, p.start_min), 0)
            self.blocks.setdefault((p.day, p.end_min), 0)
        return self

    def offenders(self, day: int, start: int, end: int) -> list[str]:
        """Человеческие описания конфликтов в конкретном окне."""
        out: list[str] = []
        for (d, t) in sorted(self.blocks):
            if _overlaps(day, start, end, d, t - 1, t + 1) and t in (start, end):
                out.append(f"{DAY_SHORT[d]} {fmt_clock(t)}")
        return out


def diagnose(
    lesson: UnplacedLesson,
    placements: list[Placement],
    slots: list[tuple[int, int]],
    student_windows: list[tuple[str, dict[int, list[tuple[int, int]]]]],
    teacher_windows: dict[int, dict[int, list[tuple[int, int]]]],
    room_windows: dict[int, dict[int, list[tuple[int, int]]]],
    teacher_labels: dict[int, str],
    room_labels: dict[int, str],
    teacher_exists: bool,
    room_exists: bool,
) -> Diagnosis:
    """Собирает конкретное объяснение: что именно не сошлось."""
    who = _who(lesson)
    kind = "групповое" if lesson.lesson_type == "group" else "индивидуальное"
    head = f"{kind} занятие «{lesson.subject_name}»{who}"
    need = lesson.duration_minutes
    hints: list[str] = []

    if not student_windows:
        hints.append(
            f"Ни у одного участника не задана доступность — она считается равной "
            f"рабочему времени центра."
        )
    if not lesson.teacher_candidates:
        return _teacher_problem(
            lesson, head, teacher_exists, teacher_labels, hints, room_exists
        )
    if not lesson.room_candidates:
        return _room_problem(lesson, head, room_exists, room_labels, hints)

    if not slots:
        return _student_problem(lesson, head, student_windows, need, hints)

    # Окно, общее для всех участников. Ресурс подходит только там, где его
    # собственная доступность пересекается с этим окном, — иначе педагог,
    # свободный сам по себе, будет считаться подходящим при нулевом overlap.
    student_common = _intersect_all(student_windows)
    teacher_common = {
        tid: _intersect(student_common, w) for tid, w in teacher_windows.items()
    }
    room_common = {
        rid: _intersect(student_common, w) for rid, w in room_windows.items()
    }

    usable_teachers = {tid: _cut(w, need) for tid, w in teacher_common.items()}
    usable_rooms = {rid: _cut(w, need) for rid, w in room_common.items()}

    free_teachers = [
        (tid, name)
        for tid, name in lesson.teacher_candidates
        if usable_teachers.get(tid)
    ]
    if not free_teachers:
        return _teacher_no_overlap(
            lesson,
            head,
            teacher_common,
            student_windows,
            need,
            hints,
            teacher_own=teacher_windows,
        )

    free_rooms = [
        (rid, name) for rid, name, _ in lesson.room_candidates if usable_rooms.get(rid)
    ]
    if not free_rooms:
        return _room_no_overlap(
            lesson, head, room_common, student_windows, need, hints, room_own=room_windows
        )

    return _contention(lesson, head, slots, placements, free_teachers, free_rooms, hints)


# ── сценарии ──────────────────────────────────────────────────────────────


def _who(lesson: UnplacedLesson) -> str:
    if not lesson.student_names:
        return ""
    if len(lesson.student_names) == 1:
        return f" ({lesson.student_names[0]})"
    return " (" + ", ".join(lesson.student_names) + ")"


def _teacher_problem(
    lesson: UnplacedLesson,
    head: str,
    teacher_exists: bool,
    teacher_labels: dict[int, str],
    hints: list[str],
    room_exists: bool,
) -> Diagnosis:
    preferred = lesson.preferred_teacher
    details: list[str] = []
    suggestions: list[str] = []

    if preferred and lesson.teacher_required:
        tid, tname = preferred
        if not teacher_exists:
            reason = f"{head}: обязательный педагог {tname} не ведёт направление «{lesson.subject_name}»."
            details.append(
                f"В карточке педагога {tname} нет направления «{lesson.subject_name}» — "
                f"поэтому он не рассматривается как кандидат."
            )
            suggestions.append(f"Добавить направление «{lesson.subject_name}» педагогу {tname}")
            suggestions.append("Снять флаг «Педагог обязателен» или сменить педагога")
        elif tid not in teacher_labels:
            reason = f"{head}: обязательный педагог {tname} отключён (не активен)."
            details.append(
                "Деактивированные педагоги не участвуют в составлении расписания."
            )
            suggestions.append(f"Вернуть педагога {tname} в активные")
        else:
            reason = f"{head}: обязательный педагог {tname} не может вести это занятие."
            suggestions.append("Снять флаг «Педагог обязателен» или сменить педагога")
        details.extend(hints)
        return Diagnosis(reason=reason, details=details, suggestions=suggestions)

    # Отключённые проверяются раньше «не назначен»: иначе активный, но
    # отключённый педагог выглядит как «никто не назначен».
    if not teacher_exists and lesson.inactive_teachers:
        reason = f"{head}: все педагоги направления «{lesson.subject_name}» отключены."
        details.append(
            "Отключены: "
            + ", ".join(lesson.inactive_teachers)
            + ". Деактивированные педагоги не участвуют в составлении расписания."
        )
        suggestions.append("Активировать педагога в разделе «Педагоги»")
        details.extend(hints)
        return Diagnosis(reason=reason, details=details, suggestions=suggestions)

    if not teacher_exists:
        reason = f"{head}: по направлению «{lesson.subject_name}» не назначен ни один педагог."
        details.append(
            "Занятие невозможно разместить без педагога, даже если ученик свободен."
        )
        suggestions.append(
            f"Добавить педагога на направление «{lesson.subject_name}»"
        )
        details.extend(hints)
        return Diagnosis(reason=reason, details=details, suggestions=suggestions)

    reason = f"{head}: не удалось подобрать педагога."
    details.append("Ни один педагог направления не подошёл под требования занятия.")
    suggestions.append("Расширить доступность педагога или снять «Педагог обязателен»")
    details.extend(hints)
    return Diagnosis(reason=reason, details=details, suggestions=suggestions)


def _room_problem(
    lesson: UnplacedLesson,
    head: str,
    room_exists: bool,
    room_labels: dict[int, str],
    hints: list[str],
) -> Diagnosis:
    n = lesson.participants
    details: list[str] = []
    suggestions: list[str] = []

    if not room_exists:
        reason = (
            f"{head}: ни один кабинет не разрешён для направления «{lesson.subject_name}»."
        )
        details.append(
            "Занятие невозможно разместить без кабинета, даже если свободны педагог и время."
        )
        suggestions.append(
            f"Разрешить кабинет для направления «{lesson.subject_name}»"
        )
        details.extend(hints)
        return Diagnosis(reason=reason, details=details, suggestions=suggestions)

    # Кабинеты направления, которые не проходят по вместимости. room_candidates
    # уже отфильтрован оптимизатором, поэтому здесь нужен полный список.
    too_small = [(rid, cap) for rid, _, cap in lesson.subject_rooms if cap < n]
    if too_small:
        biggest = max(cap for _, cap in too_small)
        reason = (
            f"{head}: для занятия нужен кабинет вместимостью не менее {n}, "
            f"а максимальная вместимость среди кабинетов направления "
            f"«{lesson.subject_name}» — {biggest}."
        )
        details.append(
            "Кабинеты направления: "
            + ", ".join(
                f"{room_labels.get(rid, str(rid))} — {cap} мест"
                for rid, cap in sorted(too_small, key=lambda x: -x[1])
            )
            + "."
        )
        suggestions.append("Добавить кабинет большей вместимости")
        suggestions.append("Уменьшить размер группы либо разделить её на части")
        details.extend(hints)
        return Diagnosis(reason=reason, details=details, suggestions=suggestions)

    reason = f"{head}: нет ни одного доступного кабинета для направления «{lesson.subject_name}»."
    details.append(
        "Все подходящие по вместимости кабинеты сейчас заняты другими занятиями."
    )
    suggestions.append("Освободить кабинет в это время или добавить дополнительный")
    details.extend(hints)
    return Diagnosis(reason=reason, details=details, suggestions=suggestions)


def _student_problem(
    lesson: UnplacedLesson,
    head: str,
    student_windows: list[tuple[str, dict[int, list[tuple[int, int]]]]],
    need: int,
    hints: list[str],
) -> Diagnosis:
    details: list[str] = []
    suggestions: list[str] = []

    if not student_windows:
        reason = (
            f"{head}: не найдено ни одного окна длительностью {need} мин, "
            f"доступного ученику внутри рабочего времени."
        )
        suggestions.append("Задать доступность ученику на вкладке «Доступность»")
        details.extend(hints)
        return Diagnosis(reason=reason, details=details, suggestions=suggestions)

    # 1) ищем пару учеников без общих часов
    for i in range(len(student_windows)):
        for j in range(i + 1, len(student_windows)):
            (n1, w1), (n2, w2) = student_windows[i], student_windows[j]
            common = _intersect(w1, w2)
            if not common:
                reason = (
                    f"{head}: у учеников {n1} и {n2} нет общих свободных часов."
                )
                details.append(f"{n1}: {describe_windows(w1) or 'доступность не задана'}.")
                details.append(f"{n2}: {describe_windows(w2) or 'доступность не задана'}.")
                details.append(
                    f"Групповое занятие возможно только в часы, свободные у всех участников "
                    f"сразу; таких часов нет, поэтому оно не размещается как групповое."
                )
                suggestions.append(
                    f"Расширить доступность: {n1} или {n2} должны иметь пересекающиеся часы"
                )
                suggestions.append("Разделить группу на подгруппы с разным расписанием")
                details.extend(hints)
                return Diagnosis(reason=reason, details=details, suggestions=suggestions)

    # 2) общие часы есть, но короче длительности
    common_all = student_windows[0][1]
    for _, w in student_windows[1:]:
        common_all = _intersect(common_all, w)
    longest = _longest(common_all)
    reason = (
        f"{head}: общие свободные часы участников — максимум {longest} мин, "
        f"а занятие длится {need} мин."
    )
    details.append(
        "Общие свободные часы: " + (describe_windows(common_all) or "нет") + "."
    )
    suggestions.append(f"Уменьшить длительность занятия до {longest} мин или меньше")
    suggestions.append("Расширить доступность хотя бы одного участника")
    details.extend(hints)
    return Diagnosis(reason=reason, details=details, suggestions=suggestions)


def _overlap_report(
    a_name: str,
    a_windows: dict[int, list[tuple[int, int]]],
    b_name: str,
    b_windows: dict[int, list[tuple[int, int]]],
    need: int,
) -> tuple[str, list[str]]:
    common = _intersect(a_windows, b_windows)
    usable = _cut(common, need)
    if usable:
        return (
            f"{a_name} и {b_name} имеют общие часы ({describe_windows(usable)}), "
            f"но к ним не добавляется ещё одно звено.",
            [],
        )
    if common:
        longest = _longest(common)
        return (
            f"у {a_name} и {b_name} общие часы ({describe_windows(common)}), "
            f"но самый длинный общий отрезок — {longest} мин, "
            f"а нужно {need} мин.",
            [
                f"Сократить занятие до {longest} мин или расширить доступность.",
                "Расширить рабочие часы, чтобы пересечение выросло до "
                f"{need} мин.",
            ],
        )
    return (
        f"у {a_name} и {b_name} нет пересекающихся дней или часов.",
        [
            f"Изменить часы доступности так, чтобы {b_name} и {a_name} пересекались "
            f"не менее чем на {need} мин.",
            "Либо назначить педагога, доступного в часы ученика.",
        ],
    )


def _teacher_no_overlap(
    lesson: UnplacedLesson,
    head: str,
    teacher_common: dict[int, dict[int, list[tuple[int, int]]]],
    student_windows: list[tuple[str, dict[int, list[tuple[int, int]]]]],
    need: int,
    hints: list[str],
    teacher_own: dict[int, dict[int, list[tuple[int, int]]]] | None = None,
) -> Diagnosis:
    # teacher_own — собственные часы педагога (для показа пользователю),
    # teacher_common — уже пересечённые с часами учеников (для выводов).
    own = teacher_own if teacher_own is not None else teacher_common
    s_name, s_win = student_windows[0]
    per_teacher: list[tuple[int, str, dict[int, list[tuple[int, int]]]]] = []
    for tid, tname in lesson.teacher_candidates:
        merged = s_win
        for _, other in student_windows[1:]:
            merged = _intersect(merged, other)
        per_teacher.append((tid, tname, _intersect(merged, teacher_common.get(tid, {}))))

    empty = [(tid, tname, common) for tid, tname, common in per_teacher if not common]
    if empty:
        names = ", ".join(tname for _, tname, _ in empty)
        if len(empty) == 1:
            tid, tname, _ = empty[0]
            reason = (
                f"{head}: у ученика {s_name} и педагога {tname} "
                f"{'нет общих часов' if len(student_windows) == 1 else 'нет общих часов со всеми участниками'}."
            )
            _, suggestions = _overlap_report(
                f"ученик {s_name}",
                _intersect_all(student_windows),
                f"педагог {tname}",
                own.get(tid, {}),
                need,
            )
        else:
            reason = (
                f"{head}: ни один педагог направления «{lesson.subject_name}» "
                f"не пересекается по часам с учеником {s_name}."
            )
            suggestions = [
                f"Изменить часы доступности, чтобы педагоги ({names}) "
                f"пересекались с учеником {s_name} хотя бы на {need} мин.",
                "Добавить педагога, доступного в часы ученика.",
            ]
        details = [f"Часы ученика {s_name}: {describe_windows(_intersect_all(student_windows))}."]
        details += [
            f"Часы педагога {tname}: {describe_windows(own.get(tid, {})) or 'не заданы — считается доступен весь рабочий день'}."
            for tid, tname in lesson.teacher_candidates
        ]
        details.extend(hints)
        return Diagnosis(
            reason=reason,
            details=details,
            suggestions=suggestions or ["Расширить часы доступности педагога или ученика"],
        )

    # общие часы с учеником есть, но короче длительности
    best = max(per_teacher, key=lambda x: _longest(x[2]))
    tid, tname, common = best
    longest = _longest(common)
    reason = (
        f"{head}: с педагогом {tname} общие часы есть, но они короче занятия — "
        f"максимум {longest} мин при длительности {need} мин."
    )
    details = [
        f"Общие часы ученика {s_name} и педагога {tname}: "
        f"{describe_windows(common) or 'нет'}.",
        f"Другие педагоги направления не дают большего пересечения.",
    ]
    suggestions = [
        f"Уменьшить длительность занятия до {longest} мин.",
        "Расширить часы педагога или ученика хотя бы на "
        f"{need - longest} мин.",
    ]
    details.extend(hints)
    return Diagnosis(reason=reason, details=details, suggestions=suggestions)


def _intersect_all(
    student_windows: list[tuple[str, dict[int, list[tuple[int, int]]]]]
) -> dict[int, list[tuple[int, int]]]:
    if not student_windows:
        return {}
    merged = student_windows[0][1]
    for _, w in student_windows[1:]:
        merged = _intersect(merged, w)
    return merged


def _room_no_overlap(
    lesson: UnplacedLesson,
    head: str,
    room_common: dict[int, dict[int, list[tuple[int, int]]]],
    student_windows: list[tuple[str, dict[int, list[tuple[int, int]]]]],
    need: int,
    hints: list[str],
    room_own: dict[int, dict[int, list[tuple[int, int]]]] | None = None,
) -> Diagnosis:
    own = room_own if room_own is not None else room_common
    merged = _intersect_all(student_windows)
    per_room = [
        (rid, name, _intersect(merged, room_common.get(rid, {})))
        for rid, name, _ in lesson.room_candidates
    ]
    room_desc = "кабинетов" if len(per_room) > 1 else "кабинета"
    names = ", ".join(f"«{name}»" for _, name, _ in per_room)
    empty = [(rid, name, common) for rid, name, common in per_room if not common]
    if empty:
        reason = (
            f"{head}: у кабинета {names} нет общих свободных часов "
            f"с доступным временем учеников."
        )
        _, suggestions = _overlap_report(
            "доступное время учеников",
            merged,
            f"кабинет {names}",
            own.get(per_room[0][0], {}),
            need,
        )
        details = [
            f"Общие доступные часы учеников: {describe_windows(merged) or 'нет'}."
        ]
        details += [
            f"Часы кабинета {name}: {describe_windows(own.get(rid, {})) or 'не заданы (считаются весь рабочий день)'}."
            for rid, name, _ in per_room
        ]
        details.append(
            "Чтобы кабинет считался доступным, он должен быть свободен в те же часы, "
            "что и ученик."
        )
        details.extend(hints)
        return Diagnosis(reason=reason, details=details, suggestions=suggestions)

    best = max(per_room, key=lambda x: _longest(x[2]))
    rid, name, common = best
    longest = _longest(common)
    reason = (
        f"{head}: с кабинетом «{name}» общие часы есть, но они короче занятия — "
        f"максимум {longest} мин при длительности {need} мин."
    )
    details = [
        f"Общие часы учеников и кабинета «{name}»: {describe_windows(common) or 'нет'}.",
        f"Другие подходящие кабинеты не дают большего пересечения.",
    ]
    suggestions = [
        f"Уменьшить длительность занятия до {longest} мин.",
        f"Указать кабинету «{name}» доступность, покрывающую часы учеников.",
    ]
    details.extend(hints)
    return Diagnosis(reason=reason, details=details, suggestions=suggestions)


def _contention(
    lesson: UnplacedLesson,
    head: str,
    slots: list[tuple[int, int]],
    placements: list[Placement],
    free_teachers: list[tuple[int, str]],
    free_rooms: list[tuple[int, str]],
    hints: list[str],
) -> Diagnosis:
    t_busy: dict[int, _Resource] = {}
    r_busy: dict[int, _Resource] = {}
    for tid, name in free_teachers:
        t_busy[tid] = _Resource(name).blocked_by(
            [p for p in placements if p.teacher_id == tid]
        )
    for rid, name in free_rooms:
        r_busy[rid] = _Resource(name).blocked_by(
            [p for p in placements if p.room_id == rid]
        )

    blocked_by_teachers = 0
    blocked_by_rooms = 0
    blocked_by_both = 0
    free_slots: list[tuple[int, int]] = []
    for (day, start) in slots:
        end = start + lesson.duration_minutes
        t_free = [tid for tid, _ in free_teachers if t_busy[tid].hit(day, start, end) == 0]
        r_free = [rid for rid, _ in free_rooms if r_busy[rid].hit(day, start, end) == 0]
        if t_free and r_free:
            free_slots.append((day, start))
            continue
        if not t_free and not r_free:
            blocked_by_both += 1
        elif not t_free:
            blocked_by_teachers += 1
        else:
            blocked_by_rooms += 1

    examples = ", ".join(
        f"{DAY_SHORT[d]} {fmt_clock(s)}" for (d, s) in slots[:MAX_WINDOWS_IN_TEXT]
    )
    if len(slots) > MAX_WINDOWS_IN_TEXT:
        examples += f" и ещё {len(slots) - MAX_WINDOWS_IN_TEXT}"

    t_names = " и ".join(n for _, n in free_teachers)
    parts: list[str] = []
    if blocked_by_teachers:
        names = ", ".join(n for _, n in free_teachers)
        parts.append(
            f"педагог(и) {names} заняты в это время другими занятиями "
            f"({blocked_by_teachers} из {len(slots)} окон)"
        )
    if blocked_by_rooms:
        names = ", ".join(f"«{n}»" for _, n in free_rooms)
        parts.append(
            f"кабинет(ы) {names} заняты ({blocked_by_rooms} из {len(slots)} окон)"
        )
    if blocked_by_both:
        parts.append(
            f"одновременно заняты и педагог, и кабинет ({blocked_by_both} окон)"
        )

    if free_slots:
        reason = (
            f"{head}: подходящих окон {len(slots)} ({examples}), но свободных "
            f"из них только {len(free_slots)} — этого не хватает, чтобы поставить "
            f"все занятия."
        )
    else:
        reason = (
            f"{head}: подходящие окна есть ({examples}), но в каждом из них заняты "
            f"{t_names} или все подходящие кабинеты."
        )
    if parts:
        reason += " " + "; ".join(parts) + "."
    details = [
        f"Подходящих окон, где ученики, педагог и кабинет свободны по графику: {len(slots)} "
        f"({examples}).",
        f"Из них невозможных из-за занятости ресурсов: {len(slots) - len(free_slots)}.",
    ]
    for (day, start) in slots[:2]:
        end = start + lesson.duration_minutes
        for tid, name in free_teachers:
            busy = t_busy[tid].offenders(day, start, end)
            if busy:
                details.append(
                    f"{DAY_SHORT[day]} {fmt_clock(start)}: педагог {name} уже занят в "
                    + ", ".join(busy)
                    + "."
                )
        for rid, name in free_rooms:
            busy = r_busy[rid].offenders(day, start, end)
            if busy:
                details.append(
                    f"{DAY_SHORT[day]} {fmt_clock(start)}: кабинет «{name}» уже занят в "
                    + ", ".join(busy)
                    + "."
                )
    suggestions = [
        f"Добавить второго педагога на направление «{lesson.subject_name}»",
        "Добавить дополнительный кабинет",
        "Расширить доступность педагога или кабинета",
        "Уменьшить количество занятий в неделю либо их длительность",
    ]
    details.extend(hints)
    return Diagnosis(reason=reason, details=details, suggestions=suggestions)