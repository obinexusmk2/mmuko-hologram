# MMUKO Holographic Interface
## Trilateral Consensus Cybernetic System

**OBINexus Computing — Nnamdi M. Okpala**

---

## What This Is

MMUKO is a **real-world-to-digital-world bridge**. When you move in front of a camera, your physical motion is translated into movement in a 2D holographic side-scroll world — no AI, no machine learning. Pure vector mathematics via the **Drift Theorem**.

Your body is the controller. The camera reads your position. The system computes drift. The digital character moves.

---

## The Drift Theorem

The core principle driving all motion tracking:

```
V(t) = P(t) − C(t)
```

Where:
- `P(t)` = position of the observed object (you) in space
- `C(t)` = position of the camera observer
- `V(t)` = relative observation vector (the gap between you and the lens)

**Radial drift** — are you getting closer or further?

```
Dr = d(|V(t)|)/dt

Dr < 0  →  Approaching
Dr > 0  →  Separating
Dr = 0  →  Stable
```

**Angular drift** — are you moving sideways?

```
ω = dθ/dt
```

Where `θ` is the angle between successive observation vectors. Lateral movement produces angular drift, not radial drift.

**Weighted frame smoothing** — reduces jitter between frames:

```
W(t) = (2/3)·P(t) + (1/3)·P(t−Δt)
```

The camera does not track *you specifically*. It tracks **itself relative to everything it sees**. That is why it works without a trained model — the math is self-referential.

---

## Trilateral Consensus

The camera frame is split into three lateral zones:

```
┌─────────┬──────────┬─────────┐
│  LEFT   │  CENTER  │  RIGHT  │
│  (L-R)  │  (C-G)   │  (R-B)  │
└─────────┴──────────┴─────────┘
```

Each zone computes an average RGB value, then XOR-folds it to a single byte:

```
byte = R XOR G XOR B
```

That byte drives the **MMUKO cubit ring** — an 8-bit state register that maps to compass directions (N, S, E, W, NE, NW, SE, SW) and determines the **superposition state** of the system:

- Primary direction — dominant orientation
- Secondary direction — secondary pull
- Cubits — 8 state units, each with a spin, direction, and entanglement flag

The three zones produce a **trilateral consensus** — a three-part agreement about where the scene is pointing. This is what drives the HUD bars (L-R, C-G, R-B) and the BYTE display.

---

## Motion States

| State | Condition | Display |
|---|---|---|
| Approaching | Dr < 0, object closing | Character moves toward center |
| Separating | Dr > 0, object receding | Character drifts away |
| Angular Drift | ω > 0, lateral movement | Character walks left or right |
| Stable | Dr ≈ 0 and ω ≈ 0 | Character idles |
| Orthogonal | Pure sideways vector | Registered as drift, not approach |

---

## Real World → Digital World

If you walk left in front of the camera, the character walks left in the digital world.
If you approach the camera, the system reads it as forward motion.
If you step back, the character retreats.

The digital world is a **holographic mirror** of your movement in space — computed entirely from frame-to-frame vector displacement. No pose detection. No neural network. Just geometry.

---

## Interface Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ [MMUKO SYSTEM]          [TRILATERAL CONSENSUS]              [HUD]│
│  STATUS: BOOT_OK         Venn diagram of L/C/R               L-R │
│                          PRI: SW   SEC: E                    C-G │
│ [CUBIT RING]                                                 R-B │
│  8-node graph                                               BYTE │
│                                                                  │
│ [LATTICE L2]                                                     │
│  Direct-product                                                  │
│  node positions                                                  │
│                                                                  │
│ WORLD X: 0                                                       │
│ NODE: BOT                                                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│           [  DIGITAL WORLD — side-scroll canvas  ]              │
│                                                                  │
│   stars · trees · ground · player character · props             │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│ [BOOT LOG]                                    [MMUKO CAM feed]   │
│  phase-by-phase consensus output                                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## Controls

### Keyboard (digital world)

