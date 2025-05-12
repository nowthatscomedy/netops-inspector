import telnetlib
import time
import os
from datetime import datetime
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
            f"{self.device['ip']}_{self.device['vendor']}_{self.device['model']}.txt"
        )


class UbiquossE4020Handler(CustomDeviceHandler):
    """유비쿼스 E4020 장비 핸들러"""
    
    def __init__(self, device, timeout=10, session_log_file=None):
        super().__init__(device, timeout, session_log_file)
        self.tn = None
    
    def connect(self):
        """텔넷으로 장비에 연결"""
        if self.device['connection_type'].lower() != 'telnet':
            raise ValueError("UbiquossE4020Handler는 텔넷 연결만 지원합니다")
        
        self.logger.debug(f"유비쿼스 장비 Telnet 접속 시작: {self.device['ip']}")
        
        self.tn = telnetlib.Telnet(self.device['ip'], port=self.device['port'], timeout=self.timeout)
        
        # Username 입력
        self.tn.read_until(b"Username:", timeout=10)
        self.tn.write(self.device['username'].encode('utf-8') + b"\n")
        time.sleep(1)
        
        # Password 입력
        self.tn.read_until(b"Password:", timeout=10)
        self.tn.write(self.device['password'].encode('utf-8') + b"\n")
        time.sleep(2)
        
        # 로그인 후 출력 확인
        output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
        self.log_output("로그인 후 출력", output)
        
        return True
    
    def enable(self):
        """특권 모드 진입"""
        self.tn.write(b"enable\n")
        time.sleep(1)
        
        # Enable 비밀번호 입력 (있는 경우)
        if self.device.get('enable_password'):
            self.tn.read_until(b"Password:", timeout=10)
            self.tn.write(self.device['enable_password'].encode('utf-8') + b"\n")
            time.sleep(2)
        
        # terminal length 0 명령어 실행 (스크롤 없이 전체 출력)
        self.tn.write(b"terminal length 0\n")
        time.sleep(1)
        output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
        self.log_output("terminal length 0 명령어 실행 결과", output)
    
    def send_command(self, command, timeout=None):
        """명령어 실행"""
        if timeout is None:
            timeout = 3  # 기본 타임아웃 값
        
        self.log_output(f"명령어 실행: {command}", "")
        
        self.tn.write(command.encode('utf-8') + b"\n")
        time.sleep(timeout)  # 명령어 실행 결과 기다림
        output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
        
        self.log_output("출력", output)
        
        return output
    
    def disconnect(self):
        """텔넷 연결 종료"""
        if self.tn:
            self.tn.write(b"exit\n")
            self.tn.close()
            self.tn = None
            
            # 세션 로그 종료
            if self.session_log_file:
                with open(self.session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\n{'='*50}\n")
                    log.write(f"세션 완료 - {datetime.now()}\n")
                    log.write(f"{'='*50}\n\n")


class Axgate80DHandler(CustomDeviceHandler):
    """Axgate-80D 장비 핸들러"""
    
    def __init__(self, device, timeout=30, session_log_file=None):
        super().__init__(device, timeout, session_log_file)
        self.tn = None
    
    def connect(self):
        """텔넷으로 장비에 연결"""
        if self.device['connection_type'].lower() != 'telnet':
            raise ValueError("Axgate80DHandler는 텔넷 연결만 지원합니다")
        
        self.logger.debug(f"Axgate-80D 장비 접속 시작: {self.device['ip']}")
        
        self.tn = telnetlib.Telnet(self.device['ip'], port=self.device['port'], timeout=self.timeout)
        
        # Username 입력 (타임아웃 20초로 늘림)
        self.tn.read_until(b"Username:", timeout=20)
        self.tn.write(self.device['username'].encode('utf-8') + b"\n")
        time.sleep(2)  # 대기 시간 증가
        
        # Password 입력 (타임아웃 20초로 늘림)
        self.tn.read_until(b"Password:", timeout=20)
        self.tn.write(self.device['password'].encode('utf-8') + b"\n")
        time.sleep(3)  # 대기 시간 증가
        
        # 로그인 후 출력 확인
        output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
        self.log_output("로그인 후 출력", output)
        
        return True
    
    def enable(self):
        """특권 모드 진입 - Axgate-80D는 enable 명령어가 필요 없음"""
        # Axgate-80D는 로그인 후 이미 특권 모드이므로 아무 작업도 수행하지 않음
        self.logger.debug(f"Axgate-80D는 enable 명령어가 필요 없음: {self.device['ip']}")
        
        # 로그에 기록
        if self.session_log_file:
            with open(self.session_log_file, 'a', encoding='utf-8') as log:
                log.write("\nAxgate-80D는 enable 명령어가 필요 없음\n")
                log.write("-"*50 + "\n")
    
    def send_command(self, command, timeout=None):
        """명령어 실행"""
        if timeout is None:
            timeout = 3  # 기본 타임아웃 값
        
        self.log_output(f"명령어 실행: {command}", "")
        
        self.tn.write(command.encode('utf-8') + b"\n")
        time.sleep(timeout)  # 명령어 실행 결과 기다림
        output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
        
        self.log_output("출력", output)
        
        return output
    
    def disconnect(self):
        """텔넷 연결 종료"""
        if self.tn:
            self.tn.write(b"exit\n")
            self.tn.close()
            self.tn = None
            
            # 세션 로그 종료
            if self.session_log_file:
                with open(self.session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\n{'='*50}\n")
                    log.write(f"세션 완료 - {datetime.now()}\n")
                    log.write(f"{'='*50}\n\n")


# 장비 유형에 따른 핸들러 팩토리 함수
def get_custom_handler(device, timeout=10, session_log_file=None):
    """장비 유형에 따른 적절한 핸들러 반환"""
    vendor = device['vendor'].lower()
    model = device['model'].lower()
    
    if vendor == 'ubiquoss' and model == 'e4020' and device['connection_type'].lower() == 'telnet':
        return UbiquossE4020Handler(device, timeout, session_log_file)
    elif vendor == 'axgate' and model == 'axgate-80d' and device['connection_type'].lower() == 'telnet':
        return Axgate80DHandler(device, timeout, session_log_file)
    else:
        return None 