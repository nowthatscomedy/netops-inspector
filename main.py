import logging
from collections.abc import Callable
from datetime import datetime
from zipfile import BadZipFile

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.inspector import NetworkInspector
from core.file_handler import read_excel_file, save_results_to_excel, read_command_file
from core.validator import validate_dataframe
from core.ui import get_password_from_cli
from core.tui_dashboard import TuiDashboard
from core.custom_exceptions import NetworkInspectorError
from core.logging_config import init_logging
from core.settings import load_settings, AppSettings, resolve_inspection_column_order
from core.menu import (
    show_main_menu,
    show_action_menu,
    show_settings_menu,
    show_netmiko_device_types,
    ask_yes_no,
)
from core.cli_input import get_filepath_from_cli, get_command_filepath_from_cli

logger = logging.getLogger(__name__)
console = Console()


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------

def _read_excel_with_retry(filepath: str) -> pd.DataFrame | None:
    """엑셀 파일을 읽습니다. 실패 시 암호 입력 후 재시도합니다."""
    try:
        return read_excel_file(filepath)
    except (BadZipFile, Exception):
        password = get_password_from_cli()
        if not password:
            logger.warning("암호가 입력되지 않았습니다.")
            return None
        try:
            return read_excel_file(filepath, password=password)
        except Exception as e:
            logger.error("암호화된 엑셀 파일 읽기 실패: %s", e)
            return None


def _create_inspector(
    output_excel: str,
    run_timestamp: str,
    settings: AppSettings,
    *,
    inspection_only: bool = False,
    backup_only: bool = False,
    status_callback: Callable[[dict[str, object]], None] | None = None,
) -> NetworkInspector:
    """NetworkInspector 인스턴스를 생성합니다."""
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
    """로깅을 초기화하고 (run_timestamp, log_file)을 반환합니다."""
    console_level = getattr(logging, settings.console_log_level, logging.INFO)
    run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
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
    """실행 전 요약 패널을 표시합니다."""
    table = Table(border_style="dim", expand=False, show_header=False)
    table.add_column("항목", style="cyan")
    table.add_column("값", style="bold")
    table.add_row("RUN ID", run_timestamp)
    table.add_row("모드", mode)
    table.add_row("장비 수", f"{device_count}대")
    table.add_row("파일", filepath)
    table.add_row("타임아웃", f"{settings.timeout}초")
    table.add_row("최대 재시도", f"{settings.max_retries}회")
    table.add_row("동시 처리", f"{settings.max_workers}대")
    table.add_row("로그 파일", log_file)
    console.print(Panel(table, title="[bold cyan]실행 요약[/bold cyan]", border_style="green", expand=False))


def _print_result_summary(inspector: NetworkInspector, log_file: str) -> None:
    """작업 완료 후 결과 요약을 표시합니다."""
    console.print()
    if inspector.results:
        console.print("[bold green]작업이 완료되었습니다.[/bold green]")
        console.print(f"  결과 파일: {inspector.output_excel}")
        if not inspector.inspection_only:
            console.print(f"  백업 디렉토리: {inspector.backup_dir}")
        console.print(f"  세션 로그: {inspector.session_log_dir}")
        console.print(f"  로그 파일: {log_file}")
    else:
        console.print("[yellow]처리된 결과가 없어 결과 파일을 저장하지 않았습니다.[/yellow]")
        console.print(f"  세션 로그: {inspector.session_log_dir}")
        console.print(f"  로그 파일: {log_file}")

    console.print()
    input("Enter를 누르면 메인 메뉴로 돌아갑니다.")


# ---------------------------------------------------------------------------
# 사용자 명령 파일 실행
# ---------------------------------------------------------------------------

