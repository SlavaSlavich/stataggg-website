@echo off
echo Starting Stataggg Services...

:: Start Website
start "Stataggg Website" cmd /k "cd web_v1 && python main.py"

:: Start Payment Bot
start "Stataggg Payment Bot" cmd /k "cd bot_payment && python main.py"

echo.
echo ===================================================
echo   Services are starting in separate windows.
echo   Website: http://localhost:8090
echo   Bot: Active in background window
echo ===================================================
echo.
pause
