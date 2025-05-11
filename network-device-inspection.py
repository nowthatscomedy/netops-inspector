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
import psutil
import logging
from pathlib import Path

class NetworkInspector:
    def __init__(self, input_excel: str, output_excel: str):
        self.input_excel = input_excel
        self.output_excel = output_excel
        self.max_retries = 3  # 최대 재시도 횟수
        self.timeout = 10  # 연결 타임아웃 (초)
        self.max_memory_percent = 80  # 최대 메모리 사용량 제한 (%)
        self.setup_logging()
        self.devices = self._load_devices()
        self.results = []
        self.results_lock = threading.Lock()
        self.backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_log_dir = f"session_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.session_log_dir, exist_ok=True)
        
    def setup_logging(self):
        """로깅 설정을 초기화합니다."""
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"network_inspector_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _check_memory_usage(self):
        """메모리 사용량을 확인합니다."""
        memory_percent = psutil.Process().memory_percent()
        if memory_percent > self.max_memory_percent:
            self.logger.warning(f"High memory usage detected: {memory_percent}%")
            return False
        return True

    def _validate_excel_format(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """엑셀 파일 형식을 검증합니다."""
        required_columns = ['ip', 'vendor', 'model', 'version', 'connection_type', 'port', 'username', 'password']
        
        # 필수 컬럼 확인
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return False, f"Missing required columns: {', '.join(missing_columns)}"
        
        # 데이터 타입 확인
        if not df['port'].apply(lambda x: isinstance(x, (int, float))).all():
            return False, "Port numbers must be numeric"
        
        # 중복 IP 확인
        if df['ip'].duplicated().any():
            return False, "Duplicate IP addresses found"
        
        # 칼럼 이름을 소문자로 변환
        df.columns = df.columns.str.lower()
        
        # 필요한 칼럼만 선택하고 순서 재정렬
        df = df[required_columns]
        
        return True, ""

    def _validate_password(self, password: str) -> Tuple[bool, str]:
        """비밀번호 복잡도를 검증합니다."""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        if not re.search(r"[A-Z]", password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r"[a-z]", password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r"\d", password):
            return False, "Password must contain at least one number"
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            return False, "Password must contain at least one special character"
        return True, ""

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
        # 필수 필드 확인
        required_fields = ['ip', 'vendor', 'model', 'version', 'connection_type', 'port', 'username', 'password']
        for field in required_fields:
            if field not in device or not device[field]:
                return False, f"Missing required field: {field}"

        # IP 주소 검증
        if not self._validate_ip(device['ip']):
            return False, f"Invalid IP address: {device['ip']}"

        # 접속 방식 검증
        if not self._validate_connection_type(device['connection_type']):
            return False, f"Invalid connection type: {device['connection_type']}"

        # 포트 번호 검증
        if not self._validate_port(device['port'], device['connection_type']):
            return False, f"Invalid port number for {device['connection_type']}: {device['port']}"

        # 벤더/모델/버전 검증
        try:
            if device['vendor'].lower() not in INSPECTION_COMMANDS:
                return False, f"Unsupported vendor: {device['vendor']}"
            if device['model'].lower() not in INSPECTION_COMMANDS[device['vendor'].lower()]:
                return False, f"Unsupported model for {device['vendor']}: {device['model']}"
            if device['version'] not in INSPECTION_COMMANDS[device['vendor'].lower()][device['model'].lower()]:
                return False, f"Unsupported version for {device['vendor']} {device['model']}: {device['version']}"
        except KeyError:
            return False, f"Invalid device configuration: {device['vendor']} {device['model']} {device['version']}"

        return True, ""

    def _get_device_commands(self, vendor: str, model: str, version: str) -> List[str]:
        """장비별 점검 명령어를 가져옵니다."""
        try:
            return INSPECTION_COMMANDS[vendor.lower()][model.lower()][version]
        except KeyError:
            return []
    
    def _get_backup_command(self, vendor: str, model: str, version: str) -> str:
        """장비별 백업 명령어를 가져옵니다."""
        try:
            return BACKUP_COMMANDS[vendor.lower()][model.lower()][version]
        except KeyError:
            return ""
    
    def _parse_command_output(self, vendor: str, model: str, command: str, output: str) -> Dict:
        """명령어 출력을 파싱합니다."""
        result = {}
        try:
            rules = PARSING_RULES[vendor.lower()][model.lower()][command]
            pattern = rules['pattern']
            column = rules['output_column']
            
            matches = re.finditer(pattern, output, re.MULTILINE)
            values = [match.group(1) for match in matches]
            result[column] = ', '.join(values)
        except (KeyError, AttributeError):
            pass
        return result
    
    def _connect_to_device(self, device: Dict) -> Tuple[Dict, Dict]:
        """장비에 연결하고 명령어를 실행합니다."""
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                if not self._check_memory_usage():
                    self.logger.error("Memory usage exceeded limit")
                    return device, {"error": "Memory usage exceeded limit"}

                connection_params = {
                    'device_type': f"{device['vendor']}_{device['model']}",
                    'host': device['ip'],
                    'username': device['username'],
                    'password': device['password'],
                    'port': device['port'],
                    'secret': device.get('enable_password', ''),
                    'timeout': self.timeout
                }
                
                # 장비별 세션 로그 디렉토리 생성
                device_log_dir = os.path.join(self.session_log_dir, f"{device['ip']}_{device['vendor']}_{device['model']}")
                os.makedirs(device_log_dir, exist_ok=True)
                
                with ConnectHandler(**connection_params) as conn:
                    # 점검 명령어 실행
                    inspection_results = {}
                    commands = self._get_device_commands(
                        device['vendor'],
                        device['model'],
                        device['version']
                    )
                    
                    for cmd in commands:
                        try:
                            output = conn.send_command(cmd)
                            # 명령어별 세션 로그 저장
                            log_filename = os.path.join(device_log_dir, f"{cmd.replace(' ', '_')}.txt")
                            with open(log_filename, 'w', encoding='utf-8') as f:
                                f.write(f"Command: {cmd}\n")
                                f.write("="*50 + "\n")
                                f.write(output)
                            
                            parsed = self._parse_command_output(
                                device['vendor'],
                                device['model'],
                                cmd,
                                output
                            )
                            inspection_results.update(parsed)
                        except Exception as e:
                            self.logger.error(f"Error executing command {cmd} on {device['ip']}: {str(e)}")
                            inspection_results[f"error_{cmd}"] = str(e)
                    
                    # 설정 백업
                    backup_cmd = self._get_backup_command(
                        device['vendor'],
                        device['model'],
                        device['version']
                    )
                    if backup_cmd:
                        try:
                            backup_output = conn.send_command(backup_cmd)
                            backup_filename = os.path.join(
                                self.backup_dir,
                                f"{device['ip']}_{device['vendor']}_{device['model']}.txt"
                            )
                            with open(backup_filename, 'w', encoding='utf-8') as f:
                                f.write(backup_output)
                        except Exception as e:
                            self.logger.error(f"Error backing up {device['ip']}: {str(e)}")
                            inspection_results["backup_error"] = str(e)
                    
                    return device, inspection_results
                    
            except Exception as e:
                retry_count += 1
                self.logger.warning(f"Attempt {retry_count} failed for {device['ip']}: {str(e)}")
                if retry_count < self.max_retries:
                    time.sleep(2 ** retry_count)  # 지수 백오프
                else:
                    error_log_dir = os.path.join(self.session_log_dir, f"{device['ip']}_{device['vendor']}_{device['model']}")
                    os.makedirs(error_log_dir, exist_ok=True)
                    error_log = os.path.join(error_log_dir, "error.log")
                    with open(error_log, 'w', encoding='utf-8') as f:
                        f.write(f"Error connecting to {device['ip']}: {str(e)}\n")
                        f.write(f"Retry attempts: {retry_count}\n")
                    self.logger.error(f"Failed to connect to {device['ip']} after {retry_count} attempts")
                    return device, {"error": str(e)}

    def _load_devices(self) -> List[Dict]:
        """엑셀 파일에서 장비 정보를 로드하고 검증합니다."""
        try:
            # 엑셀 파일 존재 확인
            if not Path(self.input_excel).exists():
                raise FileNotFoundError(f"Input file not found: {self.input_excel}")

            # 엑셀 파일 읽기 (칼럼 이름을 소문자로 변환)
            df = pd.read_excel(self.input_excel)
            df.columns = df.columns.str.lower()
            
            # 엑셀 형식 검증
            is_valid, error_message = self._validate_excel_format(df)
            if not is_valid:
                raise ValueError(f"Invalid Excel format: {error_message}")

            # 필요한 칼럼만 선택하고 순서 재정렬
            required_columns = ['ip', 'vendor', 'model', 'version', 'connection_type', 'port', 'username', 'password']
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
                    f.write("Invalid Device Information:\n")
                    f.write("="*50 + "\n")
                    for invalid in invalid_devices:
                        f.write(f"Device: {invalid['device']}\n")
                        f.write(f"Error: {invalid['error']}\n")
                        f.write("-"*30 + "\n")

            if not valid_devices:
                raise ValueError("No valid devices found in the input file")

            return valid_devices

        except Exception as e:
            self.logger.error(f"Error loading devices: {str(e)}")
            raise ValueError(f"Error loading devices: {str(e)}")
    
    def inspect_devices(self):
        """모든 장비를 점검합니다."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_device = {
                executor.submit(self._connect_to_device, device): device
                for device in self.devices
            }
            
            for future in concurrent.futures.as_completed(future_to_device):
                device, results = future.result()
                # Lock을 사용하여 결과 저장
                with self.results_lock:
                    self.results.append({
                        'IP': device['ip'],
                        'Vendor': device['vendor'],
                        'Model': device['model'],
                        'Version': device['version'],
                        **results
                    })
    
    def save_results(self):
        """결과를 엑셀 파일에 저장합니다."""
        df = pd.DataFrame(self.results)
        df.to_excel(self.output_excel, index=False)

def main():
    input_excel = "devices.xlsx"  # 입력 엑셀 파일
    output_excel = "inspection_results.xlsx"  # 출력 엑셀 파일
    
    inspector = NetworkInspector(input_excel, output_excel)
    inspector.inspect_devices()
    inspector.save_results()

if __name__ == "__main__":
    main() 