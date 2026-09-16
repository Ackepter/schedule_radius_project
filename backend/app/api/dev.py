import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import MessageResponse

router = APIRouter()


@router.get("/export")
def dev_export(db: Session = Depends(get_db)):
    """Выгружает все данные в JSON-файл (формат для бэкапа и загрузки)."""
    from app.services.backup_service import export_all

    payload = export_all(db)
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="backup.json"'},
    )


@router.post("/import")
def dev_import(payload: dict, db: Session = Depends(get_db)):
    """Удаляет текущие данные и загружает всё из JSON (формат /export)."""
    from app.services.backup_service import import_all

    try:
        result = import_all(db, payload)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка импорта: {exc}") from exc
    return {
        "message": "Импорт выполнен успешно",
        "counts": {k: v for k, v in result.items() if k != "warnings"},
        "warnings": result.get("warnings", []),
    }


@router.post("/wipe", response_model=MessageResponse)
def dev_wipe(db: Session = Depends(get_db)):
    """Полностью удаляет все данные (справочники, расписания, цены)."""
    from app.services.backup_service import wipe_all_data

    try:
        wipe_all_data(db)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Ошибка очистки: {exc}") from exc
    return MessageResponse(message="Все данные удалены")