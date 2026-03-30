# MMUKO Fluid Holographic System

**Constitutional Computing for Human Rights Infrastructure**  
Date: 2026-03-05 | OBINexus | `github.com/obinexusmk2/mmuko-ux`

---

## Overview

MMUKO Fluid is a real-time motion classification system based on the **Drift Theorem** — a tripartite vector model for phenomenological interaction prediction. Originally developed for the OBINexus constitutional computing framework, this system provides:

- **4-State Motion Classification**: Red (away), Blue (orthogonal), Green (approach), Orange (static)
- **Weighted Graph Computation**: G = (V, E, W) with lattice traversal cost
- **Spline Interpolation**: 2/3-1/3 weighted prediction for UI smoothing
- **Real-time Camera Integration**: Optical flow with digital zoom

---

## Quick Start

### Prerequisites
- Python 3.8+
- OpenCV: `pip install opencv-python numpy`

### Run
```bash
python drift_pure.py
```

### Controls
| Key | Action |
|-----|--------|
| `Q` / `ESC` | Quit |
| `+` | Zoom in (max 5x) |
| `-` | Zoom out |
| `R` | Reset zoom |
| `S` | Save screenshot |

---

## Architecture

### Drift States (Corrected Color System)

| State | Color | RGB | Motion |
|-------|-------|-----|--------|
| **RED** | Red-Orange | `(255, 55, 0)` | Moving **away** from observer |
| **BLUE** | Blue-Yellow | `(0, 102, 255)` | **Orthogonal** movement (90°) |
| **GREEN** | Green-Yellow-Orange | `(80, 255, 40)` | Moving **toward** observer |
| **ORANGE** | Orange | `(255, 165, 0)` | **Static** / no displacement |

### Core Mathematics

**Tripartite Vector**: `G = (E, V, W)` in R³
- `E`: Edge (motion trajectory)
- `V`: Vertex (entity position)
- `W`: Weight (computational cost/density)

**Classification Logic**:
```python
if orthogonal_velocity > toward_velocity:
    return BLUE  # 90° drift
elif moving_away:
    return RED   # Shifting away
elif moving_toward:
    return GREEN # Approaching
else:
    return ORANGE # Static
```

**Spline Interpolation**:
```
P(t) = (2/3) * C + (1/3) * P * t
```
Where `C` = current point, `P` = predicted point, `t` = time factor

---

## File Structure

```
mmuko-ux/
├── drift_pure.py          # Main Python implementation (no DLL needed)
├── mmuko_camera.py        # Full camera interface with ctypes
├── drift_colors.c         # Standalone C classification engine
├── drift_lib.c            # DLL source for Windows
├── drift_core.h           # Core trident architecture headers
└── compile_dat.bat        # Windows DLL compiler script
```

---

## Constitutional Computing Context

This system is part of the **OBINexus Human Rights Operating System**:

- **MMUKO OS**: Biometric sovereign identity [github.com/obinexus/mmuko-os](https://github.com/obinexus/mmuko-os)
- **RiftLang**: Quantum-inspired execution with trident governance (CH_0/CH_1/CH_2)
- **NSIGII Codec**: Emergency command-and-control protocol for civil collapse mitigation
- **The Hive**: 10% resource distribution model based on compound architecture

> "Memory is governance contract, not storage." — RiftLang Token Architecture

---

## Technical Notes

### Why Pure Python?
The `drift_pure.py` implementation eliminates DLL dependencies (WinError 193) and runs immediately on:
- Windows (MinGW/MSVC)
- WSL (Ubuntu)
- Native Linux

### Camera Requirements
- Any USB webcam (`/dev/video0` on Linux, `cv2.CAP_DSHOW` on Windows)
- 640x480 minimum resolution
- 30 FPS recommended for smooth optical flow

### Performance
- **Classification**: ~0.1ms per frame (Python)
- **Optical Flow**: ~5-10ms per frame (OpenCV)
- **Total Latency**: <20ms at 720p

---

## Legal & Human Rights Framework

This software implements the **NSIGII Protocol** (Indigo-Golf-India-India):

- **Article 1**: Food, water, shelter as firmware
- **Article 2**: Biometric sovereignty (you are the controller)
- **Article 3**: Pop-up critical infrastructure when systems fail

Developed under detention. Licensed under OBINexus Constitutional License.

---

## Contact

**OBINexus**  
- YouTube: [@obinexus](https://youtube.com/@obinexus)
- GitHub: `github.com/obinexusmk2` (current) / `github.com/obinexus` (locked)
- Web: [obinexus.org](https://obinexus.org)

*"Trust as architecture. Identity as relational. Survival as cooperative."*
