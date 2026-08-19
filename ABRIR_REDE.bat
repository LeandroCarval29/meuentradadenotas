@echo off
chcp 65001 >nul
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
echo Celular/tablet na mesma rede: http://%IP%:8501
".venv\Scripts\python.exe" -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --browser.gatherUsageStats false
pause
