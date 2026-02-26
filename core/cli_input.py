import logging
import os
import msvcrt
import sys
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


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
        if key == "\x08":
            if buffer:
                buffer = buffer[:-1]
                previous_length = _redraw_input(prompt, buffer, previous_length)
            continue
        if key in ("\x00", "\xe0"):
            msvcrt.getwch()
            continue

        buffer += key
        previous_length = _redraw_input(prompt, buffer, previous_length)


def get_filepath_from_cli() -> str | None:
    """CLI에서 엑셀 파일 경로 입력 받기"""
    raw_input = _input_with_tab_completion(
        ">> 접속 정보 엑셀 파일 경로를 입력하세요 (예: test.xlsx 또는 C:\\Users\\PC\\Desktop\\test.xlsx): ",
        (".xlsx", ".xls", ".xlsm")
    ).strip()
    if not raw_input:
        return None

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
