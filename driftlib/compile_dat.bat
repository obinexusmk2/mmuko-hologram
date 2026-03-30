@echo off
# Compile 64-bit DLL
gcc -m64 -shared -o drift_lib.dll drift_lib.c -lm -O3
echo DLL compiled: drift_lib.dll
pause