@echo off
chcp 65001 >nul
title HNT FoodService BI - Rede Local
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Execute INSTALAR_E_ABRIR.bat primeiro.
  pause
  exit /b
)

for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
 set IP=%%a
 goto :found
)
:found
set IP=%IP: =%
echo.
echo No computador: http://localhost:8501
echo Em celulares/tablets na mesma rede Wi-Fi: http://%IP%:8501
echo.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --browser.gatherUsageStats false
pause
