import logging
import os
from datetime import datetime


def init_logging(run_timestamp: str | None = None,
                 log_dir: str = "logs",
                 enable_console: bool = True,
                 file_level: int = logging.DEBUG,
                 console_level: int = logging.INFO) -> str:
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

    formatter = logging.Formatter('%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s')

    # 파일 핸들러
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 콘솔 핸들러 (옵션)
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # 서드파티 라이브러리 로깅 레벨 정리 (과도한 디버그 억제)
    logging.getLogger('paramiko').setLevel(logging.DEBUG)
    logging.getLogger('netmiko').setLevel(logging.DEBUG)

    root_logger.debug("전역 로깅 초기화 완료")
    root_logger.debug(f"로그 파일 경로: {log_file}")

    return log_file


