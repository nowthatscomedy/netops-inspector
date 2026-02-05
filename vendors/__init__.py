# vendors/__init__.py

import os
import json
import importlib
import pkgutil
import logging
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

# 각 벤더 모듈에서 필요한 딕셔너리들을 임포트
from .axgate import AXGATE_INSPECTION_COMMANDS, AXGATE_BACKUP_COMMANDS, AXGATE_PARSING_RULES
from .cisco import CISCO_INSPECTION_COMMANDS, CISCO_BACKUP_COMMANDS, CISCO_PARSING_RULES
from .alcatel_lucent import ALCATEL_LUCENT_INSPECTION_COMMANDS, ALCATEL_LUCENT_BACKUP_COMMANDS, ALCATEL_LUCENT_PARSING_RULES
from .juniper import JUNIPER_INSPECTION_COMMANDS, JUNIPER_BACKUP_COMMANDS, JUNIPER_PARSING_RULES
from .nexg import NEXG_INSPECTION_COMMANDS, NEXG_BACKUP_COMMANDS, NEXG_PARSING_RULES
from .ubiquoss import UBIQUOSS_INSPECTION_COMMANDS, UBIQUOSS_BACKUP_COMMANDS, UBIQUOSS_PARSING_RULES
from .piolink import PIOLINK_INSPECTION_COMMANDS, PIOLINK_BACKUP_COMMANDS, PIOLINK_PARSING_RULES
from .handreamnet import HANDREAMNET_INSPECTION_COMMANDS, HANDREAMNET_BACKUP_COMMANDS, HANDREAMNET_PARSING_RULES

# 메인 딕셔너리 초기화 (defaultdict 사용으로 키 존재 여부 확인 불필요)
INSPECTION_COMMANDS = defaultdict(dict)
BACKUP_COMMANDS = defaultdict(dict)
PARSING_RULES = defaultdict(dict)

# 커스텀 파서 함수들을 담을 딕셔너리
CUSTOM_PARSERS = {}

# 커스텀 벤더/OS -> Netmiko device_type 매핑
CONNECTION_OVERRIDES = defaultdict(dict)

# custom_rules.json에서 정의된 벤더/OS 목록
CUSTOM_RULE_PAIRS: set[tuple[str, str]] = set()

def _load_vendor_modules():
    """
    vendors 패키지 내의 모든 모듈을 동적으로 임포트하고,
    각 모듈의 명령어, 파싱 규칙, 커스텀 파서 함수를 자동으로 로드합니다.
    """
    pkg_path = os.path.dirname(__file__)
    pkg_name = os.path.basename(pkg_path)

    for _, name, _ in pkgutil.iter_modules([pkg_path]):
        if name in ['base']:  # 기본 모듈 등은 건너뛰기
            continue
        try:
            module = importlib.import_module(f'.{name}', pkg_name)
            
            # --- 명령어 및 파싱 규칙 로드 ---
            # vendor_name = name.split('_')[0] # ex) 'alcatel_lucent' -> 'alcatel-lucent'
            # if 'alcatel' in vendor_name: vendor_name = 'alcatel-lucent'
            vendor_name = name.replace('_', '-') # ex) 'alcatel_lucent' -> 'alcatel-lucent'

            # 1. 점검 명령어 로드
            cmd_dict_name = f"{name.upper()}_INSPECTION_COMMANDS"
            if hasattr(module, cmd_dict_name):
                vendor_cmds = getattr(module, cmd_dict_name)
                if vendor_name in vendor_cmds:
                    INSPECTION_COMMANDS[vendor_name].update(vendor_cmds[vendor_name])

            # 2. 백업 명령어 로드
            backup_cmd_dict_name = f"{name.upper()}_BACKUP_COMMANDS"
            if hasattr(module, backup_cmd_dict_name):
                vendor_backup_cmds = getattr(module, backup_cmd_dict_name)
                if vendor_name in vendor_backup_cmds:
                    BACKUP_COMMANDS[vendor_name].update(vendor_backup_cmds[vendor_name])

            # 3. 파싱 규칙 로드
            rules_dict_name = f"{name.upper()}_PARSING_RULES"
            if hasattr(module, rules_dict_name):
                vendor_rules = getattr(module, rules_dict_name)
                if vendor_name in vendor_rules:
                    PARSING_RULES[vendor_name].update(vendor_rules[vendor_name])
            
            # --- 커스텀 파서 함수 로드 ---
            for attr_name in dir(module):
                if attr_name.startswith('parsing_'):
                    attr = getattr(module, attr_name)
                    if callable(attr):
                        CUSTOM_PARSERS[attr_name] = attr
                        logger.debug(f"커스텀 파서 등록: {attr_name}")

        except Exception as e:
            logger.error(f"벤더 모듈 '{name}' 로드 실패: {e}")

