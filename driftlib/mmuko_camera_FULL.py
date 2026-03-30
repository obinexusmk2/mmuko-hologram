"""
MMUKO Fluid Camera System — FULL ELECTROMAGNETIC RUNTIME
OBINexus Constitutional Computing | Nnamdi M. Okpala
Date: 2026-03-18

REAL-TIME LAYERS:
  1. Drift Theorem        — V(t) = P(t) − C(t), Dr, ω
  2. Magnetic Trident     — UCHE/EZE/OBI spring physics
  3. Compile-Time State   — LINK → THEN → EXECUTE phases
  4. Fractional Rotation  — MAYBE escalation ½→¼→⅙→⅛
  5. GPS Lattice Drift    — Marco/Polo vector closure
  6. Color State Map      — RED/BLUE/GREEN/ORANGE/YELLOW

No ML. Pure vector mathematics.
"""

import cv2
import numpy as np
import math
import time
import sys
import os
from collections import deque

# ─────────────────────────────────────────────────────────────
# DRIFT LIBRARY — Pure Python (no DLL required)
# ─────────────────────────────────────────────────────────────

def classify_drift(v_toward, v_ortho, threshold=0.5):
    """
    Drift Theorem classification.
    Maps (v_toward, v_ortho) → DriftColorState
    """
    abs_toward = abs(v_toward)
    abs_ortho  = abs(v_ortho)

    if abs_toward < threshold and abs_ortho < threshold:
        return 3   # ORANGE — STATIC

    if abs_ortho > abs_toward * 1.5 and abs_ortho > threshold:
        return 1   # BLUE   — ORTHOGONAL

    if v_toward > threshold:
        return 2   # GREEN  — APPROACH

    if v_toward < -threshold:
        return 0   # RED    — AWAY

    return 4       # YELLOW — TRANSITION


STATE_NAMES = {
    0: "RED    (AWAY)",
    1: "BLUE   (ORTHOGONAL)",
    2: "GREEN  (APPROACH)",
    3: "ORANGE (STATIC)",
    4: "YELLOW (TRANSITION)",
}

# BGR for OpenCV overlays
STATE_BGR = {
    0: (0,   55,  255),   # Red-Orange
    1: (255, 102,   0),   # Blue-Yellow
    2: (40,  255,  80),   # Green
    3: (0,   165, 255),   # Orange
    4: (0,   255, 255),   # Yellow
}

# ─────────────────────────────────────────────────────────────
# SPRING / MAGNETIC TRIDENT — NSIGII Physics
# ─────────────────────────────────────────────────────────────

class SpringState:
    """
    UCHE/EZE/OBI magnetic spring model.
    Extension x = F / k
    Collapse ratio r = x / x_max  (0 = open, 1 = collapsed)
    Consensus: YES (r>=1), MAYBE (0.5<=r<1), NO (r<0.5)
    """
    K_MAX   = 2.0   # maximum stiffness (fully tracking)
    X_MAX   = 1.0   # maximum extension (normalised)

    def __init__(self):
        self.force      = 0.0   # F — optical flow magnitude (normalised)
        self.stiffness  = 1.0   # k — feature-track confidence (0–2)
        self.extension  = 0.0   # x = F/k
        self.ratio      = 0.0   # r = x/x_max
        self.consensus  = "NO"
        self.escalation = 0     # MAYBE escalation level 0–3

    ROTATION_FRACS = [0.5, 0.25, 1/6, 0.125]
    ROTATION_NAMES = ["½", "¼", "⅙", "⅛"]

    def update(self, flow_mag, feature_count, dt):
        """Update spring from optical flow."""
        # Force proportional to flow magnitude (capped at 1)
        self.force     = min(1.0, flow_mag / 30.0)
        # Stiffness proportional to how many features we tracked
        self.stiffness = max(0.1, min(self.K_MAX, feature_count / 50.0))
        self.extension = self.force / self.stiffness
        self.ratio     = min(1.0, self.extension / self.X_MAX)

        if self.ratio >= 1.0:
            self.consensus  = "YES"
            self.escalation = 0
        elif self.ratio >= 0.5:
            # MAYBE — escalate over time
            self.consensus = "MAYBE"
            # escalation level driven by how long in MAYBE
            self.escalation = min(3, int((self.ratio - 0.5) * 8))
        else:
            self.consensus  = "NO"
            self.escalation = 0

    def multiplier(self):
        frac = self.ROTATION_FRACS[self.escalation]
        return 1.0 / frac   # M = 1/fraction

    def frac_name(self):
        return self.ROTATION_NAMES[self.escalation]


