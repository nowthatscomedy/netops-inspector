from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

import main
from core.plugin_platform import (
    CSV_INVENTORY_PLUGIN,
    EXCEL_INVENTORY_PLUGIN,
    JSON_INVENTORY_PLUGIN,
)
from core.settings import AppSettings


def test_read_excel_with_retry_returns_dataframe_without_password(monkeypatch) -> None:
    expected = pd.DataFrame([{"ip": "192.0.2.10"}])
    monkeypatch.setattr(main, "read_excel_file", lambda filepath, password=None: expected)

    result = main._read_excel_with_retry("devices.xlsx")
    pd.testing.assert_frame_equal(result, expected)


def test_read_excel_with_retry_uses_password_on_second_try(monkeypatch) -> None:
    expected = pd.DataFrame([{"ip": "192.0.2.11"}])
    call_count = {"count": 0}

    def fake_read(filepath: str, password: str | None = None):
        call_count["count"] += 1
        if password is None:
            raise ValueError("encrypted workbook")
        assert password == "secret"
        return expected

    monkeypatch.setattr(main, "read_excel_file", fake_read)
    monkeypatch.setattr(main, "get_password_from_cli", lambda: "secret")

    result = main._read_excel_with_retry("devices.xlsx")
    pd.testing.assert_frame_equal(result, expected)
    assert call_count["count"] == 2


def test_read_excel_with_retry_returns_none_when_password_not_entered(monkeypatch) -> None:
    monkeypatch.setattr(main, "read_excel_file", lambda filepath, password=None: (_ for _ in ()).throw(ValueError("encrypted workbook")))
    monkeypatch.setattr(main, "get_password_from_cli", lambda: None)

    result = main._read_excel_with_retry("devices.xlsx")
    assert result is None


def test_create_inspector_applies_settings_fields() -> None:
    settings = AppSettings(
        inspection_excludes={"cisco": {"ios": ["show version"]}},
        max_retries=5,
        timeout=15,
        max_workers=4,
        column_aliases={"host name": "Hostname"},
    )

    inspector = main._create_inspector(
        output_excel="inspection_results.xlsx",
        run_timestamp="20260101_120000",
        settings=settings,
        inspection_only=True,
    )

    assert inspector.inspection_only is True
    assert inspector.backup_only is False
    assert inspector.max_retries == 5
    assert inspector.timeout == 15
    assert inspector.max_workers == 4
    assert inspector.inspection_excludes == {"cisco": {"ios": ["show version"]}}
    assert inspector.column_aliases["host name"] == "Hostname"
    assert inspector.output_excel.endswith("inspection_results_20260101_120000.xlsx")


def test_init_run_returns_timestamp_and_logfile(monkeypatch) -> None:
    monkeypatch.setattr(main, "init_logging", lambda **kwargs: "logs/test.log")
    settings = AppSettings(console_log_level="INFO")

    run_timestamp, log_file = main._init_run(settings)
    assert re.fullmatch(r"\d{8}_\d{6}", run_timestamp) is not None
    assert log_file == "logs/test.log"


@pytest.mark.parametrize(
    ("filepath", "plugin_name"),
    [
        ("devices.xlsx", EXCEL_INVENTORY_PLUGIN),
        ("devices.xls", EXCEL_INVENTORY_PLUGIN),
        ("devices.xlsm", EXCEL_INVENTORY_PLUGIN),
        ("devices.csv", CSV_INVENTORY_PLUGIN),
        ("devices.json", JSON_INVENTORY_PLUGIN),
    ],
)
def test_inventory_plugin_for_filepath(filepath: str, plugin_name: str) -> None:
    assert main._inventory_plugin_for_filepath(filepath) == plugin_name


def test_inventory_plugin_for_filepath_raises_on_unsupported_extension() -> None:
    with pytest.raises(main.InventoryLoadError):
        main._inventory_plugin_for_filepath(str(Path("devices.txt")))
