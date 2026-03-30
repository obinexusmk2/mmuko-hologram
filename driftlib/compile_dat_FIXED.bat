@echo off
REM compile_dat.bat - DLL compilation for OBINexus drift_lib
REM Fixed version: proper batch syntax, 64-bit support
REM Date: 2026-03-11

echo ========================================
echo  OBINexus drift_lib DLL Compiler
echo ========================================
echo.

REM Check if GCC is available
where gcc >nul 2>nul
if errorlevel 1 (
    echo ERROR: GCC not found. Install MinGW-w64 for 64-bit compilation
    echo Download from: https://www.mingw-w64.org/
    pause
    exit /b 1
)

echo [*] Compiler detected: GCC
gcc --version
echo.

REM Compile to 64-bit DLL
echo [*] Compiling drift_lib.c to 64-bit DLL...
echo.

REM Remove old DLL if exists
if exist drift_lib.dll (
    echo [*] Removing old drift_lib.dll...
    del drift_lib.dll
)

REM Compile with 64-bit flags
gcc -O2 -m64 -shared -o drift_lib.dll drift_lib.c -lmsvcrt
if errorlevel 1 (
    echo.
    echo ERROR: Compilation failed!
    echo Make sure:
    echo  - drift_lib.c exists in current directory
    echo  - GCC is properly installed
    echo  - You have write permissions
    pause
    exit /b 1
)

echo.
echo ========================================
echo [✓] DLL compiled successfully: drift_lib.dll
echo ========================================
echo.

REM Verify DLL
if exist drift_lib.dll (
    for /F "usebackq" %%A in ('drift_lib.dll') do set size=%%~zA
    echo [✓] DLL Size: !size! bytes
    echo.
    echo You can now run: python mmuko_camera.py
) else (
    echo ERROR: DLL not created!
    pause
    exit /b 1
)

pause
