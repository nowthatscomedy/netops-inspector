"""
Network Device Inspection Tool - Base Module

기본 장비 핸들러 클래스와 핸들러 선택 함수를 제공합니다.
모든 벤더별 핸들러는 이 기본 클래스를 상속받아 구현됩니다.
"""

import os
import logging

logger = logging.getLogger(__name__)

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

def get_custom_handler(device, timeout=10, session_log_file=None):
    """장비 유형에 맞는 커스텀 핸들러 반환"""
    # 메인 코드에 임포트 문제를 피하기 위해 내부에서 임포트
    from vendors.cisco import CiscoLegacyTelnetHandler
    from vendors.ubiquoss import UbiquossE4020Handler, UbiquossE4020SSHHandler
    from vendors.axgate import AxgateHandler, AxgateSSHHandler
    from vendors.nexg import VForceSSHHandler, VForceTelnetHandler
    from vendors.alcatel_lucent import AlcatelLucentHandler
    from vendors.piolink import PiolinkTifrontSSHHandler
    
    vendor = device.get('vendor', '').lower()
    model = device.get('os', '').lower()
    connection_type = device.get('connection_type', '').lower()
    
    # 유비쿼스 E4020 장비 처리
    if vendor == 'ubiquoss' and model == 'e4020':
        if connection_type == 'telnet':
            return UbiquossE4020Handler(device, timeout, session_log_file)
        elif connection_type == 'ssh':
            return UbiquossE4020SSHHandler(device, timeout, session_log_file)
    # Axgate 장비 처리
    elif vendor == 'axgate' and model == 'axgate':
        if connection_type == 'telnet':
            return AxgateHandler(device, timeout, session_log_file)
        elif connection_type == 'ssh':
            return AxgateSSHHandler(device, timeout, session_log_file)
    elif vendor == 'nexg' and model == 'vforce':
        if connection_type == 'ssh':
            return VForceSSHHandler(device, timeout, session_log_file)
        elif connection_type == 'telnet':
            return VForceTelnetHandler(device, timeout, session_log_file)
    elif vendor == 'cisco' and model == 'legacy':
        return CiscoLegacyTelnetHandler(device, timeout, session_log_file)
    # Alcatel-Lucent 장비 처리
    elif vendor == 'alcatel-lucent' and (model == 'aos6' or model == 'aos8'):
        if connection_type == 'ssh':
            return AlcatelLucentHandler(device, timeout, session_log_file)
    # Piolink 장비 처리
    elif vendor == 'piolink' and model == 'tifront':
        if connection_type == 'ssh':
            return PiolinkTifrontSSHHandler(device, timeout, session_log_file)
    
    return None 