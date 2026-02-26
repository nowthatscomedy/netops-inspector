import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List


@dataclass
class AppSettings:
    console_log_level: str = "WARNING"
    inspection_excludes: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    max_retries: int = 3
    timeout: int = 10
    max_workers: int = 10


def get_settings_path() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "settings.json"


def _normalize_excludes(raw: object) -> Dict[str, Dict[str, List[str]]]:
    if not isinstance(raw, dict):
        return {}

    normalized: Dict[str, Dict[str, List[str]]] = {}
    for vendor_key, os_map in raw.items():
        if not isinstance(vendor_key, str) or not isinstance(os_map, dict):
            continue
        vendor = vendor_key.strip().lower()
        if not vendor:
            continue

        normalized_os: Dict[str, List[str]] = {}
        for os_key, commands in os_map.items():
            if not isinstance(os_key, str) or not isinstance(commands, list):
                continue
            os_name = os_key.strip().lower()
            if not os_name:
                continue

            cleaned_commands = []
            for cmd in commands:
                if isinstance(cmd, str) and cmd.strip():
                    cleaned_commands.append(cmd.strip())
            if cleaned_commands:
                normalized_os[os_name] = cleaned_commands

        if normalized_os:
            normalized[vendor] = normalized_os

    return normalized


def load_settings() -> AppSettings:
    settings_path = get_settings_path()
    if not settings_path.exists():
        return AppSettings()

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return AppSettings()

    console_log_level = data.get("console_log_level", "WARNING")
    if not isinstance(console_log_level, str) or not console_log_level:
        console_log_level = "WARNING"

    inspection_excludes = _normalize_excludes(data.get("inspection_excludes", {}))

    max_retries = data.get("max_retries", 3)
    if not isinstance(max_retries, int) or max_retries < 1:
        max_retries = 3

    timeout = data.get("timeout", 10)
    if not isinstance(timeout, int) or timeout < 1:
        timeout = 10

    max_workers = data.get("max_workers", 10)
    if not isinstance(max_workers, int) or max_workers < 1:
        max_workers = 10

    return AppSettings(
        console_log_level=console_log_level.upper(),
        inspection_excludes=inspection_excludes,
        max_retries=max_retries,
        timeout=timeout,
        max_workers=max_workers,
    )


def save_settings(settings: AppSettings) -> None:
    settings_path = get_settings_path()
    settings_path.write_text(
        json.dumps(asdict(settings), ensure_ascii=True, indent=2),
        encoding="utf-8"
    )