# ─────────────────────────────────────────────────────────────
# COMPILE-TIME STATE MACHINE — LINK → THEN → EXECUTE
# ─────────────────────────────────────────────────────────────

class CompilePhase:
    """
    LTF pipeline phase tracker.
    LINK   = identity + GPS resolved
    THEN   = payload bound to spacetime state
    EXECUTE= signed output emitted
    Each phase has a confidence score driven by tracking quality.
    """
    PHASES = ["LINK", "THEN", "EXECUTE"]

    def __init__(self):
        self.phase      = 0      # 0/1/2
        self.confidence = 0.0    # 0–1
        self.sequence   = 0      # monotonic counter
        self._timer     = 0.0

    def update(self, feature_count, consensus, dt):
        self._timer += dt
        # Confidence: enough features = LINK phase succeeds
        self.confidence = min(1.0, feature_count / 80.0)

        if self.confidence > 0.8 and consensus == "YES":
            self.phase = 2   # EXECUTE
        elif self.confidence > 0.4 or consensus == "MAYBE":
            self.phase = 1   # THEN
        else:
            self.phase = 0   # LINK

        if self._timer > 0.1:
            self.sequence += 1
            self._timer = 0.0

    def name(self):
        return self.PHASES[self.phase]


# ─────────────────────────────────────────────────────────────
# MARCO/POLO GPS TRACKER — Drift Theorem vector maths
# ─────────────────────────────────────────────────────────────

class MarcoPolo:
    """
    Tracks observer C(t) and centroid P(t) in pixel space.
    Computes Dr (radial drift) and ω (angular drift) live.
    W(t) = ⅔P(t) + ⅓P(t−Δt) — weighted smoother.
    """
    def __init__(self, cx, cy):
        self.C      = np.array([cx, cy], dtype=float)   # Observer (crosshair)
        self.P      = np.array([cx, cy], dtype=float)   # Target centroid
        self.P_prev = np.array([cx, cy], dtype=float)
        self.V      = np.zeros(2)                        # V(t) = P−C
        self.V_prev = np.zeros(2)
        self.Dr     = 0.0                                # Radial drift
        self.omega  = 0.0                                # Angular drift
        self.W      = np.array([cx, cy], dtype=float)   # Weighted position
        self.hist   = deque(maxlen=60)                   # Distance history

    def update(self, px, py, dt):
        self.P_prev = self.P.copy()
        self.V_prev = self.V.copy()
        self.P      = np.array([px, py], dtype=float)
        self.V      = self.P - self.C

        d_now  = np.linalg.norm(self.V)
        d_prev = np.linalg.norm(self.V_prev)

        self.Dr = (d_now - d_prev) / dt if dt > 1e-6 else 0.0

        # Angular drift ω = dθ/dt
        if d_now > 1e-3 and d_prev > 1e-3:
            cos_a = np.clip(
                np.dot(self.V, self.V_prev) / (d_now * d_prev), -1.0, 1.0
            )
            theta = math.acos(cos_a)
            self.omega = theta / dt if dt > 1e-6 else 0.0
        else:
            self.omega = 0.0

        # Weighted smoother W(t) = ⅔P + ⅓P_prev
        self.W = (2.0/3.0) * self.P + (1.0/3.0) * self.P_prev
        self.hist.append(d_now)


