from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Stock, DailyQuote, Financial, Announcement, Report
from app.services.ai_service import generate_stock_report, agent_answer

router = APIRouter(prefix="/api/ai", tags=["ai"])

class StockReportRequest(BaseModel):
    ts_code: str

class AgentRequest(BaseModel):
    question: str
    ts_code: str = ""

@router.post("/report")
def create_report(req: StockReportRequest, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.ts_code == req.ts_code).first()
    if not stock:
        raise HTTPException(404, "Stock not found")
    quotes = db.query(DailyQuote).filter(DailyQuote.ts_code == req.ts_code).order_by(DailyQuote.trade_date.desc()).limit(60).all()
    quotes.reverse()
    financials = db.query(Financial).filter(Financial.ts_code == req.ts_code).order_by(Financial.period.desc()).limit(8).all()
    financials.reverse()
    announcements = db.query(Announcement).filter(Announcement.ts_code == req.ts_code).order_by(Announcement.publish_date.desc()).limit(10).all()

    content, refs = generate_stock_report(db, stock, quotes, financials, announcements)
    report = Report(ts_code=req.ts_code, report_type="stock_report", content=content,
                    references=refs, status="completed")
    db.add(report)
    db.commit()
    db.refresh(report)
    return dict(id=report.id, ts_code=req.ts_code, content=content, references=refs)

@router.get("/reports")
def list_reports(ts_code: str = "", limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(Report)
    if ts_code:
        q = q.filter(Report.ts_code == ts_code)
    reports = q.order_by(Report.created_at.desc()).limit(limit).all()
    return [dict(id=r.id, ts_code=r.ts_code, report_type=r.report_type, content=r.content, created_at=str(r.created_at)) for r in reports]

@router.post("/ask")
def ask(req: AgentRequest, db: Session = Depends(get_db)):
    stock = None
    quotes = None
    financials = None
    announcements = None
    if req.ts_code:
        stock = db.query(Stock).filter(Stock.ts_code == req.ts_code).first()
        quotes = db.query(DailyQuote).filter(DailyQuote.ts_code == req.ts_code).order_by(DailyQuote.trade_date.desc()).limit(30).all()
        quotes.reverse()
        financials = db.query(Financial).filter(Financial.ts_code == req.ts_code).order_by(Financial.period.desc()).limit(4).all()
        announcements = db.query(Announcement).filter(Announcement.ts_code == req.ts_code).order_by(Announcement.publish_date.desc()).limit(5).all()
    result = agent_answer(db, req.question, stock, quotes, financials, announcements)
    return result
