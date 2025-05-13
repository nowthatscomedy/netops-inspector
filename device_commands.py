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
        'axgate': {
            'show system version': {
                'pattern': r'Version\s+:\s+(.*)',
                'output_column': 'Version'
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
    'juniper': {
        'junos': {
            'show version': {
                'pattern': r'Model:\s+srx\d+.*?\nJunos:\s+([\d\.\-A-Z]+)',
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
                        'pattern': r'CB\s+\d+\s+(\S+)\s+',
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
                        'output_column': 'HW Version'
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
    }
} 