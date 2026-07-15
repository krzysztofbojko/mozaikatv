@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
    echo Nie znaleziono programu Docker. Zainstaluj i uruchom Docker Desktop.
    pause
    exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
    echo Docker Desktop nie jest uruchomiony.
    pause
    exit /b 1
)

docker compose up -d --build
if errorlevel 1 (
    echo Nie udalo sie uruchomic aplikacji.
    pause
    exit /b 1
)

start "" "http://localhost:8090"
echo Mozaika TV dziala pod adresem http://localhost:8090
echo Zamkniecie tego okna nie zatrzyma aplikacji.
pause
