#!/usr/bin/env python3
"""
OBINexus DLL Diagnostic Tool
Identifies DLL loading and architecture issues
"""

import os
import sys
import ctypes
import platform
import struct

def diagnose_dll_issue():
    """Run comprehensive diagnostics"""

    print("=" * 70)
    print("OBINexus DLL Diagnostic Report")
    print("=" * 70)
    print(f"Date: 2026-03-11")
    print(f"Python Version: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"Architecture: {struct.calcsize('P')*8}-bit")
    print()

    # Check current directory
    cwd = os.getcwd()
    print(f"Current Directory: {cwd}")
    print()

    # List files in current directory
    print("Files in current directory:")
    for item in os.listdir('.'):
        full_path = os.path.abspath(item)
        if os.path.isfile(full_path):
            size = os.path.getsize(full_path)
            print(f"  - {item:<30} ({size:>10} bytes)")
    print()

    # Check for drift_lib.dll
    dll_paths = [
        './drift_lib.dll',
        'drift_lib.dll',
        os.path.join(cwd, 'drift_lib.dll'),
    ]

    print("DLL Search Results:")
    dll_found = False
    for path in dll_paths:
        exists = os.path.exists(path)
        status = "✓ FOUND" if exists else "✗ NOT FOUND"
        print(f"  {path:<40} {status}")
        if exists:
            dll_found = True
            size = os.path.getsize(path)
            print(f"    Size: {size} bytes")

    print()

    if not dll_found:
        print("⚠ CRITICAL: drift_lib.dll not found in expected locations")
        print()
        print("NEXT STEPS:")
        print("1. Run: dir drift_lib.dll /s (search all subdirectories)")
        print("2. Check compile_dat.bat for errors")
        print("3. Verify C compiler is installed (GCC for MinGW)")
        print()
        return False

    # Try to load DLL
    print("DLL Load Attempt:")
    try:
        dll = ctypes.CDLL('./drift_lib.dll')
        print("  ✓ Successfully loaded drift_lib.dll")
        print()

        # Try to access functions
        print("Function Export Check:")
        functions = ['classify_drift', 'get_color', 'get_state_name']
        for func_name in functions:
            try:
                func = getattr(dll, func_name)
                print(f"  ✓ {func_name:<30} exported")
            except AttributeError:
                print(f"  ✗ {func_name:<30} NOT EXPORTED")

        return True

    except OSError as e:
        print(f"  ✗ Failed to load: {e}")
        print()
        print("POSSIBLE CAUSES:")
        print("  - DLL architecture (32-bit vs 64-bit mismatch)")
        print("  - Missing dependencies (MSVCRT, runtime libraries)")
        print("  - Corrupted DLL file")
        print("  - Path issues (try absolute path)")
        print()

        # Check architecture
        print("Architecture Check:")
        try:
            import platform
            bits = struct.calcsize('P') * 8
            print(f"  Python is running as: {bits}-bit")
            print(f"  Expected DLL arch: {bits}-bit")
            print()
            print("  → If DLL is 32-bit and Python is 64-bit (or vice versa),")
            print("    you need to recompile the DLL or use matching Python")
        except:
            pass

        return False

if __name__ == "__main__":
    success = diagnose_dll_issue()
    sys.exit(0 if success else 1)
