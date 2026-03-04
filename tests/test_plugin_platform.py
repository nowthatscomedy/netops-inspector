from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import pytest

from core.plugin_platform.contracts import (
    InventoryLoadError,
    OutputRequest,
    TaskRequest,
    TaskResult,
)
from core.plugin_platform.legacy import (
    CSV_INVENTORY_PLUGIN,
    JSON_INVENTORY_PLUGIN,
    CsvCliInventoryPlugin,
    ExcelCliInventoryPlugin,
    ExcelResultOutputPlugin,
    JsonCliInventoryPlugin,
    LegacyNetworkTaskPlugin,
    build_legacy_plugin_runtime,
)
from core.plugin_platform.registry import PluginRegistry
from core.settings import AppSettings


def test_registry_rejects_duplicate_plugin_names() -> None:
    registry = PluginRegistry()

    class DummyInventory:
        name = "dummy"

        def load(self, *, settings: AppSettings, options: dict | None = None) -> Any:
            return None

    registry.register_inventory(DummyInventory())
    with pytest.raises(ValueError):
        registry.register_inventory(DummyInventory())


def test_excel_cli_inventory_plugin_loads_and_validates() -> None:
    df = pd.DataFrame(
        [
            {
                "ip": "192.0.2.10",
                "vendor": "cisco",
                "os": "ios",
                "connection_type": "ssh",
                "port": 22,
                "password": "pw",
            }
        ]
    )
    plugin = ExcelCliInventoryPlugin(
        filepath_provider=lambda: "devices.xlsx",
        password_provider=lambda: None,
        excel_reader=lambda *args, **kwargs: df,
        dataframe_validator=lambda frame, _: frame,
    )
    payload = plugin.load(settings=AppSettings())
    assert payload.filepath == "devices.xlsx"
    assert payload.metadata["device_count"] == 1
    assert payload.devices[0]["ip"] == "192.0.2.10"


def test_excel_cli_inventory_plugin_raises_when_filepath_missing() -> None:
    plugin = ExcelCliInventoryPlugin(
        filepath_provider=lambda: None,
        password_provider=lambda: None,
        excel_reader=lambda *args, **kwargs: pd.DataFrame(),
        dataframe_validator=lambda frame, _: frame,
    )
    with pytest.raises(InventoryLoadError):
        plugin.load(settings=AppSettings())


def test_csv_cli_inventory_plugin_loads_from_filepath_option(tmp_path) -> None:
    csv_path = tmp_path / "devices.csv"
    csv_path.write_text(
        "ip,vendor,os,connection_type,port,password\n"
        "192.0.2.20,cisco,ios,ssh,22,pw\n",
        encoding="utf-8",
    )
    plugin = CsvCliInventoryPlugin(
        filepath_provider=lambda: None,
        dataframe_validator=lambda frame, _: frame,
    )
    payload = plugin.load(
        settings=AppSettings(),
        options={"filepath": str(csv_path)},
    )
    assert payload.filepath == str(csv_path)
    assert payload.devices[0]["ip"] == "192.0.2.20"


def test_json_cli_inventory_plugin_loads_list_from_filepath_option(tmp_path) -> None:
    json_path = tmp_path / "devices.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "ip": "192.0.2.30",
                    "vendor": "cisco",
                    "os": "ios",
                    "connection_type": "ssh",
                    "port": 22,
                    "password": "pw",
                }
            ]
        ),
        encoding="utf-8",
    )
    plugin = JsonCliInventoryPlugin(
        filepath_provider=lambda: None,
        dataframe_validator=lambda frame, _: frame,
    )
    payload = plugin.load(
        settings=AppSettings(),
        options={"filepath": str(json_path)},
    )
    assert payload.filepath == str(json_path)
    assert payload.devices[0]["ip"] == "192.0.2.30"


