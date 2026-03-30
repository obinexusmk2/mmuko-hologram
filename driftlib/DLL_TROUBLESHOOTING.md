# OBINexus MMUKO Camera - DLL Troubleshooting Guide

**Project**: OBINexus Constitutional Computing
**Module**: MMUKO Fluid Camera System
**Date**: 2026-03-11
**Status**: Build Recovery Phase

---

## Problem Summary

Your `mmuko_camera.py` requires `drift_lib.dll`, but compilation and loading are failing.

**Error**: `ERROR: drift_lib.dll not found. Run compile_dll.bat first.`

---

## Root Causes Identified

### 1. **Batch File Syntax Error**
The original `compile_dat.bat` contains invalid comment syntax (`#` instead of `REM`).
- Windows batch files use `REM` for comments, not `#`
- Invalid comments break script execution

**Solution**: Use `compile_dat_FIXED.bat` provided

### 2. **Architecture Mismatch (32-bit vs 64-bit)**
Error message: `"64-bit mode not compiled in"`
- Your Python is likely 64-bit
- Your GCC compiler may be 32-bit or not properly configured for 64-bit
- The compiled DLL architecture must match Python's architecture

**Solution**:
```bash
# Check Python architecture:
python -c "import struct; print(f'{struct.calcsize(\"P\")*8}-bit')"

# Install MinGW-w64 (64-bit capable):
# https://www.mingw-w64.org/
```

### 3. **Compiler Not Installed**
The compilation error suggests the C compiler (GCC) may not be properly installed.

---

## Step-by-Step Recovery

### Step 1: Verify Python Architecture
```powershell
python -c "import struct; print(f'Python: {struct.calcsize(\"P\")*8}-bit')"
```
**Expected**: `Python: 64-bit` (typical modern setup)

### Step 2: Check GCC Installation
```powershell
gcc --version
```
**Expected**: Shows GCC version (e.g., `x86_64-w64-mingw32-gcc (GCC) 11.2.0`)

If not found:
- Install MinGW-w64: https://www.mingw-w64.org/
- Or use: `choco install mingw` (if using Chocolatey)

### Step 3: Verify Current Directory
```powershell
ls
```
Expected files:
- `drift_lib.c` (source)
- `drift_lib.h` (header)
- `compile_dat_FIXED.bat` (corrected compiler)
- `mmuko_camera.py` (main script)

### Step 4: Run Fixed Compiler
```powershell
.\compile_dat_FIXED.bat
```
Expected output:
```
[*] Compiler detected: GCC
[*] Compiling drift_lib.c to 64-bit DLL...
[✓] DLL compiled successfully: drift_lib.dll
```

### Step 5: Verify DLL Creation
```powershell
ls drift_lib.dll
```
Expected: File exists with size > 0 bytes

### Step 6: Run Diagnostics
```powershell
python diagnose_dll.py
```
Expected:
```
✓ Successfully loaded drift_lib.dll
✓ classify_drift         exported
✓ get_color              exported
✓ get_state_name         exported
```

### Step 7: Launch Application
```powershell
python mmuko_camera.py
```

---

## OBINexus Build Continuity

This troubleshooting preserves project structure:

- **Toolchain**: nlink → polybuild (build orchestration)
- **Module Layer**: mmuko_camera.py + drift_lib.dll (C acceleration)
- **Compliance**: drift_lib includes color classification (OpenSense recruitment logic)
- **Status**: Recovery phase → Build validation → Resumed operations

---

## If Problems Persist

### Create Minimal Test
Save as `test_dll_load.py`:
```python
import ctypes
import sys

print(f"Python architecture: {sys.maxsize > 2**32 and '64-bit' or '32-bit'}")
print(f"Looking for drift_lib.dll...")

try:
    dll = ctypes.CDLL('./drift_lib.dll')
    print("✓ DLL loaded successfully")
    print(f"✓ classify_drift: {dll.classify_drift}")
except OSError as e:
    print(f"✗ Failed: {e}")
    print("Check:")
    print("  - DLL exists: dir drift_lib.dll")
    print("  - Architecture match: python --version (should be 64-bit)")
    print("  - Dependencies: check System32 for MSVCRT140.dll")
```

### Check System Dependencies
```powershell
# List runtime libraries
dir C:\Windows\System32\MSVCRT*

# Install Visual C++ Redistributable if missing
# Download: https://support.microsoft.com/en-us/help/2977003/
```

---

## Reference: Expected File Structure

```
auxilvary-vector/
├── mmuko_camera.py          (main application)
├── drift_lib.c              (C source)
├── drift_lib.h              (header)
├── drift_colors.c           (color logic)
├── drift_colors.h
├── drift_core.h
├── drift_pure.py            (Python fallback)
├── compile_dat.bat          (ORIGINAL - has bugs)
├── compile_dat_FIXED.bat    (CORRECTED)
├── drift_lib.dll            (compiled output - MUST EXIST)
├── diagnose_dll.py          (diagnostic tool)
└── README.md
```

---

## Build Orchestration Context

For OBINexus milestone tracking:
- **Milestone**: Build Recovery Phase
- **Artifact**: drift_lib.dll compilation
- **Compliance**: #NoGhosting policy (transparent build logs)
- **Next**: Deploy to polybuild orchestrator

---

**Generated**: 2026-03-11 | OBINexus Recovery Protocol
