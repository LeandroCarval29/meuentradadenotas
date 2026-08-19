@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==== HNT FOODSERVICE BI - DIAGNOSTICO ==== > diagnostico.txt
echo Data: %date% %time% >> diagnostico.txt
echo. >> diagnostico.txt

echo ==== PYTHON ==== >> diagnostico.txt
where py >> diagnostico.txt 2>&1
where python >> diagnostico.txt 2>&1
py -3 --version >> diagnostico.txt 2>&1
python --version >> diagnostico.txt 2>&1

echo. >> diagnostico.txt
echo ==== VENV ==== >> diagnostico.txt
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" --version >> diagnostico.txt 2>&1
  ".venv\Scripts\python.exe" -m pip list >> diagnostico.txt 2>&1
  echo. >> diagnostico.txt
  echo ==== TESTE APP ==== >> diagnostico.txt
  ".venv\Scripts\python.exe" -m py_compile app.py >> diagnostico.txt 2>&1
) else (
  echo .venv NAO EXISTE >> diagnostico.txt
)

echo. >> diagnostico.txt
echo ==== BANCO ==== >> diagnostico.txt
if exist "hnt_foodservice_v3.db" (
  echo Banco hnt_foodservice_v3.db encontrado. >> diagnostico.txt
) else (
  echo Banco ainda nao existe; sera criado na primeira abertura. >> diagnostico.txt
)

echo. >> diagnostico.txt
echo ==== ARQUIVOS ==== >> diagnostico.txt
dir /b >> diagnostico.txt 2>&1

notepad diagnostico.txt
