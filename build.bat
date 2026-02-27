@echo off
chcp 65001 >nul 2>&1
setlocal

echo ============================================
echo  NetworkDeviceInspector - EXE 빌드
echo ============================================
echo.

:: PyInstaller 설치 확인
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller가 설치되어 있지 않습니다. 설치합니다...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] PyInstaller 설치 실패
        pause
        exit /b 1
    )
)

:: 이전 빌드 정리
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo [1/3] PyInstaller 빌드 시작...
echo.
pyinstaller NetworkDeviceInspector.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] 빌드 실패
    pause
    exit /b 1
)

echo.
echo [2/3] 설정 파일 복사...
if exist "custom_rules.example.yaml" copy /y "custom_rules.example.yaml" "dist\custom_rules.example.yaml" >nul

echo.
echo [3/3] 빌드 완료!
echo.
echo  출력: dist\NetworkDeviceInspector.exe
echo.
echo  배포 시 dist 폴더에 아래 파일을 함께 배치하세요:
echo    - NetworkDeviceInspector.exe  (필수)
echo    - settings.yaml              (없으면 자동 생성)
echo    - custom_rules.yaml          (선택 - 커스텀 규칙 사용 시)
echo    - custom_rules.example.yaml  (참고용)
echo.

pause
