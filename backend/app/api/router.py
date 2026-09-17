from fastapi import APIRouter

from app.api import (
    availabilities,
    dev,
    export,
    finance,
    lesson_requests,
    optimizer_settings,
    parents,
    prices,
    rooms,
    schedules,
    seed,
    students,
    subjects,
    teachers,
)

api_router = APIRouter(prefix="/api")

api_router.include_router(students.router, prefix="/students", tags=["students"])
api_router.include_router(teachers.router, prefix="/teachers", tags=["teachers"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(subjects.router, prefix="/subjects", tags=["subjects"])
api_router.include_router(parents.router, prefix="/parents", tags=["parents"])
api_router.include_router(
    lesson_requests.router,
    prefix="/lesson-requests",
    tags=["lesson-requests"],
)
api_router.include_router(prices.router, prefix="/prices", tags=["prices"])
api_router.include_router(
    availabilities.router,
    prefix="/availabilities",
    tags=["availabilities"],
)
api_router.include_router(
    schedules.router, prefix="/schedules", tags=["schedules"]
)
api_router.include_router(
    optimizer_settings.router,
    prefix="/optimizer-settings",
    tags=["optimizer-settings"],
)
api_router.include_router(
    finance.router, prefix="/finance", tags=["finance"]
)
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(seed.router, prefix="/seed", tags=["seed"])
api_router.include_router(dev.router, prefix="/dev", tags=["developer"])
