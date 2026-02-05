import logging
import os
import msvcrt
import sys
import shutil
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from core.inspector import NetworkInspector
from core.file_handler import read_excel_file, save_results_to_excel, read_command_file
from core.validator import validate_dataframe
from core.ui import get_password_from_dialog
from core.custom_exceptions import NetworkInspectorError
from core.logging_config import init_logging
from core.settings import load_settings, save_settings, AppSettings
from vendors import INSPECTION_COMMANDS, PARSING_RULES

logger = logging.getLogger(__name__)

BANNER = [
    "⡴⠒⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣼⠉⠳⡆⠀",
    "⣇⠰⠉⢙⡄⠀⠀⣴⠖⢦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣆⠁⠙⡆",
    "⠘⡇⢠⠞⠉⠙⣾⠃⢀⡼⠀⠀⠀⠀⠀⠀⠀⢀⣼⡀⠄⢷⣄⣀⠀⠀⠀⠀⠀⠀⠀⠰⠒⠲⡄⠀⣏⣆⣀⡍",
    "⠀⢠⡏⠀⡤⠒⠃⠀⡜⠀⠀⠀⠀⠀⢀⣴⠾⠛⡁⠀⠀⢀⣈⡉⠙⠳⣤⡀⠀⠀⠀⠘⣆⠀⣇⡼⢋⠀⠀⢱",
    "⠀⠘⣇⠀⠀⠀⠀⠀⡇⠀⠀⠀⠀⡴⢋⡣⠊⡩⠋⠀⠀⠀⠣⡉⠲⣄⠀⠙⢆⠀⠀⠀⣸⠀⢉⠀⢀⠿⠀⢸",
    "⠀⠀⠸⡄⠀⠈⢳⣄⡇⠀⠀⢀⡞⠀⠈⠀⢀⣴⣾⣿⣿⣿⣿⣦⡀⠀⠀⠀⠈⢧⠀⠀⢳⣰⠁⠀⠀⠀⣠⠃",
    "⠀⠀⠀⠘⢄⣀⣸⠃⠀⠀⠀⡸⠀⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣆⠀⠀⠀⠈⣇⠀⠀⠙⢄⣀⠤⠚⠁⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡇⠀⠀⢠⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡄⠀⠀⠀⢹⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡀⠀⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡀⠀⠀⢘⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⡇⠀⢰⣿⣿⣿⡿⠛⠁⠀⠉⠛⢿⣿⣿⣿⣧⠀⠀⣼⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⡀⣸⣿⣿⠟⠀⠀⠀⠀⠀⠀⠀⢻⣿⣿⣿⡀⢀⠇⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⡇⠹⠿⠋⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⢿⡿⠁⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠻⣤⣞⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢢⣀⣠⠇⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
    "⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⠲⢤⣀⣀⠀⢀⣀⣀⠤⠒⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀",
]

try:
    from colorama import Fore, Style, init as colorama_init
except Exception:
    Fore = None
    Style = None
    colorama_init = None

if colorama_init is not None:
    colorama_init(autoreset=True)

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

def _strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)

def _text_width(text: str) -> int:
    cleaned = _strip_ansi(text.rstrip())
    width = 0
    for ch in cleaned:
        if ch == "\t":
            width += 4
            continue
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            width += 2
        else:
            width += 1
    return width

def _color(text: str, color: str) -> str:
    if Fore is None or Style is None:
        return text
    return f"{color}{text}{Style.RESET_ALL}"

def _with_banner(hints: list[str] | None) -> list[str]:
    """메뉴 힌트에 배너를 일관되게 포함"""
    lines = [line.rstrip() for line in BANNER]
    if hints:
        lines.extend(line.rstrip() for line in hints)
    return lines

def _is_banner_line(line: str) -> bool:
    return line.rstrip() in BANNER

def _pad(text: str, width: int, align: str = "left") -> str:
    plain_len = _text_width(text)
    if plain_len >= width:
        return text
    if align == "center":
        left = (width - plain_len) // 2
        right = width - plain_len - left
        return (" " * left) + text + (" " * right)
    return text + (" " * (width - plain_len))

