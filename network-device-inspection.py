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

class NetworkInspector:
    def __init__(self, input_excel: str, output_excel: str):
        self.input_excel = input_excel
        self.output_excel = output_excel
        self.devices = self._load_devices()
        self.results = []
        self.results_lock = threading.Lock()  # 결과 저장을 위한 Lock 추가
        self.backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_log_dir = f"session_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.session_log_dir, exist_ok=True)
        
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

    def _load_devices(self) -> List[Dict]:
        """엑셀 파일에서 장비 정보를 로드하고 검증합니다."""
        try:
            df = pd.read_excel(self.input_excel)
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
            raise ValueError(f"Error loading devices: {str(e)}")
    
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
        try:
            connection_params = {
                'device_type': f"{device['vendor']}_{device['model']}",
                'host': device['ip'],
                'username': device['username'],
                'password': device['password'],
                'port': device['port'],
                'secret': device.get('enable_password', '')
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
                
                # 설정 백업
                backup_cmd = self._get_backup_command(
                    device['vendor'],
                    device['model'],
                    device['version']
                )
                if backup_cmd:
                    backup_output = conn.send_command(backup_cmd)
                    backup_filename = os.path.join(
                        self.backup_dir,
                        f"{device['ip']}_{device['vendor']}_{device['model']}.txt"
                    )
                    with open(backup_filename, 'w', encoding='utf-8') as f:
                        f.write(backup_output)
                
                return device, inspection_results
                
        except Exception as e:
            # 에러 로그 저장
            error_log_dir = os.path.join(self.session_log_dir, f"{device['ip']}_{device['vendor']}_{device['model']}")
            os.makedirs(error_log_dir, exist_ok=True)
            error_log = os.path.join(error_log_dir, "error.log")
            with open(error_log, 'w', encoding='utf-8') as f:
                f.write(f"Error connecting to {device['ip']}: {str(e)}")
            print(f"Error connecting to {device['ip']}: {str(e)}")
            return device, {}
    
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