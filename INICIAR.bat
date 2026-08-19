@echo off
cd /d %~dp0
if not exist .venv ( py -m venv .venv )
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
start http://localhost:8501
streamlit run app.py
pause
