@echo off
setlocal
title MatchPoint - Detener
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
    echo Docker no esta instalado o no se encuentra en PATH.
    pause
    exit /b 1
)

docker compose down
if errorlevel 1 (
    echo.
    echo No se pudo detener MatchPoint. Comprueba que Docker Desktop este iniciado.
    pause
    exit /b 1
)

echo.
echo MatchPoint se ha detenido correctamente.
timeout /t 3 /nobreak >nul
endlocal
