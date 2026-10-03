from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import OptimizerSettings
from app.schemas.schemas import (
    DataResponse,
    OptimizerSettingsBase,
    OptimizerSettingsUpdate,
)

router = APIRouter()


def _defaults_payload() -> OptimizerSettingsBase:
    """Настройки по умолчанию — из колонок модели, без рассинхрона со схемой."""
    values: dict[str, object] = {"id": 0}
    for col in OptimizerSettings.__table__.columns:
        default = getattr(col, "default", None)
        arg = getattr(default, "arg", None)
        if isinstance(arg, (int, float)):
            values[col.name] = arg
    return OptimizerSettingsBase(**values)


@router.get("", response_model=DataResponse[OptimizerSettingsBase])
def get_optimizer_settings(db: Session = Depends(get_db)):
    obj = db.execute(select(OptimizerSettings).limit(1)).scalar_one_or_none()
    if not obj:
        # Настройки появляются при первой генерации, но клиенту нужно знать
        # рабочее окно заранее — отдаём те же значения, что использует оптимизатор.
        return DataResponse(data=_defaults_payload())
    return DataResponse(data=OptimizerSettingsBase.model_validate(obj))


@router.put("", response_model=DataResponse[OptimizerSettingsBase])
def update_optimizer_settings(
    body: OptimizerSettingsUpdate, db: Session = Depends(get_db)
):
    obj = db.execute(select(OptimizerSettings).limit(1)).scalar_one_or_none()
    if not obj:
        obj = OptimizerSettings()
        db.add(obj)
        db.flush()
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return DataResponse(data=OptimizerSettingsBase.model_validate(obj))
