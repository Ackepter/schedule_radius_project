"""Пароли, сессионные токены. Пароли хранятся только как Argon2id-хэши."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()

HASH_ALGORITHM = "argon2id"


def hash_password(password: str) -> str:
    """Возвращает self-describing Argon2id hash (алгоритм+соль+параметры+хэш)."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет пароль против хэша. Никогда не бросает исключений наружу."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def generate_session_token() -> str:
    """Случайный токен сессии, отдаваемый в HttpOnly cookie."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """SHA-256 токена для хранения в БД."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()