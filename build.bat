@echo off
chcp 65001 >nul 2>&1
setlocal

echo ============================================
echo  NetOpsInspector - EXE 鍮뚮뱶
echo ============================================
echo.

:: PyInstaller ?ㅼ튂 ?뺤씤
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller媛 ?ㅼ튂?섏뼱 ?덉? ?딆뒿?덈떎. ?ㅼ튂?⑸땲??..
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] PyInstaller ?ㅼ튂 ?ㅽ뙣
        pause
        exit /b 1
    )
)

:: ?댁쟾 鍮뚮뱶 ?뺣━
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo [1/3] PyInstaller 鍮뚮뱶 ?쒖옉...
echo.
pyinstaller NetOpsInspector.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] 鍮뚮뱶 ?ㅽ뙣
    pause
    exit /b 1
)

echo.
echo [2/3] ?ㅼ젙 ?뚯씪 蹂듭궗...
if exist "custom_rules.example.yaml" copy /y "custom_rules.example.yaml" "dist\custom_rules.example.yaml" >nul

echo.
echo [3/3] 鍮뚮뱶 ?꾨즺!
echo.
echo  異쒕젰: dist\NetOpsInspector.exe
echo.
echo  諛고룷 ??dist ?대뜑???꾨옒 ?뚯씪???④퍡 諛곗튂?섏꽭??
echo    - NetOpsInspector.exe  (?꾩닔)
echo    - settings.yaml              (?놁쑝硫??먮룞 ?앹꽦)
echo    - custom_rules.yaml          (?좏깮 - 而ㅼ뒪? 洹쒖튃 ?ъ슜 ??
echo    - custom_rules.example.yaml  (李멸퀬??
echo.

pause

