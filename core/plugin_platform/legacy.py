from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from core.cli_input import get_filepath_from_cli
from core.file_handler import (
    is_likely_encrypted_excel_error,
    read_excel_file,
    save_results_to_excel,
)
from core.i18n import t
from core.inspector import NetworkInspector
from core.plugin_platform.contracts import (
    InventoryLoadError,
    InventoryPayload,
    OutputRequest,
    OutputWriteError,
    TaskExecutionError,
    TaskRequest,
    TaskResult,
)
from core.plugin_platform.registry import PluginRegistry
from core.plugin_platform.runtime import PluginRuntime
from core.settings import AppSettings, canonicalize_column_name
from core.ui import get_password_from_cli
from core.validator import validate_dataframe

logger = logging.getLogger(__name__)

EXCEL_INVENTORY_PLUGIN = "excel_cli"
CSV_INVENTORY_PLUGIN = "csv_cli"
JSON_INVENTORY_PLUGIN = "json_cli"
LEGACY_INVENTORY_PLUGIN = EXCEL_INVENTORY_PLUGIN
LEGACY_TASK_PLUGIN = "legacy_network_task"
LEGACY_OUTPUT_PLUGIN = "excel_results"
JSON_OUTPUT_PLUGIN = "json_results"
CSV_OUTPUT_PLUGIN = "csv_results"


def _default_inspector_factory(
    output_excel: str,
    run_timestamp: str,
    settings: AppSettings,
    *,
    inspection_only: bool = False,
    backup_only: bool = False,
    status_callback: Callable[[dict[str, object]], None] | None = None,
) -> NetworkInspector:
    return NetworkInspector(
        output_excel,
        inspection_only=inspection_only,
        backup_only=backup_only,
        run_timestamp=run_timestamp,
        inspection_excludes=settings.inspection_excludes,
        max_retries=settings.max_retries,
        timeout=settings.timeout,
        max_workers=settings.max_workers,
        column_aliases=settings.column_aliases,
        status_callback=status_callback,
    )


class ExcelCliInventoryPlugin:
    name = EXCEL_INVENTORY_PLUGIN

    def __init__(
        self,
        *,
        filepath_provider: Callable[[], str | None] = get_filepath_from_cli,
        password_provider: Callable[[], str | None] = get_password_from_cli,
        excel_reader: Callable[..., pd.DataFrame] = read_excel_file,
        dataframe_validator: Callable[[pd.DataFrame, dict[str, str] | None], pd.DataFrame]
        = validate_dataframe,
    ) -> None:
        self._filepath_provider = filepath_provider
        self._password_provider = password_provider
        self._excel_reader = excel_reader
        self._dataframe_validator = dataframe_validator

    def _read_excel_with_retry(self, filepath: str) -> pd.DataFrame | None:
        try:
            return self._excel_reader(filepath)
        except Exception as exc:
            if not is_likely_encrypted_excel_error(exc):
                logger.error(
                    t("file_handler.error.excel_read_failed", filepath=filepath, error=exc),
                )
                return None
            password = self._password_provider()
            if not password:
                logger.warning(t("main.warning.password_not_entered"))
                return None
            try:
                return self._excel_reader(filepath, password=password)
            except Exception as exc:
                logger.error(t("main.warning.encrypted_excel_read_failed", error=exc))
                return None

    def load(
        self,
        *,
        settings: AppSettings,
        options: dict[str, Any] | None = None,
    ) -> InventoryPayload:
        filepath = str((options or {}).get("filepath", "")).strip() or self._filepath_provider()
        if not filepath:
            raise InventoryLoadError(t("main.warning.input_path_missing"))

        devices_df = self._read_excel_with_retry(filepath)
        if devices_df is None:
            raise InventoryLoadError(t("main.warning.encrypted_excel_read_failed", error="n/a"))

        devices_df = self._dataframe_validator(devices_df, settings.input_column_aliases)
        devices = devices_df.to_dict("records")
        return InventoryPayload(
            source=self.name,
            filepath=filepath,
            devices=devices,
            metadata={"device_count": len(devices)},
        )


class CsvCliInventoryPlugin:
    name = CSV_INVENTORY_PLUGIN

    def __init__(
        self,
        *,
        filepath_provider: Callable[[], str | None] = get_filepath_from_cli,
        csv_reader: Callable[[str], pd.DataFrame] = pd.read_csv,
        dataframe_validator: Callable[[pd.DataFrame, dict[str, str] | None], pd.DataFrame]
        = validate_dataframe,
    ) -> None:
        self._filepath_provider = filepath_provider
        self._csv_reader = csv_reader
        self._dataframe_validator = dataframe_validator

    def load(
        self,
        *,
        settings: AppSettings,
        options: dict[str, Any] | None = None,
    ) -> InventoryPayload:
        filepath = str((options or {}).get("filepath", "")).strip() or self._filepath_provider()
        if not filepath:
            raise InventoryLoadError(t("main.warning.input_path_missing"))

        try:
            devices_df = self._csv_reader(filepath)
        except Exception as exc:
            raise InventoryLoadError(str(exc)) from exc

        devices_df = self._dataframe_validator(devices_df, settings.input_column_aliases)
        devices = devices_df.to_dict("records")
        return InventoryPayload(
            source=self.name,
            filepath=filepath,
            devices=devices,
            metadata={"device_count": len(devices)},
        )


