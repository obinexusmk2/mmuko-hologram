@echo off
REM ================================================================
REM  MMUKO Holographic Interface — Windows launcher
REM  1. Install deps if needed
REM  2. Start the Flask/SocketIO server
REM  3. Open the browser
REM ================================================================

title MMUKO Holographic Interface

echo.
echo  MMUKO Holographic Interface
echo  Trilateral Consensus Cybernetic System
echo ================================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

REM Install dependencies
echo.
echo [MMUKO] Installing Python dependencies...
pip install -r requirements.txt --quiet

REM Copy AnimatedTreeFree sprites if they exist in Downloads
set TREE_SRC=%USERPROFILE%\Downloads\AnimatedTreeFree
set TREE_DST=%~dp0static\assets\trees

if exist "%TREE_SRC%" (
    echo [MMUKO] Copying AnimatedTreeFree sprites...
    xcopy /E /I /Y "%TREE_SRC%\*" "%TREE_DST%\" >nul 2>&1
    echo [MMUKO] Sprites copied to static\assets\trees\
) else (
    echo [MMUKO] AnimatedTreeFree folder not found - using procedural trees
    echo         (Place sprites in: static\assets\trees\tree_row.png)
)

REM Start server
echo.
echo [MMUKO] Starting server on http://localhost:5000
echo [MMUKO] Press Ctrl+C to stop
echo.

REM Open browser after a short delay
start "" timeout /t 2 >nul && start http://localhost:5000

python server.py
pause
