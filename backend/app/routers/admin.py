from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CollectionLog
from app.config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/collection-logs")
def collection_logs(limit: int = 50, db: Session = Depends(get_db)):
    logs = db.query(CollectionLog).order_by(CollectionLog.created_at.desc()).limit(limit).all()
    return [dict(id=l.id, api_name=l.api_name, params=l.params, status=l.status,
                 rows_affected=l.rows_affected, error_message=l.error_message,
                 duration_ms=l.duration_ms, source=l.source, created_at=str(l.created_at)) for l in logs]

@router.get("/status")
def status(db: Session = Depends(get_db)):
    return dict(scheduler_enabled=settings.SCHEDULER_ENABLED, collection_time=settings.COLLECTION_TIME,
                tushare_configured=bool(settings.TUSHARE_TOKEN),
                openai_configured=bool(settings.OPENAI_API_KEY))

@router.post("/collect/stock-basic")
def trigger_stock_basic(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from app.collectors.tushare_collector import collect_stock_basic
    def task():
        session = SessionLocal()
        try:
            collect_stock_basic(session)
        finally:
            session.close()
    background_tasks.add_task(task)
    return dict(message="stock_basic collection started")
