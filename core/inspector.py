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
import sys

from vendors import (
    INSPECTION_COMMANDS,
    BACKUP_COMMANDS,
    PARSING_RULES,
    get_custom_handler,
    CUSTOM_PARSERS
)

class NetworkInspector:
    def __init__(
        self,
        output_excel: str,
        backup_only: bool = False,
        inspection_only: bool = False,
        run_timestamp: str | None = None,
        inspection_excludes: Dict[str, Dict[str, List[str]]] | None = None
    ):
        # 출력 파일명에 타임스탬프 추가
        file_name, file_ext = os.path.splitext(output_excel)
        timestamp = run_timestamp or datetime.now().strftime('%Y%m%d_%H%M%S')
        self.output_dir = "results"
        os.makedirs(self.output_dir, exist_ok=True)
        self.output_excel = os.path.join(self.output_dir, f"{file_name}_{timestamp}{file_ext}")
        self.max_retries = 3  # 최대 재시도 횟수
        self.timeout = 10  # 연결 타임아웃 (초)
        # 공통 로깅 설정 사용 (root 로거 기반)
        self.logger = logging.getLogger(__name__)
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
        self.cli_lock = threading.Lock()
        self.inspection_excludes = inspection_excludes or {}
        
    

    def _get_device_commands(self, vendor: str, model: str) -> List[str]:
        """장비별 점검 명령어를 가져옵니다."""
        try:
            self.logger.debug(f"장비 명령어 조회 시작: {vendor} {model}")
            v = str(vendor).strip().lower()
            m = str(model).strip().lower()
            cmds = INSPECTION_COMMANDS.get(v, {}).get(m, [])
            excludes = set(self.inspection_excludes.get(v, {}).get(m, []))
            if excludes:
                filtered_cmds: List[str] = []
                for cmd in cmds:
                    if cmd in excludes:
                        continue
                    parse_ids = self._get_parse_ids_for_command(v, m, cmd)
                    if parse_ids and parse_ids.issubset(excludes):
                        continue
                    filtered_cmds.append(cmd)
                cmds = filtered_cmds
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
        vendor_lower = str(vendor).lower()
        model_lower = str(model).lower()
        excludes = set(self.inspection_excludes.get(vendor_lower, {}).get(model_lower, []))
        if command in excludes:
            self.logger.debug(f"파싱 제외(명령어 단위): {command}")
            return result
        
        # 먼저 해당 벤더/모델/명령어에 대한 파싱 규칙이 존재하는지 확인
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
                
                # CUSTOM_PARSERS 딕셔너리에서 파서 함수 찾기
                if parser_name in CUSTOM_PARSERS:
                    parser_func = CUSTOM_PARSERS[parser_name]
                    parsed_value = parser_func(output)

                    # 파서가 딕셔너리를 반환하면, 결과를 직접 업데이트
                    if isinstance(parsed_value, dict):
                        result.update(parsed_value)
                    # 그렇지 않으면, 지정된 컬럼에 할당
                    elif 'output_column' in rules:
                        column = rules['output_column']
                        result[column] = parsed_value
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
        if excludes:
            filtered = {}
            for key, value in result.items():
                parse_id = f"{command}::{key}"
                if parse_id in excludes:
                    continue
                filtered[key] = value
            result = filtered

        return result

    def _get_parse_ids_for_command(self, vendor: str, model: str, command: str) -> set[str]:
        rules = PARSING_RULES.get(vendor, {}).get(model, {}).get(command, {})
        if not isinstance(rules, dict):
            return set()

        parse_ids: set[str] = set()

        def add_column(column: str) -> None:
            if column:
                parse_ids.add(f"{command}::{column}")

        if "custom_parser" in rules:
            add_column(str(rules.get("output_column", "")).strip())
        elif "pattern" in rules:
            add_column(str(rules.get("output_column", "")).strip())
            process = rules.get("process", {})
            if isinstance(process, dict):
                add_column(str(process.get("output_column", "")).strip())
        elif "patterns" in rules:
            for pattern_rule in rules.get("patterns", []):
                if not isinstance(pattern_rule, dict):
                    continue
                if "custom_parser" in pattern_rule:
                    add_column(str(pattern_rule.get("output_column", "")).strip())
                output_columns = pattern_rule.get("output_columns", [])
                if isinstance(output_columns, list):
                    for col in output_columns:
                        if isinstance(col, str):
                            add_column(col.strip())
                add_column(str(pattern_rule.get("output_column", "")).strip())
                process = pattern_rule.get("process", {})
                if isinstance(process, dict):
                    add_column(str(process.get("output_column", "")).strip())
        else:
            add_column(str(rules.get("output_column", "")).strip())

        parse_ids.discard(f"{command}::")
        return parse_ids

    def _get_output_columns_for_command(self, vendor: str, model: str, command: str) -> List[str]:
        """명령어에 매핑되는 출력 컬럼 목록을 순서대로 반환합니다."""
        vendor_key = str(vendor).strip().lower()
        model_key = str(model).strip().lower()
        rules = PARSING_RULES.get(vendor_key, {}).get(model_key, {}).get(command, {})
        if not isinstance(rules, dict):
            return []

        columns: List[str] = []

        def add_column(column: str | None) -> None:
            if not column:
                return
            cleaned = str(column).strip()
            if cleaned and cleaned not in columns:
                columns.append(cleaned)

        if "custom_parser" in rules:
            add_column(rules.get("output_column"))
        elif "pattern" in rules:
            add_column(rules.get("output_column"))
            process = rules.get("process", {})
            if isinstance(process, dict):
                add_column(process.get("output_column"))
        elif "patterns" in rules:
            for pattern_rule in rules.get("patterns", []):
                if not isinstance(pattern_rule, dict):
                    continue
                if "custom_parser" in pattern_rule:
                    add_column(pattern_rule.get("output_column"))
                output_columns = pattern_rule.get("output_columns", [])
                if isinstance(output_columns, list):
                    for col in output_columns:
                        add_column(col)
                add_column(pattern_rule.get("output_column"))
                process = pattern_rule.get("process", {})
                if isinstance(process, dict):
                    add_column(process.get("output_column"))
        else:
            add_column(rules.get("output_column"))

        return columns

    def get_available_inspection_columns(self, devices: List[Dict]) -> List[str]:
        """장비 목록 기준으로 점검 결과 컬럼을 순서대로 수집합니다."""
        ordered_columns: List[str] = []
        seen: set[str] = set()

        for device in devices:
            vendor = str(device.get("vendor", "")).strip()
            model = str(device.get("os", "")).strip()
            vendor_key = vendor.lower()
            model_key = model.lower()
            excludes = set(self.inspection_excludes.get(vendor_key, {}).get(model_key, []))

            commands = self._get_device_commands(vendor, model)
            for cmd in commands:
                for col in self._get_output_columns_for_command(vendor, model, cmd):
                    parse_id = f"{cmd}::{col}"
                    if cmd in excludes or parse_id in excludes:
                        continue
                    if col not in seen:
                        seen.add(col)
                        ordered_columns.append(col)

        return ordered_columns
    
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

    def _connect_to_device(
        self,
        device: Dict,
        inspection_mode: bool = True,
        backup_mode: bool = True,
        session_log_suffix: str | None = None,
        custom_commands: List[str] | None = None
    ) -> Tuple[Dict, Dict]:
        """장비에 연결하고 명령어를 실행합니다.
        
        Args:
            device: 장비 정보
            inspection_mode: 점검 명령어 실행 여부
            backup_mode: 백업 명령어 실행 여부
            
        Returns:
            Tuple[Dict, Dict]: (장비 정보, 점검/백업 결과)
        """
        retry_count = 0
        last_error = None
        self._print_cli_status(f"[{device['ip']}] 연결 테스트 시작 (TCP {device['port']})")
        
        # TCP 연결 테스트 수행
        if not self._test_tcping(device['ip'], device['port']):
            self.logger.error(f"TCP 연결 테스트 실패 ({device['ip']}:{device['port']})")
            self._print_cli_status(f"[{device['ip']}] TCP 연결 테스트 실패")
            return device, {"error": "TCP 연결 테스트 실패"}
        self._print_cli_status(f"[{device['ip']}] TCP 연결 확인 완료")
        
        # 세션 로그 파일 생성
        session_log_filename = f"{device['ip']}_{device['vendor']}_{device['os']}"
        if session_log_suffix:
            session_log_filename = f"{session_log_filename}_{session_log_suffix}"
        session_log_file = os.path.join(self.session_log_dir, f"{session_log_filename}.log")
        
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
                        self._print_cli_status(f"[{device['ip']}] 커스텀 핸들러 연결 시작")
                        custom_handler.connect()
                        custom_handler.enable()
                        self._print_cli_status(f"[{device['ip']}] 커스텀 핸들러 연결 완료")
                        
                        inspection_results = {}
                        
                        # 점검 모드일 경우 점검 명령어 실행
                        if inspection_mode:
                            # 점검 명령어 실행
                            commands = self._get_device_commands(
                                device['vendor'],
                                device['os']
                            )
                            self._print_cli_status(f"[{device['ip']}] 점검 명령 {len(commands)}개 실행 시작")
                            
                            for idx, cmd in enumerate(commands, start=1):
                                try:
                                    # 명령어 실행
                                    self._print_cli_status(f"[{device['ip']}] 점검 명령 실행 {idx}/{len(commands)}: {cmd}")
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
                        
                        # 사용자 명령어 파일 실행
                        if custom_commands:
                            self._print_cli_status(f"[{device['ip']}] 사용자 명령 {len(custom_commands)}개 실행 시작")
                            for idx, cmd in enumerate(custom_commands, start=1):
                                try:
                                    self._print_cli_status(
                                        f"[{device['ip']}] 사용자 명령 실행 {idx}/{len(custom_commands)}: {cmd}"
                                    )
                                    custom_handler.send_command(cmd)
                                except Exception as e:
                                    self.logger.error(f"사용자 명령 실행 실패 ({cmd} - {device['ip']}): {str(e)}")
                                    return device, {"error": f"사용자 명령 실행 실패: {str(e)}"}

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
                                    self._print_cli_status(f"[{device['ip']}] 백업 명령 실행: {backup_cmd}")
                                    backup_output = custom_handler.send_command(backup_cmd, timeout=10)
                                    
                                    # 백업 파일 저장
                                    backup_filename = os.path.join(
                                        self.backup_dir,
                                        f"{device['ip']}_{device['vendor']}_{device['os']}.txt"
                                    )
                                    with open(backup_filename, 'w', encoding='utf-8') as f:
                                        f.write(backup_output)
                                    self.logger.info(f"백업 파일 저장 완료: {backup_filename}")
                                    self._print_cli_status(f"[{device['ip']}] 백업 파일 저장 완료: {backup_filename}")
                                    inspection_results["backup_file"] = backup_filename
                                except Exception as e:
                                    self.logger.error(f"백업 실패 ({device['ip']}): {str(e)}")
                                    inspection_results["backup_error"] = str(e)
                        
                        # 연결 종료
                        custom_handler.disconnect()
                        
                        if custom_commands:
                            inspection_results["custom_commands_executed"] = len(custom_commands)
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
                            self._print_cli_status(f"[{device['ip']}] Netmiko 연결 완료 ({device_type})")
                            conn.enable()
                            if not (device['vendor'].lower() == 'axgate' and device['os'].lower() == 'axgate'):
                                conn.send_command_timing('terminal length 0')
                            
                            inspection_results = {}
                            if inspection_mode:
                                commands = self._get_device_commands(device['vendor'], device['os'])
                                self._print_cli_status(f"[{device['ip']}] 점검 명령 {len(commands)}개 실행 시작")
                                for idx, cmd in enumerate(commands, start=1):
                                    self._print_cli_status(f"[{device['ip']}] 점검 명령 실행 {idx}/{len(commands)}: {cmd}")
                                    output = conn.send_command(cmd, read_timeout=30)
                                    parsed = self._parse_command_output(device['vendor'], device['os'], cmd, output)
                                    inspection_results.update(parsed)

                            if custom_commands:
                                self._print_cli_status(f"[{device['ip']}] 사용자 명령 {len(custom_commands)}개 실행 시작")
                                for idx, cmd in enumerate(custom_commands, start=1):
                                    self._print_cli_status(
                                        f"[{device['ip']}] 사용자 명령 실행 {idx}/{len(custom_commands)}: {cmd}"
                                    )
                                    conn.send_command(cmd, read_timeout=30)
                            
                            if backup_mode:
                                backup_cmd = self._get_backup_command(device['vendor'], device['os'])
                                if backup_cmd:
                                    self._print_cli_status(f"[{device['ip']}] 백업 명령 실행: {backup_cmd}")
                                    backup_output = conn.send_command(backup_cmd, read_timeout=60)
                                    backup_filename = os.path.join(self.backup_dir, f"{device['ip']}_{device['vendor']}_{device['os']}.txt")
                                    with open(backup_filename, 'w', encoding='utf-8') as f:
                                        f.write(backup_output)
                                    self._print_cli_status(f"[{device['ip']}] 백업 파일 저장 완료: {backup_filename}")
                                    inspection_results["backup_file"] = backup_filename
                            
                            if custom_commands:
                                inspection_results["custom_commands_executed"] = len(custom_commands)
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
        for idx, device in enumerate(devices, start=1):
            device['device_index'] = idx
        self.devices = devices

    def _format_progress_bar(self, completed: int, total: int, width: int = 24) -> str:
        """진행률 표시를 ASCII 바 형태로 생성합니다."""
        if total <= 0:
            return f"[{'-' * width}] 0/0 (0%)"
        filled = int(width * completed / total)
        bar = "#" * filled + "-" * (width - filled)
        percent = int((completed / total) * 100)
        return f"[{bar}] {completed}/{total} ({percent}%)"

    def _print_cli_status(self, message: str) -> None:
        """로그 레벨과 무관하게 CLI에 진행 상황을 출력합니다."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        thread_name = threading.current_thread().name
        with self.cli_lock:
            sys.stdout.write(f"{timestamp} [{thread_name}] {message}\n")
            sys.stdout.flush()

    def inspect_devices(self, backup_only: bool = False):
        """네트워크 장비를 점검하고 결과를 저장합니다."""
        if backup_only:
            self.logger.info("장비 백업 시작")
            self._print_cli_status("장비 백업을 시작합니다.")
        else:
            self.logger.info("장비 점검 시작")
            self._print_cli_status("장비 점검을 시작합니다.")
            
        total_devices = len(self.devices)
        completed_devices = 0
        success_count = 0
        fail_count = 0
        self._print_cli_status(f"총 장비 수: {total_devices}대")
        
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
                status_message = "성공"
                try:
                    result = future.result()
                    with self.results_lock:
                        self.results.append(result)
                    if result.get('status') == 'error':
                        status_message = f"실패 - 오류: {result.get('error_message', '알 수 없는 오류')}"
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
                    status_message = f"실패 - 오류: {str(e)}"
                finally:
                    completed_devices += 1
                    if status_message.startswith("성공"):
                        success_count += 1
                    else:
                        fail_count += 1
                    progress = self._format_progress_bar(completed_devices, total_devices)
                    self.logger.info(f"진행 상황: {progress} | IP: {device['ip']} | 상태: {status_message}")
                    self._print_cli_status(
                        f"진행: {progress} | IP: {device['ip']} | 상태: {status_message} | 성공 {success_count} / 실패 {fail_count}"
                    )
        
        # 장비 정보 순서대로 결과 정렬
        device_order = {device['ip']: i for i, device in enumerate(self.devices)}
        self.results.sort(key=lambda r: device_order.get(r.get('ip'), float('inf')))
        
        if backup_only:
            self.logger.info("장비 백업 완료")
            self._print_cli_status(f"장비 백업 완료 (성공 {success_count} / 실패 {fail_count})")
        else:
            self.logger.info("장비 점검 완료")
            self._print_cli_status(f"장비 점검 완료 (성공 {success_count} / 실패 {fail_count})")

    def run_custom_commands(self, commands: List[str]):
        """사용자 명령어 목록을 장비에 순차 실행합니다."""
        self.logger.info("사용자 명령 실행 시작")
        self._print_cli_status("사용자 명령 실행을 시작합니다.")

        total_devices = len(self.devices)
        completed_devices = 0
        success_count = 0
        fail_count = 0
        self._print_cli_status(f"총 장비 수: {total_devices}대")

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_device = {}
            for device in self.devices:
                future = executor.submit(self._run_custom_commands_device, device, commands)
                future_to_device[future] = device

            for future in as_completed(future_to_device):
                device = future_to_device[future]
                status_message = "성공"
                try:
                    result = future.result()
                    with self.results_lock:
                        self.results.append(result)
                    if result.get('status') == 'error':
                        status_message = f"실패 - 오류: {result.get('error_message', '알 수 없는 오류')}"
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
                    status_message = f"실패 - 오류: {str(e)}"
                finally:
                    completed_devices += 1
                    if status_message.startswith("성공"):
                        success_count += 1
                    else:
                        fail_count += 1
                    progress = self._format_progress_bar(completed_devices, total_devices)
                    self.logger.info(f"진행 상황: {progress} | IP: {device['ip']} | 상태: {status_message}")
                    self._print_cli_status(
                        f"진행: {progress} | IP: {device['ip']} | 상태: {status_message} | 성공 {success_count} / 실패 {fail_count}"
                    )

        device_order = {device['ip']: i for i, device in enumerate(self.devices)}
        self.results.sort(key=lambda r: device_order.get(r.get('ip'), float('inf')))

        self.logger.info("사용자 명령 실행 완료")
        self._print_cli_status(f"사용자 명령 실행 완료 (성공 {success_count} / 실패 {fail_count})")
            
    def inspect_and_backup_devices(self):
        """네트워크 장비를 점검하고 백업합니다(병렬 작업)."""
        self.logger.info("장비 점검 및 백업 시작")
        self._print_cli_status("장비 점검 및 백업을 시작합니다.")
        total_devices = len(self.devices)
        completed_devices = 0
        success_count = 0
        fail_count = 0
        self._print_cli_status(f"총 장비 수: {total_devices}대")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_device = {}
            for device in self.devices:
                # 점검과 백업을 장비별로 분리하여 병렬 수행합니다
                future = executor.submit(self._inspect_and_backup_device_parallel, device)
                future_to_device[future] = device
            
            for future in as_completed(future_to_device):
                device = future_to_device[future]
                status_message = "성공"
                try:
                    result = future.result()
                    with self.results_lock:
                        self.results.append(result)
                    if result.get('status') == 'error':
                        status_message = f"실패 - 오류: {result.get('error_message', '알 수 없는 오류')}"
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
                    status_message = f"실패 - 오류: {str(e)}"
                finally:
                    completed_devices += 1
                    if status_message.startswith("성공"):
                        success_count += 1
                    else:
                        fail_count += 1
                    progress = self._format_progress_bar(completed_devices, total_devices)
                    self.logger.info(f"진행 상황: {progress} | IP: {device['ip']} | 상태: {status_message}")
                    self._print_cli_status(
                        f"진행: {progress} | IP: {device['ip']} | 상태: {status_message} | 성공 {success_count} / 실패 {fail_count}"
                    )
        
        # 장비 정보 순서대로 결과 정렬
        device_order = {device['ip']: i for i, device in enumerate(self.devices)}
        self.results.sort(key=lambda r: device_order.get(r.get('ip'), float('inf')))
        
        self.logger.info("장비 점검 및 백업 완료")
        self._print_cli_status(f"장비 점검 및 백업 완료 (성공 {success_count} / 실패 {fail_count})")

    def _inspect_and_backup_device(self, device: Dict) -> Dict:
        """단일 장비를 점검하고 백업합니다."""
        self.logger.info(f"장비 점검 및 백업 시작: {device['ip']}")
        self._print_cli_status(f"[{device['ip']}] 점검+백업 시작")
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
            self._print_cli_status(f"[{device['ip']}] 점검+백업 완료")
            return result

        except Exception as e:
            self.logger.error(f"장비 점검 및 백업 중 오류 발생: {device['ip']} - {str(e)}")
            result['status'] = 'error'
            result['error_message'] = str(e)
            return result

    def _inspect_and_backup_device_parallel(self, device: Dict) -> Dict:
        """단일 장비를 점검/백업 스레드로 병렬 수행합니다."""
        device_index = device.get('device_index', 'NA')
        threading.current_thread().name = f"Device-{device_index}"
        self.logger.info(f"장비 점검 및 백업(병렬) 시작: {device['ip']}")
        self._print_cli_status(f"[{device['ip']}] 점검+백업 병렬 시작")
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
            with ThreadPoolExecutor(max_workers=2) as executor:
                inspection_future = executor.submit(self._inspect_device, device, "inspection")
                backup_future = executor.submit(self._backup_device, device, "backup")
                inspection_result = inspection_future.result()
                backup_result = backup_future.result()

            errors = []
            if inspection_result.get('status') == 'error':
                error_message = inspection_result.get('error_message', '').strip()
                errors.append(f"점검 실패: {error_message or '알 수 없는 오류'}")
            if backup_result.get('status') == 'error':
                error_message = backup_result.get('error_message', '').strip()
                errors.append(f"백업 실패: {error_message or '알 수 없는 오류'}")

            if errors:
                result['status'] = 'error'
                result['error_message'] = " | ".join(errors)

            result['inspection_results'] = inspection_result.get('inspection_results', {})
            result['backup_file'] = backup_result.get('backup_file', '')

            self.logger.info(f"장비 점검 및 백업(병렬) 완료: {device['ip']}")
            self._print_cli_status(f"[{device['ip']}] 점검+백업 병렬 완료")
            return result

        except Exception as e:
            self.logger.error(f"장비 점검 및 백업(병렬) 중 오류 발생: {device['ip']} - {str(e)}")
            result['status'] = 'error'
            result['error_message'] = str(e)
            return result

    def _inspect_device(self, device: Dict, session_log_suffix: str | None = None) -> Dict:
        """단일 장비를 점검합니다."""
        device_index = device.get('device_index', 'NA')
        threading.current_thread().name = f"Device-{device_index}:Inspect"
        self.logger.info(f"장비 점검 시작: {device['ip']}")
        self._print_cli_status(f"[{device['ip']}] 점검 시작")
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
            device, inspection_results = self._connect_to_device(
                device,
                inspection_mode=True,
                backup_mode=False,
                session_log_suffix=session_log_suffix
            )
            
            # 오류 확인
            if 'error' in inspection_results:
                result['status'] = 'error'
                result['error_message'] = inspection_results['error']
                return result
                
            # 검사 결과 저장
            result['inspection_results'] = inspection_results
            
            self.logger.info(f"장비 점검 완료: {device['ip']}")
            self._print_cli_status(f"[{device['ip']}] 점검 완료")
            return result

        except Exception as e:
            self.logger.error(f"장비 점검 중 오류 발생: {device['ip']} - {str(e)}")
            result['status'] = 'error'
            result['error_message'] = str(e)
            return result

    def _run_custom_commands_device(
        self,
        device: Dict,
        commands: List[str],
        session_log_suffix: str | None = None
    ) -> Dict:
        """단일 장비에 사용자 명령어를 실행합니다."""
        device_index = device.get('device_index', 'NA')
        threading.current_thread().name = f"Device-{device_index}:Cmds"
        self.logger.info(f"사용자 명령 실행 시작: {device['ip']}")
        self._print_cli_status(f"[{device['ip']}] 사용자 명령 실행 시작")
        result = {
            'ip': device['ip'],
            'vendor': device['vendor'],
            'os': device['os'],
            'status': 'success',
            'error_message': ''
        }

        try:
            device, command_results = self._connect_to_device(
                device,
                inspection_mode=False,
                backup_mode=False,
                session_log_suffix=session_log_suffix,
                custom_commands=commands
            )

            if 'error' in command_results:
                result['status'] = 'error'
                result['error_message'] = command_results['error']
                return result

            self.logger.info(f"사용자 명령 실행 완료: {device['ip']}")
            self._print_cli_status(f"[{device['ip']}] 사용자 명령 실행 완료")
            return result

        except Exception as e:
            self.logger.error(f"사용자 명령 실행 중 오류 발생: {device['ip']} - {str(e)}")
            result['status'] = 'error'
            result['error_message'] = str(e)
            return result

    def _backup_device(self, device: Dict, session_log_suffix: str | None = None) -> Dict:
        """단일 장비를 백업합니다."""
        device_index = device.get('device_index', 'NA')
        threading.current_thread().name = f"Device-{device_index}:Backup"
        self.logger.info(f"장비 백업 시작: {device['ip']}")
        self._print_cli_status(f"[{device['ip']}] 백업 시작")
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
            device, connection_results = self._connect_to_device(
                device,
                inspection_mode=False,
                backup_mode=True,
                session_log_suffix=session_log_suffix
            )
            
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
            self._print_cli_status(f"[{device['ip']}] 백업 완료")
            return result

        except Exception as e:
            self.logger.error(f"장비 백업 중 오류 발생: {device['ip']} - {str(e)}")
            result['status'] = 'error'
            result['error_message'] = str(e)
            return result 