def _print_menu_frame(title: str, hints: list[str] | None, options: list[str], selected: int) -> None:
    control_line = "조작: ↑/↓ 이동, Enter 선택"
    hint_lines = [line.rstrip() for line in (hints or [])]
    option_lines = [
        (( ">> " if i == selected else "   ") + option).rstrip()
        for i, option in enumerate(options)
    ]

    measure_lines = [control_line, *hint_lines, *option_lines]
    if title:
        measure_lines.append(title)
    width = max(_text_width(line) for line in measure_lines) if measure_lines else 0

    top = "+" + "=" * (width + 2) + "+"
    mid = "+" + "-" * (width + 2) + "+"

    print(top)
    if title:
        title_text = _color(title, Fore.CYAN + Style.BRIGHT) if Fore and Style else title
        print("| " + _pad(title_text, width, align="center") + " |")
        print(mid)

    if hint_lines:
        for line in hint_lines:
            align = "center" if _is_banner_line(line) else "left"
            print("| " + _pad(line, width, align=align) + " |")
        print("| " + _pad("", width) + " |")

    control_text = _color(control_line, Fore.YELLOW) if Fore else control_line
    print("| " + _pad(control_text, width) + " |")
    print(mid)

    for i, line in enumerate(option_lines):
        if i == selected and Fore and Style:
            line = _color(line, Fore.GREEN + Style.BRIGHT)
        print("| " + _pad(line, width) + " |")
    print(top)

def select_menu(
    title: str,
    options: list[str],
    selected_index: int = 0,
    hints: list[str] | None = None
) -> int:
    """키보드 화살표/엔터로 메뉴 선택"""
    selected = max(0, min(selected_index, len(options) - 1))
    while True:
        os.system("cls")
        _print_menu_frame(title, hints, options, selected)

        key = msvcrt.getwch()
        if key in ("\r", "\n"):
            return selected
        if key in ("\x00", "\xe0"):
            key = msvcrt.getwch()
            if key == "H":  # Up
                selected = (selected - 1) % len(options)
            elif key == "P":  # Down
                selected = (selected + 1) % len(options)

def _print_reorder_frame(
    title: str,
    hints: list[str] | None,
    entries: list[dict],
    selected: int,
    moving: bool
) -> None:
    control_line = "조작: ↑/↓ 이동, Enter: 선택/모드 전환"
    status_line = "현재 - 이동 모드: 선택 항목 위치 변경" if moving else "현재 - 선택 모드: 항목/메뉴 선택"
    hint_lines = [line.rstrip() for line in (hints or [])]
    option_lines = []

    for i, entry in enumerate(entries):
        cursor = ">> " if i == selected else "   "
        if entry["type"] == "item":
            marker = "*" if moving and i == selected else " "
            option_lines.append(f"{cursor}[{marker}] {entry['label']}")
        else:
            option_lines.append(f"{cursor}{entry['label']}")

    measure_lines = [control_line, status_line, *hint_lines, *option_lines]
    if title:
        measure_lines.append(title)
    width = max(_text_width(line) for line in measure_lines) if measure_lines else 0

    top = "+" + "=" * (width + 2) + "+"
    mid = "+" + "-" * (width + 2) + "+"

    print(top)
    if title:
        title_text = _color(title, Fore.CYAN + Style.BRIGHT) if Fore and Style else title
        print("| " + _pad(title_text, width, align="center") + " |")
        print(mid)

    if hint_lines:
        for line in hint_lines:
            align = "center" if _is_banner_line(line) else "left"
            print("| " + _pad(line, width, align=align) + " |")
        print("| " + _pad("", width) + " |")

    control_text = _color(control_line, Fore.YELLOW) if Fore else control_line
    print("| " + _pad(control_text, width) + " |")
    print("| " + _pad(status_line, width) + " |")
    print(mid)

    for i, line in enumerate(option_lines):
        if i == selected and Fore and Style:
            line = _color(line, Fore.GREEN + Style.BRIGHT)
        print("| " + _pad(line, width) + " |")
    print(top)


