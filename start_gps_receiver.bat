@echo off
echo Starting GPS Receiver Server...
echo %DATE% %TIME% - Starting GPS Receiver >> logs\gps_receiver.log

REM Change to project directory
cd /d c:\Users\iraj\Desktop\GpsStore

REM Check if logs directory exists, create if not
if not exist logs mkdir logs

REM Kill any existing python processes running gps_receiver
taskkill /f /im python.exe /fi "WINDOWTITLE eq GPS Receiver*" 2>nul
taskkill /f /im python.exe /fi "IMAGENAME eq python.exe" 2>nul | findstr /c:"python manage.py gps_receiver" >nul
if %errorlevel%==0 (
    echo %DATE% %TIME% - Killed existing GPS receiver processes >> logs\gps_receiver.log
)

REM Start GPS receiver in background
start "GPS Receiver" cmd /c "python manage.py gps_receiver >> logs\gps_receiver.log 2>&1"

REM Wait a moment for the server to start
timeout /t 2 /nobreak >nul

REM Check if the process is running
tasklist /fi "WINDOWTITLE eq GPS Receiver" | findstr /c:"cmd.exe" >nul
if %errorlevel%==0 (
    echo %DATE% %TIME% - GPS Receiver started successfully >> logs\gps_receiver.log
    echo GPS Receiver started successfully!
) else (
    echo %DATE% %TIME% - Failed to start GPS Receiver >> logs\gps_receiver.log
    echo Failed to start GPS Receiver. Check logs\gps_receiver.log for details.
)

echo Press any key to exit...
pause >nul