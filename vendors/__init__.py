# vendors/__init__.py

# 각 벤더 모듈에서 필요한 딕셔너리들을 임포트
from .axgate import AXGATE_INSPECTION_COMMANDS, AXGATE_BACKUP_COMMANDS, AXGATE_PARSING_RULES
from .cisco import CISCO_INSPECTION_COMMANDS, CISCO_BACKUP_COMMANDS, CISCO_PARSING_RULES
from .alcatel_lucent import ALCATEL_INSPECTION_COMMANDS, ALCATEL_BACKUP_COMMANDS, ALCATEL_PARSING_RULES
from .juniper import JUNIPER_INSPECTION_COMMANDS, JUNIPER_BACKUP_COMMANDS, JUNIPER_PARSING_RULES
from .nexg import NEXG_INSPECTION_COMMANDS, NEXG_BACKUP_COMMANDS, NEXG_PARSING_RULES
from .ubiquoss import UBIQUOSS_INSPECTION_COMMANDS, UBIQUOSS_BACKUP_COMMANDS, UBIQUOSS_PARSING_RULES

# 메인 딕셔너리 초기화
INSPECTION_COMMANDS = {}
BACKUP_COMMANDS = {}
PARSING_RULES = {}

# 각 벤더의 딕셔너리들을 메인 딕셔너리에 병합
# update() 메소드를 사용하여 키가 겹치더라도 벤더별로 고유하게 유지되도록 함 (벤더명이 최상위 키이므로)

# Axgate
INSPECTION_COMMANDS.update(AXGATE_INSPECTION_COMMANDS)
BACKUP_COMMANDS.update(AXGATE_BACKUP_COMMANDS)
PARSING_RULES.update(AXGATE_PARSING_RULES)

# Cisco
INSPECTION_COMMANDS.update(CISCO_INSPECTION_COMMANDS)
BACKUP_COMMANDS.update(CISCO_BACKUP_COMMANDS)
PARSING_RULES.update(CISCO_PARSING_RULES)

# Alcatel-Lucent
INSPECTION_COMMANDS.update(ALCATEL_INSPECTION_COMMANDS)
BACKUP_COMMANDS.update(ALCATEL_BACKUP_COMMANDS)
PARSING_RULES.update(ALCATEL_PARSING_RULES)

# Juniper
INSPECTION_COMMANDS.update(JUNIPER_INSPECTION_COMMANDS)
BACKUP_COMMANDS.update(JUNIPER_BACKUP_COMMANDS)
PARSING_RULES.update(JUNIPER_PARSING_RULES)

# NexG
INSPECTION_COMMANDS.update(NEXG_INSPECTION_COMMANDS)
BACKUP_COMMANDS.update(NEXG_BACKUP_COMMANDS)
PARSING_RULES.update(NEXG_PARSING_RULES)

# Ubiquoss
INSPECTION_COMMANDS.update(UBIQUOSS_INSPECTION_COMMANDS)
BACKUP_COMMANDS.update(UBIQUOSS_BACKUP_COMMANDS)
PARSING_RULES.update(UBIQUOSS_PARSING_RULES)

# 커스텀 파서 함수 및 핸들러 선택 함수도 필요시 여기서 노출 가능
# 예: from .alcatel_lucent import parsing_alcatel_hostname 등
#     from .base import get_custom_handler

# 메인 스크립트에서 직접 임포트하는 커스텀 파서 함수들을 __all__에 명시하거나,
# 아니면 메인 스크립트에서 각 모듈로부터 직접 임포트하도록 유지합니다.
# 현재는 메인 스크립트에서 vendors.모듈명 형태로 접근하고 있으므로,
# INSPECTION_COMMANDS, BACKUP_COMMANDS, PARSING_RULES 만 __init__.py에서 준비하면 됩니다.

# get_custom_handler 함수도 여기서 임포트하여 vendors 패키지를 통해 접근 가능하게 합니다.
from .base import get_custom_handler

# 특정 함수들을 `from vendors import ...` 형태로 사용하고 싶다면 __all__에 추가합니다.
# 예를 들어, Alcatel 파서 함수들을 vendors 패키지 레벨에서 직접 접근하게 하려면:
# from .alcatel_lucent import (
#     parsing_alcatel_hostname, parsing_alcatel_temperature, parsing_alcatel_fan,
#     parsing_alcatel_power, parsing_alcatel_uptime, parsing_alcatel_version,
#     parsing_alcatel_stack, parsing_alcatel_cpu, parsing_alcatel_memory
# )
# __all__ = [
#     'INSPECTION_COMMANDS', 'BACKUP_COMMANDS', 'PARSING_RULES', 'get_custom_handler',
#     'parsing_alcatel_hostname', # ... 기타 Alcatel 파서 함수들
# ]
# 하지만 현재 메인 스크립트에서는 from vendors import parsing_alcatel_hostname 처럼 사용하고 있으므로,
# 이 방식이 유지되려면 해당 함수들이 __init__.py에 정의되거나 임포트되어야 합니다.

# 기존 메인 스크립트의 임포트 방식 (`from vendors import parsing_alcatel_hostname` 등)을 유지하기 위해
# 필요한 함수들을 여기서 임포트합니다.
from vendors.alcatel_lucent import (
    parsing_alcatel_hostname, parsing_alcatel_temperature, parsing_alcatel_fan,
    parsing_alcatel_power, parsing_alcatel_uptime, parsing_alcatel_version,
    parsing_alcatel_stack, parsing_alcatel_cpu, parsing_alcatel_memory
)
# Axgate 커스텀 파서 임포트
from vendors.axgate import parsing_axgate_power_status
# Ubiquoss 커스텀 파서 임포트
from vendors.ubiquoss import (
    parsing_ubiquoss_cpu_usage,
    parsing_ubiquoss_fan_status,
    parsing_ubiquoss_power_status
)

# 명시적으로 외부에 노출할 이름들을 정의합니다.
__all__ = [
    'INSPECTION_COMMANDS',
    'BACKUP_COMMANDS',
    'PARSING_RULES',
    'get_custom_handler',
    'parsing_alcatel_hostname',
    'parsing_alcatel_temperature',
    'parsing_alcatel_fan',
    'parsing_alcatel_power',
    'parsing_alcatel_uptime',
    'parsing_alcatel_version',
    'parsing_alcatel_stack',
    'parsing_alcatel_cpu',
    'parsing_alcatel_memory',
    'parsing_axgate_power_status',
    'parsing_ubiquoss_cpu_usage',
    'parsing_ubiquoss_fan_status',
    'parsing_ubiquoss_power_status'
] 