def reorder_columns_interactive(columns: list[str]) -> list[str] | None:
    """CLI에서 점검 항목 순서를 재정렬합니다."""
    if not columns:
        return []

    original_items = list(columns)
    items = list(columns)
    selected = 0
    moving = False

    hints = _with_banner([
        "점검 결과 열 순서를 정합니다.",
        "항목을 선택하고 Enter로 이동 모드를 전환합니다.",
    ])

    while True:
        os.system("cls")
        entries = (
            [{"type": "action", "id": "start", "label": "현재 순서로 시작"}]
            + [{"type": "item", "id": f"item:{idx}", "label": item} for idx, item in enumerate(items)]
            + [
                {"type": "action", "id": "reset", "label": "순서 초기화"},
                {"type": "action", "id": "back", "label": "뒤로가기"},
            ]
        )
        _print_reorder_frame("열 순서 편집", hints, entries, selected, moving)

        key = msvcrt.getwch()
        if key in ("\r", "\n"):
            entry = entries[selected]
            if entry["type"] == "action":
                if entry["id"] == "start":
                    return items
                if entry["id"] == "reset":
                    items = list(original_items)
                    selected = 0
                    moving = False
                    continue
                if entry["id"] == "back":
                    return None
            else:
                moving = not moving
            continue
        if key in ("\x00", "\xe0"):
            key = msvcrt.getwch()
            if key == "H":  # Up
                if moving:
                    item_indices = [i for i, entry in enumerate(entries) if entry["type"] == "item"]
                    current_pos = item_indices.index(selected)
                    if current_pos > 0:
                        swap_target = item_indices[current_pos - 1]
                        item_idx = selected - 1
                        items[item_idx], items[item_idx - 1] = items[item_idx - 1], items[item_idx]
                        selected = swap_target
                else:
                    selected = (selected - 1) % len(entries)
            elif key == "P":  # Down
                if moving:
                    item_indices = [i for i, entry in enumerate(entries) if entry["type"] == "item"]
                    current_pos = item_indices.index(selected)
                    if current_pos < len(item_indices) - 1:
                        swap_target = item_indices[current_pos + 1]
                        item_idx = selected - 1
                        items[item_idx], items[item_idx + 1] = items[item_idx + 1], items[item_idx]
                        selected = swap_target
                else:
                    selected = (selected + 1) % len(entries)

def show_main_menu() -> str:
    """프로그램 시작 메뉴"""
    settings = load_settings()
    options = [
        "작업 시작 (점검/백업 선택)",
        "사용자 명령 파일 실행",
        f"설정 변경 (로그 출력: {settings.console_log_level})",
        "Netmiko device_type 목록 보기",
        "종료"
    ]
    hints = _with_banner([
        "네트워크 장비 점검 프로그램",
        "원하는 작업을 선택하세요.",
    ])
    index = select_menu("메인 메뉴", options, hints=hints)
    return str(index + 1)

def show_netmiko_device_types() -> None:
    """Netmiko가 지원하는 device_type 목록을 출력합니다."""
    os.system("cls")
    print("Netmiko device_type 목록")
    print("-" * 50)
    try:
        from netmiko.ssh_dispatcher import CLASS_MAPPER
        device_types = sorted(CLASS_MAPPER.keys())
        if not device_types:
            print("표시할 device_type이 없습니다.")
        else:
            for name in device_types:
                print(name)
    except Exception as e:
        print(f"device_type 목록을 가져오는 데 실패했습니다: {e}")
    print("-" * 50)
    print("아무 키나 누르면 돌아갑니다.")
    msvcrt.getwch()

def show_action_menu() -> str | None:
    """실행 작업 선택 메뉴"""
    mode_options = [
        "점검만 실행 (백업 없음)",
        "백업만 실행 (점검 없음)",
        "점검 + 백업 (둘 다)",
        "뒤로가기",
    ]
    mode_hints = _with_banner([
        "실행할 작업을 선택하세요.",
        "백업은 장비 설정 파일을 저장합니다.",
    ])
    choice_index = select_menu("작업 선택", mode_options, hints=mode_hints)
    if choice_index == 3:
        return None
    return str(choice_index + 1)

def select_console_log_level(current_level: str) -> str:
    """콘솔 로그 레벨 선택"""
    options = [
        "CRITICAL 이상",
        "ERROR 이상",
        "WARNING 이상",
        "INFO 이상",
        "DEBUG 이상",
        "뒤로가기",
    ]
    level_map = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    try:
        selected_index = level_map.index(current_level)
    except ValueError:
        selected_index = 3
    hints = _with_banner([
        f"[현재] 콘솔 로그 레벨: {current_level}",
        "일반 사용자라면 'WARNING 이상'을 권장합니다.",
    ])
    index = select_menu("콘솔 로그 레벨 설정", options, selected_index, hints=hints)
    if index == 5:
        return current_level
    return level_map[index]

