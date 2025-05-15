from typing import Dict, List
import re  # 정규표현식 처리를 위한 모듈 추가

# 장비별 점검 명령어 정의
INSPECTION_COMMANDS = {
    'cisco': {
        'ios': [
            'show version',
            'show running-config'
        ],
        'ios-xe': [
            'show version',
            'show running-config'
        ],
        'legacy': [
            'show version',
            'show running-config'
        ]
    },
    'juniper': {
        'junos': [
            'show version',
            'show system uptime',
            'show chassis hardware',
            'show configuration'
        ]
    },
    'ubiquoss': {
        'e4020': [
            'show version',
            'show system'
        ]
    },
    'axgate': {
        'axgate': [
            'show system version',
            'show system hostname',
            'show system temperature',
            'show system fan',
            'show system uptime',
            'show resource cpu',
            'show resource memory',
            'show running-config'
        ]
    },
    'nexg': {
        'vforce': [
            'show version',
            'show running-config'
        ]
    },
    'alcatel-lucent': {
        'aos6': [
            'show configuration snapshot',
            'show temperature',
            'show fan',
            'show power',
            'show system',
            'show stack status',
            'show health all cpu',
            'show health all memory'
        ],
        'aos8': [
            'show configuration snapshot',
            'show temperature',
            'show fan',
            'show power',
            'show system',
            'show stack status',
            'show health all cpu',
            'show health all memory'
        ]
    }
}

# 장비별 설정 백업 명령어 정의
BACKUP_COMMANDS = {
    'cisco': {
        'ios': 'show running-config',
        'ios-xe': 'show running-config',
        'legacy': 'show running-config'
    },
    'juniper': {
        'junos': 'show configuration | display set'
    },
    'ubiquoss': {
        'e4020': 'show running-config'
    },
    'axgate': {
        'axgate': 'show running-config'
    },
    'nexg': {
        'vforce': 'show running-config'
    },
    'alcatel-lucent': {
        'aos6': 'show configuration snapshot',
        'aos8': 'show configuration snapshot'
    }
}

# Alcatel-Lucent 장비 파싱 함수들
def parsing_alcatel_hostname(output):
    """Alcatel-Lucent 장비의 호스트네임 파싱"""
    hostname = re.search(r'session prompt default "(\S+)>"', output)
    if hostname:
        result = hostname.group(1)
    else:
        result = "Error"
    return result

def parsing_alcatel_temperature(output):
    """Alcatel-Lucent 장비의 온도 정보 파싱"""
    lines = output.split("\n")
    chassis_numbers = []
    for line in lines:
        if "Temperature for chassis" in line:
            chassis_number = line.split()[-1]
        elif "Temperature Status" in line and "OVER THRESHOLD" in line:
            chassis_numbers.append(chassis_number)

    if len(chassis_numbers) > 0:
        str_list = 'Check: ' + ', '.join(str(num) for num in chassis_numbers)
        result = str_list
    else:
        result = "OK"
    return result

def parsing_alcatel_fan(output):
    """Alcatel-Lucent 장비의 팬 상태 파싱"""
    lines = output.split("\n")
    not_running_fans = []

    for line in lines:
        try:
            line_data = line.split()
            chassis = line_data[0]
            fan = line_data[1]
            status = line_data[2]

            if status == "Not" and line_data[3] == "Running":
                not_running_fans.append(chassis + "-" + fan)
        except IndexError:
            pass
    
    if len(not_running_fans) > 0:
        result = 'Check: ' + ", ".join(str(num) for num in not_running_fans)
    else:
        result = 'OK'
    return result

def parsing_alcatel_power(output):
    """Alcatel-Lucent 장비의 전원 상태 파싱"""
    lines = output.split("\n")
    powers = []

    for line in lines:
        try:
            line_output = line.split()
            slot = line_output[0]
            power = line_output[1]
            status = line_output[4]
            if status == "DOWN":
                powers.append(slot + "-" + power)
        except IndexError:
            pass
    
    if len(powers) > 0:
        result = 'Check: ' + ", ".join(str(num) for num in powers)
    else:
        result = 'OK'
    return result

def parsing_alcatel_uptime(output):
    """Alcatel-Lucent 장비의 업타임 파싱"""
    uptime = re.search(r'\s+Up\s+Time:\s+(\S+\s\S+\s\S+\s\S+)', output)
    if uptime:
        result = uptime.group(1)
    else:
        result = "Unknown"
    return result

def parsing_alcatel_version(output):
    """Alcatel-Lucent 장비의 버전 정보 파싱"""
    lines = output.strip().split('\n')
    result = "Unknown"

    try:
        for line in lines:
            words = line.split()
            if len(words) >= 2:
                result = words[-5] + ' ' + words[-4].replace(',', '')
                break
    except IndexError:
        pass
    return result

