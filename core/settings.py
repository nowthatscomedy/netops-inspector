import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class AppSettings:
    console_log_level: str = "WARNING"


def get_settings_path() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "settings.json"


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

    return AppSettings(console_log_level=console_log_level.upper())


def save_settings(settings: AppSettings) -> None:
    settings_path = get_settings_path()
    settings_path.write_text(
        json.dumps(asdict(settings), ensure_ascii=True, indent=2),
        encoding="utf-8"
    )
