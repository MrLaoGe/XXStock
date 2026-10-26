import importlib.util
import zipfile
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.skill_runtime_v2 import (
    SKILL_API_VERSION, install_zip, read_package, run_process, safe_extract,
)

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "skill_packages" / "low_valuation_screener"


def load_example():
    spec = importlib.util.spec_from_file_location("low_valuation_example", EXAMPLE / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_request():
    return {
        "protocol": SKILL_API_VERSION,
        "params": {"top_n": 10},
        "data": {
            "daily_basic": [
                {"record_id": 1, "ts_code": "000001.SZ", "trade_date": "2026-01-01", "pe_ttm": 5, "pb": 1, "source": "test"},
                {"record_id": 2, "ts_code": "000002.SZ", "trade_date": "2026-01-01", "pe_ttm": 10, "pb": 2, "source": "test"},
                {"record_id": 3, "ts_code": "000003.SZ", "trade_date": "2026-01-01", "pe_ttm": None, "pb": 2, "source": "test"},
                {"record_id": 4, "ts_code": "000004.SZ", "trade_date": "2026-01-01", "pe_ttm": -1, "pb": 0, "source": "test"},
            ],
            "stocks": [
                {"ts_code": "000001.SZ", "name": "低估甲", "industry": "测试"},
                {"ts_code": "000002.SZ", "name": "低估乙", "industry": "测试"},
            ],
        },
        "meta": {"data_as_of": "2026-01-01", "sources": [{"dataset": "daily_basic", "record_ids": [1, 2, 3, 4]}], "missing": []},
    }


def package_zip(tmp_path):
    archive = tmp_path / "example.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in EXAMPLE.iterdir():
            zf.write(path, path.name)
    return archive


def test_low_valuation_results_are_stable_and_report_exclusions():
    module = load_example()
    request = sample_request()
    first = module.run(request)
    second = module.run(request)
    assert first == second
    assert [row["ts_code"] for row in first["result"]["items"]] == ["000001.SZ", "000002.SZ"]
    assert first["result"]["eligible_count"] == 2
    assert first["result"]["excluded_count"] == 2
    assert first["result"]["exclusions"]["missing_pe"] == 1
    assert first["result"]["items"][0]["source_record_id"] == 1
    assert first["provenance"][0]["dataset"] == "daily_basic"


def test_filters_and_average_tie_ordering():
    module = load_example()
    request = sample_request()
    request["params"] = {"top_n": 1, "max_pe": 6}
    result = module.run(request)
    assert [row["ts_code"] for row in result["result"]["items"]] == ["000001.SZ"]
    assert result["result"]["exclusions"]["over_max_pe"] == 1


def test_equal_factor_values_use_code_order():
    module = load_example()
    request = sample_request()
    request["data"]["daily_basic"] = request["data"]["daily_basic"][:2]
    request["data"]["daily_basic"][1]["pe_ttm"] = 5
    request["data"]["daily_basic"][1]["pb"] = 1
    result = module.run(request)
    assert [row["ts_code"] for row in result["result"]["items"]] == ["000001.SZ", "000002.SZ"]
    assert result["result"]["items"][0]["valuation_score"] == result["result"]["items"][1]["valuation_score"]


def test_admin_key_required_and_compared():
    from app.config import settings
    from app.routers.skills_api import require_admin

    settings.X2STOCK_ADMIN_KEY = "test-secret"
    require_admin("test-secret")
    with pytest.raises(HTTPException) as error:
        require_admin("wrong")
    assert error.value.status_code == 403
    settings.X2STOCK_ADMIN_KEY = ""
    with pytest.raises(HTTPException) as error:
        require_admin("anything")
    assert error.value.status_code == 503


def test_rejects_zip_traversal(tmp_path):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "bad")
    with pytest.raises(ValueError, match="unsafe path"):
        safe_extract(archive, tmp_path / "extract")


def test_install_and_run_in_separate_environment(tmp_path, monkeypatch):
    from app import skill_runtime_v2 as runtime

    monkeypatch.setattr(runtime.settings, "SKILLS_DIR", str(tmp_path / "installed"))
    monkeypatch.setattr(runtime.settings, "SKILL_INSTALL_TIMEOUT_SECONDS", 90)
    archive = package_zip(tmp_path)
    installed = install_zip(str(archive))
    package = Path(installed["path"])
    manifest, _, _, _ = read_package(package)
    assert not (package / ".venv").exists()
    result = run_process(package, manifest, sample_request())
    assert result["status"] == "ok"
    assert result["output"]["result"]["items"][0]["ts_code"] == "000001.SZ"
    assert (tmp_path / "installed" / "envs" / manifest["skill_id"] / manifest["version"]).exists()