def _normalize_key(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()

def _mark_custom_pair(vendor: str, os_name: str) -> None:
    if vendor and os_name:
        CUSTOM_RULE_PAIRS.add((vendor, os_name))

def _merge_inspection_commands(custom_commands: dict) -> None:
    if not isinstance(custom_commands, dict):
        return

    for vendor_key, os_map in custom_commands.items():
        vendor = _normalize_key(vendor_key)
        if not vendor or not isinstance(os_map, dict):
            continue
        for os_key, commands in os_map.items():
            os_name = _normalize_key(os_key)
            if not os_name or not isinstance(commands, list):
                continue
            _mark_custom_pair(vendor, os_name)
            cleaned = [str(cmd).strip() for cmd in commands if isinstance(cmd, str) and cmd.strip()]
            if not cleaned:
                continue
            existing = INSPECTION_COMMANDS.get(vendor, {}).get(os_name, [])
            merged = list(existing)
            for cmd in cleaned:
                if cmd not in merged:
                    merged.append(cmd)
            INSPECTION_COMMANDS[vendor][os_name] = merged

def _merge_backup_commands(custom_commands: dict) -> None:
    if not isinstance(custom_commands, dict):
        return

    for vendor_key, os_map in custom_commands.items():
        vendor = _normalize_key(vendor_key)
        if not vendor or not isinstance(os_map, dict):
            continue
        for os_key, command in os_map.items():
            os_name = _normalize_key(os_key)
            if not os_name or not isinstance(command, str) or not command.strip():
                continue
            _mark_custom_pair(vendor, os_name)
            BACKUP_COMMANDS[vendor][os_name] = command.strip()

def _merge_parsing_rules(custom_rules: dict) -> None:
    if not isinstance(custom_rules, dict):
        return

    for vendor_key, os_map in custom_rules.items():
        vendor = _normalize_key(vendor_key)
        if not vendor or not isinstance(os_map, dict):
            continue
        for os_key, command_map in os_map.items():
            os_name = _normalize_key(os_key)
            if not os_name or not isinstance(command_map, dict):
                continue
            _mark_custom_pair(vendor, os_name)
            for command, rules in command_map.items():
                if not isinstance(command, str) or not command.strip():
                    continue
                if not isinstance(rules, dict):
                    continue
                PARSING_RULES[vendor].setdefault(os_name, {})
                PARSING_RULES[vendor][os_name][command.strip()] = rules

def _normalize_device_type(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()

def _merge_connection_overrides(custom_rules: dict) -> None:
    if not isinstance(custom_rules, dict):
        return

    for vendor_key, os_map in custom_rules.items():
        vendor = _normalize_key(vendor_key)
        if not vendor or not isinstance(os_map, dict):
            continue
        for os_key, override in os_map.items():
            os_name = _normalize_key(os_key)
            if not os_name:
                continue
            _mark_custom_pair(vendor, os_name)

            if isinstance(override, str):
                device_type = _normalize_device_type(override)
                if not device_type:
                    continue
                CONNECTION_OVERRIDES[vendor][os_name] = {"default": device_type}
                continue

            if not isinstance(override, dict):
                continue

            mapped: dict[str, str] = {}
            for conn_key, device_type in override.items():
                conn = _normalize_key(conn_key)
                if conn not in {"ssh", "telnet", "default", "any"}:
                    continue
                normalized_device_type = _normalize_device_type(device_type)
                if normalized_device_type:
                    mapped[conn] = normalized_device_type

            if mapped:
                CONNECTION_OVERRIDES[vendor][os_name] = mapped

def _load_custom_rules() -> None:
    project_root = Path(__file__).resolve().parents[1]
    custom_rules_path = project_root / "custom_rules.json"
    if not custom_rules_path.exists():
        return

    try:
        data = json.loads(custom_rules_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"custom_rules.json 로드 실패: {e}")
        return

    if not isinstance(data, dict):
        logger.error("custom_rules.json 형식 오류: 최상위가 dict가 아닙니다.")
        return

    _merge_inspection_commands(data.get("inspection_commands", {}))
    _merge_backup_commands(data.get("backup_commands", {}))
    _merge_parsing_rules(data.get("parsing_rules", {}))
    _merge_connection_overrides(data.get("connection_overrides", {}))

def is_custom_rule_pair(vendor: str, os_name: str) -> bool:
    vendor_key = _normalize_key(vendor)
    os_key = _normalize_key(os_name)
    if not vendor_key or not os_key:
        return False
    return (vendor_key, os_key) in CUSTOM_RULE_PAIRS

_load_vendor_modules()
_load_custom_rules()

# get_custom_handler 함수는 base에서 직접 임포트하여 사용하도록 변경
from .base import get_custom_handler

# __all__을 사용하여 외부에 노출할 이름 명시
__all__ = [
    'INSPECTION_COMMANDS',
    'BACKUP_COMMANDS',
    'PARSING_RULES',
    'CUSTOM_PARSERS',
    'CONNECTION_OVERRIDES',
    'CUSTOM_RULE_PAIRS',
    'is_custom_rule_pair',
    'get_custom_handler',
]

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
# Piolink 커스텀 파서 임포트
from vendors.piolink import (
    parsing_piolink_login_count,
    parsing_piolink_port_up_count,
    parsing_piolink_poe_enable_count
)
# Ruckus 커스텀 파서 임포트
from vendors.ruckus import (
    parsing_ruckus_power,
    parsing_ruckus_fan,
    parsing_ruckus_temp,
    parsing_ruckus_memory,
    parsing_ruckus_cpu,
)

# 명시적으로 외부에 노출할 이름들을 정의합니다.
__all__ = [
    'INSPECTION_COMMANDS',
    'BACKUP_COMMANDS',
    'PARSING_RULES',
    'CUSTOM_PARSERS',
    'CONNECTION_OVERRIDES',
    'CUSTOM_RULE_PAIRS',
    'is_custom_rule_pair',
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
    'parsing_ubiquoss_power_status',
    'parsing_piolink_login_count',
    'parsing_piolink_port_up_count',
    'parsing_piolink_poe_enable_count',
    'parsing_ruckus_power',
    'parsing_ruckus_fan',
    'parsing_ruckus_temp',
    'parsing_ruckus_memory',
    'parsing_ruckus_cpu',
] 