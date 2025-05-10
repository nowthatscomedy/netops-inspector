import pandas as pd
import concurrent.futures
import re
from netmiko import ConnectHandler
from typing import Dict, List, Tuple
import os
from datetime import datetime
from device_commands import INSPECTION_COMMANDS, BACKUP_COMMANDS, PARSING_RULES

class NetworkInspector:
    def __init__(self, input_excel: str, output_excel: str):
        self.input_excel = input_excel
        self.output_excel = output_excel
        self.devices = self._load_devices()
        self.results = []
        self.backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.backup_dir, exist_ok=True)
        
    def _load_devices(self) -> List[Dict]:
        """엑셀 파일에서 장비 정보를 로드합니다."""
        df = pd.read_excel(self.input_excel)
        return df.to_dict('records')
    
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