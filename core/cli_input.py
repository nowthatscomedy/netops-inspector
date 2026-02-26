import logging
from pathlib import Path

from InquirerPy import inquirer
from InquirerPy.validator import PathValidator

logger = logging.getLogger(__name__)

EXCEL_EXTENSIONS = (".xlsx", ".xls", ".xlsm")
COMMAND_EXTENSIONS = (".txt", ".xlsx", ".xls", ".xlsm")


def _validate_extension(path_str: str, extensions: tuple[str, ...]) -> bool:
    if not path_str:
        return False
    return Path(path_str).suffix.lower() in extensions


def get_filepath_from_cli() -> str | None:
    """CLI에서 엑셀 파일 경로 입력 받기 (Tab 자동완성 내장)"""
    result = inquirer.filepath(
        message="접속 정보 엑셀 파일 경로:",
        long_instruction="Tab: 자동완성 / Enter: 확인 / Ctrl+C: 취소",
        validate=PathValidator(is_file=True, message="유효한 파일 경로를 입력하세요."),
        only_files=True,
        mandatory=False,
    ).execute()

    if not result:
        return None

    cleaned = result.strip().strip('"').strip("'")
    path = Path(cleaned).expanduser()

    if not path.exists():
        logger.warning("입력한 파일을 찾을 수 없습니다: %s", path)
        return None

    if path.suffix.lower() not in EXCEL_EXTENSIONS:
        logger.warning("지원하지 않는 파일 형식입니다 (xlsx/xls/xlsm만 지원): %s", path.suffix)
        return None

    return str(path)


def get_command_filepath_from_cli() -> str | None:
    """CLI에서 명령어 파일 경로 입력 받기 (Tab 자동완성 내장)"""
    result = inquirer.filepath(
        message="명령어 파일 경로 (txt/xlsx):",
        long_instruction="Tab: 자동완성 / Enter: 확인 / Ctrl+C: 취소",
        validate=PathValidator(is_file=True, message="유효한 파일 경로를 입력하세요."),
        only_files=True,
        mandatory=False,
    ).execute()

    if not result:
        return None

    cleaned = result.strip().strip('"').strip("'")
    path = Path(cleaned).expanduser()

    if not path.exists():
        logger.warning("입력한 파일을 찾을 수 없습니다: %s", path)
        return None

    if path.suffix.lower() not in COMMAND_EXTENSIONS:
        logger.warning("지원하지 않는 파일 형식입니다 (txt/xlsx/xls/xlsm만 지원): %s", path.suffix)
        return None

    return str(path)
