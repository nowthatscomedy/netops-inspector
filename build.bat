@echo off
chcp 65001 >nul 2>&1
setlocal

echo ============================================
echo  NetOpsInspector - EXE Build
echo ============================================
echo.

:: Check PyInstaller installation
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller is not installed. Installing now...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller
        pause
        exit /b 1
    )
)

:: Clean previous build artifacts
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo [1/3] Starting PyInstaller build...
echo.
pyinstaller main.py --name NetOpsInspector --onefile --noconfirm --collect-submodules vendors --add-data "locales;locales"
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo [2/3] Copying config templates...
if exist "custom_rules.example.yaml" copy /y "custom_rules.example.yaml" "dist\custom_rules.example.yaml" >nul

echo.
echo [3/3] Build complete
echo.
echo  Output: dist\NetOpsInspector.exe
echo.
echo  Place the following files in the dist folder for distribution:
echo    - NetOpsInspector.exe       (required)
echo    - settings.yaml             (optional, auto-created if missing)
echo    - custom_rules.yaml         (optional)
echo    - custom_rules.example.yaml (reference)
echo.

pause