def _run_custom_commands(settings: AppSettings) -> None:
    """사용자 명령 파일 실행 플로우"""
    run_timestamp, log_file = _init_run(settings)
    output_excel = "command_results.xlsx"

    logger.info("RUN ID   : %s", run_timestamp)
    logger.info("LOG FILE : %s", log_file)
    logger.info("-----------------------------------------")
    logger.info("MODE    : 사용자 명령 실행")

    filepath = get_filepath_from_cli()
    if not filepath:
        logger.warning("파일 경로가 입력되지 않았습니다.")
        return
    logger.info("INPUT   : %s", filepath)

    devices_df = _read_excel_with_retry(filepath)
    if devices_df is None:
        return

    validate_dataframe(devices_df)
    devices = devices_df.to_dict('records')

    vendor_os_pairs = {
        (
            str(d.get("vendor", "")).strip().lower(),
            str(d.get("os", "")).strip().lower(),
        )
        for d in devices
    }
    if len(vendor_os_pairs) > 1:
        if not ask_yes_no("다른 벤더/OS가 섞여 있습니다. 계속 진행할까요?"):
            logger.info("사용자 명령 실행이 취소되었습니다.")
            return

    command_path = get_command_filepath_from_cli()
    if not command_path:
        logger.warning("명령어 파일 경로가 입력되지 않았습니다.")
        return
    logger.info("COMMAND FILE : %s", command_path)

    try:
        commands = read_command_file(command_path)
    except Exception as e:
        logger.error("명령어 파일 읽기 실패: %s", e)
        return

    if not commands:
        logger.warning("명령어 파일에 실행할 명령이 없습니다.")
        return

    _print_run_summary("사용자 명령 실행", len(devices), filepath, settings, run_timestamp, log_file)
    if not ask_yes_no("실행할까요?", default=True):
        logger.info("사용자 명령 실행이 취소되었습니다.")
        return

    dashboard = TuiDashboard("사용자 명령 실행", len(devices))
    inspector = _create_inspector(
        output_excel,
        run_timestamp,
        settings,
        inspection_only=True,
        status_callback=dashboard.handle_event,
    )
    inspector.load_devices(devices)

    dashboard.start()
    try:
        inspector.run_custom_commands(commands)
    finally:
        dashboard.mark_completed("작업 완료 (결과 요약 확인)")
        dashboard.stop()

    if inspector.results:
        save_results_to_excel(
            inspector.results,
            inspector.output_excel,
            column_aliases=settings.column_aliases,
        )

    _print_result_summary(inspector, log_file)


# ---------------------------------------------------------------------------
# 점검/백업 실행
# ---------------------------------------------------------------------------

def _run_inspection_backup(settings: AppSettings) -> None:
    """점검/백업 실행 플로우"""
    action_choice = show_action_menu()
    if action_choice is None:
        return

    choice = action_choice
    mode_map = {"1": "점검", "2": "백업", "3": "점검+백업"}
    mode_label = mode_map.get(choice, choice)

    run_timestamp, log_file = _init_run(settings)
    output_excel = "inspection_results.xlsx"

    logger.info("RUN ID   : %s", run_timestamp)
    logger.info("LOG FILE : %s", log_file)
    logger.info("-----------------------------------------")
    logger.info("MODE    : %s", mode_label)

    filepath = get_filepath_from_cli()
    if not filepath:
        logger.warning("파일 경로가 입력되지 않았습니다.")
        return
    logger.info("INPUT   : %s", filepath)

    devices_df = _read_excel_with_retry(filepath)
    if devices_df is None:
        return

    validate_dataframe(devices_df)
    devices = devices_df.to_dict('records')

    dashboard = TuiDashboard(mode_label, len(devices))
    inspector = _create_inspector(
        output_excel,
        run_timestamp,
        settings,
        inspection_only=(choice == "1"),
        backup_only=(choice == "2"),
        status_callback=dashboard.handle_event,
    )
    inspector.load_devices(devices)

    column_order = None
    if choice in ("1", "3"):
        available_columns = inspector.get_available_inspection_columns(inspector.devices)
        if available_columns:
            profile_keys = inspector.get_device_profile_keys(inspector.devices)
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
            logger.info("정렬할 점검 항목이 없습니다.")

    _print_run_summary(mode_label, len(devices), filepath, settings, run_timestamp, log_file)
    if not ask_yes_no("실행할까요?", default=True):
        logger.info("작업이 취소되었습니다.")
        return

    dashboard.start()
    try:
        if choice == "1":
            inspector.inspect_devices(backup_only=False)
        elif choice == "2":
            inspector.inspect_devices(backup_only=True)
        else:
            inspector.inspect_and_backup_devices()
    finally:
        dashboard.mark_completed("작업 완료 (결과 요약 확인)")
        dashboard.stop()

    if inspector.results:
        save_results_to_excel(
            inspector.results,
            inspector.output_excel,
            column_order=column_order,
            column_aliases=settings.column_aliases,
        )

    _print_result_summary(inspector, log_file)


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main():
    """메인 함수"""
    try:
        while True:
            settings = load_settings()
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
                console.print("[dim]프로그램을 종료합니다.[/dim]")
                return

    except KeyboardInterrupt:
        console.print("\n[dim]프로그램을 종료합니다.[/dim]")
    except NetworkInspectorError as e:
        logger.exception("애플리케이션 오류 발생: %s", e)
    except Exception as e:
        logger.exception("예상치 못한 오류 발생: %s", e)


if __name__ == "__main__":
    main()
