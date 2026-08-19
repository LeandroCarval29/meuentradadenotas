@echo off
cd /d %~dp0
echo ==============================================================
echo MIGRACAO DE BANCO HNT FoodService BI
ECHO Este utilitario copia o banco da versao anterior para esta pasta.
echo Feche as duas versoes antes de continuar.
echo ==============================================================
set /p ORIGEM=Digite o caminho COMPLETO do arquivo hnt_foodservice_v3.db anterior: 
if not exist "%ORIGEM%" (
  echo Arquivo nao encontrado.
  pause
  exit /b 1
)
if exist "hnt_foodservice_v3.db" copy /Y "hnt_foodservice_v3.db" "hnt_foodservice_v3_backup_antes_migracao.db" >nul
copy /Y "%ORIGEM%" "hnt_foodservice_v3.db"
echo Banco copiado. Na primeira abertura a V4.1 executara as migracoes de estrutura automaticamente.
pause
