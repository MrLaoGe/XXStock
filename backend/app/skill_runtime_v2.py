"""Safe package handling and isolated process execution for X2Stock skills.

Skills are trusted Python programs, not OS-level sandboxes. This module isolates
their dependencies and protocol while keeping package paths under SKILLS_DIR.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import uuid
import venv
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from jsonschema import Draft202012Validator

from app.config import settings

SKILL_API_VERSION = "x2stock.skill.v1"
SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,99}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_TOTAL_UNPACKED_BYTES = 250 * 1024 * 1024
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_PERMISSIONS = {"market.daily_basic.read", "market.stocks.read"}


def skills_root() -> Path:
    root = Path(settings.SKILLS_DIR).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def package_root(skill_id: str) -> Path:
    return skills_root() / "packages" / skill_id


def environment_root(skill_id: str) -> Path:
    return skills_root() / "envs" / skill_id


def python_for_env(env_dir: Path) -> str:
    return str(env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))


def _validate_relative_path(value: str, field: str) -> str:
    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    windows = PureWindowsPath(value)
    if (not value or posix.is_absolute() or windows.is_absolute() or windows.drive
            or any(part in ("", ".", "..") for part in posix.parts)
            or any(":" in part or part.endswith((" ", ".")) for part in posix.parts)):
        raise ValueError(f"{field} must be a safe relative path")
    return posix.as_posix()


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("manifest.json must be an object")
    required = ("skill_id", "name", "version", "api_version", "entrypoint",
                "python_requires", "permissions", "input_schema", "output_schema")
    missing = [key for key in required if not manifest.get(key)]
    if missing:
        raise ValueError("manifest missing fields: " + ", ".join(missing))
    skill_id = str(manifest["skill_id"])
    version = str(manifest["version"])
    if not SKILL_ID_RE.fullmatch(skill_id):
        raise ValueError("invalid skill_id")
    if not VERSION_RE.fullmatch(version):
        raise ValueError("version must use semantic version format")
    if manifest["api_version"] != SKILL_API_VERSION:
        raise ValueError("unsupported api_version: " + str(manifest["api_version"]))
    if not isinstance(manifest["name"], str) or len(manifest["name"]) > 200:
        raise ValueError("name must be a string of at most 200 characters")
    if not isinstance(manifest["python_requires"], str):
        raise ValueError("python_requires must be a version range string")
    try:
        if Version(".".join(map(str, sys.version_info[:3]))) not in SpecifierSet(manifest["python_requires"]):
            raise ValueError("host Python version does not satisfy python_requires")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("invalid python_requires version range") from exc
    permissions = manifest["permissions"]
    if (not isinstance(permissions, list)
            or any(not isinstance(item, str) or item not in ALLOWED_PERMISSIONS for item in permissions)):
        raise ValueError("permissions contains an unsupported data capability")
    dependencies = manifest.get("dependencies", [])
    if not isinstance(dependencies, list) or any(not isinstance(item, str) for item in dependencies):
        raise ValueError("dependencies must be an array of strings")
    manifest["skill_id"] = skill_id
    manifest["version"] = version
    manifest["entrypoint"] = _validate_relative_path(str(manifest["entrypoint"]), "entrypoint")
    manifest["input_schema"] = _validate_relative_path(str(manifest["input_schema"]), "input_schema")
    manifest["output_schema"] = _validate_relative_path(str(manifest["output_schema"]), "output_schema")
    manifest["dependencies"] = dependencies
    return manifest


def safe_extract(archive: Path, target: Path):
    if archive.stat().st_size > MAX_ZIP_BYTES:
        raise ValueError("skill archive is too large")
    target = target.resolve()
    total_size = 0
    seen = set()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if not name or name.startswith("/") or PureWindowsPath(name).drive:
                raise ValueError("unsafe path in skill archive")
            pure = PurePosixPath(name)
            if any(part in ("", ".", "..") for part in pure.parts) or any(":" in part for part in pure.parts):
                raise ValueError("unsafe path in skill archive")
            normalized = pure.as_posix()
            if normalized in seen:
                raise ValueError("duplicate path in skill archive")
            seen.add(normalized)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("symbolic links are not allowed in skill archives")
            if info.file_size > MAX_FILE_BYTES:
                raise ValueError("file in skill archive is too large")
            total_size += info.file_size
            if total_size > MAX_TOTAL_UNPACKED_BYTES:
                raise ValueError("unpacked skill archive is too large")
            output = (target / Path(*pure.parts)).resolve()
            if target != output and target not in output.parents:
                raise ValueError("unsafe path in skill archive")
            if info.is_dir():
                output.mkdir(parents=True, exist_ok=True)
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as source, output.open("xb") as destination:
                shutil.copyfileobj(source, destination)


def _load_schema(package_dir: Path, relative_path: str):
    schema_path = package_dir / relative_path
    if not schema_path.is_file():
        raise ValueError(f"schema file does not exist: {relative_path}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise ValueError(f"invalid JSON Schema {relative_path}: {exc}") from exc
    if "$ref" in json.dumps(schema):
        raise ValueError("JSON Schema $ref is not supported in skill packages")
    return schema


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
    if not entry.is_file() or entry.suffix.lower() != ".py":
        raise ValueError("entrypoint must be an existing Python file")
    input_schema = _load_schema(package_dir, manifest["input_schema"])
    output_schema = _load_schema(package_dir, manifest["output_schema"])
    return manifest, entry, input_schema, output_schema


def _validate_payload(payload, schema, label):
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "root"
        raise ValueError(f"{label} schema error at {location}: {error.message}")


def _child_environment():
    names = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL")
    environment = {name: os.environ[name] for name in names if name in os.environ}
    environment.update({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"})
    return environment


def run_process(package_dir: Path, manifest: dict, payload: dict, timeout=None, env_dir=None):
    try:
        manifest, entry, input_schema, output_schema = read_package(package_dir)
        _validate_payload(payload, input_schema, "input")
    except Exception as exc:
        return {"status": "schema_error", "duration_ms": 0, "error_message": str(exc), "stderr": ""}
    env_dir = Path(env_dir) if env_dir else package_dir.parent.parent.parent / "envs" / manifest["skill_id"] / manifest["version"]
    python = python_for_env(env_dir) if Path(python_for_env(env_dir)).is_file() else sys.executable
    started = time.perf_counter()
    try:
        result = subprocess.run(
            [python, str(entry)], cwd=str(package_dir),
            input=json.dumps(payload, ensure_ascii=False), capture_output=True, text=True,
            encoding="utf-8", timeout=timeout or settings.SKILL_RUN_TIMEOUT_SECONDS,
            env=_child_environment(),
        )
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return {"status": "timeout", "duration_ms": int((time.perf_counter()-started)*1000),
                "error_message": "skill execution timed out", "stderr": stderr[-4000:]}
    duration_ms = int((time.perf_counter() - started) * 1000)
    stderr = (result.stderr or "")[-4000:]
    if result.returncode:
        return {"status": "failed", "duration_ms": duration_ms,
                "error_message": "skill exited with code " + str(result.returncode), "stderr": stderr}
    try:
        output = json.loads(result.stdout.strip())
        _validate_payload(output, output_schema, "output")
    except Exception as exc:
        return {"status": "schema_error", "duration_ms": duration_ms,
                "error_message": str(exc) if isinstance(exc, ValueError) else "skill returned invalid JSON: " + str(exc),
                "stderr": stderr}
    if output.get("protocol") != SKILL_API_VERSION or output.get("status") not in ("ok", "error"):
        return {"status": "schema_error", "duration_ms": duration_ms,
                "error_message": "skill output does not match x2stock.skill.v1 envelope",
                "output": output, "stderr": stderr}
    return {"status": output["status"], "duration_ms": duration_ms, "output": output, "stderr": stderr}


def install_zip(archive_path: str):
    root = skills_root()
    staging = root / (".staging-" + uuid.uuid4().hex)
    staging.mkdir(parents=True, exist_ok=False)
    env_dir = None
    final_dir = None
    env_created = False
    try:
        safe_extract(Path(archive_path), staging)
        manifest, _, _, _ = read_package(staging)
        final_dir = package_root(manifest["skill_id"]) / manifest["version"]
        env_dir = environment_root(manifest["skill_id"]) / manifest["version"]
        if final_dir.exists() or env_dir.exists():
            raise ValueError("this skill version is already installed")
        env_dir.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=False).create(env_dir)
        env_created = True
        requirements = staging / "requirements.lock"
        if not requirements.is_file() and (staging / "requirements.txt").is_file():
            requirements = staging / "requirements.txt"
        if requirements.is_file():
            result = subprocess.run(
                [python_for_env(env_dir), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)],
                cwd=str(staging), capture_output=True, text=True,
                timeout=settings.SKILL_INSTALL_TIMEOUT_SECONDS, env=_child_environment(),
            )
            if result.returncode:
                raise RuntimeError("dependency installation failed: " + result.stderr[-2000:])
        smoke_payload = {
            "protocol": SKILL_API_VERSION, "params": {},
            "data": {"daily_basic": [], "stocks": []}, "meta": {},
        }
        smoke = run_process(staging, manifest, smoke_payload, timeout=20, env_dir=env_dir)
        if smoke["status"] not in ("ok", "error"):
            raise RuntimeError(smoke.get("error_message", "skill smoke test failed"))
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        final_dir.parent.resolve()
        shutil.move(str(staging), str(final_dir))
        return {"manifest": manifest, "path": str(final_dir), "entrypoint": manifest["entrypoint"]}
    except Exception:
        if env_created and env_dir and env_dir.exists():
            shutil.rmtree(env_dir, ignore_errors=True)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def remove_skill_path(skill_id: str):
    if not SKILL_ID_RE.fullmatch(skill_id):
        raise ValueError("invalid skill id")
    root = skills_root()
    for target in (package_root(skill_id), environment_root(skill_id)):
        resolved = target.resolve()
        if root not in resolved.parents:
            raise ValueError("refusing to remove path outside skills directory")
        if resolved.exists():
            shutil.rmtree(resolved)
