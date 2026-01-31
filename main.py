import logging
from datetime import datetime

from core.inspector import NetworkInspector
from core.file_handler import read_excel_file, save_results_to_excel
from core.validator import validate_dataframe
from core.ui import get_filepath_from_dialog, get_password_from_dialog
from core.custom_exceptions import NetworkInspectorError
from core.logging_config import init_logging

logger = logging.getLogger(__name__)

def main():
    """메인 함수"""
    inspector = None
    try:
        # 전역 로깅 일관 설정 (파일+콘솔) 및 실행 타임스탬프 고정
        run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = init_logging(
            run_timestamp=run_timestamp,
            console_level=logging.DEBUG,
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
        logger.info("1) 점검만 실행")
        logger.info("2) 백업만 실행")
        logger.info("3) 점검 + 백업")
        
        choice = input(">> 실행할 작업을 선택하세요 (1-3): ")
        mode_map = {"1": "점검", "2": "백업", "3": "점검+백업"}
        if choice in mode_map:
            logger.info("MODE    : %s", mode_map[choice])

        # 파일 선택
        filepath = get_filepath_from_dialog()
        if not filepath:
            logger.warning("파일이 선택되지 않았습니다. 프로그램을 종료합니다.")
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