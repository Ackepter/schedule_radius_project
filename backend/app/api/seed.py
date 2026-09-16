from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import MessageResponse

router = APIRouter()


@router.post("", response_model=MessageResponse)
def seed_data(db: Session = Depends(get_db)):
    from app.db.seed import seed_database

    seed_database(db)
    return MessageResponse(message="Seed data loaded successfully")
