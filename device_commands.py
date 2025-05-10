from typing import Dict, List

# 장비별 점검 명령어 정의
INSPECTION_COMMANDS = {
    'cisco': {
        'ios': {
            '15.0': [
                'show version',
                'show interfaces status',
                'show ip interface brief',
                'show running-config'
            ],
            '16.0': [
                'show version',
                'show interfaces status',
                'show ip interface brief',
                'show running-config'
            ]
        },
        'ios-xe': {
            '17.0': [
                'show version',
                'show interfaces status',
                'show ip interface brief',
                'show running-config'
            ]
        }
    },
    'juniper': {
        'junos': {
            '19.0': [
                'show version',
                'show interfaces terse',
                'show configuration'
            ]
        }
    }
}

# 장비별 설정 백업 명령어 정의
BACKUP_COMMANDS = {
    'cisco': {
        'ios': {
            '15.0': 'show running-config',
            '16.0': 'show running-config'
        },
        'ios-xe': {
            '17.0': 'show running-config'
        }
    },
    'juniper': {
        'junos': {
            '19.0': 'show configuration | display set'
        }
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
    }
} 