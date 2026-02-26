import logging
import os
from datetime import datetime

try:
    from colorama import Fore, Style, init as colorama_init
except Exception:
    Fore = None
    Style = None
    colorama_init = None


class ColorFormatter(logging.Formatter):
    def __init__(self, fmt: str, enable_color: bool = True):
        super().__init__(fmt)
        self.enable_color = enable_color and Fore is not None and Style is not None

    def format(self, record: logging.LogRecord) -> str:
        original_levelname = record.levelname
        if self.enable_color:
            color = {
                logging.DEBUG: Fore.CYAN,
                logging.INFO: Fore.GREEN,
                logging.WARNING: Fore.YELLOW,
                logging.ERROR: Fore.RED,
                logging.CRITICAL: Fore.RED + Style.BRIGHT,
            }.get(record.levelno, "")
            record.levelname = f"{color}{original_levelname}{Style.RESET_ALL}"
        message = super().format(record)
        record.levelname = original_levelname
        return message


def init_logging(run_timestamp: str | None = None,
                 log_dir: str = "logs",
                 enable_console: bool = True,
                 file_level: int = logging.DEBUG,
                 console_level: int = logging.WARNING,
                 enable_color: bool = True) -> str:
    """
    애플리케이션 전역 로깅을 일관되게 초기화합니다.

    - 루트 로거에만 핸들러를 부착해 중복 로그를 방지합니다
    - 파일 로그(+ 콘솔 로그)를 동일 포맷으로 사용합니다

    Returns
    -------
    log_file: str
        생성된 로그 파일 경로
    """
    os.makedirs(log_dir, exist_ok=True)

    timestamp = run_timestamp or datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f"network_inspector_{timestamp}.log")

    root_logger = logging.getLogger()

    # 기존 모든 핸들러 제거 (중복 출력 방지)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.setLevel(logging.DEBUG)  # 내부 기준은 DEBUG, 핸들러에서 레벨 제어

    log_format = '%(asctime)s | [%(threadName)s] | %(levelname)s | %(message)s'
    formatter = logging.Formatter(log_format)

    # 파일 핸들러
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 콘솔 핸들러 (옵션)
    if enable_console:
        if colorama_init is not None:
            colorama_init(autoreset=True)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(ColorFormatter(log_format, enable_color=enable_color))
        root_logger.addHandler(console_handler)

    logging.getLogger('paramiko').setLevel(logging.WARNING)
    logging.getLogger('netmiko').setLevel(logging.WARNING)

    root_logger.debug("전역 로깅 초기화 완료")
    root_logger.debug("로그 파일 경로: %s", log_file)

    return log_file


