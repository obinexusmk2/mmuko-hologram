# MMUKO Camera — Real-Time Cybernetic Vision Framework
## Production Architecture Report
**OBINexus | Nnamdi M. Okpala | 2026-06-08**

---

## Executive Summary

MMUKO's existing boot-time state model contains five computational
concepts that translate directly into a real-time camera processing pipeline.
This document defines that translation, evaluates which concepts have immediate
engineering value, which need redesign, and which are decorative.

The result is `mmuko_cv.h` / `mmuko_cv.c` — a production C library that
implements the full pipeline from camera landmark input to game engine output
at < 16 ms per frame.

---

## 1. MMUKO Concept Audit

### 1.1 Computationally Valuable (Keep, Translate)

| MMUKO Term | Engineering Translation | Value |
|---|---|---|
| **Cubit Ring** | `landmark_node_t` — 21-node state graph with ring adjacency | HIGH: O(1) neighbour lookup, maps exactly to MediaPipe skeleton topology |
| **Superposition** | `hypothesis_set_t` — N competing gesture interpretations with confidence weights | HIGH: standard probabilistic gesture model, resolved by constraint propagation |
| **Entanglement** | `constraint_pair_t` — joint dependency binding with spring physics | HIGH: pinch/curl/spread detection is a constraint satisfaction problem |
| **Frame of Reference** | `coord_frame_t` — wrist-anchored coordinate system built each frame | HIGH: required for stable gesture measurement regardless of hand orientation |
| **Nonlinear Resolution** | `feedback_estimator_t` — spline smoother W(t) = ⅔P(t) + ⅓P(t-Δt) | HIGH: exactly the Drift Theorem weighted frame smoother, already in codebase |
| **Drift Theorem** | `classify_drift(v_toward, v_ortho)` — 4-state motion classifier | HIGH: RED/BLUE/GREEN/ORANGE maps directly to slice/static/approach/orthogonal |

### 1.2 Requires Redesign

| MMUKO Term | Current Problem | Redesign |
|---|---|---|
| **Boot phase sequence** | Sequential, non-iterative; no feedback between phases | Replace with iterative constraint convergence loop; re-run Phase 2-3 until quiescence |
| **Memory map** | Fixed 16-byte `MMUKO_Byte` array | Replace with dynamic landmark ring of 21 nodes per hand |
| **Phase 6 rotation check** | Trivially true for all 8-bit values; dead code | Replace with cyclic-group symmetry check on landmark direction histogram |
| **Spin duplicates** | N==NW, NE==W spin values unexplained | Assign unique mrad values to all 8 compass directions; use physical angular velocity |

### 1.3 Decorative (Remove or Rename)

| MMUKO Term | Verdict | Recommendation |
|---|---|---|
| **Vacuum medium** (gravity/air/water) | No physical meaning in camera context | Remove. Replace with `sensor_params_t` (focal length, distortion coefficients) |
| **Aura seal / coherence** | Metaphor without measurement | Keep as `tracking_coherence` float [0,1] = mean landmark confidence × constraint satisfaction ratio |
| **Trident anchor P1/P2/P3** | Symbolic only | Rename: P1=wrist_anchor, P2=palm_centroid, P3=fingertip_cluster. Makes them measurable. |

---

## 2. Processing Pipeline

