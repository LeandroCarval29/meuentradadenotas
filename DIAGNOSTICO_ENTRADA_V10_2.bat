@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
 ".venv\Scripts\python.exe" DIAGNOSTICO_ENTRADA_V10_2.py
) else (
 py -3 DIAGNOSTICO_ENTRADA_V10_2.py
)
pause
