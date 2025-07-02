import ipaddress
import pandas as pd
import logging
from typing import Tuple

from vendors import INSPECTION_COMMANDS
from .custom_exceptions import ValidationError

logger = logging.getLogger(__name__)

def _validate_ip(ip: str) -> bool:
    """IP 주소 형식을 검증합니다."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def _validate_port(port: int) -> bool:
    """포트 번호 범위를 검증합니다."""
    try:
        port_num = int(port)
        return 1 <= port_num <= 65535
    except (ValueError, TypeError):
        return False

def _validate_connection_type(connection_type: str) -> bool:
    """접속 방식을 검증합니다."""
    return str(connection_type).lower() in ['ssh', 'telnet']

def validate_device_info(device: dict) -> Tuple[bool, str]:
    """단일 장비 정보의 유효성을 검사합니다."""
    required_fields = ['ip', 'vendor', 'os', 'connection_type', 'port', 'password']
    for field in required_fields:
        if field not in device or pd.isna(device[field]):
            msg = f"필수 필드 누락 또는 값이 비어있음: '{field}' (IP: {device.get('ip', 'N/A')})"
            logger.error(msg)
            return False, msg

    if not _validate_ip(device['ip']):
        return False, f"잘못된 IP 주소: {device['ip']}"
    if not _validate_connection_type(device['connection_type']):
        return False, f"잘못된 접속 방식: {device['connection_type']} (IP: {device['ip']})"
    if not _validate_port(device['port']):
        return False, f"잘못된 포트 번호: {device['port']} (IP: {device['ip']})"

    vendor = str(device['vendor']).lower()
    os_model = str(device['os']).lower()

    if vendor not in INSPECTION_COMMANDS:
        return False, f"지원하지 않는 벤더: {vendor} (IP: {device['ip']})"
    if os_model not in INSPECTION_COMMANDS.get(vendor, {}):
        return False, f"지원하지 않는 OS 모델: {os_model} (벤더: {vendor}, IP: {device['ip']})"
    
    return True, ""

def validate_dataframe(df: pd.DataFrame):
    """
    데이터프레임의 전체적인 유효성을 검사합니다.
    - 필수 컬럼 존재 여부
    - 중복 IP 주소
    - 각 행의 유효성
    """
    required_columns = ['ip', 'vendor', 'os', 'connection_type', 'port', 'password']
    if df.empty:
        raise ValidationError("엑셀 파일이 비어있습니다.")
    
    # 컬럼 이름을 소문자로 통일
    df.columns = [str(col).lower() for col in df.columns]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValidationError(f"필수 컬럼 누락: {', '.join(missing_columns)}")

    if df['ip'].duplicated().any():
        duplicated_ips = df[df['ip'].duplicated()]['ip'].tolist()
        raise ValidationError(f"중복된 IP 주소가 있습니다: {', '.join(duplicated_ips)}")

    all_errors = []
    for _, device in df.iterrows():
        is_valid, error_message = validate_device_info(device.to_dict())
        if not is_valid:
            all_errors.append(error_message)
    
    if all_errors:
        raise ValidationError("장비 정보에 오류가 있습니다:\n" + "\n".join(all_errors)) 