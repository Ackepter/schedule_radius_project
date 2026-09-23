"""Management CLI приложения.

Создание пользователей — только владельцем приложения:

    python -m app.cli create-user
    python -m app.cli create-user --username admin --password 'secret123'
"""

import argparse
import getpass
import sys

from app.core.database import SessionLocal
from app.services.user_service import create_user


def _prompt_password(confirm: bool = True) -> str:
    password = getpass.getpass("Password: ")
    if confirm:
        repeat = getpass.getpass("Confirm password: ")
        if password != repeat:
            raise ValueError("Пароли не совпадают.")
    return password


def cmd_create_user(args) -> int:
    username = args.username
    password = args.password
    if not username:
        username = input("Username: ").strip()
    if not password:
        password = _prompt_password(confirm=not args.password)

    db = SessionLocal()
    try:
        user = create_user(db, username, password)
    except ValueError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        if "no such table" in detail or "UndefinedTable" in detail:
            print(
                "Ошибка: таблицы ещё не созданы. Выполните сначала "
                "`alembic upgrade head`.",
                file=sys.stderr,
            )
        else:
            print(f"Ошибка при обращении к базе: {detail}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"Пользователь «{user.username}» создан (id={user.id}).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-user", help="Создать пользователя")
    create.add_argument("--username", default="", help="Имя пользователя")
    create.add_argument(
        "--password",
        default="",
        help="Пароль (если не задан — будет запрошен интерактивно)",
    )
    create.set_defaults(func=cmd_create_user)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())