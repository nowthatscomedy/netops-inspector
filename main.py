from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.cli_input import get_command_filepath_from_cli, get_filepath_from_cli
from core.custom_exceptions import NetworkInspectorError
from core.file_handler import (
    is_likely_encrypted_excel_error,
    read_command_file,
    read_excel_file,
)
from core.i18n import set_locale, t
from core.inspector import NetworkInspector
from core.logging_config import init_logging
from core.menu_i18n import (
    ask_yes_no,
    show_action_menu,
    show_main_menu,
    show_netmiko_device_types,
    show_settings_menu,
)
from core.plugin_platform import (
    CSV_INVENTORY_PLUGIN,
    EXCEL_INVENTORY_PLUGIN,
    JSON_INVENTORY_PLUGIN,
    CSV_OUTPUT_PLUGIN,
    JSON_OUTPUT_PLUGIN,
    LEGACY_OUTPUT_PLUGIN,
    LEGACY_TASK_PLUGIN,
    InventoryLoadError,
    OutputRequest,
    OutputWriteError,
    TaskExecutionError,
    TaskRequest,
    TaskResult,
    build_legacy_plugin_runtime,
)
from core.settings import AppSettings, load_settings, resolve_inspection_column_order
from core.tui_dashboard import TuiDashboard
from core.ui import get_password_from_cli

logger = logging.getLogger(__name__)
console = Console()
_PLUGIN_RUNTIME = build_legacy_plugin_runtime()

_SUPPORTED_OUTPUT_PLUGINS = (
    LEGACY_OUTPUT_PLUGIN,
    JSON_OUTPUT_PLUGIN,
    CSV_OUTPUT_PLUGIN,
)


def _read_excel_with_retry(filepath: str) -> pd.DataFrame | None:
    try:
        return read_excel_file(filepath)
    except Exception as exc:
        if not is_likely_encrypted_excel_error(exc):
            logger.error(
                t("file_handler.error.excel_read_failed", filepath=filepath, error=exc),
            )
            return None
        password = get_password_from_cli()
        if not password:
            logger.warning(t("main.warning.password_not_entered"))
            return None
        try:
            return read_excel_file(filepath, password=password)
        except Exception as exc:
            logger.error(t("main.warning.encrypted_excel_read_failed", error=exc))
            return None


def _resolve_output_plugin_name(settings: AppSettings) -> str:
    configured = str(getattr(settings, "output_plugin", LEGACY_OUTPUT_PLUGIN)).strip()
    if not configured:
        return LEGACY_OUTPUT_PLUGIN
    available = set(_PLUGIN_RUNTIME.registry.list_outputs())
    if configured not in available:
        logger.warning("Unknown output plugin '%s'. Fallback to '%s'.", configured, LEGACY_OUTPUT_PLUGIN)
        return LEGACY_OUTPUT_PLUGIN
    if configured not in _SUPPORTED_OUTPUT_PLUGINS:
        logger.warning("Unsupported output plugin '%s'. Fallback to '%s'.", configured, LEGACY_OUTPUT_PLUGIN)
        return LEGACY_OUTPUT_PLUGIN
    return configured


def _write_output(
    settings: AppSettings,
    task_result: TaskResult,
    *,
    column_order: list[str] | None = None,
) -> bool:
    output_plugin = _resolve_output_plugin_name(settings)
    try:
        _PLUGIN_RUNTIME.write_output(
            output_plugin,
            OutputRequest(
                output_name=output_plugin,
                settings=settings,
                task_result=task_result,
                column_order=column_order,
            ),
        )
        return True
    except OutputWriteError as exc:
        logger.error("%s", exc)
        return False