def show_settings_menu(settings: AppSettings) -> None:
    """설정 메뉴"""
    while True:
        options = [
            f"콘솔 로그 레벨 변경 (현재: {settings.console_log_level})",
            "점검 제외 설정",
            "뒤로가기",
        ]
        hints = _with_banner([
            "설정 메뉴",
            "로그 출력이 너무 많다면 'WARNING 이상'으로 줄이세요.",
        ])
        choice = select_menu("설정", options, hints=hints)
        if choice == 0:
            settings.console_log_level = select_console_log_level(settings.console_log_level)
            save_settings(settings)
            print("설정이 저장되었습니다.")
        elif choice == 1:
            show_inspection_exclude_menu(settings)
        elif choice == 2:
            return
        else:
            print("잘못된 선택입니다. 다시 시도하세요.")


def _get_excluded_set(settings: AppSettings, vendor: str, os_name: str) -> set[str]:
    vendor_key = vendor.lower()
    os_key = os_name.lower()
    return set(settings.inspection_excludes.get(vendor_key, {}).get(os_key, []))


def _is_parse_excluded(excludes: set[str], command: str, parse_id: str) -> bool:
    return parse_id in excludes or command in excludes


def _toggle_exclude(settings: AppSettings, vendor: str, os_name: str, parse_id: str) -> None:
    vendor_key = vendor.lower()
    os_key = os_name.lower()
    vendor_map = settings.inspection_excludes.setdefault(vendor_key, {})
    cmd_list = vendor_map.setdefault(os_key, [])

    if parse_id in cmd_list:
        cmd_list = [cmd for cmd in cmd_list if cmd != parse_id]
        if cmd_list:
            vendor_map[os_key] = cmd_list
        else:
            vendor_map.pop(os_key, None)
            if not vendor_map:
                settings.inspection_excludes.pop(vendor_key, None)
    else:
        cmd_list.append(parse_id)
        vendor_map[os_key] = cmd_list

    save_settings(settings)


def _build_exclude_list_for_os(vendor: str, os_name: str) -> list[str]:
    items = _collect_parsing_items(vendor, os_name)
    return [item["id"] for item in items]


def _set_excludes_all(settings: AppSettings, exclude_all: bool) -> None:
    if not exclude_all:
        if settings.inspection_excludes:
            settings.inspection_excludes.clear()
            save_settings(settings)
        return

    new_map: dict[str, dict[str, list[str]]] = {}
    for vendor in INSPECTION_COMMANDS.keys():
        vendor_key = vendor.lower()
        vendor_map: dict[str, list[str]] = {}
        for os_name in INSPECTION_COMMANDS.get(vendor, {}).keys():
            os_key = os_name.lower()
            items = _build_exclude_list_for_os(vendor, os_name)
            if items:
                vendor_map[os_key] = items
        if vendor_map:
            new_map[vendor_key] = vendor_map
    settings.inspection_excludes = new_map
    save_settings(settings)


def _set_excludes_vendor(settings: AppSettings, vendor: str, exclude_all: bool) -> None:
    vendor_key = vendor.lower()
    if not exclude_all:
        if vendor_key in settings.inspection_excludes:
            settings.inspection_excludes.pop(vendor_key, None)
            save_settings(settings)
        return

    vendor_map: dict[str, list[str]] = {}
    for os_name in INSPECTION_COMMANDS.get(vendor, {}).keys():
        os_key = os_name.lower()
        items = _build_exclude_list_for_os(vendor, os_name)
        if items:
            vendor_map[os_key] = items
    if vendor_map:
        settings.inspection_excludes[vendor_key] = vendor_map
    else:
        settings.inspection_excludes.pop(vendor_key, None)
    save_settings(settings)


def _set_excludes_os(settings: AppSettings, vendor: str, os_name: str, exclude_all: bool) -> None:
    vendor_key = vendor.lower()
    os_key = os_name.lower()
    vendor_map = settings.inspection_excludes.setdefault(vendor_key, {})
    if exclude_all:
        items = _build_exclude_list_for_os(vendor, os_name)
        if items:
            vendor_map[os_key] = items
            settings.inspection_excludes[vendor_key] = vendor_map
        else:
            vendor_map.pop(os_key, None)
            if not vendor_map:
                settings.inspection_excludes.pop(vendor_key, None)
        save_settings(settings)
        return

    if os_key in vendor_map:
        vendor_map.pop(os_key, None)
        if vendor_map:
            settings.inspection_excludes[vendor_key] = vendor_map
        else:
            settings.inspection_excludes.pop(vendor_key, None)
        save_settings(settings)