| Key | Action |
|-----|--------|
| `Arrow Left` / `A` | Walk left |
| `Arrow Right` / `D` | Walk right |
| `Space` | Trigger MMUKO boot sequence |

### Camera (real world → digital world)

| Movement | Effect |
|----------|--------|
| Step left | Angular drift — character walks left |
| Step right | Angular drift — character walks right |
| Approach camera | Radial approach — Dr decreases |
| Back away | Radial separation — Dr increases |
| Move sideways at angle | Drift vector — ω increases |
| Stay still | Stable — character idles |

The `groundY` of the character tracks window height so the character always lands on the ground plane regardless of screen size.

---

## HUD Explained

**L-R / C-G / R-B bars** — live colour averages from each of the three camera zones. The length of each bar represents the byte intensity of that zone.

**BYTE** — the XOR-folded consensus byte for the current frame (e.g. `0x7E`). This is what the cubit ring is initialized from.

**Cubit Ring** — 8 state nodes arranged in a ring. Each node has a direction, spin value, and can be in superposition or entangled with another node.

**Lattice L2** — the direct-product lattice `{1,2} × {1,2}`. Each node position is a coordinate pair. Meet (`∧`) computes the component-wise minimum; join (`∨`) computes the component-wise maximum. This is the ordering structure that the consensus system resolves through.

**Trilateral Consensus Venn** — three overlapping circles representing left, center, and right zones. Where they overlap is the consensus region. The system only reaches full consensus when all three zones agree.

---

## Setup

### Requirements

- Python 3.10+
- A webcam (or the system runs in synthetic mode automatically)
- Modern browser (Chrome, Firefox, Edge)

### Install and Run (Windows)

```bat
.\start.bat
```

Then open `http://localhost:5000` in your browser.

### Install and Run (Linux / WSL / Mac)

```sh
./start.sh
```

### Manual start

```sh
pip install -r requirements.txt
python server.py
```

---

## No Camera?

If no webcam is detected, the system automatically switches to **synthetic mode**. Three sinusoidal phase signals (120° apart — a genuine trilateral spread) drive the consensus instead. The HUD still responds. The boot sequence still runs. The character is still controllable by keyboard.

---

## Architecture

```
Camera (OpenCV)
      │
      ▼
Trilateral Splitter
  LEFT │ CENTER │ RIGHT
      │
      ▼
avg BGR → XOR → byte_val
      │
      ▼
MMUKO Cubit Ring (8-bit)
      │
      ▼
Superposition Resolve (compass direction)
      │
      ▼
SocketIO → Flask → Browser
      │
      ▼
HTML5 Canvas — digital world render
```

The Python backend runs the Drift Theorem computation and cubit resolution. The browser renders the holographic world. They communicate over WebSocket in real time at 30 fps.

---

## Drift States — Colour Encoding

| Colour | State |
|--------|-------|
| Blue | Orthogonal (pure sideways drift) |
| Orange | Static / low-motion |
| Green | Stable consensus |
| Red | Radial approach above threshold |

These are displayed on the MMUKO Fluid runtime window when running the standalone camera module.

---

## File Structure

```
mmuko-holographic/
├── server.py              Flask + SocketIO server
├── mmuko_boot_sim.py      MMUKO cubit ring + boot sequence
├── mmuko_camera.py        Camera capture + trilateral processor
├── requirements.txt       Python dependencies
├── start.bat              Windows launcher
├── start.sh               Linux/Mac launcher
├── static/
│   ├── index.html         Full holographic UI (HTML5 Canvas)
│   └── assets/
│       ├── trees/         Tree sprite sheets
│       └── props/         World prop assets
└── driftlib/              C implementation of drift core
    ├── drift_lib.c
    ├── drift_core.h
    ├── drift_colors.c
    ├── drift_colors.h
    └── drift_pure.py      Pure Python fallback (no DLL required)
```

---

*MMUKO — Movement Mapped Under Kinetic Observation*
*Drift Theorem — OBINexus Computing, 2026*
