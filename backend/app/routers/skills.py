import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import DailyBasic, SkillInstall, SkillRun, Stock
from app.skills_runtime import (SKILL_API_VERSION, install_zip, read_package,
                                remove_skill_path, run_process)

router = APIRouter(prefix="/api/skills", tags=["skills"])


def require_admin(x_admin_key: str | None = Header(default=None)):
    if not settings.X2STOCK_ADMIN_KEY or x_admin_key != settings.X2STOCK_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="invalid or missing X-Admin-Key")


def serialize_skill(skill):
    return {"skill_id": skill.skill_id, "name": skill.name, "version": skill.version,
            "api_version": skill.api_version, "status": skill.status,
            "enabled": bool(skill.enabled), "manifest": skill.manifest,
            "installed_at": str(skill.installed_at) if skill.installed_at else None,
            "updated_at": str(skill.updated_at) if skill.updated_at else None}


class RunRequest(BaseModel):
    params: dict = Field(default_factory=dict)


@router.get("")
def list_skills(db: Session = Depends(get_db)):
    return [serialize_skill(item) for item in db.query(SkillInstall).order_by(SkillInstall.skill_id).all()]


@router.post("/install", dependencies=[Depends(require_admin)])
async def install_skill(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "only .zip skill packages are supported")
    with tempfile.NamedTemporaryFile(prefix="x2stock-skill-", suffix=".zip", delete=False) as tmp:
        tmp.write(await file.read())
        archive = tmp.name
    try:
        try:
            result = install_zip(archive)
        except Exception as exc:
            raise HTTPException(400, str(exc)) from exc
        manifest = result["manifest"]
        existing = db.query(SkillInstall).filter_by(skill_id=manifest["skill_id"]).first()
        if existing:
            existing.name = manifest["name"]
            existing.version = str(manifest["version"])
            existing.api_version = manifest["api_version"]
            existing.path = result["path"]
            existing.entrypoint = result["entrypoint"]
            existing.manifest = manifest
            existing.status = "installed"
            existing.enabled = 1
        else:
            existing = SkillInstall(skill_id=manifest["skill_id"], name=manifest["name"],
                                    version=str(manifest["version"]), api_version=manifest["api_version"],
                                    path=result["path"], entrypoint=result["entrypoint"],
                                    manifest=manifest, status="installed", enabled=1)
            db.add(existing)
        db.commit()
        db.refresh(existing)
        return serialize_skill(existing)
    finally:
        Path(archive).unlink(missing_ok=True)


@router.post("/{skill_id}/enable", dependencies=[Depends(require_admin)])
def enable_skill(skill_id: str, db: Session = Depends(get_db)):
    skill = db.query(SkillInstall).filter_by(skill_id=skill_id).first()
    if not skill:
        raise HTTPException(404, "skill not found")
    skill.enabled = 1
    skill.status = "installed"
    db.commit()
    return serialize_skill(skill)


@router.post("/{skill_id}/disable", dependencies=[Depends(require_admin)])
def disable_skill(skill_id: str, db: Session = Depends(get_db)):
    skill = db.query(SkillInstall).filter_by(skill_id=skill_id).first()
    if not skill:
        raise HTTPException(404, "skill not found")
    skill.enabled = 0
    skill.status = "disabled"
    db.commit()
    return serialize_skill(skill)


@router.delete("/{skill_id}", dependencies=[Depends(require_admin)])
def uninstall_skill(skill_id: str, db: Session = Depends(get_db)):
    skill = db.query(SkillInstall).filter_by(skill_id=skill_id).first()
    if not skill:
        raise HTTPException(404, "skill not found")
    try:
        remove_skill_path(skill.path)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.delete(skill)
    db.query(SkillRun).filter_by(skill_id=skill_id).delete()
    db.commit()
    return {"deleted": skill_id}


def build_low_valuation_payload(db: Session, params: dict):
    latest_date = db.query(DailyBasic.trade_date).order_by(DailyBasic.trade_date.desc()).first()
    if not latest_date:
        return {"protocol": SKILL_API_VERSION, "params": params, "data": {"stocks": []},
                "meta": {"data_as_of": None, "sources": [], "missing": ["daily_basic"]}}
    trade_date = latest_date[0]
    rows = db.query(DailyBasic, Stock).join(Stock, Stock.ts_code == DailyBasic.ts_code).filter(
        DailyBasic.trade_date == trade_date).all()
    stocks = []
    for basic, stock in rows:
        stocks.append({"ts_code": basic.ts_code, "name": stock.name, "industry": stock.industry,
                       "trade_date": str(trade_date), "pe_ttm": basic.pe_ttm,
                       "pb": basic.pb, "source": basic.source or "unknown",
                       "source_record": f"daily_basic:{basic.ts_code}:{trade_date}"})
    return {"protocol": SKILL_API_VERSION, "params": params, "data": {"stocks": stocks},
            "meta": {"data_as_of": str(trade_date), "sources": ["daily_basic", "stocks"],
                     "missing": [] if stocks else ["daily_basic"]}}


@router.post("/{skill_id}/run", dependencies=[Depends(require_admin)])
def run_skill(skill_id: str, request: RunRequest, db: Session = Depends(get_db)):
    skill = db.query(SkillInstall).filter_by(skill_id=skill_id).first()
    if not skill:
        raise HTTPException(404, "skill not found")
    if not skill.enabled:
        raise HTTPException(409, "skill is disabled")
    payload = build_low_valuation_payload(db, request.params) if skill_id == "low-valuation-screener" else {
        "protocol": SKILL_API_VERSION, "params": request.params, "data": {}, "meta": {}}
    result = run_process(Path(skill.path), skill.manifest, payload)
    record = SkillRun(skill_id=skill.skill_id, version=skill.version, status=result["status"],
                      duration_ms=result.get("duration_ms"), input_payload=payload,
                      output_payload=result.get("output"), error_message=result.get("error_message"),
                      stderr=result.get("stderr"))
    db.add(record)
    db.commit()
    return {"run_id": record.id, **result}


@router.get("/{skill_id}/runs")
def skill_runs(skill_id: str, limit: int = 20, db: Session = Depends(get_db)):
    rows = db.query(SkillRun).filter_by(skill_id=skill_id).order_by(SkillRun.created_at.desc()).limit(limit).all()
    return [{"id": row.id, "skill_id": row.skill_id, "version": row.version, "status": row.status,
             "duration_ms": row.duration_ms, "output": row.output_payload,
             "error_message": row.error_message, "created_at": str(row.created_at)} for row in rows]
