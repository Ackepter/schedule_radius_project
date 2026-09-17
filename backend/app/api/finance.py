from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import DataResponse, FinanceSummary
from app.services.pricing_service import calculate_schedule_revenue

router = APIRouter()


@router.get("/summary", response_model=DataResponse[FinanceSummary])
def finance_summary(
    schedule_id: int = Query(..., ge=1),
    day_of_week: int = Query(default=None, ge=0, le=6),
    db: Session = Depends(get_db),
):
    summary = calculate_schedule_revenue(db, schedule_id, day_of_week=day_of_week)
    return DataResponse(data=summary)