class JsonCliInventoryPlugin:
    name = JSON_INVENTORY_PLUGIN

    def __init__(
        self,
        *,
        filepath_provider: Callable[[], str | None] = get_filepath_from_cli,
        json_loader: Callable[[str], Any] | None = None,
        dataframe_validator: Callable[[pd.DataFrame, dict[str, str] | None], pd.DataFrame]
        = validate_dataframe,
    ) -> None:
        self._filepath_provider = filepath_provider
        self._json_loader = json_loader
        self._dataframe_validator = dataframe_validator

    def _load_json_data(self, filepath: str) -> Any:
        if self._json_loader is not None:
            return self._json_loader(filepath)
        raw = Path(filepath).read_text(encoding="utf-8")
        return json.loads(raw)

    def load(
        self,
        *,
        settings: AppSettings,
        options: dict[str, Any] | None = None,
    ) -> InventoryPayload:
        filepath = str((options or {}).get("filepath", "")).strip() or self._filepath_provider()
        if not filepath:
            raise InventoryLoadError(t("main.warning.input_path_missing"))

        try:
            payload = self._load_json_data(filepath)
        except Exception as exc:
            raise InventoryLoadError(str(exc)) from exc

        if isinstance(payload, dict):
            records = payload.get("devices")
        else:
            records = payload

        if not isinstance(records, list):
            raise InventoryLoadError(
                "JSON inventory must be a list of device objects or an object with 'devices'.",
            )

        devices_df = pd.DataFrame(records)
        devices_df = self._dataframe_validator(devices_df, settings.input_column_aliases)
        devices = devices_df.to_dict("records")
        return InventoryPayload(
            source=self.name,
            filepath=filepath,
            devices=devices,
            metadata={"device_count": len(devices)},
        )


class LegacyNetworkTaskPlugin:
    name = LEGACY_TASK_PLUGIN

    def __init__(
        self,
        *,
        inspector_factory: Callable[..., NetworkInspector] = _default_inspector_factory,
    ) -> None:
        self._inspector_factory = inspector_factory

    def _build_inspector(
        self,
        request: TaskRequest,
        *,
        output_excel: str,
        inspection_only: bool = False,
        backup_only: bool = False,
    ) -> NetworkInspector:
        inspector = self._inspector_factory(
            output_excel,
            request.run_timestamp,
            request.settings,
            inspection_only=inspection_only,
            backup_only=backup_only,
            status_callback=request.status_callback,
        )
        inspector.load_devices(request.devices)
        return inspector

    def run(self, request: TaskRequest) -> TaskResult:
        task_kind = str(request.options.get("task_kind", "")).strip().lower()
        if task_kind == "custom_commands":
            commands = request.options.get("commands")
            if not isinstance(commands, list) or not commands:
                raise TaskExecutionError(t("main.warning.command_list_empty"))
            output_excel = str(request.options.get("output_excel", "command_results.xlsx"))
            inspector = self._build_inspector(
                request,
                output_excel=output_excel,
                inspection_only=True,
            )
            inspector.run_custom_commands(commands)
            return TaskResult(
                task_name=request.task_name,
                output_excel=inspector.output_excel,
                results=inspector.results,
                backup_dir=inspector.backup_dir,
                session_log_dir=inspector.session_log_dir,
                inspection_only=True,
            )

        if task_kind == "inspection_backup":
            action_choice = str(request.options.get("action_choice", "1"))
            output_excel = str(request.options.get("output_excel", "inspection_results.xlsx"))
            inspection_only = action_choice == "1"
            backup_only = action_choice == "2"
            inspector = self._build_inspector(
                request,
                output_excel=output_excel,
                inspection_only=inspection_only,
                backup_only=backup_only,
            )

            available_columns: list[str] = []
            profile_keys: list[str] = []
            if action_choice in ("1", "3"):
                available_columns = inspector.get_available_inspection_columns(inspector.devices)
                if available_columns:
                    profile_keys = inspector.get_device_profile_keys(inspector.devices)

            if action_choice == "1":
                inspector.inspect_devices(backup_only=False)
            elif action_choice == "2":
                inspector.inspect_devices(backup_only=True)
            elif action_choice == "3":
                inspector.inspect_and_backup_devices()
            else:
                raise TaskExecutionError(f"Unsupported action choice: {action_choice}")

            return TaskResult(
                task_name=request.task_name,
                output_excel=inspector.output_excel,
                results=inspector.results,
                backup_dir=inspector.backup_dir,
                session_log_dir=inspector.session_log_dir,
                inspection_only=inspection_only,
                metadata={
                    "available_columns": available_columns,
                    "profile_keys": profile_keys,
                },
            )

        if task_kind == "preflight":
            output_excel = str(request.options.get("output_excel", "preflight_results.xlsx"))
            inspector = self._build_inspector(
                request,
                output_excel=output_excel,
                inspection_only=True,
            )
            inspector.preflight_devices()
            return TaskResult(
                task_name=request.task_name,
                output_excel=inspector.output_excel,
                results=inspector.results,
                backup_dir=inspector.backup_dir,
                session_log_dir=inspector.session_log_dir,
                inspection_only=True,
            )

        raise TaskExecutionError(f"Unsupported task kind: {task_kind}")


