@echo off
chcp 65001 >nul
title HNT FoodService BI - Instalação Local
cd /d "%~dp0"

set PY=
where py >nul 2>&1 && set PY=py -3
if "%PY%"=="" (
  where python >nul 2>&1 && set PY=python
)

if "%PY%"=="" (
  echo.
  echo Python nao foi encontrado.
  echo.
  echo Instale o Python 3.12 e marque a opcao "Add Python to PATH".
  echo Depois execute este arquivo novamente.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual...
  %PY% -m venv .venv
  if errorlevel 1 goto :erro
)

echo Atualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :erro

echo Instalando dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :erro

echo Testando o aplicativo...
".venv\Scripts\python.exe" -m py_compile app.py
if errorlevel 1 goto :erro

echo.
echo Instalacao concluida.
echo Abrindo HNT FoodService BI...
start "" http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
exit /b

:erro
echo.
echo Ocorreu um erro.
echo Execute DIAGNOSTICO.bat e envie o diagnostico.txt.
pause
exit /b 1
