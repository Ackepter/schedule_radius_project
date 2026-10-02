"""Management CLI приложения.

Управление пользователями — только владельцем приложения:

    python -m app.cli create-user
    python -m app.cli create-user --username admin --password 'secret123'

    python -m app.cli list-users

    python -m app.cli delete-user --username admin
"""

import argparse
import getpass
import sys

from app.core.database import SessionLocal
from app.services.user_service import (
    create_user,
    delete_user,
    list_users,
)


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


def cmd_list_users(args) -> int:
    db = SessionLocal()
    try:
        users = list_users(db)
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка при обращении к базе: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    if not users:
        print("Пользователи не найдены.")
        return 0

    print(f"Всего пользователей: {len(users)}")
    print(f"{'ID':<4} {'Статус':<8} {'Имя пользователя':<24} {'Создан'}")
    print("-" * 60)
    for u in users:
        status = "активен" if u.is_active else "отключен"
        created = u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "—"
        print(f"{u.id:<4} {status:<8} {u.username:<24} {created}")
    return 0


def cmd_delete_user(args) -> int:
    username = (args.username or "").strip()
    if not username:
        print("Укажите имя пользователя: --username <имя>", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        if not args.yes:
            confirm = input(
                f"Удалить пользователя «{username}» и все его сессии? "
                "Введите его имя для подтверждения: "
            ).strip()
            if confirm != username:
                print("Отмена: подтверждение не совпало.", file=sys.stderr)
                return 1
        delete_user(db, username)
    except ValueError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка при обращении к базе: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"Пользователь «{username}» удалён.")
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

    list_cmd = sub.add_parser("list-users", help="Список пользователей")
    list_cmd.set_defaults(func=cmd_list_users)

    delete = sub.add_parser("delete-user", help="Удалить пользователя")
    delete.add_argument("--username", default="", help="Имя пользователя")
    delete.add_argument(
        "--yes",
        action="store_true",
        help="Без интерактивного подтверждения",
    )
    delete.set_defaults(func=cmd_delete_user)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())