```
Camera frame (BGR 640×480 @ 30fps)
  │
  ▼  [~2 ms]
MediaPipe Hands (WASM / C++)
  → 21 landmarks per hand × {x,y,z,confidence}
  │
  ▼  [~0.5 ms]
mmuko_cv_begin_frame()
  → timestamp, dt, fps rolling average
  │
  ▼  [~0.5 ms]
mmuko_cv_feed_landmark() × 21
  → velocity = (pos_new - pos_old) / dt
  → drift_state = classify_drift(vel.z, vel.x, threshold)
  │
  ▼  [~0.2 ms]
mmuko_update_coord_frame()          ← Frame of Reference
  → origin = wrist[0].pos
  → axis_x = normalise(idx_mcp - wrist)
  → scale  = |axis_x| in px
  │
  ▼  [~0.3 ms]
mmuko_build_state_graph()           ← Cubit Ring
  → direction = quantise_8compass(vel)
  → spin_mrad = |vel - neighbour.vel| × 1000
  → LM_RING[i][0..3] = anatomical neighbours
  │
  ▼  [~0.5 ms]
mmuko_smooth_landmarks()            ← Nonlinear Resolution
  → estimator.push(pos)
  → smoothed  = ⅔ pos + ⅓ prev_pos
  → predicted = 2×pos - prev_pos
  │
  ▼  [~0.5 ms]
mmuko_resolve_constraints()         ← Entanglement
  → extension = |pos_a - pos_b| - rest_distance
  → stiffness = conf_a × conf_b
  → consensus = YES/MAYBE/NO per pair
  │
  ▼  [~0.3 ms]
mmuko_update_hypotheses()           ← Superposition
  → PINCH:     f(pinch.consensus)
  → OPEN_PALM: f(no constraints firing)
  → SWIPE_*:   f(palm_speed > threshold, direction ratio)
  │
  ▼  [~0.1 ms]
mmuko_collapse_hypotheses()         ← Resolution collapse
  → winner = argmax(confidence)
  │
  ▼  [~0.1 ms]
mmuko_detect_slice()
  → slice_detected = (winner ∈ {SWIPE_H, SWIPE_V, SWIPE_DIAG})
                   ∧ (velocity > 0.35)
  │
  ▼
Game engine event / Visual feedback
  → score delta, trail render, haptic
```

**Total pipeline budget: ~5 ms (leaves 11 ms for render + network @ 60fps)**

---

## 3. Data Structures

### 3.1 Landmark Node (Cubit Ring)
```c
typedef struct {
    int           index;          // [0..20] MediaPipe landmark ID
    vec3f_t       pos;            // normalised [0,1]^3 position
    vec3f_t       vel;            // frame-delta velocity
    vec3f_t       pos_predicted;  // spline next-frame prediction
    float         confidence;     // [0,1] detection score
    drift_state_t drift;          // RED/BLUE/GREEN/ORANGE/YELLOW
    compass_dir_t direction;      // 8-compass quantised velocity direction
    uint16_t      spin_mrad;      // angular velocity (milliradians)
    bool          active;         // visible this frame
    int           neighbours[4];  // anatomically adjacent landmark indices
} landmark_node_t;
```

### 3.2 Constraint Pair (Entanglement)
```c
typedef struct {
    int          lm_a, lm_b;     // bound landmark pair
    float        rest_distance;  // spring rest length (normalised)
    float        stiffness;      // k = conf_a × conf_b
    float        extension;      // |pos_a - pos_b| - rest_distance
    consensus_t  consensus;      // YES / MAYBE / NO
    char         label[16];      // "pinch", "curl", "spread"
} constraint_pair_t;
```

### 3.3 Hypothesis Set (Superposition)
```c
typedef struct {
    gesture_hypothesis_t items[8]; // candidate interpretations
    int                  count;
    int                  winner_idx; // argmax(confidence) after collapse
} hypothesis_set_t;
```

### 3.4 Feedback Estimator (Nonlinear Resolution)
```c
typedef struct {
    vec3f_t history[8]; // ring buffer — last 8 positions
    int     head;       // write pointer
    int     count;      // valid entries
    vec3f_t smoothed;   // W(t) = α·P(t) + (1-α)·P(t-1), α=0.667
    vec3f_t predicted;  // P(t+1) = 2P(t) - P(t-1)
    float   alpha;      // default 2/3 (Drift Theorem weight)
} feedback_estimator_t;
```

---

## 4. Memory Model

```
mmuko_cv_ctx_t (stack or heap, ~18 KB total):
  ├── hands[2] (hand_state_t × 2, ~9 KB each)
  │   ├── landmarks[21]       (landmark_node_t, 21 × ~80 bytes = 1.7 KB)
  │   ├── estimators[21]      (feedback_estimator_t, 21 × ~120 bytes = 2.5 KB)
  │   ├── constraints[10]     (constraint_pair_t, 10 × ~48 bytes = 480 bytes)
  │   ├── hypotheses          (hypothesis_set_t, ~320 bytes)
  │   └── frame + centroid    (~64 bytes)
  ├── frame metadata          (~32 bytes)
  └── slice output            (~32 bytes)

Zero heap allocation after init.
No malloc() in hot path.
All state lives in the context struct.
Cache-friendly: hand loop accesses contiguous arrays.
```

