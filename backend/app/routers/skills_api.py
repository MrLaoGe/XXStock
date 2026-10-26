"""Skill management API. Installation and execution require the admin key."""
import hmac
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import DailyBasic, SkillInstall, SkillInstallJob, SkillRun, Stock
from app.skill_runtime_v2 import (
    SKILL_API_VERSION, environment_root, install_zip, package_root,
    read_package, remove_skill_path, run_process, skills_root,
)

router = APIRouter(prefix="/api/skills", tags=["skills"])
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def require_admin(x_admin_key: str | None = Header(default=None)):
    configured = settings.X2STOCK_ADMIN_KEY
    if not configured:
        raise HTTPException(status_code=503, detail="Skill management is disabled: X2STOCK_ADMIN_KEY is not configured")
    if not x_admin_key or not hmac.compare_digest(x_admin_key, configured):
        raise HTTPException(status_code=403, detail="invalid or missing X-Admin-Key")


def serialize_skill(skill):
    return {
        "skill_id": skill.skill_id, "name": skill.name, "version": skill.version,
        "api_version": skill.api_version, "status": skill.status,
        "enabled": bool(skill.enabled), "manifest": skill.manifest,
        "installed_at": str(skill.installed_at) if skill.installed_at else None,
        "updated_at": str(skill.updated_at) if skill.updated_at else None,
    }


def serialize_job(job):
    return {
        "job_id": job.id, "status": job.status, "skill_id": job.skill_id,
        "version": job.version, "message": job.message,
        "created_at": str(job.created_at) if job.created_at else None,
        "updated_at": str(job.updated_at) if job.updated_at else None,
    }


class RunRequest(BaseModel):
    params: dict = Field(default_factory=dict)


def _process_install_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(SkillInstallJob).filter_by(id=job_id).first()
        if not job:
            return
        job.status = "installing"
        job.message = "Validating package and preparing an isolated Python environment"
        db.commit()
        try:
            result = install_zip(job.archive_path)
            manifest = result["manifest"]
            existing = db.query(SkillInstall).filter_by(skill_id=manifest["skill_id"]).first()
            if existing:
                existing.name = manifest["name"]
                existing.version = manifest["version"]
                existing.api_version = manifest["api_version"]
                existing.path = result["path"]
                existing.entrypoint = result["entrypoint"]
                existing.manifest = manifest
                existing.status = "installed"
                existing.enabled = 1
            else:
                db.add(SkillInstall(
                    skill_id=manifest["skill_id"], name=manifest["name"],
                    version=manifest["version"], api_version=manifest["api_version"],
                    path=result["path"], entrypoint=result["entrypoint"],
                    manifest=manifest, status="installed", enabled=1,
                ))
            job.skill_id = manifest["skill_id"]
            job.version = manifest["version"]
            job.status = "completed"
            job.message = "Skill installed and enabled"
            db.commit()
        except Exception as exc:
            db.rollback()
            job = db.query(SkillInstallJob).filter_by(id=job_id).first()
            if job:
                job.status = "failed"
                job.message = str(exc)[:4000]
                db.commit()
    finally:
        job = db.query(SkillInstallJob).filter_by(id=job_id).first()
        if job and job.archive_path:
            Path(job.archive_path).unlink(missing_ok=True)
        db.close()


@router.get("")
def list_skills(db: Session = Depends(get_db)):
    return [serialize_skill(item) for item in db.query(SkillInstall).order_by(SkillInstall.skill_id).all()]


@router.post("/install", dependencies=[Depends(require_admin)], status_code=202)
async def install_skill(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "only .zip skill packages are supported")
    job_id = str(uuid.uuid4())
    upload_dir = skills_root() / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    archive = upload_dir / (job_id + ".zip")
    size = 0
    try:
        with archive.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "skill archive exceeds the 50 MB upload limit")
                output.write(chunk)
        if size == 0:
            raise HTTPException(400, "skill archive is empty")
        job = SkillInstallJob(
            id=job_id, status="queued", message="Waiting for installer",
            archive_path=str(archive),
        )
        db.add(job)
        db.commit()
        background_tasks.add_task(_process_install_job, job_id)
        return serialize_job(job)
    except Exception:
        archive.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@router.get("/install/{job_id}")
