"""Install and execute versioned X2Stock skill packages."""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import venv
import zipfile
from pathlib import Path

from app.config import settings

SKILL_API_VERSION = "x2stock.skill.v1"
SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,99}$")
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024


def skills_root() -> Path:
    root = Path(settings.SKILLS_DIR).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def python_for_env(env_dir: Path) -> str:
    return str(env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json must be an object")
    required = ("skill_id", "name", "version", "api_version", "entrypoint")
    missing = [key for key in required if not manifest.get(key)]
    if missing:
        raise ValueError("manifest missing fields: " + ", ".join(missing))
    if not SKILL_ID_RE.fullmatch(str(manifest["skill_id"])):
        raise ValueError("invalid skill_id")
    if manifest["api_version"] != SKILL_API_VERSION:
        raise ValueError("unsupported api_version: " + str(manifest["api_version"]))
    entrypoint = Path(str(manifest["entrypoint"]))
    if entrypoint.is_absolute() or ".." in entrypoint.parts:
        raise ValueError("entrypoint must stay inside the package")
    permissions = manifest.get("permissions", [])
    if not isinstance(permissions, list) or any(not isinstance(item, str) for item in permissions):
        raise ValueError("permissions must be a string array")
    dependencies = manifest.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise ValueError("dependencies must be an array")
    manifest["skill_id"] = str(manifest["skill_id"])
    manifest["entrypoint"] = entrypoint.as_posix()
    manifest["dependencies"] = dependencies
    return manifest


def safe_extract(archive: Path, target: Path):
    if archive.stat().st_size > MAX_ZIP_BYTES:
        raise ValueError("skill archive is too large")
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename.replace(chr(92), "/")
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or name.startswith("/"):
                raise ValueError("unsafe path in skill archive")
            if info.file_size > MAX_FILE_BYTES:
                raise ValueError("file in skill archive is too large")
        zf.extractall(target)


def read_package(package_dir: Path):
    manifest_file = package_dir / "manifest.json"
    if not manifest_file.is_file() or not (package_dir / "README.md").is_file():
        raise ValueError("package root must contain manifest.json and README.md")
    try:
        manifest = validate_manifest(json.loads(manifest_file.read_text(encoding="utf-8")))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("invalid manifest.json: " + str(exc)) from exc
    entry = package_dir / manifest["entrypoint"]
    if not entry.is_file():
        raise ValueError("manifest entrypoint does not exist")
    for schema_name in ("input.schema.json", "output.schema.json"):
        schema_path = package_dir / schema_name
        if schema_path.exists():
            json.loads(schema_path.read_text(encoding="utf-8"))
    return manifest, entry


def run_process(package_dir: Path, manifest: dict, payload: dict, timeout=None):
    entry = package_dir / manifest["entrypoint"]
    env_dir = package_dir / ".venv"
    python = python_for_env(env_dir) if env_dir.exists() else sys.executable
    started = time.perf_counter()
    try:
        result = subprocess.run(
            [python, str(entry)], cwd=str(package_dir),
            input=json.dumps(payload, ensure_ascii=False), capture_output=True,
            text=True, timeout=timeout or settings.SKILL_RUN_TIMEOUT_SECONDS,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except subprocess.TimeoutExpired as exc:
        return {"status": "timeout", "duration_ms": int((time.perf_counter()-started)*1000),
                "error_message": "skill execution timed out", "stderr": str(exc.stderr or "")[-4000:]}
    duration_ms = int((time.perf_counter() - started) * 1000)
    stderr = (result.stderr or "")[-4000:]
    if result.returncode:
        return {"status": "failed", "duration_ms": duration_ms,
                "error_message": "skill exited with code " + str(result.returncode), "stderr": stderr}
    try:
        output = json.loads(result.stdout.strip())
    except Exception as exc:
        return {"status": "invalid_output", "duration_ms": duration_ms,
                "error_message": "skill returned invalid JSON: " + str(exc), "stderr": stderr}
    if not isinstance(output, dict) or output.get("protocol") != SKILL_API_VERSION or output.get("status") not in ("ok", "error"):
        return {"status": "schema_error", "duration_ms": duration_ms,
                "error_message": "skill output does not match x2stock.skill.v1 envelope",
                "output": output, "stderr": stderr}
    return {"status": output["status"], "duration_ms": duration_ms, "output": output, "stderr": stderr}


def install_zip(archive_path: str):
    root = skills_root()
    staging = root / (".staging-" + uuid.uuid4().hex)
    staging.mkdir(parents=True, exist_ok=False)
    try:
        safe_extract(Path(archive_path), staging)
        manifest, _ = read_package(staging)
        env_dir = staging / ".venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        requirements = staging / "requirements.lock"
        if not requirements.is_file():
            requirements = staging / "requirements.txt"
        if requirements.is_file():
            result = subprocess.run(
                [python_for_env(env_dir), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],
                cwd=str(staging), capture_output=True, text=True,
                timeout=settings.SKILL_INSTALL_TIMEOUT_SECONDS,
            )
            if result.returncode:
                raise RuntimeError("dependency installation failed: " + result.stderr[-2000:])
        smoke = run_process(staging, manifest,
                            {"protocol": SKILL_API_VERSION, "params": {}, "data": {}, "meta": {}}, timeout=20)
        if smoke["status"] not in ("ok", "error"):
            raise RuntimeError(smoke.get("error_message", "skill smoke test failed"))
        final_dir = root / manifest["skill_id"] / str(manifest["version"])
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.move(str(staging), str(final_dir))
        return {"manifest": manifest, "path": str(final_dir), "entrypoint": manifest["entrypoint"]}
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def remove_skill_path(path: str):
    target = Path(path).resolve()
    root = skills_root()
    if root not in target.parents:
        raise ValueError("refusing to remove path outside skills directory")
    if target.exists():
        shutil.rmtree(target)
