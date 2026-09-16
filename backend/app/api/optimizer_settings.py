from fastapi import APIRouter, Depends, HTTPException
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


@router.get("", response_model=DataResponse[OptimizerSettingsBase])
def get_optimizer_settings(db: Session = Depends(get_db)):
    obj = db.execute(select(OptimizerSettings).limit(1)).scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="No optimizer settings found")
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
