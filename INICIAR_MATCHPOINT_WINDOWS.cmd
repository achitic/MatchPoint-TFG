@echo off
setlocal
title MatchPoint - Inicio portable
cd /d "%~dp0"

echo ========================================
echo       MATCHPOINT - INICIO PORTABLE
echo ========================================
echo.

where docker >nul 2>nul
if errorlevel 1 (
    echo [FALTA DOCKER DESKTOP]
    echo Instala Docker Desktop desde https://www.docker.com/products/docker-desktop/
    echo Despues, abre Docker Desktop y vuelve a ejecutar este archivo.
    echo.
    pause
    exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
    echo [DOCKER NO ESTA INICIADO]
    echo Abre Docker Desktop, espera a que termine de arrancar y vuelve a intentarlo.
    echo.
    pause
    exit /b 1
)

echo Preparando MatchPoint. La primera vez puede tardar varios minutos...
docker compose up --build -d --wait
if errorlevel 1 (
    echo.
    echo [ERROR] No se pudo iniciar MatchPoint.
    echo Revisa el mensaje anterior y asegurate de tener conexion a Internet.
    pause
    exit /b 1
)

start "" "http://localhost"
echo.
echo MatchPoint esta disponible en http://localhost
echo Para detenerlo, ejecuta DETENER_MATCHPOINT_WINDOWS.cmd
timeout /t 4 /nobreak >nul
endlocal
