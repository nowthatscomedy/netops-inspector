import pandas as pd
import re
from netmiko import ConnectHandler
from typing import Dict, List, Tuple
import os
from datetime import datetime
import threading
import ipaddress
import socket
import time
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import telnetlib

from vendors import (
    INSPECTION_COMMANDS,
    BACKUP_COMMANDS,
    PARSING_RULES,
    get_custom_handler,
    CUSTOM_PARSERS
)

class NetworkInspector:
    def __init__(self, output_excel: str, backup_only: bool = False, inspection_only: bool = False):
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
        
        self.devices = [] # This will be loaded later
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
        
        self.logger.info("로깅 초기화 완료")
        self.logger.debug(f"로그 파일 경로: {log_file}")

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
                
                # CUSTOM_PARSERS 딕셔너리에서 파서 함수 찾기
                if parser_name in CUSTOM_PARSERS:
                    parser_func = CUSTOM_PARSERS[parser_name]
                    result[column] = parser_func(output)
                else:
                    self.logger.error(f"커스텀 파서 함수 '{parser_name}'를 찾을 수 없습니다.")

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
                        
                        if parser_name in CUSTOM_PARSERS:
                            parser_func = CUSTOM_PARSERS[parser_name]
                            result[column] = parser_func(output)
                        else:
                            self.logger.error(f"커스텀 파서 함수 '{parser_name}'를 찾을 수 없습니다.")
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
                else: # Netmiko
                    # 장비 타입 설정
                    if device['connection_type'].lower() == 'telnet':
                        device_type = f"{str(device['vendor']).lower()}_{str(device['os']).lower()}_telnet"
                    else: # ssh
                        device_type = f"{str(device['vendor']).lower()}_{str(device['os']).lower()}"
                    
                    if device['vendor'].lower() == 'juniper':
                        device_type = 'juniper_junos'

                    # 일반 장비 접속 (Netmiko 사용)
                    safe_device = {
                        'ip': str(device['ip']),
                        'vendor': str(device['vendor']),
                        'os': str(device['os']),
                        'username': str(device['username']),
                        'password': str(device['password']),
                        'port': int(device['port']),
                        'connection_type': str(device['connection_type'])
                    }
                    
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
                            conn.enable()
                            if not (device['vendor'].lower() == 'axgate' and device['os'].lower() == 'axgate'):
                                conn.send_command_timing('terminal length 0')
                            
                            inspection_results = {}
                            if inspection_mode:
                                commands = self._get_device_commands(device['vendor'], device['os'])
                                for cmd in commands:
                                    output = conn.send_command(cmd, read_timeout=30)
                                    parsed = self._parse_command_output(device['vendor'], device['os'], cmd, output)
                                    inspection_results.update(parsed)
                            
                            if backup_mode:
                                backup_cmd = self._get_backup_command(device['vendor'], device['os'])
                                if backup_cmd:
                                    backup_output = conn.send_command(backup_cmd, read_timeout=60)
                                    backup_filename = os.path.join(self.backup_dir, f"{device['ip']}_{device['vendor']}_{device['os']}.txt")
                                    with open(backup_filename, 'w', encoding='utf-8') as f:
                                        f.write(backup_output)
                                    inspection_results["backup_file"] = backup_filename
                            
                            return device, inspection_results
                    except Exception as e:
                        last_error = e
                        retry_count += 1
                        self.logger.warning(f"Netmiko 연결 시도 {retry_count} 실패 ({device['ip']}): {str(e)}")
                        if retry_count >= self.max_retries:
                            return device, {"error": f"Netmiko 연결 실패: {str(e)}"}
                        time.sleep(2 ** retry_count)  # 지수 백오프
                        continue
            except Exception as e:
                last_error = e
                retry_count += 1
                self.logger.warning(f"연결 시도 {retry_count} 실패 ({device['ip']}): {str(e)}")
                
                with open(session_log_file, 'a', encoding='utf-8') as log:
                    log.write(f"\n{'='*50}\n")
                    log.write(f"연결 시도 {retry_count} 실패 - {datetime.now()}\n")
                    log.write(f"오류: {str(e)}\n")
                    log.write(f"{'='*50}\n\n")
                
                if retry_count < self.max_retries:
                    time.sleep(2 ** retry_count)
                    continue
                else:
                    return device, {"error": f"최종 연결 실패: {str(e)}"}
    
    def load_devices(self, devices: List[Dict]):
        self.devices = devices

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
        
        # 장비 정보 순서대로 결과 정렬
        device_order = {device['ip']: i for i, device in enumerate(self.devices)}
        self.results.sort(key=lambda r: device_order.get(r.get('ip'), float('inf')))
        
        if backup_only:
            self.logger.info("장비 백업 완료")
        else:
            self.logger.info("장비 점검 완료")
            
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
        
        # 장비 정보 순서대로 결과 정렬
        device_order = {device['ip']: i for i, device in enumerate(self.devices)}
        self.results.sort(key=lambda r: device_order.get(r.get('ip'), float('inf')))
        
        self.logger.info("장비 점검 및 백업 완료")

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