def _create_inspector(
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


def _init_run(settings: AppSettings) -> tuple[str, str]:
    console_level = getattr(logging, settings.console_log_level, logging.INFO)
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = init_logging(
        run_timestamp=run_timestamp,
        console_level=console_level,
        file_level=logging.DEBUG,
        enable_color=True,
    )
    return run_timestamp, log_file


def _print_run_summary(
    mode: str,
    device_count: int,
    filepath: str,
    settings: AppSettings,
    run_timestamp: str,
    log_file: str,
) -> None:
    table = Table(border_style="dim", expand=False, show_header=False)
    table.add_column(t("main.run_summary.item"), style="cyan")
    table.add_column(t("main.run_summary.value"), style="bold")
    table.add_row("RUN ID", run_timestamp)
    table.add_row(t("main.run_summary.mode"), mode)
    table.add_row(t("main.run_summary.devices"), str(device_count))
    table.add_row(t("main.run_summary.file"), filepath)
    table.add_row(t("main.run_summary.timeout"), str(settings.timeout))
    table.add_row(t("main.run_summary.max_retries"), str(settings.max_retries))
    table.add_row(t("main.run_summary.max_workers"), str(settings.max_workers))
    table.add_row(t("main.run_summary.log_file"), log_file)
    console.print(
        Panel(
            table,
            title=f"[bold cyan]{t('main.run_summary.title')}[/bold cyan]",
            border_style="green",
            expand=False,
        ),
    )


def _print_result_summary(task_result: TaskResult, log_file: str) -> None:
    console.print()
    if task_result.results:
        console.print(f"[bold green]{t('main.result.completed')}[/bold green]")
        console.print(f"  {t('main.result.result_file')}: {task_result.output_excel}")
        if not task_result.inspection_only:
            console.print(f"  {t('main.result.backup_dir')}: {task_result.backup_dir}")
        console.print(f"  {t('main.result.session_log')}: {task_result.session_log_dir}")
        console.print(f"  {t('main.result.log_file')}: {log_file}")
    else:
        console.print(f"[yellow]{t('main.result.no_results')}[/yellow]")
        console.print(f"  {t('main.result.session_log')}: {task_result.session_log_dir}")
        console.print(f"  {t('main.result.log_file')}: {log_file}")

    console.print()
    input(t("main.prompts.return_main_menu"))


def _inventory_plugin_for_filepath(filepath: str) -> str:
    suffix = Path(filepath).suffix.lower()
    if suffix in (".xlsx", ".xls", ".xlsm"):
        return EXCEL_INVENTORY_PLUGIN
    if suffix == ".csv":
        return CSV_INVENTORY_PLUGIN
    if suffix == ".json":
        return JSON_INVENTORY_PLUGIN
    raise InventoryLoadError(t("file_handler.error.unsupported_extension", suffix=suffix or filepath))


def _load_inventory_payload(settings: AppSettings):
    filepath = get_filepath_from_cli()
    if not filepath:
        raise InventoryLoadError(t("main.warning.input_path_missing"))
    plugin_name = _inventory_plugin_for_filepath(filepath)
    return _PLUGIN_RUNTIME.load_inventory(
        plugin_name,
        settings=settings,
        options={"filepath": filepath},
    )


def _run_custom_commands(settings: AppSettings) -> None:
    run_timestamp, log_file = _init_run(settings)
    output_excel = "command_results.xlsx"
    mode_label = t("main.modes.custom_commands")

    logger.info("RUN ID   : %s", run_timestamp)
    logger.info("LOG FILE : %s", log_file)
    logger.info("-----------------------------------------")
    logger.info(t("main.info.mode_log_prefix", mode=mode_label))

    try:
        inventory_payload = _load_inventory_payload(settings)
    except InventoryLoadError as exc:
        logger.warning("%s", exc)
        return

    filepath = inventory_payload.filepath
    logger.info("INPUT   : %s", filepath)
    devices = inventory_payload.devices

    vendor_os_pairs = {
        (
            str(device.get("vendor", "")).strip().lower(),
            str(device.get("os", "")).strip().lower(),
        )
        for device in devices
    }
    if len(vendor_os_pairs) > 1:
        if not ask_yes_no(t("main.confirm.mixed_vendor_os")):
            logger.info(t("main.info.custom_commands_cancelled"))
            return

    command_path = get_command_filepath_from_cli()
    if not command_path:
        logger.warning(t("main.warning.command_path_missing"))
        return
    logger.info("COMMAND FILE : %s", command_path)

    try:
        commands = read_command_file(command_path)
    except Exception as exc:
        logger.error(t("main.warning.command_file_read_failed", error=exc))
        return

    if not commands:
        logger.warning(t("main.warning.command_list_empty"))
        return

    _print_run_summary(mode_label, len(devices), filepath, settings, run_timestamp, log_file)
    if not ask_yes_no(t("main.confirm.run_now"), default=True):
        logger.info(t("main.info.custom_commands_cancelled"))
        return

    dashboard = TuiDashboard(mode_label, len(devices))
    request = TaskRequest(
        task_name="custom_commands",
        run_timestamp=run_timestamp,
        settings=settings,
        devices=devices,
        status_callback=dashboard.handle_event,
        options={
            "task_kind": "custom_commands",
            "commands": commands,
            "output_excel": output_excel,
        },
    )

    dashboard.start()
    try:
        task_result = _PLUGIN_RUNTIME.run_task(LEGACY_TASK_PLUGIN, request)
    except TaskExecutionError as exc:
        logger.error("%s", exc)
        return
    finally:
        dashboard.mark_completed(t("main.info.dashboard_completed_note"))
        dashboard.stop()

    if not _write_output(settings, task_result):
        return

    _print_result_summary(task_result, log_file)


def _run_inspection_backup(settings: AppSettings) -> None:
    action_choice = show_action_menu()
    if action_choice is None:
        return

    mode_map = {
        "1": t("main.modes.inspection"),
        "2": t("main.modes.backup"),
        "3": t("main.modes.inspection_backup"),
    }
    mode_label = mode_map.get(action_choice, action_choice)

    run_timestamp, log_file = _init_run(settings)
    output_excel = "inspection_results.xlsx"

    logger.info("RUN ID   : %s", run_timestamp)
    logger.info("LOG FILE : %s", log_file)
    logger.info("-----------------------------------------")
    logger.info(t("main.info.mode_log_prefix", mode=mode_label))

    try:
        inventory_payload = _load_inventory_payload(settings)
    except InventoryLoadError as exc:
        logger.warning("%s", exc)
        return

    filepath = inventory_payload.filepath
    logger.info("INPUT   : %s", filepath)
    devices = inventory_payload.devices

    dashboard = TuiDashboard(mode_label, len(devices))
    request = TaskRequest(
        task_name="inspection_backup",
        run_timestamp=run_timestamp,
        settings=settings,
        devices=devices,
        status_callback=dashboard.handle_event,
        options={
            "task_kind": "inspection_backup",
            "action_choice": action_choice,
            "output_excel": output_excel,
        },
    )

    _print_run_summary(mode_label, len(devices), filepath, settings, run_timestamp, log_file)
    if not ask_yes_no(t("main.confirm.run_now"), default=True):
        logger.info(t("main.info.job_cancelled"))
        return

    dashboard.start()
    try:
        task_result = _PLUGIN_RUNTIME.run_task(LEGACY_TASK_PLUGIN, request)
    except TaskExecutionError as exc:
        logger.error("%s", exc)
        return
    finally:
        dashboard.mark_completed(t("main.info.dashboard_completed_note"))
        dashboard.stop()

    column_order: list[str] | None = None
    if action_choice in ("1", "3"):
        available_columns = task_result.metadata.get("available_columns", [])
        profile_keys = task_result.metadata.get("profile_keys", [])
        if available_columns:
            column_order = resolve_inspection_column_order(
                available_columns,
                profile_keys,
                settings,
            )
            logger.info(
                "COLUMN ORDER APPLIED | profiles=%s | columns=%s",
                profile_keys,
                column_order,
            )
        else:
            logger.info(t("main.warning.no_order_columns"))

    if not _write_output(settings, task_result, column_order=column_order):
        return

    _print_result_summary(task_result, log_file)


def _run_preflight(settings: AppSettings) -> None:
    mode_label = t("main.modes.preflight")
    run_timestamp, log_file = _init_run(settings)
    output_excel = "preflight_results.xlsx"

    logger.info("RUN ID   : %s", run_timestamp)
    logger.info("LOG FILE : %s", log_file)
    logger.info("-----------------------------------------")
    logger.info(t("main.info.mode_log_prefix", mode=mode_label))

    try:
        inventory_payload = _load_inventory_payload(settings)
    except InventoryLoadError as exc:
        logger.warning("%s", exc)
        return

    filepath = inventory_payload.filepath
    devices = inventory_payload.devices
    logger.info("INPUT   : %s", filepath)

    _print_run_summary(mode_label, len(devices), filepath, settings, run_timestamp, log_file)
    if not ask_yes_no(t("main.confirm.run_now"), default=True):
        logger.info(t("main.info.job_cancelled"))
        return

    dashboard = TuiDashboard(mode_label, len(devices))
    request = TaskRequest(
        task_name="preflight",
        run_timestamp=run_timestamp,
        settings=settings,
        devices=devices,
        status_callback=dashboard.handle_event,
        options={
            "task_kind": "preflight",
            "output_excel": output_excel,
        },
    )

    dashboard.start()
    try:
        task_result = _PLUGIN_RUNTIME.run_task(LEGACY_TASK_PLUGIN, request)
    except TaskExecutionError as exc:
        logger.error("%s", exc)
        return
    finally:
        dashboard.mark_completed(t("main.info.dashboard_completed_note"))
        dashboard.stop()

    if not _write_output(settings, task_result):
        return
    _print_result_summary(task_result, log_file)


def main() -> None:
    try:
        while True:
            settings = load_settings()
            set_locale(settings.language, settings.fallback_language)
            menu_choice = show_main_menu()

            if menu_choice == "1":
                _run_inspection_backup(settings)
            elif menu_choice == "2":
                _run_custom_commands(settings)
            elif menu_choice == "3":
                show_settings_menu(settings)
            elif menu_choice == "4":
                show_netmiko_device_types()
            elif menu_choice == "5":
                _run_preflight(settings)
            elif menu_choice == "6":
                console.print(f"[dim]{t('main.shutdown')}[/dim]")
                return
    except KeyboardInterrupt:
        console.print(f"\n[dim]{t('main.shutdown')}[/dim]")
    except NetworkInspectorError as exc:
        logger.exception(t("main.errors.app_error", error=exc))
    except Exception as exc:
        logger.exception(t("main.errors.unexpected", error=exc))


if __name__ == "__main__":
    main()
