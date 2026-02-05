"""
Network Device Inspection Tool - Handreamnet Module

Handreamnet 장비의 명령어, 파싱 규칙, 핸들러 클래스를 제공합니다.
지원 OS: nmk, hn
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

import paramiko
from netmiko import ConnectHandler
from netmiko.base_connection import BaseConnection

from vendors.base import CustomDeviceHandler, register_handler

logger = logging.getLogger(__name__)


def parsing_handreamnet_hostname(output: str) -> str:
    """Handreamnet running-config에서 호스트네임 파싱"""
    match = re.search(r"hostname\s+(\S+)", output)
    return match.group(1) if match else ""


def parsing_handreamnet_fan_status(output: str) -> str:
    """Handreamnet 팬 상태 파싱"""
    fan_patterns = [
        r"Fan\s*+is\s*(\w+)",
        r"System\s*+Fan\s*:\s*(\w+)",
        r"Status\s*:\s*(\w+)",
    ]
    for pattern in fan_patterns:
        match = re.search(pattern, output)
        if match:
            return match.group(1)
    return ""


def parsing_handreamnet_temperature(output: str) -> str:
    """Handreamnet 온도 파싱"""
    match = re.search(r"M/B\s*Temp\s*:\s*(\d+\.\d+)", output)
    return match.group(1) if match else ""


def parsing_handreamnet_uptime(output: str) -> str:
    """Handreamnet 업타임 파싱"""
    match = re.search(r"up\s+(.+?),", output)
    return match.group(1) if match else ""


def parsing_handreamnet_cpu_usage(output: str) -> str:
    """Handreamnet CPU 사용량 파싱"""
    match = re.search(r"5\s+sec\s+:\s+([\d.]+)", output)
    return match.group(1) if match else ""


def parsing_handreamnet_memory_usage(output: str) -> str:
    """Handreamnet 메모리 사용량 파싱"""
    used_match = re.search(r"Used\s*:\s*(\d+)\s*kB", output)
    usage_match = re.search(r"Current\s+memory\s+usage\s+:\s+(\d+\.\d+)", output)
    if used_match:
        return used_match.group(1)
    if usage_match:
        return usage_match.group(1)
    return ""


# Handreamnet 장비 점검 명령어 정의
HANDREAMNET_INSPECTION_COMMANDS = {
    "handreamnet": {
        "nmk": [
            "show running-config",
            "show system fan",
            "show system temperature",
            "show system uptime",
            "show system cpu-load",
            "show system memory",
        ],
        "hn": [
            "show running-config | include hostname",
            "show system fan",
            "show system temperature",
            "show system system-info",
            "show system cpu-load",
            "show system memory",
        ],
    }
}

# Handreamnet 장비 설정 백업 명령어 정의
HANDREAMNET_BACKUP_COMMANDS = {
    "handreamnet": {
        "nmk": "show running-config",
        "hn": "show running-config",
    }
}

# Handreamnet 장비 출력 파싱 규칙
HANDREAMNET_PARSING_RULES = {
    "handreamnet": {
        "nmk": {
            "show running-config": {
                "custom_parser": "parsing_handreamnet_hostname",
                "output_column": "Hostname",
            },
            "show system fan": {
                "custom_parser": "parsing_handreamnet_fan_status",
                "output_column": "Fan Status",
            },
            "show system temperature": {
                "custom_parser": "parsing_handreamnet_temperature",
                "output_column": "System Temperature",
            },
            "show system uptime": {
                "custom_parser": "parsing_handreamnet_uptime",
                "output_column": "Uptime",
            },
            "show system cpu-load": {
                "custom_parser": "parsing_handreamnet_cpu_usage",
                "output_column": "CPU Usage",
            },
            "show system memory": {
                "custom_parser": "parsing_handreamnet_memory_usage",
                "output_column": "Memory Usage",
            },
        }
        ,
        "hn": {
            "show running-config | include hostname": {
                "pattern": r"hostname\s+(\S+)",
                "output_column": "Hostname",
                "first_match_only": True,
            },
            "show system fan": {
                "pattern": r"Fan Status\s*:\s*(.+)",
                "output_column": "Fan Status",
                "first_match_only": True,
            },
            "show system temperature": {
                "pattern": r"M/B\s+Temp\s*:\s*(.+)",
                "output_column": "System Temperature",
                "first_match_only": True,
            },
            "show system system-info": {
                "patterns": [
                    {
                        "pattern": r"Model\s*:\s*(\S+)",
                        "output_column": "Model",
                        "first_match_only": True,
                    },
                    {
                        "pattern": r"Serial No\s*:\s*(\S+)",
                        "output_column": "Serial Number",
                        "first_match_only": True,
                    },
                    {
                        "pattern": r"OS Version\s*:\s*(\S+)",
                        "output_column": "Version",
                        "first_match_only": True,
                    },
                    {
                        "pattern": r"Accumulation Time\s*:\s*(.+)",
                        "output_column": "Uptime",
                        "first_match_only": True,
                    },
                ],
            },
            "show system cpu-load": {
                "pattern": r"5 sec\s*:\s*([\d\.]+\s*%)",
                "output_column": "CPU Usage %",
                "first_match_only": True,
            },
            "show system memory": {
                "pattern": r"Current memory usage\s*:\s*([\d\.]+\s*%)",
                "output_column": "Memory Usage %",
                "first_match_only": True,
            },
        },
    }
}


@register_handler("handreamnet", "nmk", "ssh")
class HandreamnetNmkSSHHandler(CustomDeviceHandler):
    """Handreamnet NMK SSH 장비 핸들러 (Netmiko 기반)"""

    def __init__(self, device, timeout: int = 30, session_log_file: Optional[str] = None):
        super().__init__(device, timeout, session_log_file)
        self.conn: Optional[BaseConnection] = None

    def _build_params(self) -> dict:
        enable_password = self.device.get("enable_password") or self.device.get("password")
        params = {
            "device_type": "generic",
            "host": str(self.device["ip"]),
            "username": str(self.device["username"]),
            "password": str(self.device["password"]),
            "port": int(self.device["port"]),
            "secret": str(enable_password or ""),
            "timeout": int(self.timeout),
            "fast_cli": False,
        }
        if self.session_log_file:
            params["session_log"] = str(self.session_log_file)
        return params

    def connect(self) -> bool:
        """SSH로 장비에 연결"""
        if self.device["connection_type"].lower() != "ssh":
            raise ValueError("HandreamnetNmkSSHHandler는 SSH 연결만 지원합니다")

        try:
            self.conn = ConnectHandler(**self._build_params())
            self.logger.debug("Handreamnet NMK 접속 성공: %s", self.device.get("ip"))
            return True
        except Exception as exc:
            self.logger.error("Handreamnet NMK SSH 접속 실패: %s", exc)
            self.conn = None
            raise

    def enable(self) -> None:
        """특권 모드 진입 및 페이지 비활성화"""
        if not self.conn:
            raise ConnectionError("Netmiko 연결이 초기화되지 않았습니다.")
        self.conn.enable()
        output = self.conn.send_command_timing("terminal length 0")
        self.log_output("terminal length 0 명령어 후", output)

    def send_command(self, command: str, timeout: Optional[int] = None) -> str:
        """명령어 실행"""
        if not self.conn:
            raise ConnectionError("Netmiko 연결이 초기화되지 않았습니다.")
        read_timeout = int(timeout or 30)
        self.log_output(f"명령어 실행: {command}", "")
        output = self.conn.send_command(command, read_timeout=read_timeout, strip_command=True, strip_prompt=True)
        self.log_output("정리된 명령어 결과", output)
        return output.strip()

    def disconnect(self) -> None:
        """SSH 연결 종료"""
        if self.conn:
            self.conn.disconnect()
        self.conn = None


@register_handler("handreamnet", "hn", "ssh")
class HandreamnetHnSSHHandler(CustomDeviceHandler):
    """Handreamnet HN SSH 장비 핸들러 (Paramiko 기반)"""

    def __init__(self, device, timeout: int = 30, session_log_file: Optional[str] = None):
        super().__init__(device, timeout, session_log_file)
        self.ssh = None
        self.channel = None
        self.prompt = None

    def connect(self) -> bool:
        """SSH로 장비에 연결"""
        if self.device["connection_type"].lower() != "ssh":
            raise ValueError("HandreamnetHnSSHHandler는 SSH 연결만 지원합니다")

        self.logger.debug("Handreamnet HN 장비 SSH 접속 시작: %s", self.device.get("ip"))

        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(
                hostname=self.device["ip"],
                username=self.device["username"],
                password=self.device["password"],
                port=int(self.device["port"]),
                timeout=self.timeout,
                allow_agent=False,
                look_for_keys=False,
            )
            self.channel = self.ssh.invoke_shell(width=200, height=1000)
            self.channel.settimeout(self.timeout)

            time.sleep(2)
            output = self._read_channel()
            self.log_output("초기 출력", output)

            if ">" in output or "#" in output:
                last_line = output.strip().splitlines()[-1]
                self.prompt = last_line.strip()
                self.logger.debug("Handreamnet HN 접속 성공: %s", self.prompt)
                return True

            raise ConnectionError("Handreamnet HN 접속 실패: 프롬프트를 찾을 수 없습니다.")
        except Exception as exc:
            self.logger.error("Handreamnet HN SSH 접속 실패: %s", exc)
            if self.ssh:
                self.ssh.close()
            raise

    def _read_channel(self) -> str:
        """채널에서 출력 읽기"""
        output = ""
        time.sleep(0.5)
        if self.channel and self.channel.recv_ready():
            while self.channel.recv_ready():
                output += self.channel.recv(65535).decode("utf-8", "ignore")
                time.sleep(0.1)
        return output

    def enable(self) -> None:
        """특권 모드 진입"""
        if not self.channel:
            raise ConnectionError("SSH 채널이 연결되지 않았습니다.")

        self.channel.send("\n")
        time.sleep(0.5)
        output = self._read_channel()
        last_line = output.strip().splitlines()[-1] if output.strip() else ""
        self.prompt = last_line.strip()

        if "#" not in self.prompt and ">" in self.prompt:
            self.channel.send("enable\n")
            time.sleep(1)
            output = self._read_channel()
            self.log_output("enable 명령어 후", output)

            if "Password:" in output:
                enable_password = self.device.get("enable_password", self.device["password"])
                self.channel.send(enable_password + "\n")
                time.sleep(1)
                output = self._read_channel()
                self.log_output("enable 비밀번호 입력 후", output)

        self.channel.send("terminal length 0\n")
        time.sleep(1)
        output = self._read_channel()
        self.log_output("terminal length 0 명령어 후", output)

    def send_command(self, command: str, timeout: Optional[int] = None) -> str:
        """명령어 실행"""
        if not self.channel:
            raise ConnectionError("SSH 채널이 연결되지 않았습니다.")

        if timeout is None:
            timeout = 10

        self.log_output(f"명령어 실행: {command}", "")
        self._read_channel()
        self.channel.send(command + "\n")

        full_output = ""
        time.sleep(2)
        for _ in range(50):
            output_chunk = self._read_channel()
            full_output += output_chunk
            if "--More--" in output_chunk:
                self.channel.send(" ")
                time.sleep(1)
            else:
                break

        lines = full_output.splitlines()
        if not lines:
            return ""
        if command.strip() in lines[0]:
            lines = lines[1:]
        if lines and self.prompt and self.prompt in lines[-1]:
            lines = lines[:-1]

        cleaned_output = "\n".join(lines).strip()
        self.log_output("정리된 명령어 결과", cleaned_output)
        return cleaned_output

    def disconnect(self) -> None:
        """SSH 연결 종료"""
        if self.channel:
            self.channel.close()
        if self.ssh:
            self.ssh.close()
        self.channel = None
        self.ssh = None