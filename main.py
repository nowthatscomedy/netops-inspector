import logging
import traceback

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
        # 전역 로깅 일관 설정 (파일+콘솔)
        init_logging(console_level=logging.DEBUG, file_level=logging.DEBUG)

        output_excel = "inspection_results.xlsx"
        
        print("\n=== 네트워크 장비 점검 및 백업 도구 ===")
        print("1. 점검만 실행")
        print("2. 백업만 실행")
        print("3. 점검과 백업 모두 실행")
        
        choice = input("\n실행할 작업을 선택하세요 (1-3): ")

        # 파일 선택
        filepath = get_filepath_from_dialog()
        if not filepath:
            print("파일이 선택되지 않았습니다. 프로그램을 종료합니다.")
            return
            
        # 파일 읽기 시도
        try:
            devices_df = read_excel_file(filepath)
        except Exception:
            password = get_password_from_dialog()
            if not password:
                print("암호가 입력되지 않았습니다. 프로그램을 종료합니다.")
                return
            devices_df = read_excel_file(filepath, password=password)

        # 데이터 유효성 검사
        validate_dataframe(devices_df)
        devices = devices_df.to_dict('records')

        if choice == "1":
            inspector = NetworkInspector(output_excel, inspection_only=True)
            inspector.load_devices(devices)
            inspector.inspect_devices(backup_only=False)
        elif choice == "2":
            inspector = NetworkInspector(output_excel, backup_only=True)
            inspector.load_devices(devices)
            inspector.inspect_devices(backup_only=True)
        elif choice == "3":
            inspector = NetworkInspector(output_excel)
            inspector.load_devices(devices)
            inspector.inspect_and_backup_devices()
        else:
            print("잘못된 선택입니다. 1-3 사이의 숫자를 입력하세요.")
            return
        
        # 결과 저장
        if inspector and inspector.results:
            save_results_to_excel(inspector.results, inspector.output_excel)
            print("\n작업이 완료되었습니다.")
            print(f"결과 파일: {inspector.output_excel}")
            if not inspector.inspection_only:
                 print(f"백업 디렉토리: {inspector.backup_dir}")
        else:
            print("\n처리된 결과가 없어 파일을 저장하지 않았습니다.")

    except NetworkInspectorError as e:
        logger.error(f"애플리케이션 오류 발생: {e}")
        traceback.print_exc()
    except Exception as e:
        logger.error(f"예상치 못한 오류 발생: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 