**WASM target**: ~18 KB data segment + ~15 KB code = ~33 KB total WASM module.
Fits in L1 cache on any modern CPU.

---

## 5. Landmark Constraint Map

Ten predefined constraint pairs derived from hand anatomy:

| Label | Joint A | Joint B | Detects |
|---|---|---|---|
| pinch | THUMB_TIP (4) | INDEX_TIP (8) | Pinch gesture |
| thumb_mid | THUMB_TIP (4) | MIDDLE_TIP (12) | Wide pinch |
| index_mid | INDEX_TIP (8) | MIDDLE_TIP (12) | Index-middle proximity |
| wrist_palm | WRIST (0) | MIDDLE_MCP (9) | Hand scale / calibration |
| knuckle_bar | INDEX_MCP (5) | PINKY_MCP (17) | Knuckle spread |
| index_reach | INDEX_TIP (8) | WRIST (0) | Finger extension |
| mid_reach | MIDDLE_TIP (12) | WRIST (0) | Finger extension |
| thumb_curl | THUMB_TIP (4) | THUMB_MCP (2) | Thumb curl |
| index_pip | INDEX_PIP (6) | INDEX_MCP (5) | Index PIP bend |
| mid_pip | MIDDLE_PIP (10) | MIDDLE_MCP (9) | Middle PIP bend |

---

## 6. Performance Analysis

### Latency Budget (@ 30fps = 33.3 ms per frame)
| Stage | Estimated time | Notes |
|---|---|---|
| Camera capture | 2–4 ms | V4L2 DMA, double-buffered |
| MediaPipe inference | 3–8 ms | WASM / GPU delegate |
| mmuko_cv_end_frame() | 0.5–2 ms | Pure C, O(21) per stage |
| Game engine update | 1–3 ms | JavaScript / C |
| Canvas render | 8–16 ms | Browser rasteriser |
| **Total** | **~16–33 ms** | Target: < 33 ms |

### Bottlenecks and Mitigations
1. **MediaPipe inference** is the dominant cost. Use GPU delegate (WebGL) on
   browser, NNAPI / CoreML on mobile. Keep model at "lite" quality.
2. **landmark_node velocity** computed per-feed avoids a second O(21) pass.
3. **Constraint resolution** is O(10) — not O(21²). Pairs are predefined, not
   searched.
4. **Hypothesis set** has fixed size 8 — no dynamic allocation.
5. **History buffer** is a ring — push is O(1), smooth is O(1).

### SIMD Opportunity (R2 roadmap)
`mmuko_smooth_landmarks()` is a candidate for NEON / AVX2 vectorisation.
21 × 3 floats = 63 floats per smoothing pass. With AVX2 (8-float lanes),
this is ~8 SIMD operations — measurable speedup on x86-64 desktop.

---

## 7. Cybernetic Control Loop (Fruit Ninja)

```
Human intent (slice a fruit)
  │
  ▼
Motor action (arm swing)
  │
  ▼  [physical]
Camera sensor (BGR frame)
  │
  ▼  [2–8 ms]
MediaPipe landmark extraction
  │
  ▼  [0.5–2 ms]
MMUKO state graph + constraint resolution
  │
  ▼  [0.1 ms]
Slice event emission
  │
  ▼  [1–3 ms]
Game engine: collision test, fruit split, score
  │
  ▼  [8–16 ms]
Visual feedback (slice trail, halves, splash)
  │
  ▼  [physiological: ~80 ms visual processing]
Human perceives result
  │
  ▼
Motor adjustment (next swing)
  └──────────────────────────────────────────┘
  Total loop: ~100–130 ms end-to-end
  Technical contribution: ~20–30 ms (15–23% of loop)
  Optimisation ceiling: ~80 ms (human perceptual limit)
```

