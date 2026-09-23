"""Authentication endpoints: login / logout / me.

Публичная регистрация отсутствует: пользователи создаются только
владельцем приложения через `python -m app.cli create-user`.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.ratelimit import LoginRateLimiter
from app.core.security import (
    generate_session_token,
    hash_session_token,
    verify_password,
)
from app.models.entities import AuthSession, User

settings = get_settings()

router = APIRouter(prefix="/api/auth", tags=["auth"])

login_limiter = LoginRateLimiter(
    max_failures=settings.login_max_failures,
    window_seconds=settings.login_window_minutes * 60,
)

INVALID_CREDENTIALS = HTTPException(
    status_code=401,
    detail="Неверное имя пользователя или пароль",
)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_active: bool


class LoginResponse(BaseModel):
    user: UserOut


class MessageOut(BaseModel):
    message: str


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    ip_key = f"ip:{_client_ip(request)}"
    user_key = f"user:{body.username.strip().lower()}"

    if login_limiter.is_blocked(ip_key) or login_limiter.is_blocked(user_key):
        raise HTTPException(
            status_code=429,
            detail="Слишком много попыток входа. Попробуйте позже.",
        )

    user = db.scalar(
        select(User).where(User.username == body.username.strip())
    )
    # Одинаковая ошибка для несуществующего пользователя, неверного пароля
    # и неактивного аккаунта — нельзя перебирать имена пользователей.
    password_ok = user is not None and verify_password(
        body.password, user.password_hash
    )
    if user is None or not password_ok or not user.is_active:
        login_limiter.record_failure(ip_key)
        login_limiter.record_failure(user_key)
        raise INVALID_CREDENTIALS

    login_limiter.record_success(user_key)

    token = generate_session_token()
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    db.commit()

    _set_session_cookie(response, token)
    return LoginResponse(user=UserOut.model_validate(user))


@router.post("/logout", response_model=MessageOut)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    # Инвалидизация на сервере даже без активной сессии (идемпотентно).
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == hash_session_token(token)
            )
        )
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
    _clear_session_cookie(response)
    return MessageOut(message="Вы вышли из системы")


@router.get("/me", response_model=LoginResponse)
def me(user: User = Depends(get_current_user)):
    return LoginResponse(user=UserOut.model_validate(user))