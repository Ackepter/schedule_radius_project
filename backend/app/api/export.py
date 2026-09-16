from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import Schedule
from app.schemas.schemas import ExportFormat

router = APIRouter()


@router.get("/{schedule_id}")
def export_schedule(
    schedule_id: int,
    format: ExportFormat = Query(default=ExportFormat.xlsx),
    db: Session = Depends(get_db),
):
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    from pathlib import Path

    export_dir = Path("exports")
    export_dir.mkdir(exist_ok=True)

    ext_map = {
        ExportFormat.png: ("image/png", "png"),
        ExportFormat.pdf: ("application/pdf", "pdf"),
        ExportFormat.xlsx: (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "xlsx",
        ),
    }
    media_type, file_ext = ext_map[format]
    file_path = export_dir / f"schedule_{schedule_id}.{file_ext}"

    if not file_path.exists():
        from app.services.export_service import generate_export

        generate_export(db, schedule_id, format, file_path)

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=f"schedule_{schedule_id}.{file_ext}",
    )
