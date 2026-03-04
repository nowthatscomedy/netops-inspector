from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from zipfile import BadZipFile

import pandas as pd

from core.cli_input import get_filepath_from_cli
from core.file_handler import read_excel_file, save_results_to_excel
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
from core.settings import AppSettings
from core.ui import get_password_from_cli
from core.validator import validate_dataframe

logger = logging.getLogger(__name__)

LEGACY_INVENTORY_PLUGIN = "excel_cli"
LEGACY_TASK_PLUGIN = "legacy_network_task"
LEGACY_OUTPUT_PLUGIN = "excel_results"


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
    name = LEGACY_INVENTORY_PLUGIN

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
        except (BadZipFile, Exception):
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
        filepath = self._filepath_provider()
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


def build_legacy_plugin_runtime() -> PluginRuntime:
    registry = PluginRegistry()
    registry.register_inventory(ExcelCliInventoryPlugin())
    registry.register_task(LegacyNetworkTaskPlugin())
    registry.register_output(ExcelResultOutputPlugin())
    return PluginRuntime(registry)
