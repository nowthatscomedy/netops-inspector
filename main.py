import logging
import os
import msvcrt
from datetime import datetime
from pathlib import Path

from core.inspector import NetworkInspector
from core.file_handler import read_excel_file, save_results_to_excel
from core.validator import validate_dataframe
from core.ui import get_password_from_dialog
from core.custom_exceptions import NetworkInspectorError
from core.logging_config import init_logging
from core.settings import load_settings, save_settings, AppSettings

logger = logging.getLogger(__name__)

def select_menu(
    title: str,
    options: list[str],
    selected_index: int = 0,
    hints: list[str] | None = None
) -> int:
    """키보드 화살표/엔터로 메뉴 선택"""
    selected = max(0, min(selected_index, len(options) - 1))
    while True:
        os.system("cls")
        print("=========================================")
        if title:
            print(title)
        if hints:
            for line in hints:
                print(line)
        print("조작: ↑/↓ 이동, Enter 선택")
        print("-----------------------------------------")
        for i, option in enumerate(options):
            prefix = ">> " if i == selected else "   "
            print(f"{prefix}{option}")

        key = msvcrt.getwch()
        if key in ("\r", "\n"):
            return selected
        if key in ("\x00", "\xe0"):
            key = msvcrt.getwch()
            if key == "H":  # Up
                selected = (selected - 1) % len(options)
            elif key == "P":  # Down
                selected = (selected + 1) % len(options)

def show_main_menu() -> str:
    """프로그램 시작 메뉴"""
    settings = load_settings()
    options = [
        "작업 시작 (점검/백업 선택)",
        f"설정 변경 (로그 출력: {settings.console_log_level})",
        "종료"
    ]
    hints = [
        "네트워크 장비 점검 프로그램",
        "원하는 작업을 선택하세요.",
    ]
    index = select_menu("메인 메뉴", options, hints=hints)
    return str(index + 1)

def show_action_menu() -> str | None:
    """실행 작업 선택 메뉴"""
    mode_options = [
        "점검만 실행 (백업 없음)",
        "백업만 실행 (점검 없음)",
        "점검 + 백업 (둘 다)",
        "뒤로가기",
    ]
    mode_hints = [
        "실행할 작업을 선택하세요.",
        "백업은 장비 설정 파일을 저장합니다.",
    ]
    choice_index = select_menu("작업 선택", mode_options, hints=mode_hints)
    if choice_index == 3:
        return None
    return str(choice_index + 1)

def select_console_log_level(current_level: str) -> str:
    """콘솔 로그 레벨 선택"""
    options = ["경고 이상만", "기본 정보", "상세 디버그", "뒤로가기"]
    level_map = ["WARNING", "INFO", "DEBUG"]
    try:
        selected_index = level_map.index(current_level)
    except ValueError:
        selected_index = 1
    hints = [
        f"[현재] 콘솔 로그 레벨: {current_level}",
        "일반 사용자라면 '기본 정보'를 권장합니다.",
    ]
    index = select_menu("콘솔 로그 레벨 설정", options, selected_index, hints=hints)
    if index == 3:
        return current_level
    return level_map[index]

def show_settings_menu(settings: AppSettings) -> None:
    """설정 메뉴"""
    while True:
        options = [
            f"콘솔 로그 레벨 변경 (현재: {settings.console_log_level})",
            "뒤로가기",
        ]
        hints = [
            "설정 메뉴",
            "로그 출력이 너무 많다면 '경고 이상만'으로 줄이세요.",
        ]
        choice = select_menu("설정", options, hints=hints)
        if choice == 0:
            settings.console_log_level = select_console_log_level(settings.console_log_level)
            save_settings(settings)
            print("설정이 저장되었습니다.")
        elif choice == 1:
            return
        else:
            print("잘못된 선택입니다. 다시 시도하세요.")

def get_filepath_from_cli() -> str | None:
    """CLI에서 엑셀 파일 경로 입력 받기"""
    raw_input = input(">> 엑셀 파일 경로를 입력하세요 (예: test.xlsx 또는 C:\\Users\\PC\\Desktop\\test.xlsx): ").strip()
    if not raw_input:
        return None

    # 따옴표로 감싼 경로 처리
    cleaned = raw_input.strip('"').strip("'")
    path = Path(cleaned).expanduser()

    if not path.exists():
        logger.warning("입력한 파일을 찾을 수 없습니다: %s", path)
        return None

    return str(path)

