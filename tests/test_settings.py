from __future__ import annotations

import re

import yaml

import core.settings as settings_module
from core.settings import (
    AppSettings,
    canonicalize_input_column_name,
    resolve_inspection_column_order,
)


def test_load_settings_normalizes_and_applies_fallbacks(
    monkeypatch, tmp_path
) -> None:
    raw_data = {
        "console_log_level": 123,
        "max_retries": 0,
        "timeout": -5,
        "max_workers": "bad",
        "language": "xx",
        "fallback_language": "ko",
        "input_column_aliases": {"IP 주소": "ip", "장비사": "vendor", "bad": "unknown"},
        "inspection_excludes": {"Cisco": {"IOS": [" show version ", "", 123]}},
        "column_aliases": {" host name ": "Hostname"},
        "inspection_column_order_global": [" host name ", "CPU Usage", "", "Hostname"],
        "inspection_column_order_by_profile": {"Cisco|IOS": [" host name ", "CPU Usage"]},
        "output_plugin": "invalid_plugin",
    }
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(yaml.dump(raw_data), encoding="utf-8")
    monkeypatch.setattr(settings_module, "get_app_dir", lambda: tmp_path)

    loaded = settings_module.load_settings()

    assert loaded.console_log_level == "WARNING"
    assert loaded.max_retries == 3
    assert loaded.timeout == 10
    assert loaded.max_workers == 10
    assert loaded.language == "en"
    assert loaded.fallback_language == "ko"
    assert loaded.input_column_aliases == {"ip 주소": "ip", "장비사": "vendor"}
    assert loaded.inspection_excludes == {"cisco": {"ios": ["show version"]}}
    assert loaded.column_aliases["host name"] == "Hostname"
    assert loaded.column_aliases["hostname"] == "Hostname"
    assert loaded.inspection_column_order_global == ["Hostname", "CPU Usage"]
    assert loaded.inspection_column_order_by_profile == {
        "cisco|ios": ["Hostname", "CPU Usage"]
    }
    assert loaded.output_plugin == "excel_results"


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
        language="pt_br",
        fallback_language="ja",
        input_column_aliases={"connection type": "connection_type"},
        column_aliases={" host name ": "Hostname"},
        inspection_column_order_global=[" host name ", "Hostname", "Version"],
        inspection_column_order_by_profile={"Cisco|IOS": [" host name ", "Version"]},
        output_plugin="csv_results",
    )

    settings_module.save_settings(settings)
    loaded = settings_module.load_settings()

    assert loaded.console_log_level == "INFO"
    assert loaded.max_retries == 3
    assert loaded.timeout == 10
    assert loaded.max_workers == 10
    assert loaded.language == "pt-BR"
    assert loaded.fallback_language == "ja"
    assert loaded.input_column_aliases == {"connection type": "connection_type"}
    assert loaded.inspection_excludes == {"cisco": {"ios": ["show run"]}}
    assert loaded.inspection_column_order_global == ["Hostname", "Version"]
    assert loaded.inspection_column_order_by_profile == {
        "cisco|ios": ["Hostname", "Version"]
    }
    assert loaded.output_plugin == "csv_results"
    raw_text = (tmp_path / "settings.yaml").read_text(encoding="utf-8")
    assert re.search(r"console_log_level:\s+INFO", raw_text)


def test_canonicalize_input_column_name_uses_default_and_custom_aliases() -> None:
    assert canonicalize_input_column_name("IP Address") == "ip"
    assert canonicalize_input_column_name("connection_type") == "connection_type"
    assert canonicalize_input_column_name(
        "장비사",
        {"장비사": "vendor"},
    ) == "vendor"
