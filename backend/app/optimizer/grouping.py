"""Автоматическое формирование групп из групповых заявок учеников.

Групповые заявки (LessonRequest с lesson_type=group) объединяются в группы
по совместимости: направление, длительность, количество занятий в неделю,
общая доступность учеников и совместимость педагогов.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    Availability,
    EntityTypeEnum,
    LessonRequest,
    Student,
)


@dataclass
class FormedGroup:
    """Сформированная автоматически группа из групповых заявок."""

    lesson_request_ids: list[int] = field(default_factory=list)
    student_ids: list[int] = field(default_factory=list)
    subject_id: int = 0
    subject_name: str = ""
    duration_minutes: int = 60
    lessons_per_week: int = 1
    priority: int = 1
    preferred_teacher_id: Optional[int] = None
    teacher_is_required: bool = False


@dataclass
class FailedGroup:
    """Групповая заявка, которую не удалось включить в группу."""

    lesson_request_id: int
    student_id: int
    subject_id: int
    subject_name: str
    reason: str


@dataclass
class _Member:
    req: LessonRequest
    windows: list[tuple[int, int, int]] = field(default_factory=list)


@dataclass
class _Cluster:
    members: list[_Member] = field(default_factory=list)
    windows: list[tuple[int, int, int]] = field(default_factory=list)
    required_teacher_id: Optional[int] = None
    preferred_teacher_id: Optional[int] = None

    def can_add(self, m: _Member) -> bool:
        if not m.windows or not _intersect_windows(self.windows, m.windows):
            return False
        pid, req = m.req.preferred_teacher_id, m.req.teacher_is_required
        if req:
            if self.required_teacher_id is not None and self.required_teacher_id != pid:
                return False
            return True
        if self.required_teacher_id is None:
            return (
                self.preferred_teacher_id is None
                or pid is None
                or self.preferred_teacher_id == pid
            )
        return True

    def add(self, m: _Member) -> None:
        self.windows = _intersect_windows(self.windows, m.windows)
        self.members.append(m)
        pid, req = m.req.preferred_teacher_id, m.req.teacher_is_required
        if req:
            self.required_teacher_id = pid
            self.preferred_teacher_id = pid
        elif self.required_teacher_id is None:
            if self.preferred_teacher_id is None:
                self.preferred_teacher_id = pid
            elif self.preferred_teacher_id != pid:
                self.preferred_teacher_id = None


def _merge_intervals(intervals: list[list[int]]) -> list[tuple[int, int]]:
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


def _intersect_lists(a: list[tuple[int, int]], b: list[tuple[int, int]]) -> list[tuple[int, int]]:
    res: list[tuple[int, int]] = []
    i = j = 0
    while i < len(a) and j < len(b):
        s = max(a[i][0], b[j][0])
        e = min(a[i][1], b[j][1])
        if s < e:
            res.append((s, e))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return res


def _intersect_windows(
    a: list[tuple[int, int, int]], b: list[tuple[int, int, int]]
) -> list[tuple[int, int, int]]:
    """Пересечение списков окон вида (day, start_min, end_min)."""
    if not a or not b:
        return []
    by_day: dict[int, list[list[int]]] = defaultdict(list)
    for lst in (a, b):
        by_day2: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for d, s, e in lst:
            by_day2[d].append((s, e))
        for d, ivs in by_day2.items():
            by_day[d].append(ivs)
    res: list[tuple[int, int, int]] = []
    for d, ivs_list in by_day.items():
        if len(ivs_list) < 2:
            continue
        common = ivs_list[0]
        for other in ivs_list[1:]:
            common = _intersect_lists(common, other)
        for s, e in common:
            res.append((d, s, e))
    return res


def _student_windows(db: Session, student_id: int, duration_minutes: int) -> list[tuple[int, int, int]]:
    """День -> свободные интервалы ученика в абсолютных минутах (длина >= duration)."""
    settings = get_settings()
    open_min = settings.center_open_hour * 60
    rows = db.scalars(
        select(Availability).where(
            Availability.entity_type == EntityTypeEnum.student,
            Availability.entity_id == student_id,
        )
    ).all()
    if not rows:
        return []
    by_day: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for r in rows:
        s = r.start_time.hour * 60 + r.start_time.minute
        e = r.end_time.hour * 60 + r.end_time.minute
        if e - s < duration_minutes:
            continue
        by_day[r.day_of_week].append((s, e))
    result: list[tuple[int, int, int]] = []
    for d, ivs in by_day.items():
        merged = _merge_intervals([list(iv) for iv in ivs])
        for s, e in merged:
            result.append((d, s, e))
    return result


def form_groups(
    db: Session,
    requests: list[LessonRequest],
    min_size: int = 2,
    max_size: int = 8,
    subject_names: Optional[dict[int, str]] = None,
) -> tuple[list[FormedGroup], list[FailedGroup]]:
    """Разбивает групповые заявки на группы.

    Возвращает (сформированные группы, неразрешённые заявки).
    """
    formed: list[FormedGroup] = []
    failed: list[FailedGroup] = []

    active_students = set(
        db.execute(select(Student.id).where(Student.is_active)).scalars()
    )
    subject_names = subject_names or {}
    subj_default_name = lambda sid: f"Предмет #{sid}"

    buckets: dict[tuple[int, int, int], list[LessonRequest]] = defaultdict(list)
    for r in requests:
        if r.student_id not in active_students:
            continue
        buckets[(r.subject_id, r.duration_minutes or 60, r.lessons_per_week or 1)].append(r)

    for (subject_id, duration, lpw), reqs in buckets.items():
        members: list[_Member] = []
        for r in sorted(reqs, key=lambda x: (x.student_id, x.id)):
            windows = _student_windows(db, r.student_id, duration)
            members.append(_Member(req=r, windows=windows))

        for m in members:
            if not m.windows:
                failed.append(
                    FailedGroup(
                        lesson_request_id=m.req.id,
                        student_id=m.req.student_id,
                        subject_id=subject_id,
                        subject_name=subject_names.get(subject_id, subj_default_name(subject_id)),
                        reason=(
                            f"Нет доступности ученика длительностью {duration} мин "
                            f"для группового занятия."
                        ),
                    )
                )
        members = [m for m in members if m.windows]

        clusters: list[_Cluster] = []
        for m in members:
            placed = False
            for c in clusters:
                if len(c.members) >= max_size:
                    continue
                if c.can_add(m):
                    c.add(m)
                    placed = True
                    break
            if not placed:
                clusters.append(_Cluster(members=[m], windows=m.windows))

        for c in clusters:
            if len(c.members) >= min_size:
                c.members.sort(key=lambda x: (x.req.student_id, x.req.id))
                formed.append(
                    FormedGroup(
                        lesson_request_ids=[m.req.id for m in c.members],
                        student_ids=[m.req.student_id for m in c.members],
                        subject_id=subject_id,
                        subject_name=subject_names.get(subject_id, subj_default_name(subject_id)),
                        duration_minutes=duration,
                        lessons_per_week=lpw,
                        priority=max((m.req.priority or 1) for m in c.members),
                        preferred_teacher_id=c.preferred_teacher_id,
                        teacher_is_required=c.required_teacher_id is not None,
                    )
                )
            else:
                for m in c.members:
                    failed.append(
                        FailedGroup(
                            lesson_request_id=m.req.id,
                            student_id=m.req.student_id,
                            subject_id=subject_id,
                            subject_name=subject_names.get(subject_id, subj_default_name(subject_id)),
                            reason=(
                                f"Недостаточно учеников для формирования группы "
                                f"(минимальный размер группы — {min_size})."
                            ),
                        )
                    )

    return formed, failed