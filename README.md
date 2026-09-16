# Расписание Центра Детских Занятий

Полнофункциональное веб-приложение для автоматического составления недельного расписания занятий центра детского дополнительного образования.

- Генерация расписания через CP-SAT оптимизатор (OR-Tools)
- Ручное редактирование с проверкой конфликтов (включая drag-and-drop)
- Экспорт расписания (PNG / PDF / Excel)
- Финансовая статистика
- CRUD по всем сущностям (ученики, педагоги, предметы, кабинеты, группы, цены)
- Группы формируются пользователем; оптимизатор не изменяет их состав

---

## Стек

| Слой | Технологии |
|------|-----------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.x, Pydantic, Alembic, OR-Tools (CP-SAT), psycopg2 |
| Frontend | React 18, TypeScript, Vite, Material UI, react-router-dom, axios |
| База данных | PostgreSQL 16 |
| Контейнеризация | Docker, Docker Compose |

---

## Быстрый старт (Docker — рекомендуемый)

```bash
# скопировать файл окружения
cp .env.example .env

# собрать и запустить всё
docker compose up --build

# при первом запуске создаются таблицы через Alembic,
# после чего автоматически заполняются демо-данными (SEED_ON_STARTUP=true)
```

| Сервис | URL |
|--------|-----|
| Frontend | http://localhost:8080 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |

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

# 12 сценарных тестов оптимизатора
python -m pytest tests/test_schedule.py -v

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
| `SEED_ON_STARTUP` | `true` | Заполнять демо-данными при старте |

---

## Структура проекта

```
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI роутеры
│   │   ├── core/          # config, database
│   │   ├── db/            # seed
│   │   ├── models/        # SQLAlchemy модели
│   │   ├── optimizer/     # CP-SAT оптимизатор (scheduler.py)
│   │   ├── schemas/       # Pydantic схемы
│   │   ├── services/      # Бизнес-логика (конфликт, цены, экспорт)
│   │   └── main.py
│   ├── alembic/           # Миграции
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/           # axios клиент, типы
│   │   ├── pages/         # React страницы
│   │   └── App.tsx
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
└── .env.example
```

---

## Лицензия

Внутренний учебный проект.
