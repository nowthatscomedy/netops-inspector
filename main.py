import logging
import sys
from datetime import datetime
from zipfile import BadZipFile

from core.inspector import NetworkInspector
from core.file_handler import read_excel_file, save_results_to_excel, read_command_file
from core.validator import validate_dataframe
from core.ui import get_password_from_cli
from core.custom_exceptions import NetworkInspectorError
from core.logging_config import init_logging
from core.settings import load_settings
from core.menu import (
    show_main_menu,
    show_action_menu,
    show_settings_menu,
    show_netmiko_device_types,
    reorder_columns_interactive,
    ask_yes_no,
)
from core.cli_input import get_filepath_from_cli, get_command_filepath_from_cli

logger = logging.getLogger(__name__)


def main():
    """메인 함수"""
    try:
        while True:
            settings = load_settings()

            while True:
                menu_choice = show_main_menu()
                if menu_choice == "1":
                    break
                if menu_choice == "2":
                    console_level = getattr(logging, settings.console_log_level, logging.INFO)

                    run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    log_file = init_logging(
                        run_timestamp=run_timestamp,
                        console_level=console_level,
                        file_level=logging.DEBUG,
                        enable_color=True
                    )

                    output_excel = "command_results.xlsx"
                    logger.info("RUN ID   : %s", run_timestamp)
                    logger.info("LOG FILE : %s", log_file)
                    logger.info("-----------------------------------------")
                    logger.info("MODE    : 사용자 명령 실행")

                    filepath = get_filepath_from_cli()
                    if not filepath:
                        logger.warning("파일 경로가 입력되지 않았습니다.")
                        continue
                    logger.info("INPUT   : %s", filepath)

                    try:
                        devices_df = read_excel_file(filepath)
                    except (BadZipFile, Exception):
                        password = get_password_from_cli()
                        if not password:
                            logger.warning("암호가 입력되지 않았습니다.")
                            continue
                        try:
                            devices_df = read_excel_file(filepath, password=password)
                        except Exception as e:
                            logger.error("암호화된 엑셀 파일 읽기 실패: %s", e)
                            continue

                    validate_dataframe(devices_df)
                    devices = devices_df.to_dict('records')

                    vendor_os_pairs = {
                        (
                            str(d.get("vendor", "")).strip().lower(),
                            str(d.get("os", "")).strip().lower()
                        )
                        for d in devices
                    }
                    if len(vendor_os_pairs) > 1:
                        if not ask_yes_no(
                            "다른 벤더/OS가 섞여 있습니다. 계속 진행할까요?",
                            default=False
                        ):
                            logger.info("사용자 명령 실행이 취소되었습니다.")
                            continue

                    command_path = get_command_filepath_from_cli()
                    if not command_path:
                        logger.warning("명령어 파일 경로가 입력되지 않았습니다.")
                        continue
                    logger.info("COMMAND FILE : %s", command_path)

                    try:
                        commands = read_command_file(command_path)
                    except Exception as e:
                        logger.error("명령어 파일 읽기 실패: %s", e)
                        continue

                    if not commands:
                        logger.warning("명령어 파일에 실행할 명령이 없습니다.")
                        continue

                    inspector = NetworkInspector(
                        output_excel,
                        inspection_only=True,
                        run_timestamp=run_timestamp,
                        inspection_excludes=settings.inspection_excludes,
                        max_retries=settings.max_retries,
                        timeout=settings.timeout,
                        max_workers=settings.max_workers,
                    )
                    inspector.load_devices(devices)
                    inspector.run_custom_commands(commands)

                    if inspector and inspector.results:
                        save_results_to_excel(
                            inspector.results,
                            inspector.output_excel
                        )
                        logger.info("작업이 완료되었습니다.")
                        logger.info("결과 파일: %s", inspector.output_excel)
                        logger.info("결과 디렉토리: %s", inspector.output_dir)
                    else:
                        logger.info("처리된 결과가 없어 파일을 저장하지 않았습니다.")
                    return
                if menu_choice == "3":
                    show_settings_menu(settings)
                    continue
                if menu_choice == "4":
                    show_netmiko_device_types()
                    continue
                if menu_choice == "5":
                    print("프로그램을 종료합니다.")
                    return
                print("잘못된 선택입니다. 다시 시도하세요.")

            while True:
                action_choice = show_action_menu()
                if action_choice is None:
                    break
                choice = action_choice

                console_level = getattr(logging, settings.console_log_level, logging.INFO)

                run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                log_file = init_logging(
                    run_timestamp=run_timestamp,
                    console_level=console_level,
                    file_level=logging.DEBUG,
                    enable_color=True
                )

                output_excel = "inspection_results.xlsx"
                logger.info("RUN ID   : %s", run_timestamp)
                logger.info("LOG FILE : %s", log_file)
                logger.info("-----------------------------------------")
                mode_map = {"1": "점검", "2": "백업", "3": "점검+백업"}
                if choice in mode_map:
                    logger.info("MODE    : %s", mode_map[choice])

                filepath = get_filepath_from_cli()
                if not filepath:
                    logger.warning("파일 경로가 입력되지 않았습니다.")
                    continue
                logger.info("INPUT   : %s", filepath)

                try:
                    devices_df = read_excel_file(filepath)
                except (BadZipFile, Exception):
                    password = get_password_from_cli()
                    if not password:
                        logger.warning("암호가 입력되지 않았습니다.")
                        continue
                    try:
                        devices_df = read_excel_file(filepath, password=password)
                    except Exception as e:
                        logger.error("암호화된 엑셀 파일 읽기 실패: %s", e)
                        continue

                validate_dataframe(devices_df)
                devices = devices_df.to_dict('records')

                column_order = None
                cancel_requested = False
                if choice == "1":
                    inspector = NetworkInspector(
                        output_excel,
                        inspection_only=True,
                        run_timestamp=run_timestamp,
                        inspection_excludes=settings.inspection_excludes,
                        max_retries=settings.max_retries,
                        timeout=settings.timeout,
                        max_workers=settings.max_workers,
                    )
                elif choice == "2":
                    inspector = NetworkInspector(
                        output_excel,
                        backup_only=True,
                        run_timestamp=run_timestamp,
                        inspection_excludes=settings.inspection_excludes,
                        max_retries=settings.max_retries,
                        timeout=settings.timeout,
                        max_workers=settings.max_workers,
                    )
                elif choice == "3":
                    inspector = NetworkInspector(
                        output_excel,
                        run_timestamp=run_timestamp,
                        inspection_excludes=settings.inspection_excludes,
                        max_retries=settings.max_retries,
                        timeout=settings.timeout,
                        max_workers=settings.max_workers,
                    )
                else:
                    logger.warning("잘못된 선택입니다. 1-3 사이의 숫자를 입력하세요.")
                    continue

                inspector.load_devices(devices)

                if choice in ("1", "3"):
                    if ask_yes_no("점검 결과 열 순서를 정할까요?", default=False):
                        available_columns = inspector.get_available_inspection_columns(inspector.devices)
                        if available_columns:
                            reordered = reorder_columns_interactive(available_columns)
                            if reordered is None:
                                cancel_requested = True
                            else:
                                column_order = reordered
                        else:
                            logger.info("정렬할 점검 항목이 없습니다.")

                if cancel_requested:
                    logger.info("작업이 취소되었습니다.")
                    continue

                if choice == "1":
                    inspector.inspect_devices(backup_only=False)
                elif choice == "2":
                    inspector.inspect_devices(backup_only=True)
                else:
                    inspector.inspect_and_backup_devices()

                if inspector and inspector.results:
                    save_results_to_excel(
                        inspector.results,
                        inspector.output_excel,
                        column_order=column_order
                    )
                    logger.info("작업이 완료되었습니다.")
                    logger.info("결과 파일: %s", inspector.output_excel)
                    logger.info("결과 디렉토리: %s", inspector.output_dir)
                    if not inspector.inspection_only:
                        logger.info("백업 디렉토리: %s", inspector.backup_dir)
                else:
                    logger.info("처리된 결과가 없어 파일을 저장하지 않았습니다.")
                return

    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
    except NetworkInspectorError as e:
        logger.exception("애플리케이션 오류 발생: %s", e)
    except Exception as e:
        logger.exception("예상치 못한 오류 발생: %s", e)

if __name__ == "__main__":
    main()
