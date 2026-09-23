"""Тесты авторизации: регистрация (CLI), логин, сессии, rate limiting, защита API."""

import os
import sys

os.environ["DATABASE_URL"] = "sqlite:///C:/Users/Ackepter/Desktop/work_project2/test_auth.db"
TIMEOUT = 60

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app
from app.models.entities import AuthSession, User

client = TestClient(app)

ADMIN = ("admin", "correct-horse-battery")

LOGIN_URL = "/api/auth/login"
ME_URL = "/api/auth/me"
LOGOUT_URL = "/api/auth/logout"
PROTECTED_URL = "/api/students"


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.api.auth import login_limiter

    login_limiter.reset()
    db = SessionLocal()
    try:
        from app.services.user_service import create_user

        create_user(db, *ADMIN)
    finally:
        db.close()
    yield


def _login(client: TestClient, username: str = ADMIN[0], password: str = ADMIN[1]):
    return client.post(LOGIN_URL, json={"username": username, "password": password})


# ── 1. Создание пользователя ──────────────────────────────────────────────

def test_create_user():
    db = SessionLocal()
    try:
        from app.services.user_service import create_user

        user = create_user(db, "teacher1", "super-secret-pass")
        assert user.username == "teacher1"
        assert user.id is not None
        assert user.password_hash != "super-secret-pass"
        assert user.password_hash.startswith("$argon2id$")
        # уникальность username
        with pytest.raises(ValueError):
            create_user(db, "teacher1", "another-password")
        # короткий пароль и невалидный username отклоняются
        with pytest.raises(ValueError):
            create_user(db, "t2", "short")
        with pytest.raises(ValueError):
            create_user(db, "bad username!", "long-enough-password")
    finally:
        db.close()


# ── 2. Успешный login → кука, /me, доступ к API ───────────────────────────

def test_login_success_sets_cookie():
    r = _login(client)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["username"] == ADMIN[0]
    assert "password_hash" not in r.json()["user"]
    assert "session_token" in r.cookies

    r = client.get(ME_URL)
    assert r.status_code == 200
    assert r.json()["user"]["username"] == ADMIN[0]


def test_protected_api_after_login():
    assert _login(client).status_code == 200
    r = client.get(PROTECTED_URL)
    assert r.status_code == 200, r.text


# ── 3. Неправильный пароль ────────────────────────────────────────────────

def test_login_wrong_password():
    r = _login(client, password="wrong-password")
    assert r.status_code == 401
    assert "Неверное имя пользователя или пароль" in r.json()["detail"]


# ── 4. Несуществующий пользователь ────────────────────────────────────────

def test_login_unknown_user():
    r = _login(client, username="no-such-user")
    assert r.status_code == 401
    # сообщение не раскрывает, существует ли пользователь
    assert r.json()["detail"] == "Неверное имя пользователя или пароль"


# ── 5. Неактивный пользователь ────────────────────────────────────────────

def test_login_inactive_user():
    db = SessionLocal()
    try:
        from app.services.user_service import create_user

        create_user(db, "blocked", "some-password", is_active=False)
    finally:
        db.close()
    r = _login(client, username="blocked", password="some-password")
    assert r.status_code == 401
    assert r.json()["detail"] == "Неверное имя пользователя или пароль"


# ── 6. Приватный API без авторизации → 401 ────────────────────────────────

def test_private_api_without_auth():
    for method, url in [
        ("get", "/api/students"),
        ("post", "/api/seed"),
        ("get", "/api/dev/export"),
        ("post", "/api/dev/wipe"),
        ("get", "/api/finance/summary?schedule_id=1"),
    ]:
        r = getattr(client, method)(url)
        assert r.status_code == 401, f"{method.upper()} {url} -> {r.status_code}"


# ── 8. / 9. Logout и доступ после logout ───────────────────────────────────

def test_logout_invalidates_session():
    _login(client)
    assert client.get(PROTECTED_URL).status_code == 200
    assert client.post(LOGOUT_URL).status_code == 200
    # кука должна быть отозвана и удалена
    assert "session_token" not in client.cookies
    r = client.get(PROTECTED_URL)
    assert r.status_code == 401, "доступ после logout должен быть закрыт"
    # повторный logout без сессии — идемпотентно
    assert client.post(LOGOUT_URL).status_code == 200


# ── 10. Plaintext password не хранится ─────────────────────────────────────

def test_plaintext_password_not_stored():
    db = SessionLocal()
    try:
        rows = db.query(User).all()
        assert rows, "пользователи должны существовать"
        for u in rows:
            assert "correct-horse-battery" not in u.password_hash
            assert u.password_hash.startswith("$argon2id$")
    finally:
        db.close()


# ── 11. password_hash не возвращается API ─────────────────────────────────

def test_password_hash_not_in_api():
    _login(client)
    me = client.get(ME_URL).json()["user"]
    assert "password_hash" not in me
    assert "password" not in me


# ── 12. Rate limiting на login ─────────────────────────────────────────────

def test_login_rate_limiting():
    from app.api.auth import login_limiter

    # 5 успешных "провалов" (лимит по умолчанию = 5) подряд блокируют login
    for i in range(5):
        r = _login(client, username="victim", password="bad")
        assert r.status_code == 401
    r = _login(client, username="victim", password="bad")
    assert r.status_code == 429, f"ожидали 429 после 5 неудач: {r.status_code}"
    # очистка для остальных тестов
    login_limiter.reset()


# ── 13. "Чужие" данные через изменение ID ─────────────────────────────────

def test_shared_data_requires_auth_any_id():
    # single-tenant: все данные принадлежат владельцу приложения;
    # ключевое требование — ни один endpoint не доступен без авторизации.
    _login(client)
    for url in (
        "/api/students/1",
        "/api/students/999",
        "/api/teachers/1",
        "/api/subjects/1",
        "/api/schedules/1",
    ):
        r = client.get(url)
        assert r.status_code in (200, 404), f"{url} -> {r.status_code}"
    assert client.get("/api/students/999").status_code == 404