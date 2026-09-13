@echo off
chcp 65001 >nul
title 表白应用
cd /d "%~dp0"
echo ==========================================
echo   表白应用启动中...
echo   启动后请保持本窗口打开，不要关闭
echo ==========================================
python app.py
pause
