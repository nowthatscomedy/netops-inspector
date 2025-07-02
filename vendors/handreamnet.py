"""
Network Device Inspection Tool - Handreamnet Module

Handreamnet 장비의 명령어, 파싱 규칙, 핸들러 클래스를 제공합니다.
지원 OS: hn
"""

import time
import logging
import paramiko
import re
from vendors.base import CustomDeviceHandler, register_handler

logger = logging.getLogger(__name__)

# Handreamnet 장비 점검 명령어 정의
HANDREAMNET_INSPECTION_COMMANDS = {
    'handreamnet': {
        'hn': [
            'show running-config | include hostname',
            'show system fan',
            'show system temperature',
            'show system system-info',
            'show system cpu-load',
            'show system memory',
        ]
    }
}

# Handreamnet 장비 설정 백업 명령어 정의
HANDREAMNET_BACKUP_COMMANDS = {
    'handreamnet': {
        'hn': 'show running-config'
    }
}

# Handreamnet 장비 출력 파싱 규칙
HANDREAMNET_PARSING_RULES = {
    'handreamnet': {
        'hn': {
            'show running-config | include hostname': {
                'pattern': r'hostname\s+(\S+)',
                'output_column': 'Hostname',
                'first_match_only': True
            },
            'show system fan': {
                'pattern': r'Fan Status\s*:\s*(.+)',
                'output_column': 'Fan Status',
                'first_match_only': True
            },
            'show system temperature': {
                'pattern': r"M/B\s+Temp\s*:\s*(.+)",
                'output_column': 'System Temperature',
                'first_match_only': True
            },
            'show system system-info': {
                'patterns': [
                    {
                        'pattern': r'Model\s*:\s*(\S+)',
                        'output_column': 'Model',
                        'first_match_only': True
                    },
                    {
                        'pattern': r'Serial No\s*:\s*(\S+)',
                        'output_column': 'Serial Number',
                        'first_match_only': True
                    },
                    {
                        'pattern': r'OS Version\s*:\s*(\S+)',
                        'output_column': 'Version',
                        'first_match_only': True
                    },
                    {
                        'pattern': r'Accumulation Time\s*:\s*(.+)',
                        'output_column': 'Uptime',
                        'first_match_only': True
                    }
                ]
            },
            'show system cpu-load': {
                'pattern': r'5 sec\s*:\s*([\d\.]+\s*%)',
                'output_column': 'CPU Usage %',
                'first_match_only': True
            },
            'show system memory': {
                'pattern': r'Current memory usage\s*:\s*([\d\.]+\s*%)',
                'output_column': 'Memory Usage %',
                'first_match_only': True
            }
        }
    }
}


@register_handler('handreamnet', 'hn', 'ssh')
class HandreamnetHnSSHHandler(CustomDeviceHandler):
    """Handreamnet HN SSH 장비 핸들러"""

    def __init__(self, device, timeout=30, session_log_file=None):
        super().__init__(device, timeout, session_log_file)
        self.ssh = None
        self.channel = None
        self.prompt = None

    def connect(self):
        """SSH로 장비에 연결"""
        if self.device['connection_type'].lower() != 'ssh':
            raise ValueError("HandreamnetHnSSHHandler는 SSH 연결만 지원합니다")

        self.logger.debug(f"Handreamnet HN 장비 SSH 접속 시작: {self.device['ip']}")

        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            self.ssh.connect(
                hostname=self.device['ip'],
                username=self.device['username'],
                password=self.device['password'],
                port=int(self.device['port']),
                timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False
            )

            self.channel = self.ssh.invoke_shell(width=200, height=1000)
            self.channel.settimeout(self.timeout)

            time.sleep(2)
            output = self._read_channel()
            self.log_output("초기 출력", output)

            if ">" in output or "#" in output:
                # Find prompt from the last line
                last_line = output.strip().splitlines()[-1]
                self.prompt = last_line.strip()
                self.logger.debug(f"Handreamnet HN 접속 성공 및 프롬프트 확인: {self.prompt}")
                return True
            else:
                self.logger.error("Handreamnet HN 접속 실패: 프롬프트를 찾을 수 없습니다.")
                raise ConnectionError("Handreamnet HN 접속 실패: 프롬프트를 찾을 수 없습니다.")

        except Exception as e:
            self.logger.error(f"Handreamnet HN SSH 접속 실패: {str(e)}")
            if self.ssh:
                self.ssh.close()
            raise

    def _read_channel(self):
        """채널에서 출력 읽기"""
        output = ""
        time.sleep(0.5)
        if self.channel.recv_ready():
            while self.channel.recv_ready():
                output += self.channel.recv(65535).decode('utf-8', 'ignore')
                time.sleep(0.1)
        return output

    def enable(self):
        """특권 모드 진입"""
        self.logger.debug(f"Handreamnet HN enable 모드 진입 시도: {self.device['ip']}")

        self.channel.send('\n')
        time.sleep(0.5)
        output = self._read_channel()
        last_line = output.strip().splitlines()[-1] if output.strip() else ''
        self.prompt = last_line.strip()

        if "#" in self.prompt:
            self.logger.debug("이미 특권 모드입니다.")
        elif ">" in self.prompt:
            self.channel.send('enable\n')
            time.sleep(1)
            output = self._read_channel()
            self.log_output("enable 명령어 후", output)

            if "Password:" in output:
                enable_password = self.device.get('enable_password', self.device['password'])
                self.channel.send(enable_password + '\n')
                time.sleep(1)
                output = self._read_channel()
                self.log_output("enable 비밀번호 입력 후", output)

            last_line = output.strip().splitlines()[-1] if output.strip() else ''
            if "#" in last_line:
                self.prompt = last_line.strip()
                self.logger.debug(f"특권 모드 진입 성공. 새 프롬프트: {self.prompt}")
            else:
                self.logger.warning("특권 모드 진입에 실패했을 수 있습니다.")

        self.logger.debug("터미널 길이 설정 시도")
        self.channel.send("terminal length 0\n")
        time.sleep(1)
        output = self._read_channel()
        self.log_output("terminal length 0 명령어 후", output)

    def send_command(self, command, timeout=None):
        """명령어 실행"""
        if timeout is None:
            timeout = 10

        if not self.channel:
            raise ConnectionError("SSH 채널이 연결되지 않았습니다.")

        self.log_output(f"명령어 실행: {command}", "")

        self._read_channel() # Clear buffer

        self.channel.send(command + "\n")

        full_output = ""
        time.sleep(2)

        max_pages = 50
        for _ in range(max_pages):
            output_chunk = self._read_channel()
            full_output += output_chunk
            
            if "--More--" in output_chunk:
                self.channel.send(" ")
                time.sleep(1)
            else:
                break
        
        output = full_output
        lines = output.splitlines()

        if not lines:
            return ""

        if command.strip() in lines[0]:
            lines = lines[1:]

        if lines and self.prompt and self.prompt in lines[-1]:
            lines = lines[:-1]

        cleaned_output = "\n".join(lines).strip()
        self.log_output("정리된 명령어 결과", cleaned_output)

        return cleaned_output

    def disconnect(self):
        """SSH 연결 종료"""
        self.logger.debug(f"Handreamnet HN SSH 연결 종료: {self.device['ip']}")
        if self.channel:
            self.channel.close()
        if self.ssh:
            self.ssh.close()

        self.channel = None
        self.ssh = None

        if self.session_log_file:
            with open(self.session_log_file, 'a', encoding='utf-8') as log:
                log.write(f"\n{'='*50}\n")
                log.write(f"세션 종료\n")
                log.write(f"{'='*50}\n\n") 