def _collect_parsing_items(vendor: str, os_name: str) -> list[dict]:
    vendor_key = vendor.lower()
    os_key = os_name.lower()
    rules_by_command = PARSING_RULES.get(vendor_key, {}).get(os_key, {})
    items: list[dict] = []
    seen = set()

    for command, rules in rules_by_command.items():
        if not isinstance(rules, dict):
            continue

        def add_item(column: str) -> None:
            if not column:
                return
            parse_id = f"{command}::{column}"
            if parse_id in seen:
                return
            seen.add(parse_id)
            items.append({
                "command": command,
                "column": column,
                "id": parse_id,
                "label": f"{column}  ({command})"
            })

        if "custom_parser" in rules:
            column = rules.get("output_column", "").strip()
            if column:
                add_item(column)
        elif "pattern" in rules:
            column = rules.get("output_column", "").strip()
            if column:
                add_item(column)
            process = rules.get("process", {})
            if isinstance(process, dict):
                process_column = str(process.get("output_column", "")).strip()
                if process_column:
                    add_item(process_column)
        elif "patterns" in rules:
            for pattern_rule in rules.get("patterns", []):
                if not isinstance(pattern_rule, dict):
                    continue
                if "custom_parser" in pattern_rule:
                    column = str(pattern_rule.get("output_column", "")).strip()
                    if column:
                        add_item(column)
                output_columns = pattern_rule.get("output_columns", [])
                if isinstance(output_columns, list):
                    for col in output_columns:
                        if isinstance(col, str) and col.strip():
                            add_item(col.strip())
                column = str(pattern_rule.get("output_column", "")).strip()
                if column:
                    add_item(column)
                process = pattern_rule.get("process", {})
                if isinstance(process, dict):
                    process_column = str(process.get("output_column", "")).strip()
                    if process_column:
                        add_item(process_column)
        else:
            column = rules.get("output_column", "").strip()
            if column:
                add_item(column)

    return items


def show_inspection_exclude_menu(settings: AppSettings) -> None:
    while True:
        vendors = sorted(INSPECTION_COMMANDS.keys())
        options = [vendor for vendor in vendors] + ["점검 항목 모두 포함", "점검 항목 모두 제외", "뒤로가기"]
        hints = _with_banner([
            "점검 제외 설정",
            "벤더를 선택하세요.",
        ])
        choice = select_menu("점검 제외 - 벤더 선택", options, hints=hints)
        if choice == len(vendors):
            if _ask_yes_no("모든 점검 항목을 포함으로 변경할까요?"):
                _set_excludes_all(settings, False)
                print("모든 점검 항목이 포함으로 변경되었습니다.")
            continue
        if choice == len(vendors) + 1:
            if _ask_yes_no("모든 점검 항목을 제외로 변경할까요?"):
                _set_excludes_all(settings, True)
                print("모든 점검 항목이 제외로 변경되었습니다.")
            continue
        if choice == len(vendors) + 2:
            return
        vendor = vendors[choice]
        _show_inspection_exclude_os_menu(settings, vendor)


def _show_inspection_exclude_os_menu(settings: AppSettings, vendor: str) -> None:
    while True:
        os_list = sorted(INSPECTION_COMMANDS.get(vendor, {}).keys())
        options = [os_name for os_name in os_list] + ["해당 벤더 항목 모두 포함", "해당 벤더 항목 모두 제외", "뒤로가기"]
        hints = _with_banner([
            f"벤더: {vendor}",
            "OS를 선택하세요.",
        ])
        choice = select_menu("점검 제외 - OS 선택", options, hints=hints)
        if choice == len(os_list):
            if _ask_yes_no(f"벤더 '{vendor}'의 점검 항목을 모두 포함으로 변경할까요?"):
                _set_excludes_vendor(settings, vendor, False)
                print(f"벤더 '{vendor}'의 점검 항목이 모두 포함으로 변경되었습니다.")
            continue
        if choice == len(os_list) + 1:
            if _ask_yes_no(f"벤더 '{vendor}'의 점검 항목을 모두 제외로 변경할까요?"):
                _set_excludes_vendor(settings, vendor, True)
                print(f"벤더 '{vendor}'의 점검 항목이 모두 제외로 변경되었습니다.")
            continue
        if choice == len(os_list) + 2:
            return
        os_name = os_list[choice]
        _show_inspection_exclude_commands_menu(settings, vendor, os_name)


