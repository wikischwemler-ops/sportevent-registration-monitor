@echo off
setlocal
cd /d "%~dp0"

echo Waiting for Docker Desktop...
for /l %%i in (1,1,20) do (
    docker info >nul 2>&1 && goto docker_ready
    timeout /t 3 /nobreak >nul
)

echo Docker did not become ready within 60 seconds.
echo Make sure Docker Desktop is installed and running.
pause
exit /b 1

:docker_ready
docker compose up -d --build
if errorlevel 1 (
    echo Failed to start the SportEvent Monitor.
    pause
    exit /b 1
)

echo SportEvent Monitor is running at http://localhost:8000