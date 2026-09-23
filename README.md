# Расписание Центра Детских Занятий

Полнофункциональное веб-приложение для автоматического составления недельного расписания занятий центра детского дополнительного образования.

- Генерация расписания через CP-SAT оптимизатор (OR-Tools)
- Ручное редактирование с проверкой конфликтов (включая drag-and-drop)
- Экспорт расписания (PNG / PDF / Excel)
- Финансовая статистика
- CRUD по всем сущностям (ученики, педагоги, предметы, кабинеты, группы, цены)
- Группы формируются пользователем; оптимизатор не изменяет их состав
- Авторизация: вход по логину/паролю, server-side сессии (HttpOnly cookie)

---

## Стек

| Слой | Технологии |
|------|-----------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.x, Pydantic, Alembic, OR-Tools (CP-SAT), psycopg2 |
| Frontend | React 18, TypeScript, Vite, Material UI, react-router-dom, axios |
| База данных | PostgreSQL 16 |
| Контейнеризация | Docker, Docker Compose |
| Пароли | Argon2id (`argon2-cffi`) |

---

## Авторизация

- Публичной регистрации **нет**. Пользователей создаёт только владелец приложения.
- Пароли хранятся только как Argon2id-хэши; в API никогда не возвращаются.
- Сессии server-side: в cookie — случайный токен (HttpOnly), в БД — только его SHA-256.
  Logout инвалидирует сессию на сервере; TTL по умолчанию 24 часа.
- Все `/api/*` endpoints (кроме `/health`, `login`, `logout`, `me`) требуют авторизации → 401.
- Login защищён rate limiting: 5 неудачных попыток на 15 минут (по IP и имени пользователя).

### Создание первого пользователя (локально, вне Docker)

```bash
cd backend
python -m app.cli create-user
# или неинтерактивно:
python -m app.cli create-user --username admin --password 'сложный-пароль'
```

### Создание пользователя в Docker

```bash
# на хосте, где есть доступ к сети compose:
docker compose exec backend python -m app.cli create-user
```

---

## Быстрый старт (Docker — рекомендуемый)

```bash
# скопировать файл окружения
cp .env.example .env

# собрать и запустить всё
docker compose up --build

# создать пользователя для входа
docker compose exec backend python -m app.cli create-user
```

| Сервис | URL |
|--------|-----|
| Frontend | http://localhost:8080 |
| API Docs (локально) | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

> Backend API намеренно **не публикуется** наружу: доступ только через nginx
> на фронтовом контейнере. Для локальной разработки backend поднимается
> отдельно (см. ниже).

---

## Локальная разработка (без Docker)

### Бэкенд

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/macOS

pip install -r requirements.txt

export DATABASE_URL=sqlite:///./dev.db   # для быстрой разработки
alembic upgrade head
python -m app.cli create-user
uvicorn app.main:app --reload --port 8000
```

### Фронтенд

```bash
cd frontend
npm install
npm run dev    # Vite dev-сервер на :5173 с прокси /api → localhost:8000
```

---

## Тесты

```bash
cd backend

# сценарные тесты оптимизатора
python -m pytest tests/test_schedule.py -v

# тесты авторизации (login, сессии, rate limiting, защита API)
python -m pytest tests/test_auth.py -v

# Функциональный тест полного цикла
python tests/functional_test.py
```

---

## Переменные окружения (.env)

| Переменная | По умолчанию | Описание |
|-----------|-------------|---------|
| `DATABASE_URL` | `postgresql+psycopg2://...` | Строка подключения к БД |
| `POSTGRES_USER` | `children` | Имя пользователя PostgreSQL |
| `POSTGRES_PASSWORD` | `children_password` | Пароль PostgreSQL |
| `POSTGRES_DB` | `children_center` | Имя базы данных |
| `CORS_ORIGINS` | `http://localhost:8080,...` | Разрешённые origins через запятую |
| `SEED_ON_STARTUP` | `false` | Заполнять демо-данными при старте |
| `SESSION_TTL_HOURS` | `24` | Время жизни сессии, часы |
| `COOKIE_SECURE` | `false` | `Secure` для cookie (включать за HTTPS) |
| `COOKIE_SAMESITE` | `lax` | `SameSite` для cookie |
| `LOGIN_MAX_FAILURES` | `5` | Неудачных попыток входа до блокировки |
| `LOGIN_WINDOW_MINUTES` | `15` | Окно для блокировки, минуты |

> **Внимание:** файл `.env` занесён в `.gitignore`; не коммитьте секреты.

---

## Структура проекта

```
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI роутеры (+auth, deps)
│   │   ├── core/          # config, database, security, ratelimit
│   │   ├── db/            # seed
│   │   ├── models/        # SQLAlchemy модели (users, sessions)
│   │   ├── optimizer/     # CP-SAT оптимизатор (scheduler.py)
│   │   ├── schemas/       # Pydantic схемы
│   │   ├── services/      # Бизнес-логика (+user_service)
│   │   └── main.py
│   ├── alembic/           # Миграции
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/           # axios клиент, типы
│   │   ├── auth/          # AuthContext, ProtectedRoute
│   │   ├── pages/         # React страницы (+LoginPage)
│   │   └── App.tsx
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
└── .env.example
```

---

## Лицензия

Внутренний учебный проект.