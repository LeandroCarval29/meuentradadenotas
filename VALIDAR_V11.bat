@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
 ".venv\Scripts\python.exe" VALIDAR_V11.py
) else (
 py -3 VALIDAR_V11.py
)
pause