def _show_inspection_exclude_commands_menu(settings: AppSettings, vendor: str, os_name: str) -> None:
    selected_index = 0
    while True:
        excluded = _get_excluded_set(settings, vendor, os_name)
        items = _collect_parsing_items(vendor, os_name)
        if not items:
            hints = _with_banner([
                f"벤더: {vendor} / OS: {os_name}",
                "파싱 항목이 없습니다.",
            ])
            select_menu("점검 제외 - 항목 선택", ["뒤로가기"], 0, hints=hints)
            return
        options: list[str] = []
        for item in items:
            parse_id = item["id"]
            command = item["command"]
            status = "제외" if _is_parse_excluded(excluded, command, parse_id) else "포함"
            label = f"[{status}] {item['label']}"
            if status == "포함" and Fore and Style:
                label = _color(label, Fore.CYAN + Style.BRIGHT)
            options.append(label)
        options.append("해당 OS 항목 모두 포함")
        options.append("해당 OS 항목 모두 제외")
        options.append("뒤로가기")

        hints = _with_banner([
            f"벤더: {vendor} / OS: {os_name}",
            "Enter로 포함/제외를 전환합니다. (파싱 항목 기준)",
        ])
        choice = select_menu("점검 제외 - 항목 선택", options, selected_index, hints=hints)
        if choice == len(options) - 1:
            return
        if choice == len(options) - 3:
            if _ask_yes_no(f"OS '{os_name}'의 점검 항목을 모두 포함으로 변경할까요?"):
                _set_excludes_os(settings, vendor, os_name, False)
                print(f"OS '{os_name}'의 점검 항목이 모두 포함으로 변경되었습니다.")
                selected_index = 0
            continue
        if choice == len(options) - 2:
            if _ask_yes_no(f"OS '{os_name}'의 점검 항목을 모두 제외로 변경할까요?"):
                _set_excludes_os(settings, vendor, os_name, True)
                print(f"OS '{os_name}'의 점검 항목이 모두 제외로 변경되었습니다.")
                selected_index = 0
            continue
        selected_index = choice
        _toggle_exclude(settings, vendor, os_name, items[choice]["id"])

def _autocomplete_path(partial: str, extensions: tuple[str, ...]) -> str:
    if not partial:
        return partial

    quote = ""
    trimmed = partial
    if partial[0] in ("'", '"'):
        quote = partial[0]
        trimmed = partial[1:]

    if trimmed.endswith(("\\", "/")):
        dir_part = trimmed
        fragment = ""
    else:
        dir_part, fragment = os.path.split(trimmed)

    if not dir_part:
        dir_part = "."

    search_dir = Path(dir_part).expanduser()
    if not search_dir.is_absolute():
        search_dir = Path.cwd() / search_dir
    if not search_dir.exists() or not search_dir.is_dir():
        return partial

    matches: list[str] = []
    for child in search_dir.iterdir():
        if not child.is_file():
            continue
        if extensions and child.suffix.lower() not in extensions:
            continue
        name = child.name
        if name.lower().startswith(fragment.lower()):
            matches.append(name)

    if not matches:
        return partial

    matches.sort()
    if len(matches) == 1:
        completion = matches[0]
    else:
        completion = os.path.commonprefix(matches)
        if len(completion) <= len(fragment):
            return partial

    completed_path = os.path.join(dir_part, completion)
    if dir_part == ".":
        completed_path = completion
    if quote:
        return f"{quote}{completed_path}"
    return completed_path

def _redraw_input(prompt: str, buffer: str, previous_length: int) -> int:
    width = shutil.get_terminal_size((80, 20)).columns
    sys.stdout.write("\r")
    sys.stdout.write(" " * max(1, width - 1))
    sys.stdout.write("\r")
    sys.stdout.write(prompt + buffer)
    sys.stdout.flush()
    return len(buffer)

def _input_with_tab_completion(prompt: str, extensions: tuple[str, ...]) -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    buffer = ""
    previous_length = 0

    while True:
        key = msvcrt.getwch()
        if key in ("\r", "\n"):
            print()
            return buffer.strip()
        if key == "\t":
            new_buffer = _autocomplete_path(buffer, extensions)
            if new_buffer != buffer:
                buffer = new_buffer
                previous_length = _redraw_input(prompt, buffer, previous_length)
            continue
        if key == "\x08":  # Backspace
            if buffer:
                buffer = buffer[:-1]
                previous_length = _redraw_input(prompt, buffer, previous_length)
            continue
        if key in ("\x00", "\xe0"):
            msvcrt.getwch()
            continue

        buffer += key
        previous_length = _redraw_input(prompt, buffer, previous_length)