def parsing_alcatel_stack(output):
    """Alcatel-Lucent 장비의 스택 상태 파싱"""
    if "Redundant cable status  : not present" in output:
        return "not present"
    elif "Redundant cable status  : present" in output:
        return "present"
    else:
        return "Unknown"
    
def parsing_alcatel_cpu(output):
    """Alcatel-Lucent 장비의 CPU 사용률 파싱"""
    lines = output.strip().split('\n')
    cpu_usage = 0

    for line in lines: 
        values = line.split()
        try:
            max_value = int(values[-2])
            if max_value > cpu_usage:
                cpu_usage = max_value
        except IndexError:
            pass
        except ValueError:
            pass
    return cpu_usage

def parsing_alcatel_memory(output):
    """Alcatel-Lucent 장비의 메모리 사용률 파싱"""
    lines = output.strip().split('\n')
    memory_usage = 0

    for line in lines: 
        values = line.split()
        try:
            max_value = int(values[-2])
            if max_value > memory_usage:
                memory_usage = max_value
        except IndexError:
            pass
        except ValueError:
            pass
    return memory_usage

# 명령어 결과 파싱 규칙 정의
PARSING_RULES = {
    'cisco': {
        'ios': {
            'show version': {
                'pattern': r'Cisco IOS Software.*Version\s+([^\s,]+)',
                'output_column': 'Version'
            }
        },
        'legacy': {
            'show version': {
                'patterns': [
                    {
                        'pattern': r'(?:Cisco IOS Software|IOS \(tm\)).*?Version\s+([^\s,]+)',
                        'output_column': 'Version',
                        'first_match_only': True
                    },
                    {
                        'pattern': r'([^\s]+) uptime is (.+)',
                        'output_columns': ['Hostname', 'Uptime'],
                        'first_match_only': True
                    },
                    {
                        'pattern': r'(?:cisco|Cisco)\s+(\S+)(?:\s+\([\w\s]+\))?\s+processor',
                        'output_column': 'Model',
                        'first_match_only': True
                    },
                    {
                        'pattern': r'Processor board ID\s+(\S+)',
                        'output_column': 'Serial Number',
                        'first_match_only': True
                    }
                ]
            }
        }
    },
    'ubiquoss': {
        'e4020': {
            'show version': {
                'pattern': r'Version\s+([^\s,]+)',
                'output_column': 'Version'
            }
        }
    },
    'axgate': {
        'axgate': {
            'show system version': {
                'patterns': [
                    {
                        'pattern': r'OS:\s+(.+)',
                        'output_column': 'Version',
                        'first_match_only': True
                    },
                    {
                        'pattern': r'Serial:\s+(.+)',
                        'output_column': 'Serial Number',
                        'first_match_only': True
                    },
                    {
                        'pattern': r'Board:\s+(.+)',
                        'output_column': 'Model',
                        'first_match_only': True
                    }
                ]
            },
            'show system hostname': {
                'pattern': r'Hostname:\s+(.+)',
                'output_column': 'Hostname',
                'first_match_only': True
            },
            'show system temperature': {
                'patterns': [
                    {
                        'pattern': r'System:\s+(\+?[0-9.-]+\s*C)',
                        'output_column': 'System Temperature',
                        'first_match_only': True
                    },
                    {
                        'pattern': r'CPU:\s+(\+?[0-9.-]+\s*C)',
                        'output_column': 'CPU Temperature',
                        'first_match_only': True
                    }
                ]
            },
            'show system fan': {
                'pattern': r'Chassis:\s+(\S+)',
                'output_column': 'Fan Status',
                'first_match_only': True
            },
            'show system uptime': {
                'pattern': r'Uptime:\s+(.+)',
                'output_column': 'Uptime',
                'first_match_only': True
            },
            'show resource cpu': {
                'patterns': [
                    {
                        'pattern': r'T\s+(\d+)\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+\S+\s+(\d+)',
                        'output_columns': ['CPU Total', 'CPU Used'],
                        'first_match_only': True,
                        'process': {
                            'type': 'percentage',
                            'inputs': ['CPU Used', 'CPU Total'],
                            'output_column': 'CPU Usage %'
                        }
                    }
                ]
            },
            'show resource memory': {
                'patterns': [
                    {
                        'pattern': r'T\s+(\d+)\s+\S+\s+\S+\s+\S+\s+(\d+)',
                        'output_columns': ['Memory Total', 'Memory Used'],
                        'first_match_only': True,
                        'process': {
                            'type': 'percentage',
                            'inputs': ['Memory Used', 'Memory Total'],
                            'output_column': 'Memory Usage %'
                        }
                    }
                ]
            }
        }
    },
    'juniper': {
        'junos': {
            'show version': {
                'pattern': r'Junos:\s+([\d\.\-A-Z]+)',
                'output_column': 'Version',
                'first_match_only': True
            },
            'show system uptime': {
                'pattern': r'System booted:\s+(.*?\))',
                'output_column': 'Uptime',
                'first_match_only': True
            },
            'show chassis hardware': {
                'patterns': [
                    {
                        'pattern': r'Chassis\s+(\S+)\s+',
                        'output_column': 'Serial Number',
                        'first_match_only': True
                    },
                    {
                        'pattern': r'Routing Engine\s+\d*\s+(\S+)',
                        'output_column': 'Model',
                        'first_match_only': True
                    }
                ]
            }
        }
    },
    'ubiquoss': {
        'e4020': {
            'show version': {
                'patterns': [
                    {
                        'pattern': r'SW Version\s+:\s+([\d\.]+)',
                        'output_column': 'Version'
                    },
                    {
                        'pattern': r'HW Version\s+:\s+([\d\.]+)',
                        'output_column': 'Version'
                    },
                    {
                        'pattern': r'System Name\s+:\s+(\S+)',
                        'output_column': 'Hostname'
                    },
                    {
                        'pattern': r'Switch Serial No\s+:\s+(\S+)',
                        'output_column': 'Serial Number'
                    }
                ]
            },
            'show system': {
                'pattern': r'Up Time\s+:\s+(.*)',
                'output_column': 'Uptime'
            }
        }
    },
    'nexg': {
        'vforce': {
            'show version': {
                'patterns': [
                    {
                        'pattern': r'Version\s+:\s+([\d\.]+)',
                        'output_column': 'Version'
                    },
                    {
                        'pattern': r'Hostname\s+:\s+(\S+)',
                        'output_column': 'Hostname'
                    },
                    {
                        'pattern': r'Uptime\s+:\s+(.*)',
                        'output_column': 'Uptime'
                    },
                    {
                        'pattern': r'Model\s+:\s+(\S+)',
                        'output_column': 'Model'
                    },
                    {
                        'pattern': r'Serial Number\s+:\s+(\S+)',
                        'output_column': 'Serial Number'
                    }
                ]
            }
        }
    },
    'alcatel-lucent': {
        'aos6': {
            'show configuration snapshot': {
                'pattern': r'session prompt default "(\S+)>"',
                'output_column': 'Hostname',
                'first_match_only': True
            },
            'show temperature': {
                'custom_parser': 'parsing_alcatel_temperature',
                'output_column': 'Temperature'
            },
            'show fan': {
                'custom_parser': 'parsing_alcatel_fan',
                'output_column': 'Fan Status'
            },
            'show power': {
                'custom_parser': 'parsing_alcatel_power',
                'output_column': 'Power Status'
            },
            'show system': {
                'patterns': [
                    {
                        'pattern': r'\s+Up\s+Time:\s+(\S+\s\S+\s\S+\s\S+)',
                        'output_column': 'Uptime',
                        'first_match_only': True
                    },
                    {
                        'custom_parser': 'parsing_alcatel_version',
                        'output_column': 'Version'
                    }
                ]
            },
            'show stack status': {
                'pattern': r'Redundant cable status\s+:\s+(\S+)',
                'output_column': 'Stack Status',
                'first_match_only': True
            },
            'show health all cpu': {
                'custom_parser': 'parsing_alcatel_cpu',
                'output_column': 'CPU Usage %'
            },
            'show health all memory': {
                'custom_parser': 'parsing_alcatel_memory',
                'output_column': 'Memory Usage %'
            }
        },
        'aos8': {
            'show configuration snapshot': {
                'pattern': r'session prompt default "(\S+)>"',
                'output_column': 'Hostname',
                'first_match_only': True
            },
            'show temperature': {
                'custom_parser': 'parsing_alcatel_temperature',
                'output_column': 'Temperature'
            },
            'show fan': {
                'custom_parser': 'parsing_alcatel_fan',
                'output_column': 'Fan Status'
            },
            'show power': {
                'custom_parser': 'parsing_alcatel_power',
                'output_column': 'Power Status'
            },
            'show system': {
                'patterns': [
                    {
                        'pattern': r'\s+Up\s+Time:\s+(\S+\s\S+\s\S+\s\S+)',
                        'output_column': 'Uptime',
                        'first_match_only': True
                    },
                    {
                        'custom_parser': 'parsing_alcatel_version',
                        'output_column': 'Version'
                    }
                ]
            },
            'show stack status': {
                'pattern': r'Redundant cable status\s+:\s+(\S+)',
                'output_column': 'Stack Status',
                'first_match_only': True
            },
            'show health all cpu': {
                'custom_parser': 'parsing_alcatel_cpu',
                'output_column': 'CPU Usage %'
            },
            'show health all memory': {
                'custom_parser': 'parsing_alcatel_memory',
                'output_column': 'Memory Usage %'
            }
        }
    }
} 