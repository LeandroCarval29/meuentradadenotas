@echo off
chcp 65001 >nul
title HNT FoodService BI
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Primeira execucao detectada.
  call INSTALAR_E_ABRIR.bat
  exit /b
)

".venv\Scripts\python.exe" -m py_compile app.py
if errorlevel 1 (
  echo Erro no aplicativo.
  call DIAGNOSTICO.bat
  exit /b
)

start "" http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
pause