# ─────────────────────────────────────────────────────────────
# RENDERING HELPERS
# ─────────────────────────────────────────────────────────────

def draw_panel(frame, x, y, w, h, alpha=0.55, color=(10, 10, 10)):
    """Semi-transparent dark panel."""
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x+w, y+h), color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

def draw_bar(frame, x, y, w, h, val, color, bg=(40,40,40)):
    """Horizontal fill bar 0–1."""
    cv2.rectangle(frame, (x, y), (x+w, y+h), bg, -1)
    fill = int(w * max(0.0, min(1.0, val)))
    if fill > 0:
        cv2.rectangle(frame, (x, y), (x+fill, y+h), color, -1)
    cv2.rectangle(frame, (x, y), (x+w, y+h), (80,80,80), 1)

def draw_sparkline(frame, x, y, w, h, data, color):
    """Mini line graph from deque of floats."""
    if len(data) < 2:
        return
    vals = list(data)
    mn, mx = min(vals), max(vals)
    rng = mx - mn if mx != mn else 1.0
    pts = []
    for i, v in enumerate(vals):
        px = x + int(i * w / (len(vals)-1))
        py = y + h - int((v - mn) / rng * h)
        pts.append((px, py))
    for i in range(len(pts)-1):
        cv2.line(frame, pts[i], pts[i+1], color, 1, cv2.LINE_AA)

