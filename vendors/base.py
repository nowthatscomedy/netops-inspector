"""
Network Device Inspection Tool - Base Module

기본 장비 핸들러 클래스와 핸들러 선택 함수를 제공합니다.
모든 벤더별 핸들러는 이 기본 클래스를 상속받아 구현됩니다.
"""

import os
import logging
import importlib
import pkgutil

logger = logging.getLogger(__name__)

# 핸들러 등록을 위한 레지스트리
HANDLER_REGISTRY = {}

def register_handler(vendor, os_name, conn_type):
    """핸들러 클래스를 레지스트리에 등록하는 데코레이터"""
    def decorator(cls):
        key = (vendor.lower(), os_name.lower(), conn_type.lower())
        if key in HANDLER_REGISTRY:
            logger.warning(f"핸들러 키 중복: {key}가 이미 등록되어 있습니다. 기존 핸들러를 덮어씁니다.")
        HANDLER_REGISTRY[key] = cls
        logger.debug(f"핸들러 등록: {key} -> {cls.__name__}")
        return cls
    return decorator

class CustomDeviceHandler:
    """커스텀 장비 핸들러 기본 클래스"""
    
    def __init__(self, device, timeout=10, session_log_file=None):
        self.device = device
        self.timeout = timeout
        self.session_log_file = session_log_file
        self.logger = logging.getLogger(__name__)
    
    def connect(self):
        """장비에 연결"""
        raise NotImplementedError("Subclasses must implement connect method")
    
    def disconnect(self):
        """장비 연결 종료"""
        raise NotImplementedError("Subclasses must implement disconnect method")
    
    def send_command(self, command, timeout=None):
        """명령어 실행"""
        raise NotImplementedError("Subclasses must implement send_command method")
    
    def enable(self):
        """특권 모드 진입"""
        raise NotImplementedError("Subclasses must implement enable method")
    
    def log_output(self, message, output):
        """출력 로깅"""
        if self.session_log_file:
            with open(self.session_log_file, 'a', encoding='utf-8') as log:
                log.write(f"\n{message}\n")
                log.write("-"*50 + "\n")
                log.write(f"{output}\n")
                log.write("-"*50 + "\n")
    
    def get_backup_filename(self, backup_dir):
        """백업 파일명 생성"""
        return os.path.join(
            backup_dir,
            f"{self.device['ip']}_{self.device['vendor']}_{self.device['os']}.txt"
        )

def _load_handlers():
    """
    vendors 패키지 내의 모든 모듈을 임포트하여 핸들러가 레지스트리에 등록되도록 합니다.
    이 함수는 get_custom_handler가 처음 호출될 때 한 번만 실행됩니다.
    """
    pkg_path = os.path.dirname(__file__)
    pkg_name = os.path.basename(pkg_path)
    for _, name, _ in pkgutil.iter_modules([pkg_path]):
        importlib.import_module(f'.{name}', pkg_name)

_load_handlers() # 이 파일을 임포트하는 시점에 모든 핸들러 로드

def get_custom_handler(device, timeout=10, session_log_file=None):
    """장비 유형에 맞는 커스텀 핸들러 반환"""
    vendor = device.get('vendor', '').lower()
    model = device.get('os', '').lower()
    connection_type = device.get('connection_type', '').lower()
    
    key = (vendor, model, connection_type)
    handler_class = HANDLER_REGISTRY.get(key)
    
    if handler_class:
        logger.debug(f"핸들러 찾음: {key} -> {handler_class.__name__}")
        return handler_class(device, timeout, session_log_file)
    
    # 레거시 cisco 핸들러 같이 특정 os가 아닌 경우도 찾아보기
    key_generic_os = (vendor, '*', connection_type)
    handler_class = HANDLER_REGISTRY.get(key_generic_os)
    if handler_class:
        logger.debug(f"핸들러 찾음 (Generic OS): {key_generic_os} -> {handler_class.__name__}")
        return handler_class(device, timeout, session_log_file)
        
    logger.debug(f"커스텀 핸들러를 찾을 수 없음: {key}")
    return None 