def test_json_cli_inventory_plugin_loads_dict_with_devices_key(tmp_path) -> None:
    json_path = tmp_path / "devices.json"
    json_path.write_text(
        json.dumps(
            {
                "devices": [
                    {
                        "ip": "192.0.2.31",
                        "vendor": "cisco",
                        "os": "ios",
                        "connection_type": "ssh",
                        "port": 22,
                        "password": "pw",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    plugin = JsonCliInventoryPlugin(
        filepath_provider=lambda: None,
        dataframe_validator=lambda frame, _: frame,
    )
    payload = plugin.load(
        settings=AppSettings(),
        options={"filepath": str(json_path)},
    )
    assert payload.devices[0]["ip"] == "192.0.2.31"


def test_runtime_registers_csv_and_json_inventory_plugins(tmp_path) -> None:
    runtime = build_legacy_plugin_runtime()
    csv_path = tmp_path / "devices.csv"
    csv_path.write_text(
        "ip,vendor,os,connection_type,port,password\n"
        "192.0.2.50,cisco,ios,ssh,22,pw\n",
        encoding="utf-8",
    )
    json_path = tmp_path / "devices.json"
    json_path.write_text(
        json.dumps(
            [
                {
                    "ip": "192.0.2.51",
                    "vendor": "cisco",
                    "os": "ios",
                    "connection_type": "ssh",
                    "port": 22,
                    "password": "pw",
                }
            ]
        ),
        encoding="utf-8",
    )

    csv_payload = runtime.load_inventory(
        CSV_INVENTORY_PLUGIN,
        settings=AppSettings(),
        options={"filepath": str(csv_path)},
    )
    json_payload = runtime.load_inventory(
        JSON_INVENTORY_PLUGIN,
        settings=AppSettings(),
        options={"filepath": str(json_path)},
    )
    assert csv_payload.devices[0]["ip"] == "192.0.2.50"
    assert json_payload.devices[0]["ip"] == "192.0.2.51"


@dataclass
class _FakeInspector:
    output_excel: str
    inspection_only: bool = False
    backup_only: bool = False
    results: list[dict[str, Any]] = field(default_factory=list)
    backup_dir: str = "backup/test"
    session_log_dir: str = "session_logs/test"
    devices: list[dict[str, Any]] = field(default_factory=list)

    def load_devices(self, devices: list[dict[str, Any]]) -> None:
        self.devices = devices

    def run_custom_commands(self, commands: list[str]) -> None:
        self.results = [{"ip": "192.0.2.10", "status": "success", "commands": commands}]

    def inspect_devices(self, backup_only: bool = False) -> None:
        self.results = [
            {
                "ip": "192.0.2.10",
                "status": "success",
                "backup_only": backup_only,
                "inspection_results": {"version": "1.0"},
            }
        ]

    def inspect_and_backup_devices(self) -> None:
        self.results = [
            {
                "ip": "192.0.2.10",
                "status": "success",
                "inspection_results": {"version": "1.0"},
                "backup_file": "backup/test/192.0.2.10.txt",
            }
        ]

    def get_available_inspection_columns(self, devices: list[dict[str, Any]]) -> list[str]:
        return ["Version", "Hostname"]

    def get_device_profile_keys(self, devices: list[dict[str, Any]]) -> list[str]:
        return ["cisco|ios"]


def test_legacy_task_plugin_runs_inspection_and_returns_metadata() -> None:
    def inspector_factory(
        output_excel: str,
        run_timestamp: str,
        settings: AppSettings,
        *,
        inspection_only: bool = False,
        backup_only: bool = False,
        status_callback: Any = None,
    ) -> _FakeInspector:
        return _FakeInspector(
            output_excel=output_excel,
            inspection_only=inspection_only,
            backup_only=backup_only,
        )

    plugin = LegacyNetworkTaskPlugin(inspector_factory=inspector_factory)
    request = TaskRequest(
        task_name="inspection_backup",
        run_timestamp="20260305_120000",
        settings=AppSettings(),
        devices=[{"ip": "192.0.2.10"}],
        options={"task_kind": "inspection_backup", "action_choice": "3"},
    )
    result = plugin.run(request)
    assert result.results
    assert result.metadata["available_columns"] == ["Version", "Hostname"]
    assert result.metadata["profile_keys"] == ["cisco|ios"]


def test_excel_output_plugin_writes_results(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_save(results, output_filepath, column_order=None, column_aliases=None) -> None:
        captured["results"] = results
        captured["output_filepath"] = output_filepath
        captured["column_order"] = column_order
        captured["column_aliases"] = column_aliases

    monkeypatch.setattr("core.plugin_platform.legacy.save_results_to_excel", fake_save)
    plugin = ExcelResultOutputPlugin()
    request = OutputRequest(
        output_name="excel_results",
        settings=AppSettings(column_aliases={"host name": "Hostname"}),
        task_result=TaskResult(
            task_name="custom_commands",
            output_excel="command_results_20260305_120000.xlsx",
            results=[{"ip": "192.0.2.10", "status": "success"}],
        ),
    )
    plugin.write(request)
    assert captured["results"]
    assert captured["output_filepath"].endswith(".xlsx")
