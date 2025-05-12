import pandas as pd
import concurrent.futures
import re
from netmiko import ConnectHandler
from typing import Dict, List, Tuple
import os
from datetime import datetime
from device_commands import INSPECTION_COMMANDS, BACKUP_COMMANDS, PARSING_RULES
import threading
import ipaddress
import socket
import time
import logging
from pathlib import Path
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import telnetlib

# Netmiko 디버그 로그 활성화
logging.basicConfig(filename='netmiko_debug.log', level=logging.DEBUG)
# Netmiko 디버그 로거 설정
netmiko_logger = logging.getLogger("netmiko")
netmiko_logger.setLevel(logging.DEBUG)
# 파일 핸들러 추가
file_handler = logging.FileHandler('netmiko_debug.log')
file_handler.setLevel(logging.DEBUG)
# 포맷터 설정 - 쓰레드 정보 추가
formatter = logging.Formatter('%(asctime)s - [%(threadName)s] - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
netmiko_logger.addHandler(file_handler)

class NetworkInspector:
    def __init__(self, input_excel: str, output_excel: str):
        self.input_excel = input_excel
        # 출력 파일명에 타임스탬프 추가
        file_name, file_ext = os.path.splitext(output_excel)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_excel = f"{file_name}_{timestamp}{file_ext}"
        self.max_retries = 3  # 최대 재시도 횟수
        self.timeout = 10  # 연결 타임아웃 (초)
        self.setup_logging()
        # 동일한 타임스탬프 사용
        self.backup_dir = os.path.join("backup", timestamp)
        self.session_log_dir = os.path.join("session_logs", timestamp)
        os.makedirs("backup", exist_ok=True)
        os.makedirs("session_logs", exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.session_log_dir, exist_ok=True)
        self.devices = self._load_devices()
        self.results = []
        self.results_lock = threading.Lock()
        self.log_lock = threading.Lock()
        
    def setup_logging(self):
        """로깅 설정을 초기화합니다."""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"network_inspector_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        # 로그 파일 핸들러 설정 - 쓰레드 식별정보 추가
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s'))
        
        # 로거 설정
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # DEBUG 레벨로 변경
        
        # 기존 핸들러 제거
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 새로운 핸들러 추가
        self.logger.addHandler(file_handler)
        
        # 콘솔 출력을 위한 핸들러 추가 - 쓰레드 식별정보 추가
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s'))
        self.logger.addHandler(console_handler)
        
        self.logger.info("로깅 초기화 완료")
        self.logger.debug(f"로그 파일 경로: {log_file}")

    def _validate_excel_format(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """엑셀 파일 형식을 검증합니다."""
        try:
            self.logger.debug("엑셀 파일 형식 검증 시작")
            required_columns = ['ip', 'vendor', 'model', 'connection_type', 'port', 'username', 'password']
            
            # 빈 데이터프레임 확인
            if df.empty:
                self.logger.error("엑셀 파일이 비어있습니다")
                return False, "엑셀 파일이 비어있습니다"
            
            # 필수 컬럼 확인
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.logger.error(f"필수 컬럼 누락: {', '.join(missing_columns)}")
                return False, f"필수 컬럼 누락: {', '.join(missing_columns)}"
            
            # 데이터 타입 확인
            if not df['port'].apply(lambda x: isinstance(x, (int, float))).all():
                self.logger.error("포트 번호가 숫자가 아닙니다")
                return False, "포트 번호가 숫자가 아닙니다"
            
            # 중복 IP 확인
            if df['ip'].duplicated().any():
                self.logger.error("중복된 IP 주소가 있습니다")
                return False, "중복된 IP 주소가 있습니다"
            
            # 빈 값 확인
            for col in required_columns:
                if df[col].isna().any():
                    self.logger.error(f"컬럼 '{col}'에 빈 값이 있습니다")
                    return False, f"컬럼 '{col}'에 빈 값이 있습니다"
            
            # IP 주소 형식 확인
            invalid_ips = df[~df['ip'].apply(self._validate_ip)]
            if not invalid_ips.empty:
                self.logger.error(f"잘못된 IP 주소 발견: {', '.join(invalid_ips['ip'].tolist())}")
                return False, f"잘못된 IP 주소 발견: {', '.join(invalid_ips['ip'].tolist())}"
            
            # 포트 번호 범위 확인
            invalid_ports = df[~df['port'].apply(lambda x: 1 <= int(x) <= 65535)]
            if not invalid_ports.empty:
                self.logger.error(f"잘못된 포트 번호 발견: {', '.join(invalid_ports['port'].astype(str).tolist())}")
                return False, f"잘못된 포트 번호 발견: {', '.join(invalid_ports['port'].astype(str).tolist())}"
            
            self.logger.debug("엑셀 파일 형식 검증 완료")
            return True, ""
            
        except Exception as e:
            self.logger.error(f"엑셀 파일 형식 검증 중 오류 발생: {str(e)}")
            return False, f"엑셀 파일 형식 검증 중 오류 발생: {str(e)}"

    def _validate_ip(self, ip: str) -> bool:
        """IP 주소 형식을 검증합니다."""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def _validate_port(self, port: int, connection_type: str) -> bool:
        """포트 번호를 검증합니다."""
        if not isinstance(port, (int, str)):
            return False
        try:
            port = int(port)
            if connection_type.lower() == 'ssh':
                return port == 22 or (1024 <= port <= 65535)
            elif connection_type.lower() == 'telnet':
                return port == 23 or (1024 <= port <= 65535)
            return False
        except ValueError:
            return False

    def _validate_connection_type(self, connection_type: str) -> bool:
        """접속 방식을 검증합니다."""
        return connection_type.lower() in ['ssh', 'telnet']

    def _validate_device_info(self, device: Dict) -> Tuple[bool, str]:
        """장비 정보를 검증합니다."""
        self.logger.debug(f"장비 정보 검증 시작: {device['ip']}")
        
        # 필수 필드 확인
        required_fields = ['ip', 'vendor', 'model', 'connection_type', 'port', 'username', 'password']
        for field in required_fields:
            if field not in device or not device[field]:
                self.logger.error(f"필수 필드 누락: {field}")
                return False, f"필수 필드 누락: {field}"

        # 소문자 변환
        vendor = str(device['vendor']).lower()
        model = str(device['model']).lower()

        # IP 주소 검증
        if not self._validate_ip(device['ip']):
            self.logger.error(f"잘못된 IP 주소: {device['ip']}")
            return False, f"잘못된 IP 주소: {device['ip']}"

        # 접속 방식 검증
        if not self._validate_connection_type(device['connection_type']):
            self.logger.error(f"잘못된 접속 방식: {device['connection_type']}")
            return False, f"잘못된 접속 방식: {device['connection_type']}"

        # 포트 번호 검증
        if not self._validate_port(device['port'], device['connection_type']):
            self.logger.error(f"잘못된 포트 번호: {device['port']}")
            return False, f"잘못된 포트 번호: {device['port']}"

        # 벤더/모델 검증
        try:
            if vendor not in INSPECTION_COMMANDS:
                self.logger.error(f"지원하지 않는 벤더: {device['vendor']}")
                return False, f"지원하지 않는 벤더: {device['vendor']}"
            if model not in INSPECTION_COMMANDS[vendor]:
                self.logger.error(f"지원하지 않는 모델: {device['model']}")
                return False, f"지원하지 않는 모델: {device['model']}"
        except KeyError:
            self.logger.error(f"잘못된 장비 구성: {device['vendor']} {device['model']}")
            return False, f"잘못된 장비 구성: {device['vendor']} {device['model']}"

        self.logger.debug(f"장비 정보 검증 완료: {device['ip']}")
        return True, ""

    def _get_device_commands(self, vendor: str, model: str) -> List[str]:
        """장비별 점검 명령어를 가져옵니다."""
        try:
            self.logger.debug(f"장비 명령어 조회 시작: {vendor} {model}")
            v = str(vendor).strip().lower()
            m = str(model).strip().lower()
            cmds = INSPECTION_COMMANDS.get(v, {}).get(m, [])
            if not cmds:
                self.logger.warning(f"점검 명령어를 찾을 수 없음: {v} {m}")
            else:
                self.logger.debug(f"점검 명령어 목록: {cmds}")
            return cmds
        except Exception as e:
            self.logger.error(f"장비 명령어 조회 중 오류 발생: {str(e)}")
            return []
    
    def _get_backup_command(self, vendor: str, model: str) -> str:
        """장비별 백업 명령어를 가져옵니다."""
        try:
            self.logger.debug(f"백업 명령어 조회 시작: {vendor} {model}")
            v = str(vendor).strip().lower()
            m = str(model).strip().lower()
            cmd = BACKUP_COMMANDS.get(v, {}).get(m, '')
            if not cmd:
                self.logger.warning(f"백업 명령어를 찾을 수 없음: {v} {m}")
            else:
                self.logger.debug(f"백업 명령어: {cmd}")
            return cmd
        except Exception as e:
            self.logger.error(f"백업 명령어 조회 중 오류 발생: {str(e)}")
            return ""
    
    def _parse_command_output(self, vendor: str, model: str, command: str, output: str) -> Dict:
        """명령어 출력을 파싱합니다."""
        self.logger.debug(f"명령어 출력 파싱 시작: {command}")
        result = {}
        try:
            rules = PARSING_RULES[vendor.lower()][model.lower()][command]
            pattern = rules['pattern']
            column = rules['output_column']
            
            matches = re.finditer(pattern, output, re.MULTILINE)
            values = [match.group(1) for match in matches]
            result[column] = ', '.join(values)
            self.logger.debug(f"파싱 결과: {result}")
        except (KeyError, AttributeError) as e:
            self.logger.warning(f"파싱 실패: {str(e)}")
        return result
    
    def _test_tcping(self, ip: str, port: int, timeout: int = 5) -> bool:
        """TCP 연결 테스트를 수행합니다."""
        try:
            # 소켓 생성
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            # 연결 시도
            result = sock.connect_ex((ip, port))
            sock.close()
            
            # 연결 성공 시 0 반환
            return result == 0
        except Exception as e:
            self.logger.error(f"TCP 연결 테스트 실패 ({ip}:{port}): {str(e)}")
            return False

    def _connect_to_device(self, device: Dict) -> Tuple[Dict, Dict]:
        """장비에 연결하고 명령어를 실행합니다."""
        # 쓰레드 이름을 장비 IP로 설정하여 로그에서 구분 가능하게 함
        threading.current_thread().name = f"Device-{device['ip']}"
        
        retry_count = 0
        last_error = None
        
        # TCP 연결 테스트 수행
        if not self._test_tcping(device['ip'], device['port']):
            self.logger.error(f"TCP 연결 테스트 실패 ({device['ip']}:{device['port']})")
            return device, {"error": "TCP 연결 테스트 실패"}
        
        # 세션 로그 파일 생성
        session_log_file = os.path.join(
            self.session_log_dir,
            f"{device['ip']}_{device['vendor']}_{device['model']}.log"
        )
        
        while retry_count < self.max_retries:
            try:
                # 세션 로그 시작
                with open(session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\n{'='*50}\n")
                    log.write(f"연결 시도 {retry_count + 1} - {datetime.now()}\n")
                    log.write(f"장비: {device['ip']} ({device['vendor']} {device['model']})\n")
                    log.write(f"{'='*50}\n\n")

                # 장비 타입 설정
                if device['connection_type'].lower() == 'telnet':
                    if device['vendor'].lower() == 'cisco' and device['model'].lower() == 'ios':
                        device_type = 'cisco_ios_telnet'
                    elif device['vendor'].lower() == 'ubiquoss' and device['model'].lower() == 'e4020':
                        # 유비쿼스 장비는 Telnet 접속 시 특별 처리가 필요하므로 generic_telnet 사용
                        device_type = 'generic_telnet'
                    else:
                        device_type = f"{device['vendor']}_{device['model']}_telnet"
                else:
                    if device['vendor'].lower() == 'ubiquoss' and device['model'].lower() == 'e4020':
                        device_type = 'generic'
                    else:
                        device_type = f"{device['vendor']}_{device['model']}"

                # 유비쿼스 E4020 Telnet 접속 특별 처리
                if device['vendor'].lower() == 'ubiquoss' and device['model'].lower() == 'e4020' and device['connection_type'].lower() == 'telnet':
                    self.logger.debug(f"유비쿼스 장비 Telnet 접속 시작: {device['ip']}")
                    
                    # Telnet 직접 구현 (username/password 프롬프트 처리)
                    try:
                        tn = telnetlib.Telnet(device['ip'], port=device['port'], timeout=self.timeout)
                        
                        # Username 입력
                        tn.read_until(b"Username:", timeout=10)
                        tn.write(device['username'].encode('ascii') + b"\n")
                        time.sleep(1)
                        
                        # Password 입력
                        tn.read_until(b"Password:", timeout=10)
                        tn.write(device['password'].encode('ascii') + b"\n")
                        time.sleep(2)
                        
                        # Enable 모드 진입
                        output = tn.read_very_eager().decode('ascii')
                        with open(session_log_file, 'a', encoding='utf-8') as log:
                            log.write(f"로그인 후 출력:\n{output}\n")
                            log.write("-"*50 + "\n")
                        
                        tn.write(b"enable\n")
                        time.sleep(1)
                        
                        # Enable 비밀번호 입력 (있는 경우)
                        if device.get('enable_password'):
                            tn.read_until(b"Password:", timeout=10)
                            tn.write(device['enable_password'].encode('ascii') + b"\n")
                            time.sleep(2)
                        
                        # terminal length 0 명령어 실행 (스크롤 없이 전체 출력)
                        tn.write(b"terminal length 0\n")
                        time.sleep(1)
                        output = tn.read_very_eager().decode('ascii')
                        with open(session_log_file, 'a', encoding='utf-8') as log:
                            log.write(f"terminal length 0 명령어 실행 결과:\n{output}\n")
                            log.write("-"*50 + "\n")
                        
                        # 명령어 실행
                        inspection_results = {}
                        commands = self._get_device_commands(
                            device['vendor'],
                            device['model']
                        )
                        
                        for cmd in commands:
                            try:
                                # 명령어 실행 전 로그
                                with open(session_log_file, 'a', encoding='utf-8') as log:
                                    log.write(f"\n명령어 실행: {cmd}\n")
                                    log.write("-"*50 + "\n")
                                
                                # 명령어 실행
                                tn.write(cmd.encode('ascii') + b"\n")
                                time.sleep(3)  # 명령어 실행 결과 기다림
                                output = tn.read_very_eager().decode('ascii')
                                
                                # 명령어 실행 결과 로그
                                with open(session_log_file, 'a', encoding='utf-8') as log:
                                    log.write(f"출력:\n{output}\n")
                                    log.write("-"*50 + "\n")
                                
                                # 결과 파싱
                                parsed = self._parse_command_output(
                                    device['vendor'],
                                    device['model'],
                                    cmd,
                                    output
                                )
                                inspection_results.update(parsed)
                            except Exception as e:
                                self.logger.error(f"명령어 실행 실패 ({cmd} - {device['ip']}): {str(e)}")
                                inspection_results[f"error_{cmd}"] = str(e)
                        
                        # 설정 백업
                        backup_cmd = self._get_backup_command(
                            device['vendor'],
                            device['model']
                        )
                        if backup_cmd:
                            try:
                                # 백업 명령어 실행 전 로그
                                with open(session_log_file, 'a', encoding='utf-8') as log:
                                    log.write(f"\n백업 명령어 실행: {backup_cmd}\n")
                                    log.write("-"*50 + "\n")
                                
                                # 백업 명령어 실행
                                tn.write(backup_cmd.encode('ascii') + b"\n")
                                time.sleep(10)  # 백업 명령어는 더 긴 시간 기다림
                                backup_output = tn.read_very_eager().decode('ascii')
                                
                                # 백업 명령어 실행 결과 로그
                                with open(session_log_file, 'a', encoding='utf-8') as log:
                                    log.write(f"백업 출력:\n{backup_output}\n")
                                    log.write("-"*50 + "\n")
                                
                                # 백업 파일 저장
                                backup_filename = os.path.join(
                                    self.backup_dir,
                                    f"{device['ip']}_{device['vendor']}_{device['model']}.txt"
                                )
                                with open(backup_filename, 'w', encoding='utf-8') as f:
                                    f.write(backup_output)
                                self.logger.info(f"백업 파일 저장 완료: {backup_filename}")
                            except Exception as e:
                                self.logger.error(f"백업 실패 ({device['ip']}): {str(e)}")
                                inspection_results["backup_error"] = str(e)
                        
                        # 세션 종료
                        tn.write(b"exit\n")
                        tn.close()
                        
                        # 세션 로그 종료
                        with open(session_log_file, 'a', encoding='utf-8') as log:
                            log.write(f"\n{'='*50}\n")
                            log.write(f"세션 완료 - {datetime.now()}\n")
                            log.write(f"{'='*50}\n\n")
                        
                        return device, inspection_results
                    
                    except Exception as e:
                        self.logger.error(f"유비쿼스 Telnet 접속 실패 ({device['ip']}): {str(e)}")
                        retry_count += 1
                        last_error = e
                        
                        # 실패 로그 기록
                        with open(session_log_file, 'a', encoding='utf-8') as log:
                            log.write(f"\n{'='*50}\n")
                            log.write(f"유비쿼스 Telnet 접속 실패 ({retry_count}) - {datetime.now()}\n")
                            log.write(f"오류: {str(e)}\n")
                            log.write(f"{'='*50}\n\n")
                        
                        if retry_count < self.max_retries:
                            time.sleep(2 ** retry_count)  # 지수 백오프
                            continue
                        else:
                            return device, {"error": f"유비쿼스 Telnet 접속 실패: {str(e)}"}

                # 일반 장비 접속 (Netmiko 사용)
                connection_params = {
                    'device_type': device_type,
                    'host': device['ip'],
                    'username': device['username'],
                    'password': device['password'],
                    'port': device['port'],
                    'secret': device.get('enable_password', ''),
                    'timeout': self.timeout,
                    'session_log': session_log_file,
                    'fast_cli': False
                }

                with ConnectHandler(**connection_params) as conn:
                    # Ubiquoss E4020의 경우 프롬프트 패턴 지정 (SSH 접속 시)
                    if device['vendor'].lower() == 'ubiquoss' and device['model'].lower() == 'e4020' and device['connection_type'].lower() == 'ssh':
                        conn.expect_string = r'[>#]'
                    
                    # enable 모드 진입
                    try:
                        if device['vendor'].lower() == 'ubiquoss' and device['connection_type'].lower() == 'ssh':
                            # 로그인 후 프롬프트 대기
                            prompt = conn.find_prompt()
                            self.logger.debug(f"초기 프롬프트: {prompt}")
                            
                            if device.get('enable_password'):
                                enable_pwd = device['enable_password'].strip()
                                time.sleep(1)
                                output = conn.send_command_timing('enable')
                                time.sleep(1)
                                output = conn.send_command_timing(enable_pwd + '\n')
                                time.sleep(1)
                                prompt = conn.find_prompt()
                                if prompt.strip().endswith('#'):
                                    self.logger.info(f"Enable 모드 진입 성공 ({device['ip']})")
                                    # enable 모드 진입 성공 시 terminal length 0 실행
                                    output = conn.send_command_timing('terminal length 0')
                                    self.logger.debug(f"terminal length 0 명령어 실행 결과: {output}")
                                else:
                                    self.logger.warning(f"Enable 모드 진입 실패 ({device['ip']})")
                            else:
                                self.logger.debug(f"Enable 비밀번호가 설정되지 않음 ({device['ip']})")
                        else:
                            conn.enable()
                            # 다른 장비도 terminal length 0 실행
                            conn.send_command_timing('terminal length 0')
                    except Exception as e:
                        self.logger.warning(f"Enable 모드 진입 실패 ({device['ip']}): {str(e)}")
                        self.logger.debug(f"예외 상세: {traceback.format_exc()}")
                    
                    # 점검 명령어 실행
                    inspection_results = {}
                    commands = self._get_device_commands(
                        device['vendor'],
                        device['model']
                    )
                    
                    for cmd in commands:
                        try:
                            # 명령어 실행 전 로그
                            with open(session_log_file, 'a', encoding='utf-8') as log:
                                log.write(f"\n명령어 실행: {cmd}\n")
                                log.write("-"*50 + "\n")
                            
                            # 명령어 실행
                            output = conn.send_command(cmd, read_timeout=30)
                            
                            # 명령어 실행 결과 로그
                            with open(session_log_file, 'a', encoding='utf-8') as log:
                                log.write(f"출력:\n{output}\n")
                                log.write("-"*50 + "\n")
                            
                            # 결과 파싱
                            parsed = self._parse_command_output(
                                device['vendor'],
                                device['model'],
                                cmd,
                                output
                            )
                            inspection_results.update(parsed)
                        except Exception as e:
                            self.logger.error(f"명령어 실행 실패 ({cmd} - {device['ip']}): {str(e)}")
                            inspection_results[f"error_{cmd}"] = str(e)
                    
                    # 설정 백업
                    backup_cmd = self._get_backup_command(
                        device['vendor'],
                        device['model']
                    )
                    if backup_cmd:
                        try:
                            # 백업 명령어 실행 전 로그
                            with open(session_log_file, 'a', encoding='utf-8') as log:
                                log.write(f"\n백업 명령어 실행: {backup_cmd}\n")
                                log.write("-"*50 + "\n")
                            
                            # 백업 명령어 실행
                            backup_output = conn.send_command(backup_cmd, read_timeout=60)
                            
                            # 백업 명령어 실행 결과 로그
                            with open(session_log_file, 'a', encoding='utf-8') as log:
                                log.write(f"백업 출력:\n{backup_output}\n")
                                log.write("-"*50 + "\n")
                            
                            # 백업 파일 저장
                            backup_filename = os.path.join(
                                self.backup_dir,
                                f"{device['ip']}_{device['vendor']}_{device['model']}.txt"
                            )
                            with open(backup_filename, 'w', encoding='utf-8') as f:
                                f.write(backup_output)
                            self.logger.info(f"백업 파일 저장 완료: {backup_filename}")
                        except Exception as e:
                            self.logger.error(f"백업 실패 ({device['ip']}): {str(e)}")
                            inspection_results["backup_error"] = str(e)
                    
                    # 세션 로그 종료
                    with open(session_log_file, 'a', encoding='utf-8') as log:
                        log.write(f"\n{'='*50}\n")
                        log.write(f"세션 완료 - {datetime.now()}\n")
                        log.write(f"{'='*50}\n\n")
                    
                    return device, inspection_results
                    
            except Exception as e:
                last_error = e
                retry_count += 1
                self.logger.warning(f"연결 시도 {retry_count} 실패 ({device['ip']}): {str(e)}")
                
                # 실패 로그 기록
                with open(session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\n{'='*50}\n")
                    log.write(f"연결 시도 {retry_count} 실패 - {datetime.now()}\n")
                    log.write(f"오류: {str(e)}\n")
                    log.write(f"{'='*50}\n\n")
                
                if retry_count < self.max_retries:
                    time.sleep(2 ** retry_count)  # 지수 백오프
                else:
                    # 최종 실패 로그 기록
                    with open(session_log_file, 'a', encoding='utf-8') as log:
                        log.write(f"\n{'='*50}\n")
                        log.write(f"모든 연결 시도 실패 - {datetime.now()}\n")
                        log.write(f"마지막 오류: {str(last_error)}\n")
                        log.write("스택 트레이스:\n")
                        log.write(traceback.format_exc())
                        log.write(f"\n{'='*50}\n\n")
                    
                    self.logger.error(f"연결 실패 ({device['ip']} - {retry_count}회 시도)")
                    return device, {"error": str(e)}

    def _load_devices(self) -> List[Dict]:
        """엑셀 파일에서 장비 정보를 로드하고 검증합니다."""
        try:
            # 엑셀 파일 존재 확인
            if not Path(self.input_excel).exists():
                raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {self.input_excel}")

            # 엑셀 파일 읽기 (칼럼 이름을 소문자로 변환)
            df = pd.read_excel(self.input_excel)
            df.columns = df.columns.str.lower()
            
            # 엑셀 형식 검증
            is_valid, error_message = self._validate_excel_format(df)
            if not is_valid:
                raise ValueError(f"잘못된 엑셀 형식: {error_message}")

            # 필요한 칼럼만 선택하고 순서 재정렬
            required_columns = ['ip', 'vendor', 'model', 'connection_type', 'port', 'username', 'password', 'enable_password']
            df = df[required_columns]
            
            devices = df.to_dict('records')
            valid_devices = []
            invalid_devices = []

            for device in devices:
                is_valid, error_message = self._validate_device_info(device)
                if is_valid:
                    valid_devices.append(device)
                else:
                    invalid_devices.append({
                        'device': device,
                        'error': error_message
                    })

            # 잘못된 장비 정보 로그 저장
            if invalid_devices:
                error_log_dir = os.path.join(self.session_log_dir, "validation_errors")
                os.makedirs(error_log_dir, exist_ok=True)
                error_log = os.path.join(error_log_dir, "invalid_devices.log")
                with open(error_log, 'w', encoding='utf-8') as f:
                    f.write("잘못된 장비 정보:\n")
                    f.write("="*50 + "\n")
                    for invalid in invalid_devices:
                        f.write(f"장비: {invalid['device']}\n")
                        f.write(f"오류: {invalid['error']}\n")
                        f.write("-"*30 + "\n")

            if not valid_devices:
                raise ValueError("입력 파일에서 유효한 장비를 찾을 수 없습니다")

            return valid_devices

        except Exception as e:
            self.logger.error(f"장비 정보 로드 중 오류 발생: {str(e)}")
            raise ValueError(f"장비 정보 로드 중 오류 발생: {str(e)}")
    
    def inspect_devices(self):
        """모든 장비를 점검합니다."""
        try:
            # 장비 수에 따라 최대 쓰레드 수 제한 (CPU 코어 수의 2배 이내로 제한)
            max_workers = min(len(self.devices), os.cpu_count() * 2 or 8)
            self.logger.info(f"멀티쓰레드 작업 시작: 장비 {len(self.devices)}개, 최대 쓰레드 {max_workers}개")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 병렬 처리를 위한 future 생성
                future_to_device = {
                    executor.submit(self._connect_to_device, device): device
                    for device in self.devices
                }
                
                # 완료된 작업 처리
                completed = 0
                total = len(future_to_device)
                
                for future in as_completed(future_to_device):
                    try:
                        device, results = future.result()
                        with self.results_lock:
                            self.results.append({
                                'IP': device['ip'],
                                'Vendor': device['vendor'],
                                'Model': device['model'],
                                **results
                            })
                        
                        # 진행 상황 업데이트
                        completed += 1
                        with self.log_lock:
                            self.logger.info(f"진행 상황: {completed}/{total} (IP: {device['ip']} 완료)")
                    except Exception as e:
                        self.logger.error(f"장비 처리 중 오류 발생 ({future_to_device[future]['ip']}): {str(e)}")
                        with self.results_lock:
                            self.results.append({
                                'IP': future_to_device[future]['ip'],
                                'Vendor': future_to_device[future]['vendor'],
                                'Model': future_to_device[future]['model'],
                                'error': str(e)
                            })
                        
                        # 실패 상황 업데이트
                        completed += 1
                        with self.log_lock:
                            self.logger.info(f"진행 상황: {completed}/{total} (IP: {future_to_device[future]['ip']} 실패)")
            
            self.logger.info(f"멀티쓰레드 작업 완료: 총 {len(self.results)}개 장비 처리됨")
        except Exception as e:
            self.logger.error(f"장비 점검 중 오류 발생: {str(e)}")
            raise

    def save_results(self):
        """결과를 엑셀 파일에 저장합니다."""
        try:
            df = pd.DataFrame(self.results)
            
            # 결과 파일 저장 (이미 타임스탬프가 포함되어 있음)
            df.to_excel(self.output_excel, index=False)
            self.logger.info(f"결과가 저장되었습니다: {self.output_excel}")
        except Exception as e:
            self.logger.error(f"결과 저장 중 오류 발생: {str(e)}")
            raise

def main():
    try:
        input_excel = "devices.xlsx"  # 입력 엑셀 파일
        output_excel = "inspection_results.xlsx"  # 기본 출력 엑셀 파일명 (타임스탬프는 클래스 내부에서 추가됨)
        
        inspector = NetworkInspector(input_excel, output_excel)
        inspector.inspect_devices()
        inspector.save_results()
        
    except Exception as e:
        logging.error(f"프로그램 실행 실패: {str(e)}")
        logging.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 