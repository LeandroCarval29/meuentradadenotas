@echo off
cd /d %~dp0
if not exist .venv ( py -m venv .venv )
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do set IP=%%a
set IP=%IP: =%
echo.
echo ==============================================================
echo HNT FoodService BI V4.1 - MODO REDE
if defined IP echo Acesse em outro dispositivo: http://%IP%:8501
echo Mantenha este computador ligado enquanto outros dispositivos usam.
echo ==============================================================
echo.
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
pause
