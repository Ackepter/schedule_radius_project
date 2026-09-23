"""Общие dependency для авторизации."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import hash_session_token
from app.models.entities import AuthSession, User

settings = get_settings()

UNAUTHORIZED = HTTPException(
    status_code=401,
    detail="Требуется авторизация",
    headers={"WWW-Authenticate": "Cookie"},
)


def get_current_session(
    request: Request, db: Session = Depends(get_db)
) -> Optional[AuthSession]:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    now = datetime.now(timezone.utc)
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_session_token(token)
        )
    )
    if session is None:
        return None
    if session.revoked_at is not None:
        return None
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        return None
    return session


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """Возвращает активного пользователя или бросает 401."""
    session = get_current_session(request, db)
    if session is None:
        raise UNAUTHORIZED
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise UNAUTHORIZED
    return user


def require_auth(
    request: Request, db: Session = Depends(get_db)
) -> User:
    """Router/endpoint-level dependency: 401 для неавторизованных."""
    return get_current_user(request, db)