def get_install_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(SkillInstallJob).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(404, "installation job not found")
    return serialize_job(job)


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
        remove_skill_path(skill_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.delete(skill)
    db.query(SkillRun).filter_by(skill_id=skill_id).delete()
    db.commit()
    return {"deleted": skill_id}


def build_low_valuation_payload(db: Session, params: dict, permissions: list[str]):
    data = {}
    sources = []
    missing = []
    data_as_of = None
    if "market.daily_basic.read" in permissions:
        latest_date = db.query(DailyBasic.trade_date).order_by(DailyBasic.trade_date.desc()).first()
        if latest_date:
            trade_date = latest_date[0]
            data_as_of = str(trade_date)
            rows = db.query(DailyBasic).filter(DailyBasic.trade_date == trade_date).all()
            data["daily_basic"] = [{
                "record_id": row.id, "ts_code": row.ts_code, "trade_date": str(trade_date),
                "pe_ttm": row.pe_ttm, "pb": row.pb, "source": row.source or "unknown",
            } for row in rows]
            sources.append({
                "dataset": "daily_basic", "as_of": data_as_of,
                "record_ids": [row.id for row in rows],
                "source_names": sorted({row.source or "unknown" for row in rows}),
            })
        else:
            data["daily_basic"] = []
            missing.append("daily_basic")
    if "market.stocks.read" in permissions:
        rows = db.query(Stock).all()
        data["stocks"] = [{
            "ts_code": row.ts_code, "name": row.name, "industry": row.industry,
            "list_status": row.list_status, "delist_date": str(row.delist_date) if row.delist_date else None,
        } for row in rows]
        sources.append({"dataset": "stocks", "as_of": None, "record_count": len(rows), "source_names": ["platform"]})
        if not rows:
            missing.append("stocks")
    return {
        "protocol": SKILL_API_VERSION, "params": params, "data": data,
        "meta": {"data_as_of": data_as_of, "sources": sources, "missing": missing},
    }


@router.post("/{skill_id}/run", dependencies=[Depends(require_admin)])
def run_skill(skill_id: str, request: RunRequest, db: Session = Depends(get_db)):
    skill = db.query(SkillInstall).filter_by(skill_id=skill_id).first()
    if not skill:
        raise HTTPException(404, "skill not found")
    if not skill.enabled:
        raise HTTPException(409, "skill is disabled")
    payload = build_low_valuation_payload(db, request.params, skill.manifest.get("permissions", []))
    result = run_process(Path(skill.path), skill.manifest, payload)
    record = SkillRun(
        skill_id=skill.skill_id, version=skill.version, status=result["status"],
        duration_ms=result.get("duration_ms"), input_payload=payload,
        output_payload=result.get("output"), error_message=result.get("error_message"),
        stderr=result.get("stderr"),
    )
    db.add(record)
    db.commit()
    return {"run_id": record.id, **result}


@router.get("/{skill_id}/runs")
def skill_runs(skill_id: str, limit: int = 20, db: Session = Depends(get_db)):
    limit = min(max(limit, 1), 200)
    rows = db.query(SkillRun).filter_by(skill_id=skill_id).order_by(SkillRun.created_at.desc()).limit(limit).all()
    return [{
        "id": row.id, "skill_id": row.skill_id, "version": row.version, "status": row.status,
        "duration_ms": row.duration_ms, "output": row.output_payload,
        "error_message": row.error_message, "created_at": str(row.created_at),
    } for row in rows]


@router.get("/installable/example")
def example_skill_info():
    return {"skill_id": "low-valuation-screener", "api_version": SKILL_API_VERSION}
