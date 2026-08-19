@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
 ".venv\Scripts\python.exe" USAR_MEU_BANCO_SEM_PERDER_DADOS.py
) else (
 py -3 USAR_MEU_BANCO_SEM_PERDER_DADOS.py
)
pause
