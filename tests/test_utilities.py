from __future__ import annotations

import logging
from pathlib import Path

import core.path_utils as path_utils_module
from core.cli_input import _validate_extension
from core.logging_config import init_logging
from core.path_utils import get_app_dir


def test_validate_extension_checks_suffix_case_insensitive() -> None:
    assert _validate_extension("device.xlsx", (".xlsx", ".xls")) is True
    assert _validate_extension("device.XLSX", (".xlsx", ".xls")) is True
    assert _validate_extension("device.txt", (".xlsx", ".xls")) is False


def test_get_app_dir_returns_project_root_when_not_frozen() -> None:
    app_dir = get_app_dir()
    assert app_dir.name.startswith("network-device-inspection")


def test_get_app_dir_returns_executable_parent_when_frozen(monkeypatch) -> None:
    fake_executable = Path("C:/temp/app/NetOpsInspector.exe")
    monkeypatch.setattr(path_utils_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(path_utils_module.sys, "executable", str(fake_executable), raising=False)
    assert path_utils_module.get_app_dir() == fake_executable.parent


def test_init_logging_creates_log_file_and_handlers(tmp_path) -> None:
    log_file = init_logging(
        run_timestamp="20260101_101010",
        log_dir=str(tmp_path),
        enable_console=False,
        file_level=logging.INFO,
        console_level=logging.ERROR,
        enable_color=False,
    )
    assert Path(log_file).exists()
    logging.getLogger(__name__).info("test log message")
    assert "netops_inspector_20260101_101010.log" in log_file

