"""PyInstaller frozen 모드와 일반 실행 모드 모두에서 올바른 경로를 반환하는 유틸리티."""

import sys
from pathlib import Path


def get_app_dir() -> Path:
    """애플리케이션 루트 디렉토리를 반환합니다.

    - PyInstaller onefile: exe가 위치한 디렉토리
    - PyInstaller onedir : exe가 위치한 디렉토리
    - 일반 실행          : 프로젝트 루트 (core/ 의 상위)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]
