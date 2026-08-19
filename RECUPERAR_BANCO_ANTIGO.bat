@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
 ".venv\Scripts\python.exe" RECUPERAR_BANCO_ANTIGO.py
) else (
 py -3 RECUPERAR_BANCO_ANTIGO.py
)
pause
