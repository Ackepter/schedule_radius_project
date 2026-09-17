"""Функциональный тест полного цикла: БД -> seed -> оптимизатор -> проверки."""

import os
import sys
from datetime import time

os.environ["DATABASE_URL"] = "sqlite:///C:/Users/Ackepter/Desktop/work_project2/test_sqlite.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.db.seed import seed_database
from app.main import app

client = TestClient(app)


def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()


def test_seed_and_list():
    r = client.get("/api/students")
    assert r.status_code == 200, r.text
    data = r.json()["items"]
    assert len(data) == 10, f"expected 10 students, got {len(data)}"
    r = client.get("/api/teachers")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 5
    r = client.get("/api/rooms")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 5
    r = client.get("/api/students")
    students = r.json()["items"]
    group_requests = sum(
        1
        for s in students
        for lr in s.get("lesson_requests", [])
        if lr.get("lesson_type") == "group"
    )
    assert group_requests == 12, f"expected 12 group requests, got {group_requests}"
    both_requests = sum(
        1
        for s in students
        for lr in s.get("lesson_requests", [])
        if lr.get("lesson_type") == "both"
    )
    assert both_requests == 1, f"expected 1 'both' request, got {both_requests}"
    print("seed+list OK")


def test_generate_schedule():
    r = client.post("/api/schedules/generate")
    assert r.status_code == 200, f"{r.status_code}: {r.text[:500]}"
    resp = r.json()["data"]
    sched_id = resp["schedule_id"]
    print(f"generate OK schedule_id={sched_id} scheduled={resp['scheduled_count']} unscheduled={resp['unscheduled_count']}")
    assert resp["scheduled_count"] > 0
    return sched_id


def test_conflict_freedom(sched_id):
    r = client.get(f"/api/schedules/{sched_id}/lessons")
    assert r.status_code == 200
    lessons = r.json()["items"]
    assert len(lessons) == r.json()["total"]

    # все жёсткие ограничения
    by_teacher = {}
    by_room = {}
    by_student = {}
    for l in lessons:
        day = l["day_of_week"]
        s = time.fromisoformat(l["start_time"])
        e = time.fromisoformat(l["end_time"])
        by_teacher.setdefault((day, l["teacher_id"]), []).append((s, e))
        by_room.setdefault((day, l["room_id"]), []).append((s, e))
        if l["lesson_type"] == "individual":
            by_student.setdefault((day, l["student_id"]), []).append((s, e))
        elif l["lesson_type"] == "group":
            for p in l.get("participants", []):
                by_student.setdefault((day, p["student"]["id"]), []).append((s, e))

    def overlaps(a, b):
        return a[0] < b[1] and b[0] < a[1]

    for buckets in (by_teacher, by_room, by_student):
        for key, slots in buckets.items():
            for i in range(len(slots)):
                for j in range(i + 1, len(slots)):
                    assert not overlaps(slots[i], slots[j]), f"CONFLICT {key}: {slots[i]} vs {slots[j]}"
    print("conflict-freedom OK")


def test_pricing_and_finance(sched_id):
    r = client.get(f"/api/finance/summary", params={"schedule_id": sched_id})
    assert r.status_code == 200
    data = r.json()["data"]
    print(f"finance OK revenue={data['total_revenue']} indiv={data['individual_lessons']} group={data['group_lessons']}")
    assert data["total_revenue"] > 0
    assert data["teacher_pay_total"] > 0, "педагогам должна быть назначена оплата"
    assert data["net_revenue"] == round(data["total_revenue"] - data["teacher_pay_total"], 2)
    assert data["teacher_breakdown"], "нет разбивки по педагогам"
    assert data["student_breakdown"], "нет разбивки по ученикам"

    # валидация: ставка педагога не может превышать выручку центра
    subjects = client.get("/api/subjects").json()["items"]
    math = next(s for s in subjects if s["name"] == "Математика")
    r = client.post("/api/finance/teacher-rates", json={
        "teacher_id": None, "subject_id": math["id"],
        "lesson_type": "individual", "rate_per_lesson": 10_000_000,
    })
    assert r.status_code == 400, f"переплата педагогу должна отклоняться: {r.status_code} {r.text[:200]}"
    print("teacher-rate overpay validation OK")


def test_export(sched_id):
    for fmt in ("png", "pdf", "xlsx"):
        r = client.get(f"/api/export/{sched_id}?format={fmt}")
        assert r.status_code == 200, f"{fmt}: {r.status_code} {r.text[:200]}"
        assert len(r.content) > 100
    print("export OK")


def test_manual_edit_conflict():
    # создадим занятие вручную и проверим, что конфликт ловится
    from datetime import date as _date
    r = client.post("/api/schedules", json={"name": "Тест", "week_start": _date.today().isoformat()})
    assert r.status_code == 201, r.text
    sched_id = r.json()["data"]["id"]

    # берём совместимую тройку: Иванов (доступен Пн 15-19), математика, Петрова, кабинет №1
    student = next(
        s for s in client.get("/api/students").json()["items"]
        if s["last_name"] == "Иванов"
    )
    math = next(
        s for s in client.get("/api/subjects").json()["items"]
        if s["name"] == "Математика"
    )
    teacher = None
    for t in client.get("/api/teachers").json()["items"]:
        det = client.get(f"/api/teachers/{t['id']}").json()["data"]
        if any(x["id"] == math["id"] for x in det["subjects"]):
            teacher = det
            break
    room = None
    for rd in client.get("/api/rooms").json()["items"]:
        det = client.get(f"/api/rooms/{rd['id']}").json()["data"]
        if any(x["id"] == math["id"] for x in det["allowed_subjects"]):
            room = det
            break
    assert teacher and room

    # добавим требование
    body = {
        "student_id": student["id"], "subject_id": math["id"],
        "lesson_type": "individual", "lessons_per_week": 1, "duration_minutes": 60,
    }
    r = client.post("/api/lesson-requests", json=body)
    assert r.status_code in (200, 201), r.text
    lr = r.json()["data"]["id"]

    # Иван Иванов доступен Пн 15-19, Петрова Пн 14-19, кабинет свободен -> 201
    lesson_body = {
        "schedule_id": sched_id, "lesson_type": "individual",
        "lesson_request_id": lr, "student_id": student["id"],
        "day_of_week": 0, "start_time": "16:00", "end_time": "17:00",
        "teacher_id": teacher["id"], "room_id": room["id"],
    }
    r = client.post(f"/api/schedules/{sched_id}/lessons", json=lesson_body)
    print(f"manual add lesson: {r.status_code} {r.text[:400]}")
    assert r.status_code == 201, f"expected success, got {r.status_code}: {r.text[:400]}"

    # конфликт: та же комната в то же время
    r2 = client.post(f"/api/schedules/{sched_id}/lessons", json=lesson_body)
    print(f"conflict add lesson: {r2.status_code} {r2.text[:400]}")
    assert r2.status_code == 409, "expected 409 conflict"


if __name__ == "__main__":
    setup_db()
    test_seed_and_list()
    sched_id = test_generate_schedule()
    test_conflict_freedom(sched_id)
    test_pricing_and_finance(sched_id)
    test_export(sched_id)
    test_manual_edit_conflict()
    print("ALL BACKEND TESTS PASSED")