@echo off
REM AutoSQL Development Startup Script
echo Starting AutoSQL Development Servers...

REM Start Backend
echo.
echo [1/2] Starting Backend (FastAPI)...
start "AutoSQL Backend" cmd /k "cd /d C:\Users\Ayush\Desktop\AutoSQL\backend && autosql\Scripts\activate && python main.py"

REM Wait a moment for backend to start
timeout /t 3 /nobreak > nul

REM Start Frontend
echo [2/2] Starting Frontend (Next.js)...
start "AutoSQL Frontend" cmd /k "cd /d C:\Users\Ayush\Desktop\AutoSQL\frontend && npm run dev"

echo.
echo ✅ Both servers are starting up!
echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.
echo Press any key to exit this script (servers will continue running)...
pause > nul
