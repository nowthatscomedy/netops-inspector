from typing import Dict, List

# 장비별 점검 명령어 정의
INSPECTION_COMMANDS = {
    'cisco': {
        'ios': [
            'show version',
            'show interfaces status',
            'show ip interface brief',
            'show running-config'
        ],
        'ios-xe': [
            'show version',
            'show interfaces status',
            'show ip interface brief',
            'show running-config'
        ]
    },
    'juniper': {
        'junos': [
            'show version',
            'show interfaces terse',
            'show configuration'
        ]
    },
    'ubiquoss': {
        'e4020': [
            'show version',
            'show interfaces status',
            'show ip interface brief',
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
    }
}

# 명령어 결과 파싱 규칙 정의
PARSING_RULES = {
    'cisco': {
        'ios': {
            'show version': {
                'pattern': r'Cisco IOS Software.*Version\s+([^\s,]+)',
                'output_column': 'IOS Version'
            },
            'show interfaces status': {
                'pattern': r'(\S+)\s+connected\s+\d+\s+\S+\s+\S+\s+\S+',
                'output_column': 'Connected Interfaces'
            }
        }
    },
    'ubiquoss': {
        'e4020': {
            'show version': {
                'pattern': r'Version\s+([^\s,]+)',
                'output_column': 'Version'
            },
            'show interfaces status': {
                'pattern': r'(\S+)\s+connected\s+\d+\s+\S+\s+\S+\s+\S+',
                'output_column': 'Connected Interfaces'
            },
            'show ip interface brief': {
                'pattern': r'(\S+)\s+(?:\d+\.\d+\.\d+\.\d+|unassigned)\s+(up|down)\s+(up|down)',
                'output_column': 'Interface Status'
            }
        }
    }
} 