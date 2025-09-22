@echo off
echo Starting B2B WhatsApp AI Services...
echo.

:: Python path setup
set PYTHONPATH=%cd%;%cd%\src\core

:: Start Swarm System
echo [1/3] Starting Swarm Multi-Agent System...
start cmd /k "cd /d %cd% && python src\core\swarm_b2b_system.py"
timeout /t 3 /nobreak > nul

:: Start WhatsApp Bot
echo [2/3] Starting WhatsApp Bot...
start cmd /k "cd /d %cd% && node src\core\whatsapp-webhook-sender.js"
timeout /t 3 /nobreak > nul

:: Start Product List Server
echo [3/3] Starting Product List Server...
start cmd /k "cd /d %cd% && node src\core\product-list-server-v2.js"

echo.
echo All services started successfully!
echo.
echo Services running on:
echo - Swarm System: http://localhost:3007
echo - WhatsApp Bot: Port 3001
echo - Product Server: http://localhost:3005
echo.
pause