"""Создание пользователей (только владельцем приложения, без публичного endpoint)."""

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.entities import User

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,100}$")


def validate_username(username: str) -> Optional[str]:
    """Возвращает текст ошибки или None, если username корректен."""
    u = (username or "").strip()
    if not USERNAME_RE.fullmatch(u):
        return (
            "Имя пользователя должно быть 3–100 символов и содержать только "
            "латинские буквы, цифры, '_', '-', '.'."
        )
    return None


def validate_password(password: str) -> Optional[str]:
    if not password or len(password) < 8:
        return "Пароль должен содержать не менее 8 символов."
    return None


def create_user(
    db: Session,
    username: str,
    password: str,
    *,
    is_active: bool = True,
) -> User:
    """Создаёт пользователя. ValueError при невалидных данных или дубликате.

    Пароль не логируется и не возвращается — хранится только Argon2id-хэш.
    """
    username = (username or "").strip()
    err = validate_username(username)
    if err:
        raise ValueError(err)
    err = validate_password(password)
    if err:
        raise ValueError(err)

    existing = db.scalar(select(User).where(User.username == username))
    if existing is not None:
        raise ValueError(f"Пользователь «{username}» уже существует.")

    user = User(
        username=username,
        password_hash=hash_password(password),
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user