def main():
    """메인 함수"""
    inspector = None
    try:
        settings = load_settings()

        while True:
            menu_choice = show_main_menu()
            if menu_choice == "1":
                action_choice = show_action_menu()
                if action_choice is None:
                    continue
                choice = action_choice
                break
            if menu_choice == "2":
                show_settings_menu(settings)
                continue
            if menu_choice == "3":
                print("프로그램을 종료합니다.")
                return
            print("잘못된 선택입니다. 다시 시도하세요.")

        console_level = getattr(logging, settings.console_log_level, logging.INFO)

        # 전역 로깅 일관 설정 (파일+콘솔) 및 실행 타임스탬프 고정
        run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = init_logging(
            run_timestamp=run_timestamp,
            console_level=console_level,
            file_level=logging.DEBUG,
            enable_color=True
        )

        output_excel = "inspection_results.xlsx"
        
        banner = [
            " _   _      _                      _   _           _            ",
            "| \\ | | ___| |___      _____  _ __| \\ | | ___   __| | ___ _ __  ",
            "|  \\| |/ _ \\ __\\ \\ /\\ / / _ \\| '__|  \\| |/ _ \\ / _` |/ _ \\ '__| ",
            "| |\\  |  __/ |_ \\ V  V / (_) | |  | |\\  | (_) | (_| |  __/ |    ",
            "|_| \\_|\\___|\\__| \\_/\\_/ \\___/|_|  |_| \\_|\\___/ \\__,_|\\___|_|    ",
        ]
        for line in banner:
            logger.info(line)
        logger.info("RUN ID   : %s", run_timestamp)
        logger.info("LOG FILE : %s", log_file)
        logger.info("-----------------------------------------")
        mode_map = {"1": "점검", "2": "백업", "3": "점검+백업"}
        if choice in mode_map:
            logger.info("MODE    : %s", mode_map[choice])

        # 파일 경로 입력 (CLI)
        filepath = get_filepath_from_cli()
        if not filepath:
            logger.warning("파일 경로가 입력되지 않았습니다. 프로그램을 종료합니다.")
            return
        logger.info("INPUT   : %s", filepath)
            
        # 파일 읽기 시도
        try:
            devices_df = read_excel_file(filepath)
        except Exception:
            password = get_password_from_dialog()
            if not password:
                logger.warning("암호가 입력되지 않았습니다. 프로그램을 종료합니다.")
                return
            devices_df = read_excel_file(filepath, password=password)

        # 데이터 유효성 검사
        validate_dataframe(devices_df)
        devices = devices_df.to_dict('records')

        if choice == "1":
            inspector = NetworkInspector(output_excel, inspection_only=True, run_timestamp=run_timestamp)
            inspector.load_devices(devices)
            inspector.inspect_devices(backup_only=False)
        elif choice == "2":
            inspector = NetworkInspector(output_excel, backup_only=True, run_timestamp=run_timestamp)
            inspector.load_devices(devices)
            inspector.inspect_devices(backup_only=True)
        elif choice == "3":
            inspector = NetworkInspector(output_excel, run_timestamp=run_timestamp)
            inspector.load_devices(devices)
            inspector.inspect_and_backup_devices()
        else:
            logger.warning("잘못된 선택입니다. 1-3 사이의 숫자를 입력하세요.")
            return
        
        # 결과 저장
        if inspector and inspector.results:
            save_results_to_excel(inspector.results, inspector.output_excel)
            logger.info("작업이 완료되었습니다.")
            logger.info(f"결과 파일: {inspector.output_excel}")
            logger.info(f"결과 디렉토리: {inspector.output_dir}")
            if not inspector.inspection_only:
                logger.info(f"백업 디렉토리: {inspector.backup_dir}")
        else:
            logger.info("처리된 결과가 없어 파일을 저장하지 않았습니다.")

    except NetworkInspectorError as e:
        logger.exception(f"애플리케이션 오류 발생: {e}")
    except Exception as e:
        logger.exception(f"예상치 못한 오류 발생: {e}")

if __name__ == "__main__":
    main() 