def put(frame, text, x, y, scale=0.55, color=(220,220,220), bold=False):
    """Quick text helper."""
    thick = 2 if bold else 1
    cv2.putText(frame, text, (x, y),
                cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


# ─────────────────────────────────────────────────────────────
# MAIN CAMERA CLASS
# ─────────────────────────────────────────────────────────────

class MMUKOFullCamera:
    """
    MMUKO Fluid — Full Electromagnetic Runtime
    All layers rendered in real-time, no ML.
    """
    def __init__(self, camera_id=0):
        # ── camera init ──────────────────────────────────────
        self.cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            # try without DirectShow (Linux / fallback)
            self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {camera_id}")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT,  720)

        self.W  = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.H  = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cx, cy  = self.W // 2, self.H // 2

        # ── sub-systems ──────────────────────────────────────
        self.spring  = SpringState()
        self.compile = CompilePhase()
        self.mp      = MarcoPolo(cx, cy)

        # ── optical flow ─────────────────────────────────────
        self.prev_gray = None
        self.feature_params = dict(
            maxCorners=120, qualityLevel=0.25,
            minDistance=6,  blockSize=7
        )
        self.lk_params = dict(
            winSize=(15, 15), maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )

        # ── state ────────────────────────────────────────────
        self.zoom_level   = 1.0
        self.max_zoom     = 5.0
        self.prev_t       = time.time()
        self.state        = 3      # start ORANGE
        self.flow_vectors = []     # for arrow overlay
        self.fps_hist     = deque(maxlen=30)
        self.frame_count  = 0
        self.v_toward     = 0.0
        self.v_ortho      = 0.0
        self.feat_count   = 0

        print("╔══════════════════════════════════════════════╗")
        print("║  MMUKO Fluid — Full Electromagnetic Runtime  ║")
        print("║  OBINexus Computing | Nnamdi M. Okpala       ║")
        print("╠══════════════════════════════════════════════╣")
        print("║  Layers: Drift | Spring | Compile | Polo     ║")
        print("║  Mode: Pure Python (no DLL required)         ║")
        print("║  Controls: Q/ESC  +/-  R  S                  ║")
        print("╚══════════════════════════════════════════════╝")

    # ── digital zoom ─────────────────────────────────────────
    def zoom(self, frame):
        if self.zoom_level <= 1.0:
            return frame
        h, w = frame.shape[:2]
        nw, nh = int(w / self.zoom_level), int(h / self.zoom_level)
        x1, y1 = (w-nw)//2, (h-nh)//2
        return cv2.resize(frame[y1:y1+nh, x1:x1+nw], (w, h), interpolation=cv2.INTER_LINEAR)

    # ── optical flow computation ──────────────────────────────
    def compute_flow(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.prev_gray is None:
            self.prev_gray = gray
            return 0.0, 0.0, 0, 0.0, []

        p0 = cv2.goodFeaturesToTrack(self.prev_gray, mask=None, **self.feature_params)
        if p0 is None:
            self.prev_gray = gray
            return 0.0, 0.0, 0, 0.0, []

        p1, st, _ = cv2.calcOpticalFlowPyrLK(
            self.prev_gray, gray, p0, None, **self.lk_params)

        if p1 is None or st is None:
            self.prev_gray = gray
            return 0.0, 0.0, 0, 0.0, []

        good_new = p1[st == 1]
        good_old = p0[st == 1]

        if len(good_new) == 0:
            self.prev_gray = gray
            return 0.0, 0.0, 0, 0.0, []

        motions   = good_new - good_old
        avg       = np.mean(motions, axis=0)
        dx, dy    = float(avg[0]), float(avg[1])
        flow_mag  = math.sqrt(dx*dx + dy*dy)

        # centroid of tracked points
        ex = float(np.mean(good_new[:, 0]))
        ey = float(np.mean(good_new[:, 1]))

        # toward/away vector (relative to crosshair centre)
        cx, cy = self.W//2, self.H//2
        tvx, tvy = cx - ex, cy - ey
        dist = math.sqrt(tvx*tvx + tvy*tvy)
        if dist > 0:
            tvx /= dist; tvy /= dist

        v_toward = -(dx*tvx + dy*tvy) * self.zoom_level
        v_ortho  =  abs(dx*(-tvy) + dy*tvx) * self.zoom_level

        # arrows for overlay
        arrows = [(int(p[0]), int(p[1]), int(p[0]+m[0]*5), int(p[1]+m[1]*5))
                  for p, m in zip(good_new, motions)]

        self.prev_gray = gray
        return v_toward, v_ortho, len(good_new), flow_mag, arrows

    # ── HUD rendering ─────────────────────────────────────────
    def render(self, frame, dt):
        h, w = frame.shape[:2]
        state_bgr = STATE_BGR.get(self.state, (128,128,128))
        spring    = self.spring
        cp        = self.compile
        mp        = self.mp
        consensus = spring.consensus

        # ── border ───────────────────────────────────────────
        bw = 18
        cv2.rectangle(frame, (0,0), (w,h), state_bgr, bw)

        # ── flow arrows ──────────────────────────────────────
        arrow_col = tuple(int(c*0.7) for c in state_bgr)
        for x0, y0, x1, y1 in self.flow_vectors[:80]:
            cv2.arrowedLine(frame, (x0,y0), (x1,y1),
                            arrow_col, 1, tipLength=0.4)

        # ── Marco/Polo W(t) crosshair ────────────────────────
        wx, wy = int(mp.W[0]), int(mp.W[1])
        cv2.drawMarker(frame, (w//2, h//2),
                       (0, 255, 0), cv2.MARKER_CROSS, 44, 2)
        cv2.circle(frame, (wx, wy), 8, (255, 255, 0), 2)  # W(t)
        cv2.line(frame, (w//2, h//2), (wx, wy), (80,80,80), 1)

        # ============================================================
        # LEFT PANEL — DRIFT THEOREM
        # ============================================================
        PW = 340   # panel width
        draw_panel(frame, 0, bw, PW, 420)
        lx, ly = 10, bw + 18

        put(frame, "DRIFT THEOREM", lx, ly, 0.52, (200,200,200), bold=True)
        put(frame, "V(t) = P(t) - C(t)", lx, ly+20, 0.42, (140,200,140))
        ly += 44

        # State badge
        sname = STATE_NAMES.get(self.state, "?")
        cv2.rectangle(frame, (lx, ly), (lx+PW-20, ly+26), state_bgr, -1)
        put(frame, f"STATE: {sname}", lx+4, ly+19, 0.55, (0,0,0), bold=True)
        ly += 34

        # Toward / Ortho bars
        for label, val, col in [
            (f"Dr  toward: {self.v_toward:+.3f}", self.v_toward, (40,255,80)),
            (f"Dr  ortho:  {self.v_ortho:+.3f}",  self.v_ortho,  (0,180,255)),
        ]:
            put(frame, label, lx, ly, 0.43, (200,200,200))
            ly += 16
            draw_bar(frame, lx, ly, PW-20, 8,
                     abs(val)/3.0,
                     col if val >= 0 else (0, 55, 255))
            ly += 14

        # Radial drift Dr (signed bar, centre = 0)
        Dr_norm = max(-1.0, min(1.0, mp.Dr / 200.0))
        put(frame, f"Dr (radial):  {mp.Dr:+.1f} px/s", lx, ly, 0.43, (200,200,200))
        ly += 16
        mid = lx + (PW-20)//2
        bar_h = 8
        if Dr_norm >= 0:
            cv2.rectangle(frame, (mid, ly),
                          (mid + int(Dr_norm*(PW-20)//2), ly+bar_h),
                          (0,55,255), -1)
        else:
            cv2.rectangle(frame, (mid + int(Dr_norm*(PW-20)//2), ly),
                          (mid, ly+bar_h),
                          (40,255,80), -1)
        cv2.line(frame, (mid, ly), (mid, ly+bar_h), (180,180,180), 1)
        cv2.rectangle(frame, (lx, ly), (lx+PW-20, ly+bar_h), (80,80,80), 1)
        ly += 16

        # Angular drift ω
        put(frame, f"\u03c9 (angular): {mp.omega:.4f} rad/s", lx, ly, 0.43, (200,200,200))
        ly += 16
        draw_bar(frame, lx, ly, PW-20, 8,
                 min(1.0, mp.omega / 2.0), (255, 200, 0))
        ly += 16

        # W(t) smoother
        put(frame, f"W(t) = \u2154P(t) + \u2153P(t\u2212\u0394t)", lx, ly, 0.43, (255,220,100))
        put(frame, f"W: ({int(mp.W[0])},{int(mp.W[1])})", lx, ly+16, 0.43, (200,200,200))
        ly += 36

        # Distance sparkline
        put(frame, f"|V(t)| = {np.linalg.norm(mp.V):.1f} px", lx, ly, 0.43, (180,180,180))
        ly += 16
        draw_sparkline(frame, lx, ly, PW-20, 30, mp.hist, state_bgr)
        ly += 38

        put(frame, f"Feat: {self.feat_count}    Zoom: {self.zoom_level:.1f}x",
            lx, ly, 0.43, (160,160,160))

        # ============================================================
        # RIGHT PANEL — SPRING PHYSICS + COMPILE STATE
        # ============================================================
        rx = w - PW - bw
        draw_panel(frame, rx, bw, PW+bw, 460)
        rlx, rly = rx + 10, bw + 18

        # ── MAGNETIC SPRING ──────────────────────────────────
        put(frame, "MAGNETIC SPRING", rlx, rly, 0.52, (200,200,200), bold=True)
        put(frame, "UCHE \u2192 EZE \u2192 OBI", rlx, rly+20, 0.42, (140,180,220))
        rly += 44

        # Consensus badge
        con_col = {
            "YES":   (40,  200,  40),
            "MAYBE": (0,   200, 255),
            "NO":    (40,   40, 200),
        }.get(consensus, (128,128,128))
        cv2.rectangle(frame, (rlx, rly), (rlx+PW-10, rly+26), con_col, -1)
        put(frame, f"CONSENSUS: {consensus}", rlx+4, rly+19,
            0.55, (0,0,0), bold=True)
        rly += 34

        for label, val, col in [
            (f"Force  F = {spring.force:.4f}",
             spring.force, (255, 150, 50)),
            (f"Stiffness k = {spring.stiffness:.4f}",
             spring.stiffness / 2.0, (100, 200, 255)),
            (f"Extension x = {spring.extension:.4f}",
             spring.extension, (200, 255, 100)),
            (f"Collapse r = {spring.ratio:.4f}",
             spring.ratio, con_col),
        ]:
            put(frame, label, rlx, rly, 0.43, (200,200,200))
            rly += 16
            draw_bar(frame, rlx, rly, PW-20, 8, val, col)
            rly += 14

        # MAYBE escalation
        put(frame, "MAYBE Escalation:", rlx, rly, 0.43, (200,200,200))
        rly += 16
        frac_names = ["½", "¼", "⅙", "⅛"]
        cell_w = (PW-20)//4
        for i, fn in enumerate(frac_names):
            active = (i == spring.escalation and consensus == "MAYBE")
            bg = con_col if active else (60,60,60)
            cv2.rectangle(frame, (rlx + i*cell_w, rly),
                          (rlx + (i+1)*cell_w - 2, rly+22), bg, -1)
            fc = (0,0,0) if active else (140,140,140)
            put(frame, fn, rlx + i*cell_w + 4, rly+16, 0.5, fc)
        if consensus == "MAYBE":
            M = spring.multiplier()
            put(frame, f"M = 1/{spring.frac_name()} = {M:.0f}\u00d7",
                rlx, rly+28, 0.43, (0, 200, 255))
            rly += 12
        rly += 34

        # ── COMPILE-TIME STATE ───────────────────────────────
        put(frame, "COMPILE-TIME STATE", rlx, rly, 0.52, (200,200,200), bold=True)
        put(frame, "riftlang \u2192 ltcodec \u2192 nsigii", rlx, rly+20, 0.42, (140,180,140))
        rly += 44

        phase_cols = [(80,80,200), (200,120,0), (40,200,40)]
        phase_names = ["LINK", "THEN", "EXECUTE"]
        cell_w2 = (PW-20)//3
        for i, (pn, pc) in enumerate(zip(phase_names, phase_cols)):
            active = (i == cp.phase)
            bg = pc if active else (50,50,50)
            cv2.rectangle(frame, (rlx + i*cell_w2, rly),
                          (rlx + (i+1)*cell_w2 - 2, rly+26), bg, -1)
            fc = (255,255,255) if active else (100,100,100)
            put(frame, pn, rlx + i*cell_w2 + 4, rly+19, 0.5, fc, bold=active)
        rly += 32

        draw_bar(frame, rlx, rly, PW-20, 8,
                 cp.confidence, phase_cols[cp.phase])
        put(frame, f"Confidence: {cp.confidence:.2f}    Seq: {cp.sequence}",
            rlx, rly+14, 0.42, (160,160,160))
        rly += 30

        # ── MARCO/POLO GPS LAYER ─────────────────────────────
        put(frame, "MARCO/POLO GPS LAYER", rlx, rly, 0.52, (200,200,200), bold=True)
        rly += 22
        d_now  = np.linalg.norm(mp.V)
        d_hist = list(mp.hist)
        d_init = d_hist[0] if d_hist else d_now
        closure = d_init - d_now
        put(frame, f"MARCO C: ({w//2}, {h//2})", rlx, rly, 0.42, (180,180,180))
        rly += 16
        put(frame, f"POLO  P: ({int(mp.P[0])}, {int(mp.P[1])})",
            rlx, rly, 0.42, (180,180,180))
        rly += 16
        dr_col = (40,255,80) if mp.Dr < 0 else (0,55,255)
        put(frame, f"Dr: {mp.Dr:+.1f} px/s   \u03c9: {mp.omega:.4f} r/s",
            rlx, rly, 0.42, dr_col)
        rly += 16
        put(frame, f"Closure \u0394: {closure:+.1f} px",
            rlx, rly, 0.42, (255,220,100))
        rly += 16
        put(frame, f"W(t) = \u2154P + \u2153P\u2019 = ({int(mp.W[0])},{int(mp.W[1])})",
            rlx, rly, 0.42, (255,220,100))

        # ============================================================
        # BOTTOM BAR — FPS + pipeline
        # ============================================================
        fps = 1.0/dt if dt > 1e-6 else 0.0
        self.fps_hist.append(fps)
        avg_fps = sum(self.fps_hist)/len(self.fps_hist)

        draw_panel(frame, 0, h-38, w, 38, alpha=0.7)
        pipeline = ("riftlang.exe  \u2192  .so.a  \u2192  rift.exe  "
                    "\u2192  gosilang  \u2192  ltcodec  \u2192  nsigii")
        put(frame, pipeline, 10, h-20, 0.38, (100,180,100))
        put(frame, f"FPS: {avg_fps:.1f}  |  Frame: {self.frame_count}  |  "
            f"OBINexus #NoGhosting",
            w - 380, h-20, 0.38, (140,140,140))

        # ============================================================
        # CENTRE — sparse state label
        # ============================================================
        label = STATE_NAMES.get(self.state, "")
        txt_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)[0]
        tx = (w - txt_size[0]) // 2
        ty = h - 60
        draw_panel(frame, tx-8, ty-24, txt_size[0]+16, txt_size[1]+12,
                   alpha=0.6, color=(0,0,0))
        cv2.putText(frame, label, (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, state_bgr, 2, cv2.LINE_AA)

        return frame

    # ── main loop ─────────────────────────────────────────────
    def run(self):
        print("\nStarting MMUKO Full Electromagnetic Runtime...")
        print("Press Q or ESC to quit.\n")

        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Camera read failed.")
                break

            now = time.time()
            dt  = max(1e-6, now - self.prev_t)
            self.prev_t = now
            self.frame_count += 1

            frame = self.zoom(frame)

            # ── compute flow ─────────────────────────────────
            vt, vo, fc, fmag, arrows = self.compute_flow(frame)
            self.v_toward    = vt
            self.v_ortho     = vo
            self.feat_count  = fc
            self.flow_vectors = arrows

            # ── classify ─────────────────────────────────────
            self.state = classify_drift(vt, vo)

            # ── update sub-systems ────────────────────────────
            self.spring.update(fmag, fc, dt)
            self.compile.update(fc, self.spring.consensus, dt)

            # Centroid of tracked points → POLO position
            # (use centre when no features tracked)
            cx, cy = self.W//2, self.H//2
            if fc > 0 and len(arrows) > 0:
                px = float(np.mean([a[0] for a in arrows]))
                py = float(np.mean([a[1] for a in arrows]))
            else:
                px, py = float(cx), float(cy)
            self.mp.update(px, py, dt)

            # ── render ────────────────────────────────────────
            frame = self.render(frame, dt)

            cv2.imshow("MMUKO Fluid — OBINexus Full Runtime", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), 27):
                break
            elif key in (ord('+'), ord('=')):
                self.zoom_level = min(self.max_zoom, self.zoom_level + 0.5)
                print(f"Zoom: {self.zoom_level:.1f}x")
            elif key == ord('-'):
                self.zoom_level = max(1.0, self.zoom_level - 0.5)
                print(f"Zoom: {self.zoom_level:.1f}x")
            elif key == ord('r'):
                self.zoom_level = 1.0
                print("Zoom reset")
            elif key == ord('s'):
                fn = f"mmuko_full_{int(time.time())}.png"
                cv2.imwrite(fn, frame)
                print(f"Saved: {fn}")

        self.cap.release()
        cv2.destroyAllWindows()
        print("MMUKO shutdown complete.")


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cam_id = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    try:
        MMUKOFullCamera(cam_id).run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
