@echo off
chcp 65001 >nul
title OneDrive to Google Drive Transfer Tool
cd /d "%~dp0"

echo [*] Dang kiem tra thu vien giao dien...
python -c "import customtkinter" 2>nul
if errorlevel 1 (
    echo [*] Dang cai dat thu vien customtkinter...
    pip install -r requirements.txt
)

echo [*] Dang khoi dong ung dung...
start "" pythonw app.py
exit