class ExcelResultOutputPlugin:
    name = LEGACY_OUTPUT_PLUGIN

    def write(self, request: OutputRequest) -> None:
        if not request.task_result.results:
            return
        try:
            save_results_to_excel(
                request.task_result.results,
                request.task_result.output_excel,
                column_order=request.column_order,
                column_aliases=request.settings.column_aliases,
            )
        except Exception as exc:
            raise OutputWriteError(str(exc)) from exc


def _flatten_result_rows(
    results: list[dict[str, Any]],
    aliases: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    normalized_aliases = dict(aliases or {})
    rows: list[dict[str, Any]] = []
    for item in results:
        row: dict[str, Any] = {
            "ip": item.get("ip"),
            "vendor": item.get("vendor"),
            "os": item.get("os"),
            "status": item.get("status"),
            "error_message": item.get("error_message", ""),
        }
        inspection_results = item.get("inspection_results")
        if isinstance(inspection_results, dict):
            for key, value in inspection_results.items():
                if key.startswith("error_") or key in {"error", "backup_error", "backup_file"}:
                    continue
                canonical_key = canonicalize_column_name(key, normalized_aliases)
                if not canonical_key:
                    continue
                if canonical_key in row and row[canonical_key] not in (None, "") and value not in (None, ""):
                    if str(row[canonical_key]) != str(value):
                        row[canonical_key] = f"{row[canonical_key]}, {value}"
                else:
                    row[canonical_key] = value

        backup_file = item.get("backup_file")
        if backup_file:
            row["backup_file"] = backup_file
        rows.append(row)
    return rows


def _derive_output_filepath(source_path: str, extension: str) -> str:
    source = Path(source_path)
    if source.suffix.lower() == extension.lower():
        output = source
    else:
        output = source.with_suffix(extension)
    output.parent.mkdir(parents=True, exist_ok=True)
    return str(output)


class JsonResultOutputPlugin:
    name = JSON_OUTPUT_PLUGIN

    def write(self, request: OutputRequest) -> None:
        if not request.task_result.results:
            return
        try:
            output_path = _derive_output_filepath(request.task_result.output_excel, ".json")
            rows = _flatten_result_rows(
                request.task_result.results,
                aliases=request.settings.column_aliases,
            )
            Path(output_path).write_text(
                json.dumps(rows, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            request.task_result.output_excel = output_path
        except Exception as exc:
            raise OutputWriteError(str(exc)) from exc


class CsvResultOutputPlugin:
    name = CSV_OUTPUT_PLUGIN

    def write(self, request: OutputRequest) -> None:
        if not request.task_result.results:
            return
        try:
            output_path = _derive_output_filepath(request.task_result.output_excel, ".csv")
            rows = _flatten_result_rows(
                request.task_result.results,
                aliases=request.settings.column_aliases,
            )
            pd.DataFrame(rows).to_csv(output_path, index=False, encoding="utf-8-sig")
            request.task_result.output_excel = output_path
        except Exception as exc:
            raise OutputWriteError(str(exc)) from exc


def build_legacy_plugin_runtime() -> PluginRuntime:
    registry = PluginRegistry()
    registry.register_inventory(ExcelCliInventoryPlugin())
    registry.register_inventory(CsvCliInventoryPlugin())
    registry.register_inventory(JsonCliInventoryPlugin())
    registry.register_task(LegacyNetworkTaskPlugin())
    registry.register_output(ExcelResultOutputPlugin())
    registry.register_output(JsonResultOutputPlugin())
    registry.register_output(CsvResultOutputPlugin())
    return PluginRuntime(registry)