def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    """간단한 Y/N 입력을 처리합니다."""
    suffix = " (Y/n): " if default else " (y/N): "
    answer = input(f"{prompt}{suffix}").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")

def get_filepath_from_cli() -> str | None:
    """CLI에서 엑셀 파일 경로 입력 받기"""
    raw_input = _input_with_tab_completion(
        ">> 접속 정보 엑셀 파일 경로를 입력하세요 (예: test.xlsx 또는 C:\\Users\\PC\\Desktop\\test.xlsx): ",
        (".xlsx", ".xls", ".xlsm")
    ).strip()
    if not raw_input:
        return None

    # 따옴표로 감싼 경로 처리
    cleaned = raw_input.strip('"').strip("'")
    path = Path(cleaned).expanduser()

    if not path.exists():
        logger.warning("입력한 파일을 찾을 수 없습니다: %s", path)
        return None

    return str(path)

def get_command_filepath_from_cli() -> str | None:
    """CLI에서 명령어 파일 경로 입력 받기"""
    raw_input = _input_with_tab_completion(
        ">> 명령어 파일 경로를 입력하세요 (예: test.txt 또는 test.xlsx): ",
        (".txt", ".xlsx", ".xls", ".xlsm")
    ).strip()
    if not raw_input:
        return None

    cleaned = raw_input.strip('"').strip("'")
    path = Path(cleaned).expanduser()

    if not path.exists():
        logger.warning("입력한 파일을 찾을 수 없습니다: %s", path)
        return None

    return str(path)