The MMUKO pipeline's job is to stay well below the perceptual ceiling.
The 20–30 ms technical latency is within Fitts' Law acceptable range
for a fast-action game (comparable to console controller input lag).

---

## 8. Research Roadmap

### R0 — Current (Implemented)
- ✅ Drift Theorem 4-state classifier (`classify_drift`)
- ✅ Landmark state graph with ring topology (`mmuko_build_state_graph`)
- ✅ Spline feedback estimator (W(t) = ⅔P(t) + ⅓P(t-Δt))
- ✅ 10-pair constraint system (entanglement bindings)
- ✅ 8-hypothesis superposition set
- ✅ Coordinate frame alignment (Frame of Reference)
- ✅ Slice detection for Fruit Ninja integration

### R1 — Kalman Filter Extension (~2 weeks)
Replace spline smoother with a 6-DOF Kalman filter per landmark.
State vector: [x, y, z, vx, vy, vz].
Measurement: MediaPipe normalised coordinates.
Process noise: tuned from empirical camera jitter measurements.
Expected: 40% reduction in landmark jitter at cost of +0.5 ms/frame.

### R2 — SIMD Vectorisation (~1 week)
Vectorise `mmuko_smooth_landmarks()` with AVX2 / NEON.
Target: < 0.2 ms for full 21-joint smooth pass.
Enables 60fps pipeline on mid-range hardware.

### R3 — Gesture Template Expansion (~3 weeks)
Current: 8 gesture hypotheses.
Expand to 16 with Dynamic Time Warping for multi-frame gestures:
- rock/paper/scissors,
- wave,
- two-finger scroll,
- three-finger pinch (zoom).
Required: temporal hypothesis tracking (onset/duration).

### R4 — WebAssembly Deployment (~1 week)
Compile `mmuko_cv.c` to WASM with Emscripten.
Export 5 functions: init, begin_frame, feed_landmark, end_frame, detect_slice.
JavaScript wrapper feeds MediaPipe results directly into WASM memory.
Expected WASM module size: ~35 KB gzipped.

### R5 — Depth Integration (~4 weeks)
Incorporate MediaPipe's Z coordinate (depth estimate).
Enable 3D slice detection: swipes toward camera classify as PUSH/PULL.
Enables depth-gated games (only slice when arm is at correct depth).
Requires calibration of Z scale factor per camera intrinsics.

### R6 — Multi-Person Tracking (~4 weeks)
Extend `hand_count` beyond 2.
Add hand-identity linking between frames (Hungarian algorithm on centroid
distance to prevent ID swap when hands cross).
Required for multiplayer Fruit Ninja.

---

## 9. Integration Guide: Replacing the Python Camera Stack

Current Python stack (server.py + mmuko_camera.py) calls:
1. OpenCV frame capture → BGR numpy array
2. MediaPipe Hands inference → landmark results
3. Python drift classification → SocketIO emit

Recommended replacement:
1. OpenCV frame capture → stays Python (I/O bound, low cost)
2. MediaPipe Hands inference → stays Python (mediapipe library)
3. **Feed landmarks to `mmuko_cv.c` via ctypes** → replaces Python drift + state logic
4. **Read `ctx.slice_detected`, `ctx.hands[h].hypotheses.winner`** → SocketIO emit

ctypes bridge (5 lines):
```python
import ctypes, mmuko_cv_bindings as mmuko
ctx = mmuko.mmuko_cv_ctx_t()
mmuko.mmuko_cv_init(ctypes.byref(ctx))
# In frame loop:
mmuko.mmuko_cv_begin_frame(ctypes.byref(ctx), timestamp_us)
for lm in results.multi_hand_landmarks[0].landmark:
    mmuko.mmuko_cv_feed_landmark(ctypes.byref(ctx), 0, idx, lm.x, lm.y, lm.z, 0.9)
mmuko.mmuko_cv_end_frame(ctypes.byref(ctx))
slice_event = ctx.slice_detected
```

This preserves the existing Python server while moving all state logic
to deterministic, testable C.

---

*MMUKO Camera Architecture v1.0 — OBINexus 2026*
*mmuko_cv.h + mmuko_cv.c: 959 lines, 0 heap allocations in hot path*
