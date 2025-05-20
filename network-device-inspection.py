import pandas as pd
import concurrent.futures
import re
from netmiko import ConnectHandler
from typing import Dict, List, Tuple
import os
from datetime import datetime
# from vendors import INSPECTION_COMMANDS, BACKUP_COMMANDS, PARSING_RULES # 아래에서 한 번에 임포트
import threading
import ipaddress
import socket
import time
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import telnetlib

# vendors 패키지로부터 필요한 모든 이름들을 한 번에 임포트
from vendors import (
    INSPECTION_COMMANDS,
    BACKUP_COMMANDS,
    PARSING_RULES,
    get_custom_handler,
    parsing_alcatel_hostname,
    parsing_alcatel_temperature,
    parsing_alcatel_fan,
    parsing_alcatel_power,
    parsing_alcatel_uptime,
    parsing_alcatel_version,
    parsing_alcatel_stack,
    parsing_alcatel_cpu,
    parsing_alcatel_memory,
    parsing_axgate_power_status,
    parsing_ubiquoss_cpu_usage,
    parsing_ubiquoss_fan_status,
    parsing_ubiquoss_power_status
)

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
    def __init__(self, input_excel: str, output_excel: str, backup_only: bool = False, inspection_only: bool = False):
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
        
        # 세션 로그 디렉토리는 항상 생성
        os.makedirs("session_logs", exist_ok=True)
        os.makedirs(self.session_log_dir, exist_ok=True)
        
        # 백업만 하거나 점검과 백업을 모두 할 경우에만 백업 디렉토리 생성
        if not inspection_only:
            os.makedirs("backup", exist_ok=True)
            os.makedirs(self.backup_dir, exist_ok=True)
            
        self.backup_only = backup_only
        self.inspection_only = inspection_only
        
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
            # 필수 컬럼 리스트도 소문자로 통일
            required_columns = ['ip', 'vendor', 'os', 'connection_type', 'port', 'password']
            
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
        required_fields = ['ip', 'vendor', 'os', 'connection_type', 'port', 'password']
        for field in required_fields:
            if field not in device or not device[field]:
                self.logger.error(f"필수 필드 누락: {field}")
                return False, f"필수 필드 누락: {field}"

        # 소문자 변환
        vendor = str(device['vendor']).lower()
        model = str(device['os']).lower()

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
                self.logger.error(f"지원하지 않는 모델: {device['os']}")
                return False, f"지원하지 않는 모델: {device['os']}"
        except KeyError:
            self.logger.error(f"잘못된 장비 구성: {device['vendor']} {device['os']}")
            return False, f"잘못된 장비 구성: {device['vendor']} {device['os']}"

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
        
        # 먼저 해당 벤더/모델/명령어에 대한 파싱 규칙이 존재하는지 확인
        vendor_lower = str(vendor).lower()
        model_lower = str(model).lower()
        
        # PARSING_RULES에 해당 벤더가 없는 경우
        if vendor_lower not in PARSING_RULES:
            self.logger.debug(f"파싱 규칙 없음 (벤더): {vendor}")
            return result
            
        # PARSING_RULES에 해당 모델이 없는 경우
        if model_lower not in PARSING_RULES[vendor_lower]:
            self.logger.debug(f"파싱 규칙 없음 (모델): {model}")
            return result
            
        # PARSING_RULES에 해당 명령어가 없는 경우
        if command not in PARSING_RULES[vendor_lower][model_lower]:
            self.logger.debug(f"파싱 규칙 없음 (명령어): {command}")
            return result
        
        try:
            rules = PARSING_RULES[vendor_lower][model_lower][command]
            
            # 커스텀 파서 함수 호출 처리
            if 'custom_parser' in rules:
                parser_name = rules['custom_parser']
                column = rules['output_column']
                
                # Alcatel-Lucent 장비 파서 함수 호출
                if parser_name == 'parsing_alcatel_hostname':
                    result[column] = parsing_alcatel_hostname(output)
                elif parser_name == 'parsing_alcatel_temperature':
                    result[column] = parsing_alcatel_temperature(output)
                elif parser_name == 'parsing_alcatel_fan':
                    result[column] = parsing_alcatel_fan(output)
                elif parser_name == 'parsing_alcatel_power':
                    result[column] = parsing_alcatel_power(output)
                elif parser_name == 'parsing_alcatel_uptime':
                    result[column] = parsing_alcatel_uptime(output)
                elif parser_name == 'parsing_alcatel_version':
                    result[column] = parsing_alcatel_version(output)
                elif parser_name == 'parsing_alcatel_stack':
                    result[column] = parsing_alcatel_stack(output)
                elif parser_name == 'parsing_alcatel_cpu':
                    result[column] = parsing_alcatel_cpu(output)
                elif parser_name == 'parsing_alcatel_memory':
                    result[column] = parsing_alcatel_memory(output)
                # Ubiquoss 커스텀 파서 호출 로직 추가
                elif parser_name == 'parsing_ubiquoss_cpu_usage':
                    result[column] = parsing_ubiquoss_cpu_usage(output)
                elif parser_name == 'parsing_ubiquoss_fan_status':
                    result[column] = parsing_ubiquoss_fan_status(output)
                elif parser_name == 'parsing_ubiquoss_power_status':
                    result[column] = parsing_ubiquoss_power_status(output)
                # Axgate 커스텀 파서 호출 로직 추가
                elif parser_name == 'parsing_axgate_power_status':
                    result[column] = parsing_axgate_power_status(output)
                    
            # 단일 패턴인 경우
            elif 'pattern' in rules:
                pattern = rules['pattern']
                column = rules['output_column']
                matches = re.finditer(pattern, output, re.MULTILINE)
                values = [match.group(1) for match in matches]
                
                # first_match_only 옵션이 있으면 첫 번째 매치만 사용
                if rules.get('first_match_only', False) and values:
                    result[column] = values[0]
                else:
                    result[column] = ', '.join(values)
            # 여러 패턴인 경우
            elif 'patterns' in rules:
                for pattern_rule in rules['patterns']:
                    # 패턴별 커스텀 파서 처리
                    if 'custom_parser' in pattern_rule:
                        parser_name = pattern_rule['custom_parser']
                        column = pattern_rule['output_column']
                        
                        # Alcatel-Lucent 장비 파서 함수 호출
                        if parser_name == 'parsing_alcatel_hostname':
                            result[column] = parsing_alcatel_hostname(output)
                        elif parser_name == 'parsing_alcatel_temperature':
                            result[column] = parsing_alcatel_temperature(output)
                        elif parser_name == 'parsing_alcatel_fan':
                            result[column] = parsing_alcatel_fan(output)
                        elif parser_name == 'parsing_alcatel_power':
                            result[column] = parsing_alcatel_power(output)
                        elif parser_name == 'parsing_alcatel_uptime':
                            result[column] = parsing_alcatel_uptime(output)
                        elif parser_name == 'parsing_alcatel_version':
                            result[column] = parsing_alcatel_version(output)
                        elif parser_name == 'parsing_alcatel_stack':
                            result[column] = parsing_alcatel_stack(output)
                        elif parser_name == 'parsing_alcatel_cpu':
                            result[column] = parsing_alcatel_cpu(output)
                        elif parser_name == 'parsing_alcatel_memory':
                            result[column] = parsing_alcatel_memory(output)
                        # Ubiquoss 커스텀 파서 호출 로직 추가 (patterns 내부)
                        elif parser_name == 'parsing_ubiquoss_cpu_usage':
                            result[column] = parsing_ubiquoss_cpu_usage(output)
                        elif parser_name == 'parsing_ubiquoss_fan_status':
                            result[column] = parsing_ubiquoss_fan_status(output)
                        elif parser_name == 'parsing_ubiquoss_power_status':
                            result[column] = parsing_ubiquoss_power_status(output)
                        # Axgate 커스텀 파서 호출 로직 추가 (patterns 내부)
                        elif parser_name == 'parsing_axgate_power_status':
                            result[column] = parsing_axgate_power_status(output)
                        continue
                        
                    pattern = pattern_rule['pattern']
                    matches = list(re.finditer(pattern, output, re.MULTILINE))
                    
                    # 매치가 없으면 건너뛰기
                    if not matches:
                        continue
                    
                    # 여러 컬럼에 매핑하는 경우 (그룹이 여러 개)
                    if 'output_columns' in pattern_rule and matches:
                        columns = pattern_rule['output_columns']
                        for i, col in enumerate(columns):
                            # 인덱스는 1부터 시작 (그룹 0은 전체 매치)
                            group_idx = i + 1
                            if group_idx < len(matches[0].groups()) + 1:
                                result[col] = matches[0].group(group_idx)
                        
                        # 추가 처리 로직 (CPU 및 메모리 사용량 계산)
                        if 'process' in pattern_rule: # 'process' 키가 있는지 먼저 확인
                            process_info = pattern_rule['process'] # 'process' 정보를 가져옴
                            
                            # 'percentage' 타입 처리
                            if process_info['type'] == 'percentage':
                                # 'inputs' 키와 해당 컬럼들이 result에 있는지 확인
                                if 'inputs' in process_info and all(col in result for col in process_info['inputs']):
                                    inputs = process_info['inputs']
                                    try:
                                        numerator = float(result[inputs[0]])
                                        denominator = float(result[inputs[1]])
                                        if denominator > 0:
                                            percentage = round((numerator / denominator) * 100, 2)
                                            result[process_info['output_column']] = f"{percentage}%"
                                        else:
                                            self.logger.warning(f"분모가 0입니다: {inputs[1]} (명령어: {command})")
                                    except (ValueError, TypeError) as e:
                                        self.logger.warning(f"백분율 계산 실패: {str(e)} (명령어: {command})")
                                else:
                                    self.logger.warning(f"'percentage' process: 'inputs' 키가 없거나, result에 해당 컬럼이 없습니다. (명령어: {command})")

                            # 'calculate_usage_from_available' 타입 처리
                            elif process_info['type'] == 'calculate_usage_from_available':
                                if 'input_column' in process_info: # 'input_column' 키가 있는지 확인
                                    input_col = process_info['input_column']
                                    output_col = process_info['output_column']
                                    if input_col in result:
                                        try:
                                            available_percent_str = result[input_col].replace('%', '')
                                            available_percent = float(available_percent_str)
                                            usage_percent = round(100.0 - available_percent, 2)
                                            result[output_col] = f"{usage_percent}%"
                                            # 성공적으로 'Memory Usage %'를 계산한 후, 원본 'Memory Available %' 컬럼 삭제
                                            if input_col in result: # 삭제 전 한 번 더 확인 (이론상 항상 있어야 함)
                                                del result[input_col]
                                        except ValueError:
                                            self.logger.warning(f"사용 가능한 메모리 백분율 계산 실패: {result[input_col]} (명령어: {command})")
                                    else:
                                        self.logger.warning(f"'calculate_usage_from_available' process: 입력 컬럼 '{input_col}'을 result에서 찾을 수 없습니다. (명령어: {command})")
                                else:
                                    self.logger.warning(f"'calculate_usage_from_available' process: 'input_column' 키가 없습니다. (명령어: {command})")
                    # 단일 컬럼에 매핑하는 경우
                    elif 'output_column' in pattern_rule and matches:
                        column = pattern_rule['output_column']
                        values = [match.group(1) for match in matches]
                        
                        # first_match_only 옵션이 있으면 첫 번째 매치만 사용
                        if pattern_rule.get('first_match_only', False) and values:
                            result[column] = values[0]
                        else:
                            result[column] = ', '.join(values)
            else:
                # 패턴이 없는 경우 전체 출력을 그대로 사용
                if 'output_column' in rules:
                    result[rules['output_column']] = output.strip()
                
            self.logger.debug(f"파싱 결과: {result}")
        except (KeyError, AttributeError) as e:
            self.logger.warning(f"파싱 실패: {str(e)}")
            self.logger.debug(f"파싱 실패 예외 상세: {traceback.format_exc()}")
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

    def _connect_to_device(self, device: Dict, inspection_mode: bool = True, backup_mode: bool = True) -> Tuple[Dict, Dict]:
        """장비에 연결하고 명령어를 실행합니다.
        
        Args:
            device: 장비 정보
            inspection_mode: 점검 명령어 실행 여부
            backup_mode: 백업 명령어 실행 여부
            
        Returns:
            Tuple[Dict, Dict]: (장비 정보, 점검/백업 결과)
        """
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
            f"{device['ip']}_{device['vendor']}_{device['os']}.log"
        )
        
        while retry_count < self.max_retries:
            try:
                # 세션 로그 시작
                with open(session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\n{'='*50}\n")
                    log.write(f"연결 시도 {retry_count + 1} - {datetime.now()}\n")
                    log.write(f"장비: {device['ip']} ({device['vendor']} {device['os']})\n")
                    log.write(f"{'='*50}\n\n")

                # 장비 타입 설정
                if device['connection_type'].lower() == 'telnet':
                    if device['vendor'].lower() == 'cisco' and device['os'].lower() == 'ios':
                        device_type = 'cisco_ios_telnet'
                    elif device['vendor'].lower() == 'ubiquoss' and device['os'].lower() == 'e4020':
                        # 유비쿼스 장비는 Telnet 접속 시 특별 처리가 필요하므로 generic_telnet 사용
                        device_type = 'generic_telnet'
                    elif device['vendor'].lower() == 'axgate' and device['os'].lower() == 'axgate':
                        device_type = 'generic'
                    else:
                        device_type = f"{str(device['vendor']).lower()}_{str(device['os']).lower()}_telnet"
                else:
                    if device['vendor'].lower() == 'ubiquoss' and device['os'].lower() == 'e4020':
                        device_type = 'generic'
                    elif device['vendor'].lower() == 'axgate' and device['os'].lower() == 'axgate':
                        device_type = 'generic'
                    elif device['vendor'].lower() == 'juniper':
                        # Juniper 장비는 'juniper_junos' device_type 사용
                        device_type = 'juniper_junos'
                    else:
                        device_type = f"{str(device['vendor']).lower()}_{str(device['os']).lower()}"

                # 커스텀 핸들러 사용 시도
                custom_handler = get_custom_handler(device, self.timeout, session_log_file)
                if custom_handler:
                    self.logger.debug(f"커스텀 핸들러 사용: {device['vendor']} {device['os']}")
                    try:
                        # 연결 및 특권 모드 진입
                        custom_handler.connect()
                        custom_handler.enable()
                        
                        inspection_results = {}
                        
                        # 점검 모드일 경우 점검 명령어 실행
                        if inspection_mode:
                            # 점검 명령어 실행
                            commands = self._get_device_commands(
                                device['vendor'],
                                device['os']
                            )
                            
                            for cmd in commands:
                                try:
                                    # 명령어 실행
                                    output = custom_handler.send_command(cmd)
                                    
                                    # 결과 파싱
                                    parsed = self._parse_command_output(
                                        device['vendor'],
                                        device['os'],
                                        cmd,
                                        output
                                    )
                                    inspection_results.update(parsed)
                                except Exception as e:
                                    self.logger.error(f"명령어 실행 실패 ({cmd} - {device['ip']}): {str(e)}")
                                    inspection_results[f"error_{cmd}"] = str(e)
                        
                        # 백업 모드일 경우에만 백업 명령어 실행
                        if backup_mode:
                            # 설정 백업
                            backup_cmd = self._get_backup_command(
                                device['vendor'],
                                device['os']
                            )
                            if backup_cmd:
                                try:
                                    # 백업 명령어 실행
                                    backup_output = custom_handler.send_command(backup_cmd, timeout=10)
                                    
                                    # 백업 파일 저장
                                    backup_filename = os.path.join(
                                        self.backup_dir,
                                        f"{device['ip']}_{device['vendor']}_{device['os']}.txt"
                                    )
                                    with open(backup_filename, 'w', encoding='utf-8') as f:
                                        f.write(backup_output)
                                    self.logger.info(f"백업 파일 저장 완료: {backup_filename}")
                                    inspection_results["backup_file"] = backup_filename
                                except Exception as e:
                                    self.logger.error(f"백업 실패 ({device['ip']}): {str(e)}")
                                    inspection_results["backup_error"] = str(e)
                        
                        # 연결 종료
                        custom_handler.disconnect()
                        
                        return device, inspection_results
                    except Exception as e:
                        self.logger.error(f"커스텀 핸들러 실행 실패 ({device['ip']}): {str(e)}")
                        retry_count += 1
                        last_error = e
                        
                        # 실패 로그 기록
                        with open(session_log_file, 'a', encoding='utf-8') as log:
                            log.write(f"\n{'='*50}\n")
                            log.write(f"커스텀 핸들러 실행 실패 ({retry_count}) - {datetime.now()}\n")
                            log.write(f"오류: {str(e)}\n")
                            log.write(f"{'='*50}\n\n")
                        
                        if retry_count < self.max_retries:
                            time.sleep(2 ** retry_count)  # 지수 백오프
                            continue
                        else:
                            return device, {"error": f"커스텀 핸들러 실행 실패: {str(e)}"}

                # 유비쿼스 E4020 Telnet 접속 특별 처리 (레거시 코드 - 제거 예정)
                if device['vendor'].lower() == 'ubiquoss' and device['os'].lower() == 'e4020' and device['connection_type'].lower() == 'telnet':
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
                        
                        # terminal length 0 명령어 실행 (Axgate 제외)
                        if not (device['vendor'].lower() == 'axgate' and device['os'].lower() == 'axgate'):
                            tn.write(b"terminal length 0\n")
                            time.sleep(1)
                            output = tn.read_very_eager().decode('ascii')
                            with open(session_log_file, 'a', encoding='utf-8') as log:
                                log.write(f"terminal length 0 명령어 실행 결과:\n{output}\n")
                                log.write("-"*50 + "\n")
                        
                        inspection_results = {}
                        
                        # 점검 모드일 경우에만 점검 명령어 실행
                        if inspection_mode:
                            # 명령어 실행
                            commands = self._get_device_commands(
                                device['vendor'],
                                device['os']
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
                                        device['os'],
                                        cmd,
                                        output
                                    )
                                    inspection_results.update(parsed)
                                except Exception as e:
                                    self.logger.error(f"명령어 실행 실패 ({cmd} - {device['ip']}): {str(e)}")
                                    inspection_results[f"error_{cmd}"] = str(e)
                        
                        # 백업 모드일 경우에만 백업 명령어 실행
                        if backup_mode:
                            # 설정 백업
                            backup_cmd = self._get_backup_command(
                                device['vendor'],
                                device['os']
                            )
                            if backup_cmd:
                                try:
                                    # 백업 명령어 실행
                                    backup_output = tn.read_very_eager().decode('ascii')
                                    
                                    # 백업 파일 저장
                                    backup_filename = os.path.join(
                                        self.backup_dir,
                                        f"{device['ip']}_{device['vendor']}_{device['os']}.txt"
                                    )
                                    with open(backup_filename, 'w', encoding='utf-8') as f:
                                        f.write(backup_output)
                                    self.logger.info(f"백업 파일 저장 완료: {backup_filename}")
                                    inspection_results["backup_file"] = backup_filename
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

                # Axgate 장비 특별 처리
                if device['vendor'].lower() == 'axgate' and device['os'].lower() == 'axgate':
                    self.logger.debug(f"Axgate 장비 접속 시작: {device['ip']}")
                    
                    try:
                        # Telnet 직접 구현 (username/password 프롬프트 처리)
                        tn = telnetlib.Telnet(device['ip'], port=device['port'], timeout=self.timeout)
                        
                        # Username 입력
                        tn.read_until(b"Username:", timeout=10)
                        tn.write(device['username'].encode('ascii') + b"\n")
                        time.sleep(1)
                        
                        # Password 입력
                        tn.read_until(b"Password:", timeout=10)
                        tn.write(device['password'].encode('ascii') + b"\n")
                        time.sleep(2)
                        
                        # 로그인 후 출력 확인
                        output = tn.read_very_eager().decode('utf-8', errors='ignore')
                        
                        # 세션 로그에 저장
                        with open(session_log_file, 'a', encoding='utf-8') as log:
                            log.write(f"\n로그인 출력:\n")
                            log.write(f"{output}\n")
                    except Exception as e:
                        self.logger.error(f"Axgate Telnet 접속 실패 ({device['ip']}): {str(e)}")
                        
                        retry_count += 1
                        last_error = e
                        
                        with open(session_log_file, 'a', encoding='utf-8') as log:
                            log.write(f"Axgate Telnet 접속 실패 ({retry_count}) - {datetime.now()}\n")
                            log.write(f"오류: {str(e)}\n")
                            
                        time.sleep(1)  # 재시도 전 대기
                        continue  # 재시도
                        
                    return device, {"error": f"Axgate Telnet 접속 실패: {str(e)}"}

                # 일반 장비 접속 (Netmiko 사용)
                # device 객체의 주요 필드 문자열 변환
                safe_device = {
                    'ip': str(device['ip']),
                    'vendor': str(device['vendor']),
                    'os': str(device['os']),
                    'username': str(device['username']),
                    'password': str(device['password']),
                    'port': int(device['port']),
                    'connection_type': str(device['connection_type'])
                }
                
                # enable_password가 있는 경우 추가
                if 'enable_password' in device and device['enable_password']:
                    safe_device['enable_password'] = str(device['enable_password'])
                
                connection_params = {
                    'device_type': str(device_type),
                    'host': str(safe_device['ip']),
                    'username': str(safe_device['username']),
                    'password': str(safe_device['password']),
                    'port': int(safe_device['port']),
                    'secret': str(safe_device.get('enable_password', '')),
                    'timeout': int(self.timeout),
                    'session_log': str(session_log_file),
                    'fast_cli': False
                }

                try:
                    with ConnectHandler(**connection_params) as conn:
                        # Ubiquoss E4020의 경우 프롬프트 패턴 지정 (SSH 접속 시)
                        if device['vendor'].lower() == 'ubiquoss' and device['os'].lower() == 'e4020' and device['connection_type'].lower() == 'ssh':
                            conn.expect_string = r'[>#]'
                        # Axgate의 경우 프롬프트 패턴 지정 (SSH 접속 시)
                        elif device['vendor'].lower() == 'axgate' and device['os'].lower() == 'axgate' and device['connection_type'].lower() == 'ssh':
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
                                if not (device['vendor'].lower() == 'axgate' and device['os'].lower() == 'axgate'):
                                    conn.send_command_timing('terminal length 0')
                        except Exception as e:
                            self.logger.warning(f"Enable 모드 진입 실패 ({device['ip']}): {str(e)}")
                            self.logger.debug(f"예외 상세: {traceback.format_exc()}")
                        
                        # 점검 명령어 실행
                        inspection_results = {}
                        
                        if inspection_mode:
                            commands = self._get_device_commands(
                                device['vendor'],
                                device['os']
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
                                        device['os'],
                                        cmd,
                                        output
                                    )
                                    inspection_results.update(parsed)
                                except Exception as e:
                                    self.logger.error(f"명령어 실행 실패 ({cmd} - {device['ip']}): {str(e)}")
                                    inspection_results[f"error_{cmd}"] = str(e)
                        
                        # 백업 모드일 때만 설정 백업
                        if backup_mode:
                            backup_cmd = self._get_backup_command(
                                device['vendor'],
                                device['os']
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
                                        f"{device['ip']}_{device['vendor']}_{device['os']}.txt"
                                    )
                                    with open(backup_filename, 'w', encoding='utf-8') as f:
                                        f.write(backup_output)
                                    self.logger.info(f"백업 파일 저장 완료: {backup_filename}")
                                    inspection_results["backup_file"] = backup_filename
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
                    # 여기서 오류 처리
                    last_error = e
                    retry_count += 1
                    self.logger.warning(f"일반 장비 연결 시도 {retry_count} 실패 ({device['ip']}): {str(e)}")
                    
                    # 실패 로그 기록
                    with open(session_log_file, 'a', encoding='utf-8') as log:
                        log.write(f"\n{'='*50}\n")
                        log.write(f"일반 장비 연결 시도 {retry_count} 실패 - {datetime.now()}\n")
                        log.write(f"오류: {str(e)}\n")
                        log.write(f"{'='*50}\n\n")
                    
                    if retry_count < self.max_retries:
                        time.sleep(2 ** retry_count)  # 지수 백오프
                        continue
                    else:
                        return device, {"error": f"일반 장비 연결 실패: {str(e)}"}
                
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
                    continue
                else:
                    # 최종 실패 시 즉시 반환
                    return device, {"error": f"연결 실패: {str(e)}"}

    def _load_devices(self) -> List[Dict]:
        """엑셀 파일에서 장비 정보를 로드합니다."""
        try:
            self.logger.debug("장비 정보 로드 시작")
            df = pd.read_excel(self.input_excel)
            
            # 컬럼 이름을 소문자로 변환 (문자열이 아닌 경우 처리)
            df.columns = [str(col).lower() for col in df.columns]
            
            # 데이터프레임 검증
            is_valid, error_message = self._validate_excel_format(df)
            if not is_valid:
                raise ValueError(error_message)
            
            # 데이터프레임을 딕셔너리 리스트로 변환
            devices = df.to_dict('records')
            
            # 각 장비 정보 검증
            valid_devices = []
            for device in devices:
                is_valid, error_message = self._validate_device_info(device)
                if is_valid:
                    valid_devices.append(device)
                else:
                    self.logger.warning(f"장비 정보 검증 실패 ({device.get('ip', 'unknown')}): {error_message}")
            
            self.logger.info(f"장비 정보 로드 완료: {len(valid_devices)}개 장비")
            return valid_devices
            
        except Exception as e:
            self.logger.error(f"장비 정보 로드 중 오류 발생: {str(e)}")
            raise ValueError(f"장비 정보 로드 중 오류 발생: {str(e)}")
    
    def inspect_devices(self, backup_only: bool = False):
        """네트워크 장비를 점검하고 결과를 저장합니다."""
        if backup_only:
            self.logger.info("장비 백업 시작")
        else:
            self.logger.info("장비 점검 시작")
            
        total_devices = len(self.devices)
        completed_devices = 0
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_device = {}
            for device in self.devices:
                if backup_only:
                    future = executor.submit(self._backup_device, device)
                else:
                    future = executor.submit(self._inspect_device, device)
                future_to_device[future] = device
            
            for future in as_completed(future_to_device):
                device = future_to_device[future]
                try:
                    result = future.result()
                    with self.results_lock:
                        self.results.append(result)
                    # 로깅 메시지 수정
                    status_message = "성공"
                    if result.get('status') == 'error':
                        status_message = f"실패 - 오류: {result.get('error_message', '알 수 없는 오류')}"
                    self.logger.info(f"진행 상황: {completed_devices + 1}/{total_devices} 장비 처리 완료 (IP: {device['ip']}, 상태: {status_message})")
                except Exception as e:
                    self.logger.error(f"장비 처리 중 오류 발생: {device['ip']} - {str(e)}")
                    with self.results_lock:
                        self.results.append({
                            'ip': device['ip'],
                            'vendor': device['vendor'],
                            'os': device['os'],
                            'status': 'error',
                            'error_message': str(e)
                        })
                finally:
                    completed_devices += 1
                    self.logger.info(f"진행 상황: {completed_devices}/{total_devices} 장비 처리 완료")
        
        if backup_only:
            self.logger.info("장비 백업 완료")
        else:
            self.logger.info("장비 점검 완료")
            
        self.save_results()

    def inspect_and_backup_devices(self):
        """네트워크 장비를 점검하고 백업합니다(단일 작업)."""
        self.logger.info("장비 점검 및 백업 시작")
        total_devices = len(self.devices)
        completed_devices = 0
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_device = {}
            for device in self.devices:
                # 단일 작업으로 점검과 백업을 모두 수행합니다
                future = executor.submit(self._inspect_and_backup_device, device)
                future_to_device[future] = device
            
            for future in as_completed(future_to_device):
                device = future_to_device[future]
                try:
                    result = future.result()
                    with self.results_lock:
                        self.results.append(result)
                    # 로깅 메시지 수정
                    status_message = "성공"
                    if result.get('status') == 'error':
                        status_message = f"실패 - 오류: {result.get('error_message', '알 수 없는 오류')}"
                    self.logger.info(f"진행 상황: {completed_devices + 1}/{total_devices} 장비 처리 완료 (IP: {device['ip']}, 상태: {status_message})")
                except Exception as e:
                    self.logger.error(f"장비 처리 중 오류 발생: {device['ip']} - {str(e)}")
                    with self.results_lock:
                        self.results.append({
                            'ip': device['ip'],
                            'vendor': device['vendor'],
                            'os': device['os'],
                            'status': 'error',
                            'error_message': str(e)
                        })
                finally:
                    completed_devices += 1
                    self.logger.info(f"진행 상황: {completed_devices}/{total_devices} 장비 처리 완료")
        
        self.logger.info("장비 점검 및 백업 완료")
        self.save_results()

    def _inspect_and_backup_device(self, device: Dict) -> Dict:
        """단일 장비를 점검하고 백업합니다."""
        self.logger.info(f"장비 점검 및 백업 시작: {device['ip']}")
        result = {
            'ip': device['ip'],
            'vendor': device['vendor'],
            'os': device['os'],
            'status': 'success',
            'error_message': '',
            'inspection_results': {},
            'backup_file': ''
        }
        
        try:
            # 장비 정보 검증
            is_valid, error_message = self._validate_device_info(device)
            if not is_valid:
                result['status'] = 'error'
                result['error_message'] = error_message
                return result

            # 장비 연결 및 명령어 실행 (점검과 백업 모두 활성화)
            device, connection_results = self._connect_to_device(device, inspection_mode=True, backup_mode=True)
            
            # 오류 확인
            if 'error' in connection_results:
                result['status'] = 'error'
                result['error_message'] = connection_results['error']
                return result
                
            # 점검 결과 저장
            result['inspection_results'] = connection_results
            
            # 백업 파일명 정보 확인
            if 'backup_file' in connection_results:
                result['backup_file'] = connection_results['backup_file']
            
            self.logger.info(f"장비 점검 및 백업 완료: {device['ip']}")
            return result

        except Exception as e:
            self.logger.error(f"장비 점검 및 백업 중 오류 발생: {device['ip']} - {str(e)}")
            result['status'] = 'error'
            result['error_message'] = str(e)
            return result

    def _inspect_device(self, device: Dict) -> Dict:
        """단일 장비를 점검합니다."""
        self.logger.info(f"장비 점검 시작: {device['ip']}")
        result = {
            'ip': device['ip'],
            'vendor': device['vendor'],
            'os': device['os'],
            'status': 'success',
            'error_message': '',
            'inspection_results': {}
        }
        
        try:
            # 장비 정보 검증
            is_valid, error_message = self._validate_device_info(device)
            if not is_valid:
                result['status'] = 'error'
                result['error_message'] = error_message
                return result

            # 장비 연결 및 명령어 실행 (점검만 활성화)
            device, inspection_results = self._connect_to_device(device, inspection_mode=True, backup_mode=False)
            
            # 오류 확인
            if 'error' in inspection_results:
                result['status'] = 'error'
                result['error_message'] = inspection_results['error']
                return result
                
            # 검사 결과 저장
            result['inspection_results'] = inspection_results
            
            self.logger.info(f"장비 점검 완료: {device['ip']}")
            return result

        except Exception as e:
            self.logger.error(f"장비 점검 중 오류 발생: {device['ip']} - {str(e)}")
            result['status'] = 'error'
            result['error_message'] = str(e)
            return result

    def _backup_device(self, device: Dict) -> Dict:
        """단일 장비를 백업합니다."""
        self.logger.info(f"장비 백업 시작: {device['ip']}")
        result = {
            'ip': device['ip'],
            'vendor': device['vendor'],
            'os': device['os'],
            'status': 'success',
            'error_message': '',
            'backup_file': ''
        }
        
        try:
            # 장비 정보 검증
            is_valid, error_message = self._validate_device_info(device)
            if not is_valid:
                result['status'] = 'error'
                result['error_message'] = error_message
                return result

            # 장비 연결 (백업만 활성화)
            device, connection_results = self._connect_to_device(device, inspection_mode=False, backup_mode=True)
            
            # 오류 확인
            if 'error' in connection_results:
                result['status'] = 'error'
                result['error_message'] = connection_results['error']
                return result
            
            # 백업 관련 오류 확인
            if 'backup_error' in connection_results:
                result['status'] = 'error'
                result['error_message'] = connection_results['backup_error']
                return result
                
            # 백업 파일명 정보 확인
            if 'backup_file' in connection_results:
                result['backup_file'] = connection_results['backup_file']
            
            self.logger.info(f"장비 백업 완료: {device['ip']}")
            return result

        except Exception as e:
            self.logger.error(f"장비 백업 중 오류 발생: {device['ip']} - {str(e)}")
            result['status'] = 'error'
            result['error_message'] = str(e)
            return result

    def save_results(self):
        """결과를 엑셀 파일에 저장합니다."""
        try:
            # 필요한 컬럼만 포함하는 새 결과 리스트 생성
            simplified_results = []
            
            for result in self.results:
                # 기본 정보만 포함하는 새 항목 생성
                new_result = {
                    'ip': result.get('ip', ''),
                    'vendor': result.get('vendor', ''),
                    'os': result.get('os', '')
                }
                
                # inspection_results에서 중요 정보 추출
                if 'inspection_results' in result and result['inspection_results']:
                    inspection_data = result['inspection_results']
                    
                    # Version 정보 추출
                    if 'Version' in inspection_data:
                        new_result['Version'] = inspection_data['Version']
                    
                    # 다른 필요한 정보들 추출 (backup_file 제외)
                    for key, value in inspection_data.items():
                        if not key.startswith('error_') and key != 'backup_error' and key != 'backup_file':
                            new_result[key] = value
                
                simplified_results.append(new_result)
            
            # 새 데이터프레임 생성
            df = pd.DataFrame(simplified_results)
            
            # 결과 파일 저장 (이미 타임스탬프가 포함되어 있음)
            df.to_excel(self.output_excel, index=False)
            self.logger.info(f"결과가 저장되었습니다: {self.output_excel}")
        except Exception as e:
            self.logger.error(f"결과 저장 중 오류 발생: {str(e)}")
            raise

def main():
    """메인 함수"""
    try:
        input_excel = "devices.xlsx"
        output_excel = "inspection_results.xlsx"
        
        print("\n=== 네트워크 장비 점검 및 백업 도구 ===")
        print("1. 점검만 실행")
        print("2. 백업만 실행")
        print("3. 점검과 백업 모두 실행")
        
        choice = input("\n실행할 작업을 선택하세요 (1-3): ")
        
        if choice == "1":
            # 점검만 실행
            inspector = NetworkInspector(input_excel, output_excel, backup_only=False, inspection_only=True)
            inspector.inspect_devices(backup_only=False)
        elif choice == "2":
            # 백업만 실행
            inspector = NetworkInspector(input_excel, output_excel, backup_only=True, inspection_only=False)
            inspector.inspect_devices(backup_only=True)
        elif choice == "3":
            # 점검과 백업을 함께 실행 (단일 작업)
            inspector = NetworkInspector(input_excel, output_excel, backup_only=False, inspection_only=False)
            inspector.inspect_and_backup_devices()
        else:
            print("잘못된 선택입니다. 1-3 사이의 숫자를 입력하세요.")
            return
        
        print("\n작업이 완료되었습니다.")
        print(f"결과 파일: {inspector.output_excel}")
        if choice == "1":
            print("백업 작업을 수행하지 않았습니다.")
        else:
            print(f"백업 디렉토리: {inspector.backup_dir}")
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main() 