def main():
    """메인 함수"""
    try:
        while True:
            inspector = None
            settings = load_settings()

            while True:
                menu_choice = show_main_menu()
                if menu_choice == "1":
                    break
                if menu_choice == "2":
                    console_level = getattr(logging, settings.console_log_level, logging.INFO)

                    run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    log_file = init_logging(
                        run_timestamp=run_timestamp,
                        console_level=console_level,
                        file_level=logging.DEBUG,
                        enable_color=True
                    )

                    output_excel = "command_results.xlsx"
                    logger.info("RUN ID   : %s", run_timestamp)
                    logger.info("LOG FILE : %s", log_file)
                    logger.info("-----------------------------------------")
                    logger.info("MODE    : 사용자 명령 실행")

                    filepath = get_filepath_from_cli()
                    if not filepath:
                        logger.warning("파일 경로가 입력되지 않았습니다. 프로그램을 종료합니다.")
                        return
                    logger.info("INPUT   : %s", filepath)

                    try:
                        devices_df = read_excel_file(filepath)
                    except Exception:
                        password = get_password_from_dialog()
                        if not password:
                            logger.warning("암호가 입력되지 않았습니다. 프로그램을 종료합니다.")
                            return
                        devices_df = read_excel_file(filepath, password=password)

                    validate_dataframe(devices_df)
                    devices = devices_df.to_dict('records')

                    vendor_os_pairs = {
                        (
                            str(d.get("vendor", "")).strip().lower(),
                            str(d.get("os", "")).strip().lower()
                        )
                        for d in devices
                    }
                    if len(vendor_os_pairs) > 1:
                        if not _ask_yes_no(
                            "다른 벤더/OS가 섞여 있습니다. 계속 진행할까요?",
                            default=False
                        ):
                            logger.info("사용자 명령 실행이 취소되었습니다.")
                            continue

                    command_path = get_command_filepath_from_cli()
                    if not command_path:
                        logger.warning("명령어 파일 경로가 입력되지 않았습니다. 프로그램을 종료합니다.")
                        return
                    logger.info("COMMAND FILE : %s", command_path)

                    try:
                        commands = read_command_file(command_path)
                    except Exception as e:
                        logger.error("명령어 파일 읽기 실패: %s", e)
                        return

                    if not commands:
                        logger.warning("명령어 파일에 실행할 명령이 없습니다.")
                        return

                    inspector = NetworkInspector(
                        output_excel,
                        inspection_only=True,
                        run_timestamp=run_timestamp,
                        inspection_excludes=settings.inspection_excludes
                    )
                    inspector.load_devices(devices)
                    inspector.run_custom_commands(commands)

                    if inspector and inspector.results:
                        save_results_to_excel(
                            inspector.results,
                            inspector.output_excel
                        )
                        logger.info("작업이 완료되었습니다.")
                        logger.info(f"결과 파일: {inspector.output_excel}")
                        logger.info(f"결과 디렉토리: {inspector.output_dir}")
                    else:
                        logger.info("처리된 결과가 없어 파일을 저장하지 않았습니다.")
                    return
                if menu_choice == "3":
                    show_settings_menu(settings)
                    continue
                if menu_choice == "4":
                    show_netmiko_device_types()
                    continue
                if menu_choice == "5":
                    print("프로그램을 종료합니다.")
                    return
                print("잘못된 선택입니다. 다시 시도하세요.")

            while True:
                action_choice = show_action_menu()
                if action_choice is None:
                    break
                choice = action_choice

                console_level = getattr(logging, settings.console_log_level, logging.INFO)

                # 전역 로깅 일관 설정 (파일+콘솔) 및 실행 타임스탬프 고정
                run_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                log_file = init_logging(
                    run_timestamp=run_timestamp,
                    console_level=console_level,
                    file_level=logging.DEBUG,
                    enable_color=True
                )

                output_excel = "inspection_results.xlsx"
                logger.info("RUN ID   : %s", run_timestamp)
                logger.info("LOG FILE : %s", log_file)
                logger.info("-----------------------------------------")
                mode_map = {"1": "점검", "2": "백업", "3": "점검+백업"}
                if choice in mode_map:
                    logger.info("MODE    : %s", mode_map[choice])

                # 파일 경로 입력 (CLI)
                filepath = get_filepath_from_cli()
                if not filepath:
                    logger.warning("파일 경로가 입력되지 않았습니다. 프로그램을 종료합니다.")
                    return
                logger.info("INPUT   : %s", filepath)
                    
                # 파일 읽기 시도
                try:
                    devices_df = read_excel_file(filepath)
                except Exception:
                    password = get_password_from_dialog()
                    if not password:
                        logger.warning("암호가 입력되지 않았습니다. 프로그램을 종료합니다.")
                        return
                    devices_df = read_excel_file(filepath, password=password)

                # 데이터 유효성 검사
                validate_dataframe(devices_df)
                devices = devices_df.to_dict('records')

                column_order = None
                cancel_requested = False
                if choice == "1":
                    inspector = NetworkInspector(
                        output_excel,
                        inspection_only=True,
                        run_timestamp=run_timestamp,
                        inspection_excludes=settings.inspection_excludes
                    )
                elif choice == "2":
                    inspector = NetworkInspector(
                        output_excel,
                        backup_only=True,
                        run_timestamp=run_timestamp,
                        inspection_excludes=settings.inspection_excludes
                    )
                elif choice == "3":
                    inspector = NetworkInspector(
                        output_excel,
                        run_timestamp=run_timestamp,
                        inspection_excludes=settings.inspection_excludes
                    )
                else:
                    logger.warning("잘못된 선택입니다. 1-3 사이의 숫자를 입력하세요.")
                    return

                inspector.load_devices(devices)

                if choice in ("1", "3"):
                    if _ask_yes_no("점검 결과 열 순서를 정할까요?", default=False):
                        available_columns = inspector.get_available_inspection_columns(inspector.devices)
                        if available_columns:
                            reordered = reorder_columns_interactive(available_columns)
                            if reordered is None:
                                cancel_requested = True
                            else:
                                column_order = reordered
                        else:
                            logger.info("정렬할 점검 항목이 없습니다.")

                if cancel_requested:
                    logger.info("작업이 취소되었습니다.")
                    continue

                if choice == "1":
                    inspector.inspect_devices(backup_only=False)
                elif choice == "2":
                    inspector.inspect_devices(backup_only=True)
                else:
                    inspector.inspect_and_backup_devices()

                # 결과 저장
                if inspector and inspector.results:
                    save_results_to_excel(
                        inspector.results,
                        inspector.output_excel,
                        column_order=column_order
                    )
                    logger.info("작업이 완료되었습니다.")
                    logger.info(f"결과 파일: {inspector.output_excel}")
                    logger.info(f"결과 디렉토리: {inspector.output_dir}")
                    if not inspector.inspection_only:
                        logger.info(f"백업 디렉토리: {inspector.backup_dir}")
                else:
                    logger.info("처리된 결과가 없어 파일을 저장하지 않았습니다.")
                return

    except NetworkInspectorError as e:
        logger.exception(f"애플리케이션 오류 발생: {e}")
    except Exception as e:
        logger.exception(f"예상치 못한 오류 발생: {e}")

if __name__ == "__main__":
    main() 