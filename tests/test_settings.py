from __future__ import annotations

import re

import yaml

import core.settings as settings_module
from core.settings import AppSettings, resolve_inspection_column_order


def test_load_settings_normalizes_and_applies_fallbacks(
    monkeypatch, tmp_path
) -> None:
    raw_data = {
        "console_log_level": 123,
        "max_retries": 0,
        "timeout": -5,
        "max_workers": "bad",
        "inspection_excludes": {"Cisco": {"IOS": [" show version ", "", 123]}},
        "column_aliases": {" host name ": "Hostname"},
        "inspection_column_order_global": [" host name ", "CPU Usage", "", "Hostname"],
        "inspection_column_order_by_profile": {"Cisco|IOS": [" host name ", "CPU Usage"]},
    }
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(yaml.dump(raw_data), encoding="utf-8")
    monkeypatch.setattr(settings_module, "get_app_dir", lambda: tmp_path)

    loaded = settings_module.load_settings()

    assert loaded.console_log_level == "WARNING"
    assert loaded.max_retries == 3
    assert loaded.timeout == 10
    assert loaded.max_workers == 10
    assert loaded.inspection_excludes == {"cisco": {"ios": ["show version"]}}
    assert loaded.column_aliases["host name"] == "Hostname"
    assert loaded.column_aliases["hostname"] == "Hostname"
    assert loaded.inspection_column_order_global == ["Hostname", "CPU Usage"]
    assert loaded.inspection_column_order_by_profile == {
        "cisco|ios": ["Hostname", "CPU Usage"]
    }


def test_resolve_inspection_column_order_prefers_global_profile_then_remaining() -> None:
    settings = AppSettings(
        column_aliases={
            "host name": "Hostname",
            "cpu usage": "CPU Usage",
        },
        inspection_column_order_global=["Version", "Hostname"],
        inspection_column_order_by_profile={"cisco|ios": ["CPU Usage"]},
    )
    available = [" host name ", "CPU Usage", "Version", "Model"]
    profiles = ["Cisco|IOS", "cisco|ios", "dayou|dsw"]

    resolved = resolve_inspection_column_order(available, profiles, settings)
    assert resolved == ["Version", "Hostname", "CPU Usage", "Model"]


def test_save_settings_writes_normalized_values(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings_module, "get_app_dir", lambda: tmp_path)
    settings = AppSettings(
        console_log_level="info",
        inspection_excludes={"Cisco": {"IOS": [" show run "]}},
        max_retries=0,
        timeout=-1,
        max_workers=0,
        column_aliases={" host name ": "Hostname"},
        inspection_column_order_global=[" host name ", "Hostname", "Version"],
        inspection_column_order_by_profile={"Cisco|IOS": [" host name ", "Version"]},
    )

    settings_module.save_settings(settings)
    loaded = settings_module.load_settings()

    assert loaded.console_log_level == "INFO"
    assert loaded.max_retries == 3
    assert loaded.timeout == 10
    assert loaded.max_workers == 10
    assert loaded.inspection_excludes == {"cisco": {"ios": ["show run"]}}
    assert loaded.inspection_column_order_global == ["Hostname", "Version"]
    assert loaded.inspection_column_order_by_profile == {
        "cisco|ios": ["Hostname", "Version"]
    }
    raw_text = (tmp_path / "settings.yaml").read_text(encoding="utf-8")
    assert re.search(r"console_log_level:\s+INFO", raw_text)
