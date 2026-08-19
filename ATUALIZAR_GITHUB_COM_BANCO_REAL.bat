@echo off
chcp 65001 >nul
title HNT FoodService - Atualizar GitHub com Banco Real
cd /d "%~dp0"

echo ============================================================
echo HNT FOODSERVICE BI V11.5.2 - BANCO REAL PARA STREAMLIT
echo ============================================================
echo.
echo IMPORTANTE:
echo - Use SOMENTE em repositorio GitHub PRIVADO.
echo - Este envio inclui hnt_foodservice_v3.db.
echo - Nao inclui PFX/P12, .env ou secrets.toml.
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo Git nao encontrado. Instale Git for Windows ou use GitHub Desktop.
  pause
  exit /b 1
)

if not exist ".git" (
  echo Esta pasta ainda nao esta ligada a um repositorio Git local.
  echo Use primeiro a pasta ja clonada do seu repositorio ou GitHub Desktop.
  pause
  exit /b 1
)

git add .
git add -f hnt_foodservice_v3.db
git status

echo.
set /p CONF=Confirma publicar esta versao COM O BANCO REAL no repositorio PRIVADO? Digite SIM: 
if /I not "%CONF%"=="SIM" (
  echo Cancelado.
  pause
  exit /b 0
)

git commit -m "V11.5.2 - Streamlit com banco real inicial"
git push

if errorlevel 1 (
  echo.
  echo Falha no push. Abra o GitHub Desktop, confira o repositorio e tente Push origin.
) else (
  echo.
  echo SUCESSO.
  echo O GitHub agora deve mostrar app.py e hnt_foodservice_v3.db.
  echo O Streamlit Cloud fara novo deploy automaticamente.
)
pause
