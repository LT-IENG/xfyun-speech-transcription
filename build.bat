@echo off
chcp 65001 >nul
echo ============================================
echo   讯飞语音转写 — PyInstaller 打包脚本
echo ============================================
echo.

REM 清理旧构建
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo [1/3] 安装依赖...
pip install -r requirements.txt >nul 2>&1

echo [2/3] 开始打包（约 1-3 分钟）...
pyinstaller --noconfirm ^
    --onefile ^
    --windowed ^
    --name "讯飞语音转写" ^
    --icon "assets\p1.ico" ^
    --add-data "assets;assets" ^
    --add-data "api_config.json;." ^
    --hidden-import PyQt6.QtCore ^
    --hidden-import PyQt6.QtGui ^
    --hidden-import PyQt6.QtWidgets ^
    --hidden-import pydub ^
    --hidden-import requests ^
    --hidden-import json ^
    --clean ^
    main.py

if %errorlevel% equ 0 (
    echo.
    echo [3/3] 打包成功！
    echo 输出: dist\讯飞语音转写.exe
) else (
    echo.
    echo 打包失败，请检查错误信息。
)

pause
