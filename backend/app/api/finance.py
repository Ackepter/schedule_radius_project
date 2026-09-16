from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import DataResponse, FinanceSummary
from app.services.pricing_service import calculate_schedule_revenue

router = APIRouter()


@router.get("/summary", response_model=DataResponse[FinanceSummary])
def finance_summary(
    schedule_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    summary = calculate_schedule_revenue(db, schedule_id)
    return DataResponse(data=summary)
