import telnetlib
import time
import os
from datetime import datetime
import logging
import paramiko
import socket
import re
import traceback

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


class AxgateHandler(CustomDeviceHandler):
    """Axgate 장비 핸들러"""
    
    def __init__(self, device, timeout=30, session_log_file=None):
        super().__init__(device, timeout, session_log_file)
        self.tn = None
    
    def connect(self):
        """텔넷으로 장비에 연결"""
        if self.device['connection_type'].lower() != 'telnet':
            raise ValueError("AxgateHandler는 텔넷 연결만 지원합니다")
        
        self.logger.debug(f"Axgate 장비 접속 시작: {self.device['ip']}")
        
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
        """특권 모드 진입 - Axgate는 enable 명령어가 필요 없음"""
        # Axgate는 로그인 후 이미 특권 모드이므로 아무 작업도 수행하지 않음
        self.logger.debug(f"Axgate는 enable 명령어가 필요 없음: {self.device['ip']}")
        
        # 로그에 기록
        if self.session_log_file:
            with open(self.session_log_file, 'a', encoding='utf-8') as log:
                log.write("\nAxgate는 enable 명령어가 필요 없음\n")
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


class AxgateSSHHandler(CustomDeviceHandler):
    """Axgate 장비 SSH 핸들러"""
    
    def __init__(self, device, timeout=30, session_log_file=None):
        super().__init__(device, timeout, session_log_file)
        self.ssh = None
        self.channel = None
        
    def connect(self):
        """SSH로 장비에 연결"""
        if self.device['connection_type'].lower() != 'ssh':
            raise ValueError("AxgateSSHHandler는 SSH 연결만 지원합니다")
        
        self.logger.debug(f"Axgate 장비 SSH 접속 시작: {self.device['ip']}")
        
        try:
            # SSH 클라이언트 생성
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 연결
            self.ssh.connect(
                self.device['ip'],
                port=int(self.device['port']),
                username=self.device['username'],
                password=self.device['password'],
                look_for_keys=False,
                allow_agent=False,
                timeout=self.timeout
            )
            
            # 채널 생성
            self.channel = self.ssh.invoke_shell()
            self.channel.settimeout(self.timeout)
            
            # 초기 출력 읽기
            time.sleep(2)
            output = self._read_channel()
            self.log_output("SSH 초기 접속 출력", output)
            
            return True
            
        except socket.timeout:
            self.logger.error(f"Axgate SSH 접속 타임아웃: {self.device['ip']}")
            
            if self.session_log_file:
                with open(self.session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\nSSH 접속 타임아웃: {self.device['ip']}\n")
            
            raise ValueError(f"SSH 접속 타임아웃: {self.device['ip']}")
            
        except Exception as e:
            self.logger.error(f"Axgate SSH 접속 실패: {str(e)}")
            
            if self.session_log_file:
                with open(self.session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\nSSH 접속 실패: {str(e)}\n")
                    
            raise
    
    def _read_channel(self):
        """SSH 채널에서 데이터 읽기"""
        output = ""
        if self.channel is None:
            return output
        
        try:
            while self.channel.recv_ready():
                output += self.channel.recv(65535).decode('utf-8', errors='ignore')
        except:
            pass
        
        return output
    
    def _read_until_pattern(self, patterns, timeout=20):
        """특정 패턴이 나올 때까지 출력 읽기"""
        if self.channel is None:
            return "", -1
        
        output = ""
        pattern_index = -1
        
        end_time = time.time() + timeout
        while time.time() < end_time:
            # 채널에서 데이터를 읽을 수 있는지 확인
            if self.channel.recv_ready():
                chunk = self.channel.recv(65535).decode('utf-8', errors='ignore')
                output += chunk
                
                # 패턴 확인
                for i, pattern in enumerate(patterns):
                    if re.search(pattern, output):
                        pattern_index = i
                        return output, pattern_index
            
            time.sleep(0.1)  # CPU 사용량 줄이기 위한 짧은 대기
        
        return output, pattern_index
    
    def enable(self):
        """특권 모드 진입 - Axgate는 이미 특권 모드로 로그인됨"""
        self.logger.debug(f"Axgate SSH는 enable 명령어가 필요 없음: {self.device['ip']}")
        
        # 로그에 기록
        if self.session_log_file:
            with open(self.session_log_file, 'a', encoding='utf-8') as log:
                log.write("\nAxgate SSH는 enable 명령어가 필요 없음\n")
                log.write("-"*50 + "\n")
    
    def send_command(self, command, timeout=None):
        """명령어 실행"""
        if timeout is None:
            timeout = 10  # 기본 타임아웃 값
        
        if self.channel is None:
            raise ValueError("SSH 채널이 초기화되지 않았습니다")
        
        self.log_output(f"명령어 실행: {command}", "")
        
        # 버퍼 비우기
        output = self._read_channel()
        
        # 명령어 전송
        self.channel.send(command + "\n")
        time.sleep(1)  # 명령어 전송 후 잠시 대기
        
        # 결과 수집 (타임아웃 2배로 설정)
        output, _ = self._read_until_pattern([r"[>#]"], timeout=timeout*2)
        
        # 출력 정리 - 명령어 자체와 프롬프트 제거
        lines = output.splitlines()
        if lines and command in lines[0]:
            lines = lines[1:]
        
        # 마지막 줄이 프롬프트인 경우 제거
        if lines and (re.search(r"[>#]$", lines[-1].strip())):
            lines = lines[:-1]
        
        result = "\n".join(lines)
        self.log_output("명령어 결과", result)
        
        return result
    
    def disconnect(self):
        """SSH 연결 종료"""
        if self.channel:
            try:
                self.channel.send("exit\n")
                time.sleep(1)
                self.channel.close()
            except:
                pass
            self.channel = None
        
        if self.ssh:
            try:
                self.ssh.close()
            except:
                pass
            self.ssh = None
        
        # 세션 로그 종료
        if self.session_log_file:
            with open(self.session_log_file, 'a', encoding='utf-8') as log:
                log.write(f"\n{'='*50}\n")
                log.write(f"세션 완료 - {datetime.now()}\n")
                log.write(f"{'='*50}\n\n")


class VForceSSHHandler(CustomDeviceHandler):
    """NexG VForce SSH 장비 핸들러 (Axgate와 유사한 접속 방식)"""
    
    def __init__(self, device, timeout=30, session_log_file=None):
        super().__init__(device, timeout, session_log_file)
        self.channel = None
    
    def connect(self):
        """SSH로 장비에 연결"""
        if self.device['connection_type'].lower() != 'ssh':
            raise ValueError("VForceSSHHandler는 SSH 연결만 지원합니다")
        
        self.logger.debug(f"VForce 장비 SSH 접속 시작: {self.device['ip']}")

        # 디버깅을 위한 기본 연결 정보 출력
        self.logger.debug(f"연결 정보 - IP: {self.device['ip']}, PORT: {self.device['port']}, USER: {self.device['username']}")
        
        try:
            # 소켓 및 Transport 설정 (사용자 이름 직접 처리)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.device['ip'], int(self.device['port'])))
            
            # Transport 설정
            transport = paramiko.Transport(sock)
            transport.start_client()
            
            # 사용자 이름 전달 (자동 처리)
            transport.auth_none(str(self.device['username']))
            
            # 채널 생성
            self.channel = transport.open_session()
            self.channel.get_pty()
            self.channel.invoke_shell()
            self.channel.settimeout(self.timeout)
            
            # 초기 응답 확인 (비밀번호 프롬프트 대기)
            time.sleep(2)
            output = self._read_channel()
            self.log_output("초기 응답", output)
            
            # 비밀번호 프롬프트 확인 및 입력
            if "Password:" in output or "password:" in output:
                self.logger.debug("비밀번호 프롬프트 확인됨")
                self.channel.send(str(self.device['password']) + "\n")
                time.sleep(2)
            else:
                self.logger.warning("비밀번호 프롬프트가 없습니다. 직접 비밀번호 전송 시도")
                self.channel.send(str(self.device['password']) + "\n")
                time.sleep(2)
            
            # 로그인 성공 확인
            output = self._read_channel()
            self.log_output("비밀번호 입력 후 응답", output)
            
            # 로그인 성공 여부 확인 (프롬프트 확인)
            if "#" in output or ">" in output:
                self.logger.debug(f"로그인 성공: {self.device['ip']}")
                return True
            else:
                # 추가 출력 확인
                time.sleep(2)
                extra_output = self._read_channel()
                self.log_output("추가 대기 후 응답", extra_output)
                
                if "#" in extra_output or ">" in extra_output:
                    self.logger.debug(f"추가 대기 후 로그인 성공: {self.device['ip']}")
                    return True
                else:
                    # 로그인 성공 여부 불확실하지만 계속 진행
                    self.logger.info("프롬프트를 찾을 수 없지만 계속 진행합니다")
                    return True
            
        except Exception as e:
            self.logger.error(f"VForce SSH 연결 실패: {str(e)}")
            if self.session_log_file:
                with open(self.session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\nSSH 연결 실패: {str(e)}\n")
                    log.write(f"상세 정보: {traceback.format_exc()}\n")
                    log.write("-"*50 + "\n")
            raise
    
    def _read_channel(self):
        """채널에서 데이터를 읽어 문자열로 반환합니다."""
        output = ""
        try:
            if self.channel.recv_ready():
                while self.channel.recv_ready():
                    chunk = self.channel.recv(4096)
                    output += chunk.decode('utf-8', 'ignore')
                    time.sleep(0.1)
        except Exception as e:
            self.logger.warning(f"채널 읽기 중 오류: {str(e)}")
        return output
    
    def enable(self):
        """특권 모드 진입 - VForce는 enable 명령어가 필요할 수 있음"""
        self.logger.debug(f"VForce enable 모드 확인: {self.device['ip']}")
        
        # 로그에 기록
        if self.session_log_file:
            with open(self.session_log_file, 'a', encoding='utf-8') as log:
                log.write("\nVForce enable 모드 확인\n")
                log.write("-"*50 + "\n")
                
        # 현재 프롬프트 확인
        try:
            self.channel.send("\n")
            time.sleep(0.5)
            output = self._read_channel()
            
            # '>' 프롬프트이면 enable 모드로 전환 시도
            if ">" in output and "#" not in output:
                self.logger.debug("일반 모드(>)에서 특권 모드(#)로 전환 시도")
                self.channel.send("enable\n")
                time.sleep(1)
                
                # enable 비밀번호 프롬프트 확인
                output = self._read_channel()
                if "Password:" in output:
                    # enable 비밀번호 전송
                    if self.device.get('enable_password'):
                        enable_pwd = self.device['enable_password']
                    else:
                        enable_pwd = self.device['password']
                    
                    self.channel.send(str(enable_pwd) + "\n")
                    time.sleep(1)
                    
                    # 프롬프트 확인
                    output = self._read_channel()
                    if "#" in output:
                        self.logger.debug("특권 모드 전환 성공")
                    else:
                        self.logger.warning("특권 모드 전환 실패")
        except Exception as e:
            self.logger.warning(f"특권 모드 전환 확인 중 오류: {str(e)}")
    
    def send_command(self, command, timeout=None):
        """명령어 실행"""
        if timeout is None:
            timeout = 5  # SSH는 기본 타임아웃을 조금 더 길게 설정
        
        self.log_output(f"명령어 실행: {command}", "")
        
        try:
            # 채널 초기화 (기존 출력 비우기)
            self._read_channel()
            
            # 명령어 전송
            self.channel.send(command + "\n")
            
            # 명령어 실행 결과 대기
            time.sleep(timeout)
            
            # 출력 수집
            output = self._read_channel()
            
            # 명령어 및 프롬프트 제거 로직
            lines = output.splitlines()
            
            # 'show running-config'와 같은 페이징 명령어를 위한 처리
            if '--More--' in output:
                self.logger.debug("페이징 명령어 감지됨, 전체 출력 수집")
                # 스페이스바를 전송하여 다음 페이지 요청
                full_output = output
                max_pages = 50  # 안전을 위한 최대 페이지 수 제한
                
                for _ in range(max_pages):
                    if '--More--' in full_output:
                        # 스페이스바 전송
                        self.channel.send(" ")
                        time.sleep(1)
                        page_output = self._read_channel()
                        full_output += page_output
                    else:
                        break
                
                # 전체 출력을 라인 단위로 분할
                lines = full_output.splitlines()
            
            # 출력 처리
            if len(lines) > 0:
                # 첫 줄은 명령어 자체이거나 빈 줄일 수 있으므로 검사
                if command.strip() in lines[0]:
                    lines = lines[1:]  # 명령어 줄 제거
                
                # 마지막 줄이 프롬프트인지 확인
                if lines and ('#' in lines[-1] or '>' in lines[-1]):
                    lines = lines[:-1]  # 프롬프트 줄 제거
                
                # '--More--' 표시가 있는 줄 정리
                clean_lines = []
                for line in lines:
                    # '--More--' 제거하고 해당 줄의 나머지 부분만 유지
                    if '--More--' in line:
                        clean_line = line.split('--More--')[0].strip()
                        if clean_line:  # 빈 줄이 아니면 추가
                            clean_lines.append(clean_line)
                    else:
                        clean_lines.append(line)
                
                # 정리된 출력 합치기
                cleaned_output = "\n".join(clean_lines)
            else:
                cleaned_output = ""
            
            self.log_output("출력", cleaned_output)
            
            return cleaned_output
        except Exception as e:
            self.logger.error(f"명령어 실행 중 오류: {str(e)}")
            self.log_output("명령어 실행 오류", str(e))
            return f"명령어 실행 오류: {str(e)}"
    
    def disconnect(self):
        """SSH 연결 종료"""
        try:
            if self.channel:
                self.channel.close()
                
            # Transport 종료
            if self.channel and self.channel.get_transport():
                self.channel.get_transport().close()
                
            # 세션 로그 종료
            if self.session_log_file:
                with open(self.session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\n{'='*50}\n")
                    log.write(f"세션 완료 - {datetime.now()}\n")
                    log.write(f"{'='*50}\n\n")
        except Exception as e:
            self.logger.warning(f"연결 종료 중 오류: {str(e)}")


class VForceTelnetHandler(CustomDeviceHandler):
    """NexG VForce 장비 Telnet 핸들러"""
    
    def __init__(self, device, timeout=30, session_log_file=None):
        super().__init__(device, timeout, session_log_file)
        self.tn = None
    
    def connect(self):
        """텔넷으로 장비에 연결"""
        if self.device['connection_type'].lower() != 'telnet':
            raise ValueError("VForceTelnetHandler는 텔넷 연결만 지원합니다")
        
        self.logger.debug(f"VForce 장비 Telnet 접속 시작: {self.device['ip']}")
        
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
        """특권 모드 진입 - NexG VForce도 필요할 수 있음"""
        self.logger.debug(f"VForce enable 모드 확인: {self.device['ip']}")
        
        # 현재 프롬프트 확인
        self.tn.write(b"\n")
        time.sleep(1)
        output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
        
        # '>' 프롬프트이면 enable 모드로 전환 시도
        if ">" in output and "#" not in output:
            self.logger.debug(f"일반 모드(>)에서 특권 모드(#)로 전환 시도")
            self.tn.write(b"enable\n")
            time.sleep(1)
            
            # enable 비밀번호 입력 (있는 경우)
            output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
            if "Password:" in output:
                if self.device.get('enable_password'):
                    self.tn.write(self.device['enable_password'].encode('utf-8') + b"\n")
                else:
                    self.tn.write(self.device['password'].encode('utf-8') + b"\n")
                time.sleep(2)
        
        # 로그에 기록
        if self.session_log_file:
            with open(self.session_log_file, 'a', encoding='utf-8') as log:
                log.write("\nVForce enable 모드 확인 완료\n")
                log.write("-"*50 + "\n")
    
    def send_command(self, command, timeout=None):
        """명령어 실행"""
        if timeout is None:
            timeout = 3  # 기본 타임아웃 값
        
        self.log_output(f"명령어 실행: {command}", "")
        
        self.tn.write(command.encode('utf-8') + b"\n")
        time.sleep(timeout)  # 명령어 실행 결과 기다림
        
        # 출력 수집
        output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
        
        # 'More' 혹은 '--More--' 프롬프트 처리
        full_output = output
        max_pages = 50  # 안전을 위한 최대 페이지 수 제한
        
        for _ in range(max_pages):
            if '--More--' in full_output or ' --More-- ' in full_output:
                # 스페이스바 전송하여 다음 페이지 요청
                self.tn.write(b" ")
                time.sleep(1)
                page_output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
                full_output += page_output
            else:
                break
        
        # 출력 처리 (명령어 줄과 프롬프트 줄 제거)
        lines = full_output.splitlines()
        
        # 출력 처리
        if len(lines) > 1:
            # 첫 줄은 명령어 자체일 가능성이 높음
            if command.strip() in lines[0]:
                lines = lines[1:]
            
            # 마지막 줄은 프롬프트일 가능성이 높음
            if lines and ('#' in lines[-1] or '>' in lines[-1]):
                lines = lines[:-1]
            
            # '--More--' 표시가 있는 줄 정리
            clean_lines = []
            for line in lines:
                # '--More--' 제거하고 해당 줄의 나머지 부분만 유지
                if '--More--' in line or ' --More-- ' in line:
                    clean_line = line.split('--More--')[0].strip()
                    if not clean_line and ' --More-- ' in line:
                        clean_line = line.split(' --More-- ')[0].strip()
                    if clean_line:  # 빈 줄이 아니면 추가
                        clean_lines.append(clean_line)
                else:
                    clean_lines.append(line)
            
            # 정리된 출력 합치기
            cleaned_output = "\n".join(clean_lines)
        else:
            cleaned_output = full_output
        
        self.log_output("출력", cleaned_output)
        
        return cleaned_output
    
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


class CiscoLegacyTelnetHandler(CustomDeviceHandler):
    """Legacy Cisco 장비 Telnet 핸들러 (username 없이 password만 사용)"""
    
    def __init__(self, device, timeout=30, session_log_file=None):
        super().__init__(device, timeout, session_log_file)
        self.tn = None
    
    def connect(self):
        """텔넷으로 장비에 연결"""
        if self.device['connection_type'].lower() != 'telnet':
            raise ValueError("CiscoLegacyTelnetHandler는 텔넷 연결만 지원합니다")
        
        self.logger.debug(f"Legacy Cisco 장비 Telnet 접속 시작: {self.device['ip']}")
        
        self.tn = telnetlib.Telnet(self.device['ip'], port=self.device['port'], timeout=self.timeout)
        
        try:
            # 초기 접속 시 Password: 프롬프트가 나타날 때까지 대기
            index, match, text = self.tn.expect([b"Password:", b"Username:"], timeout=20)
            
            # 초기 출력 로깅
            output = text.decode('utf-8', errors='ignore')
            self.log_output("초기 프롬프트", output)
            
            # Password 프롬프트가 먼저 나온 경우 (username이 필요 없는 경우)
            if index == 0:
                self.tn.write(self.device['password'].encode('utf-8') + b"\n")
                time.sleep(2)
            # Username 프롬프트가 먼저 나온 경우 (일반적인 경우)
            else:
                # username이 제공된 경우에만 사용
                if 'username' in self.device and self.device['username']:
                    self.tn.write(self.device['username'].encode('utf-8') + b"\n")
                    time.sleep(1)
                else:
                    # username이 제공되지 않은 경우 엔터 키 입력
                    self.tn.write(b"\n")
                    time.sleep(1)
                
                # Password 입력
                self.tn.read_until(b"Password:", timeout=10)
                self.tn.write(self.device['password'].encode('utf-8') + b"\n")
                time.sleep(2)
            
            # 로그인 후 출력 확인
            output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
            self.log_output("로그인 후 출력", output)
            
            # 로그인 성공 확인 (프롬프트에 > 또는 # 포함 확인)
            if ">" in output or "#" in output:
                self.logger.debug(f"로그인 성공: {self.device['ip']}")
                return True
            else:
                # 추가 시간 대기 후 다시 확인
                time.sleep(3)
                output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
                
                if ">" in output or "#" in output:
                    self.logger.debug(f"로그인 성공 (추가 대기 후): {self.device['ip']}")
                    return True
                else:
                    self.logger.warning(f"로그인 상태 불확실: {self.device['ip']}")
                    # 계속 진행
                    return True
            
        except Exception as e:
            self.logger.error(f"Legacy Cisco Telnet 접속 실패: {str(e)}")
            if self.session_log_file:
                with open(self.session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\n접속 실패: {str(e)}\n")
            
            # 세션 닫기
            if self.tn:
                self.tn.close()
                self.tn = None
            
            raise
    
    def enable(self):
        """특권 모드 진입"""
        self.logger.debug(f"Legacy Cisco 장비 enable 모드 진입 시도: {self.device['ip']}")
        
        try:
            # 현재 프롬프트 확인
            self.tn.write(b"\n")
            time.sleep(1)
            output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
            
            # enable 모드(#)인지 확인
            if "#" in output:
                self.logger.debug(f"이미 enable 모드 상태: {self.device['ip']}")
                self.log_output("현재 프롬프트 (이미 enable 모드)", output)
                return True
            
            # enable 명령 실행
            self.tn.write(b"enable\n")
            time.sleep(1)
            
            # Password 프롬프트 대기
            index, match, text = self.tn.expect([b"Password:", b"#"], timeout=5)
            
            # Password 프롬프트가 나온 경우
            if index == 0:
                # enable_password가 설정된 경우 해당 값 사용, 아니면 기본 password 사용
                password = self.device.get('enable_password', self.device['password'])
                self.tn.write(password.encode('utf-8') + b"\n")
                time.sleep(2)
            
            # enable 모드 진입 확인
            output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
            self.log_output("enable 명령 실행 후 출력", output)
            
            if "#" in output:
                self.logger.debug(f"enable 모드 진입 성공: {self.device['ip']}")
                
                # terminal length 0 설정
                self.tn.write(b"terminal length 0\n")
                time.sleep(1)
                output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
                self.log_output("terminal length 0 명령 실행 결과", output)
                
                return True
            else:
                self.logger.warning(f"enable 모드 진입 실패: {self.device['ip']}")
                return False
                
        except Exception as e:
            self.logger.error(f"enable 모드 진입 중 오류: {str(e)}")
            return False
    
    def send_command(self, command, timeout=None):
        """명령어 실행"""
        if timeout is None:
            timeout = 5
        
        self.log_output(f"명령어 실행: {command}", "")
        
        try:
            # 명령어 전송
            self.tn.write(command.encode('utf-8') + b"\n")
            time.sleep(timeout)
            
            # 결과 읽기
            output = self.tn.read_very_eager().decode('utf-8', errors='ignore')
            
            # 명령어와 프롬프트 제거 처리
            lines = output.splitlines()
            
            # '--More--' 처리
            full_output = output
            
            while "--More--" in full_output:
                self.tn.write(b" ")  # Space를 보내서 더 보기
                time.sleep(1)
                chunk = self.tn.read_very_eager().decode('utf-8', errors='ignore')
                full_output += chunk
                
                # 무한루프 방지 (일정 크기 이상이면 종료)
                if len(full_output) > 1000000:  # 약 1MB
                    break
            
            # 출력 정리
            lines = full_output.splitlines()
            
            # 첫 줄에 명령어 자체가 있으면 제거
            if lines and command in lines[0]:
                lines = lines[1:]
            
            # 마지막 줄이 프롬프트인 경우 제거
            if lines and (lines[-1].strip().endswith(">") or lines[-1].strip().endswith("#")):
                lines = lines[:-1]
            
            # '--More--' 제거
            cleaned_lines = []
            for line in lines:
                if "--More--" in line:
                    cleaned_line = line.split(more_text)[0].strip()
                    if cleaned_line:
                        cleaned_lines.append(cleaned_line)
                else:
                    cleaned_lines.append(line)
            
            result = "\n".join(cleaned_lines)
            self.log_output("명령어 결과", result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"명령어 실행 실패 ({command}): {str(e)}")
            return f"Error executing command: {str(e)}"
    
    def disconnect(self):
        """연결 종료"""
        if self.tn:
            try:
                self.tn.write(b"exit\n")
                time.sleep(1)
            except:
                pass
            
            try:
                self.tn.close()
            except:
                pass
            
            self.tn = None
            
            if self.session_log_file:
                with open(self.session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\n{'='*50}\n")
                    log.write(f"세션 종료: {datetime.now()}\n")
                    log.write(f"{'='*50}\n")


# 장비 유형에 따른 핸들러 팩토리 함수
def get_custom_handler(device, timeout=10, session_log_file=None):
    """장비 유형에 맞는 커스텀 핸들러 반환"""
    vendor = device.get('vendor', '').lower()
    model = device.get('os', '').lower()
    connection_type = device.get('connection_type', '').lower()
    
    # 유비쿼스 E4020 장비 처리
    if vendor == 'ubiquoss' and model == 'e4020':
        return UbiquossE4020Handler(device, timeout, session_log_file)
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
    
    return None

class AlcatelLucentHandler(CustomDeviceHandler):
    """Alcatel-Lucent 장비 핸들러"""
    
    def __init__(self, device, timeout=30, session_log_file=None):
        super().__init__(device, timeout, session_log_file)
        self.ssh = None
        self.channel = None
        self.prompt = None
    
    def connect(self):
        """SSH로 장비에 연결"""
        self.logger.debug(f"Alcatel-Lucent 장비 SSH 접속 시작: {self.device['ip']}")
        
        try:
            # SSH 클라이언트 초기화
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 연결 설정
            self.ssh.connect(
                hostname=self.device['ip'],
                username=self.device['username'],
                password=self.device['password'],
                port=self.device['port'],
                timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False
            )
            
            # 셸 요청
            self.channel = self.ssh.invoke_shell(width=160, height=1000)
            self.channel.settimeout(self.timeout)
            
            # 초기 출력 처리
            time.sleep(3)
            output = self._read_channel()
            self.log_output("초기 출력", output)
            
            # 프롬프트 확인
            if ">" in output or "#" in output:
                last_line = output.splitlines()[-1] if output.splitlines() else ""
                self.prompt = last_line.strip()
                self.logger.debug(f"프롬프트 설정: {self.prompt}")
            
            # 로그인 성공 확인
            if ">" in output or "#" in output:
                self.logger.debug(f"Alcatel-Lucent SSH 접속 성공: {self.device['ip']}")
                return True
            else:
                self.logger.warning(f"Alcatel-Lucent SSH 접속 상태 불명확: {self.device['ip']}")
                return False
            
        except Exception as e:
            self.logger.error(f"Alcatel-Lucent SSH 접속 실패: {str(e)}")
            if self.session_log_file:
                with open(self.session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\n접속 실패: {str(e)}\n")
                    log.write(traceback.format_exc())
            
            if self.ssh:
                self.ssh.close()
                self.ssh = None
            
            raise
    
    def _read_channel(self):
        """채널에서 출력 읽기"""
        output = ""
        if self.channel:
            while self.channel.recv_ready():
                chunk = self.channel.recv(4096)
                output += chunk.decode('utf-8', errors='ignore')
                if not self.channel.recv_ready():
                    time.sleep(0.1)  # 더 데이터가 오는지 짧게 대기
        return output
    
    def enable(self):
        """특권 모드 진입 - Alcatel은 로그인 후 특별한 enable 명령 필요 없음"""
        self.logger.debug(f"Alcatel-Lucent는 별도의 enable 명령이 필요 없음: {self.device['ip']}")
        
        return True
    
    def send_command(self, command, timeout=None):
        """명령어 실행"""
        if timeout is None:
            timeout = 5
        
        self.log_output(f"명령어 실행: {command}", "")
        
        try:
            # 명령어 전송
            self.channel.send(command + "\n")
            
            # 충분한 시간 대기
            time.sleep(timeout)
            
            # 결과 읽기
            output = self._read_channel()
            
            # 명령어 자체와 프롬프트 제거
            lines = output.splitlines()
            clean_lines = []
            
            # 명령어 라인 건너뛰기
            skip_first = True
            for line in lines:
                if skip_first:
                    if command in line:
                        skip_first = False
                        continue
                    else:
                        skip_first = False
                
                # 마지막 프롬프트 라인 제외
                if ">" in line or "#" in line:
                    if line.strip() == self.prompt:
                        continue
                
                clean_lines.append(line)
            
            # '--More--' 처리
            more_text = "--More--"
            while any(more_text in line for line in clean_lines):
                self.channel.send(" ")  # 스페이스바 전송
                time.sleep(1)
                chunk = self._read_channel()
                
                for line in chunk.splitlines():
                    if line and not more_text in line and not line.strip() == self.prompt:
                        clean_lines.append(line)
            
            # '--More--' 표시 제거
            cleaned_output = []
            for line in clean_lines:
                if more_text in line:
                    cleaned_line = line.split(more_text)[0].strip()
                    if cleaned_line:
                        cleaned_output.append(cleaned_line)
                else:
                    cleaned_output.append(line)
            
            result = "\n".join(cleaned_output)
            self.log_output("명령어 결과", result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"명령어 실행 실패 ({command}): {str(e)}")
            return f"Error executing command: {str(e)}"
    
    def disconnect(self):
        """연결 종료"""
        if self.channel:
            try:
                self.channel.close()
            except:
                pass
        
        if self.ssh:
            try:
                self.ssh.close()
            except:
                pass
            
        self.channel = None
        self.ssh = None
        
        if self.session_log_file:
            with open(self.session_log_file, 'a', encoding='utf-8') as log:
                log.write(f"\n{'='*50}\n")
                log.write(f"세션 종료: {datetime.now()}\n")
                log.write(f"{'='*50}\n")