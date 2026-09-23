from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import Base, engine, SessionLocal

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.seed_on_startup:
        # Создание таблиц (в development-режиме без alembic)
        Base.metadata.create_all(bind=engine)
        from app.db.seed import seed_database

        db = SessionLocal()
        try:
            # Сидинг сам пропускается, если база уже содержит данные,
            # чтобы не затирать данные с прошлых запусков
            seed_database(db)
        finally:
            db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Автоматическое составление расписания центра детских занятий",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "app": settings.app_name}