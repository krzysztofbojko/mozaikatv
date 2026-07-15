@echo off
setlocal
cd /d "%~dp0"
docker compose down
if errorlevel 1 (
    echo Nie udalo sie zatrzymac aplikacji.
    pause
    exit /b 1
)
echo Mozaika TV zostala zatrzymana.
pause
