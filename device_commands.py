from typing import Dict, List

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
        ]
    },
    'juniper': {
        'junos': [
            'show version',
            'show configuration'
        ],
        'srx300': [
            'show version',
            'show system uptime',
            'show chassis hardware',
            'show configuration'
        ]
    },
    'ubiquoss': {
        'e4020': [
            'show version',
            'show running-config'
        ]
    },
    'axgate': {
        'axgate-80d': [
            'show system version',
            'show running-config'
        ]
    },
    'nexg': {
        'vforce': [
            'show version',
            'show running-config'
        ]
    }
}

# 장비별 설정 백업 명령어 정의
BACKUP_COMMANDS = {
    'cisco': {
        'ios': 'show running-config',
        'ios-xe': 'show running-config'
    },
    'juniper': {
        'junos': 'show configuration | display set',
        'srx300': 'show configuration | display set'
    },
    'ubiquoss': {
        'e4020': 'show running-config'
    },
    'axgate': {
        'axgate-80d': 'show running-config'
    },
    'nexg': {
        'vforce': 'show running-config'
    }
}

# 명령어 결과 파싱 규칙 정의
PARSING_RULES = {
    'cisco': {
        'ios': {
            'show version': {
                'pattern': r'Cisco IOS Software.*Version\s+([^\s,]+)',
                'output_column': 'Version'
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
        'axgate-80d': {
            'show system version': {
                'pattern': r'OS:\s+(aos v[^\r\n]+)',
                'output_column': 'Version'
            },
        }
    },
    'nexg': {
        'vforce': {
            'show version': {
                'patterns': [
                    {
                        'pattern': r'NexG VForce Software, Version\s+([^\s\r\n]+)',
                        'output_column': 'Version'
                    },
                    {
                        'pattern': r'(\S+)\s+uptime is\s+([^\r\n]+)',
                        'output_columns': ['Hostname', 'Uptime']
                    },
                    {
                        'pattern': r'NexG\s+(\S+)\s+\(',
                        'output_column': 'Model'
                    },
                    {
                        'pattern': r'Processor board serial number\s+(\S+)',
                        'output_column': 'Serial Number'
                    }
                ]
            }
        }
    },
    'juniper': {
        'junos': {
            'show version': {
                'pattern': r'Junos:\s+([^\s,]+)',
                'output_column': 'Version'
            }
        },
        'srx300': {
            'show version': {
                'pattern': r'Junos:\s+([^\s,]+)',
                'output_column': 'Version'
            },
            'show system uptime': {
                'pattern': r'System booted:\s+(.+?)(?:\n|\r\n)',
                'output_column': 'Uptime'
            },
            'show chassis hardware': {
                'patterns': [
                    {
                        'pattern': r'Chassis\s+\S*\s+\S*\s+(\S+)\s+SRX300',
                        'output_column': 'Serial Number'
                    },
                    {
                        'pattern': r'Chassis\s+\S*\s+\S*\s+\S+\s+(SRX\d+)',
                        'output_column': 'Model'
                    }
                ]
            }
        }
    }
} 