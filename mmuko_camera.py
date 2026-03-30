"""
MMUKO Camera — OpenCV Pixel Buffer + Trilateral Consensus Processor
=====================================================================
Captures frames from a physical camera (or generates synthetic data),
processes each frame through the MMUKO 8-cubit ring system, and
divides the image into three lateral zones (left / center / right)
to produce the tripartite colour consensus that drives the holographic UI.

Architecture
------------
  Camera frame (BGR)
        │
        ▼
  ┌─────────────────────────┐
  │  Trilateral Splitter    │  divides W into [L|C|R] thirds
  └──────┬──────┬──────┬───┘
       left  center  right
         │      │      │
         ▼      ▼      ▼
   avg BGR → XOR hash → byte_val (0x00–0xFF)
         │
         ▼
   init_cubit_ring(byte_val)   ← MMUKO phase-1
         │
         ▼
   lookup_superposition(base)  ← weak-map compass resolve
         │
         ▼
   { r, g, b, byte, primary, secondary, cubits[] }
         │
         ▼
   SocketIO emit('mmuko_frame', payload)
         │
         ▼
   Browser Canvas ← tripartite consensus + camera JPEG
"""

from __future__ import annotations

import base64
import math
import threading
import time
from typing import Any, Dict, Optional

# OpenCV is imported lazily so the module can load even without it
# (synthetic mode will run in that case)
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from mmuko_boot_sim import init_cubit_ring, lookup_superposition


# ---------------------------------------------------------------------------
# Pixel-buffer helpers
# ---------------------------------------------------------------------------

def frame_to_mmuko_pixel_buffer(frame: Any) -> Dict[str, Any]:
    """
    Convert an OpenCV BGR frame into an MMUKO 8×8 cubit pixel-buffer.

    Each of the 64 pixels maps to one cubit whose *value* is derived from
    the pixel's luminance (Y channel).  The 8×8 grid corresponds to a single
    ByteNode whose raw_value is the XOR-fold of all 64 luminance values.

    Returns a dict suitable for JSON serialisation.
    """
    import numpy as np  # only needed when CV2 is present

    small = cv2.resize(frame, (8, 8), interpolation=cv2.INTER_AREA)
    gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

    # Fold to a single byte via XOR
    flat      = gray.flatten().tolist()         # 64 ints [0..255]
    fold_byte = 0
    for v in flat:
        fold_byte ^= v
    fold_byte &= 0xFF

    ring = init_cubit_ring(fold_byte)
    sp   = lookup_superposition(6)

    return {
        "fold_byte":  fold_byte,
        "hex":        f"0x{fold_byte:02X}",
        "primary":    sp.primary.value,
        "secondary":  sp.secondary.value,
        "grid_8x8":   flat,          # raw luminance values for canvas rendering
        "cubits": [
            {
                "index":     c.index,
                "value":     c.value,
                "direction": c.direction.value,
                "state":     c.state.value,
                "spin":      round(c.spin, 4),
                "superposed":    c.superposed,
                "entangled_with": c.entangled_with,
            }
            for c in ring
        ],
    }


def zone_to_cubit_data(zone_bgr: Any, base: int = 6) -> Dict[str, Any]:
    """
    Compute the tripartite data for one lateral zone of a frame.

    Parameters
    ----------
    zone_bgr : numpy array  (H×W×3, uint8)
    base     : MMUKO base index for superposition lookup

    Returns
    -------
    dict with keys: r, g, b, byte, primary, secondary, cubits
    """
    avg   = zone_bgr.mean(axis=(0, 1))          # [B, G, R]
    r, g, b = int(avg[2]), int(avg[1]), int(avg[0])
    byte_val = (r ^ g ^ b) & 0xFF

    ring = init_cubit_ring(byte_val)
    sp   = lookup_superposition(base)

    return {
        "r": r, "g": g, "b": b,
        "byte":      byte_val,
        "hex":       f"0x{byte_val:02X}",
        "primary":   sp.primary.value,
        "secondary": sp.secondary.value,
        "cubits": [
            {
                "index":     c.index,
                "value":     c.value,
                "direction": c.direction.value,
                "state":     c.state.value,
                "spin":      round(c.spin, 4),
            }
            for c in ring
        ],
    }


def encode_frame_jpeg(frame: Any, width: int = 320, height: int = 240,
                      quality: int = 60) -> str:
    """Resize + JPEG-encode a frame; return as data-URI string."""
    small = cv2.resize(frame, (width, height))
    ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


# ---------------------------------------------------------------------------
# Synthetic data generator (no camera required)
# ---------------------------------------------------------------------------

def _synthetic_zone(t: float, phase_offset: float) -> Dict[str, Any]:
    """
    Generate a fake zone payload driven by sinusoidal phase cycling.
    The three zones are 120° apart — a genuine trilateral consensus signal.
    """
    phase = t + phase_offset
    r = int((math.sin(phase) + 1.0) * 127)
    g = int((math.sin(phase + 2.094395) + 1.0) * 127)   # +120°
    b = int((math.sin(phase + 4.188790) + 1.0) * 127)   # +240°
    byte_val = (r ^ g ^ b) & 0xFF

    ring = init_cubit_ring(byte_val)
    sp   = lookup_superposition(6)

    return {
        "r": r, "g": g, "b": b,
        "byte":      byte_val,
        "hex":       f"0x{byte_val:02X}",
        "primary":   sp.primary.value,
        "secondary": sp.secondary.value,
        "cubits": [
            {
                "index":     c.index,
                "value":     c.value,
                "direction": c.direction.value,
                "state":     c.state.value,
                "spin":      round(c.spin, 4),
            }
            for c in ring
        ],
    }


# ---------------------------------------------------------------------------
# Main camera class
# ---------------------------------------------------------------------------

class MmukoCamera:
    """
    Manages camera capture (or synthetic generation) and streams MMUKO
    tripartite consensus data to connected SocketIO clients.

    Usage
    -----
        cam = MmukoCamera(socketio_instance)
        cam.start()   # called on client connect
        cam.stop()    # called on client disconnect (optional)
    """

    TARGET_FPS    = 30
    JPEG_WIDTH    = 320
    JPEG_HEIGHT   = 240
    JPEG_QUALITY  = 60

    def __init__(self, socketio: Any, camera_index: int = 0) -> None:
        self.socketio      = socketio
        self.camera_index  = camera_index
        self._thread: Optional[threading.Thread] = None
        self._running      = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        target = self._camera_loop if CV2_AVAILABLE else self._synthetic_loop
        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal loops
    # ------------------------------------------------------------------

    def _camera_loop(self) -> None:
        """Real camera loop — falls back to synthetic if camera fails."""
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            print("[MMUKO-CAM] Camera not found — switching to synthetic mode")
            self._synthetic_loop()
            return

        print(f"[MMUKO-CAM] Camera {self.camera_index} opened")
        interval = 1.0 / self.TARGET_FPS

        try:
            while self._running:
                t0  = time.monotonic()
                ret, frame = cap.read()
                if not ret:
                    time.sleep(interval)
                    continue

                payload = self._build_payload(frame, synthetic=False)
                self.socketio.emit("mmuko_frame", payload)

                elapsed = time.monotonic() - t0
                sleep   = max(0.0, interval - elapsed)
                time.sleep(sleep)
        finally:
            cap.release()
            print("[MMUKO-CAM] Camera released")

    def _synthetic_loop(self) -> None:
        """Synthetic loop — trilateral sinusoidal phase cycling."""
        print("[MMUKO-CAM] Synthetic mode active")
        interval = 1.0 / self.TARGET_FPS
        t        = 0.0

        while self._running:
            t0 = time.monotonic()

            tripartite = {
                "left":   _synthetic_zone(t, 0.0),
                "center": _synthetic_zone(t, 2.094395),
                "right":  _synthetic_zone(t, 4.188790),
            }

            self.socketio.emit("mmuko_frame", {
                "tripartite": tripartite,
                "pixel_buffer": None,
                "frame":     None,
                "synthetic": True,
                "timestamp": t,
            })

            t      += 0.05
            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, interval - elapsed))

    # ------------------------------------------------------------------
    # Frame → payload
    # ------------------------------------------------------------------

    def _build_payload(self, frame: Any, synthetic: bool) -> Dict[str, Any]:
        h, w = frame.shape[:2]

        tripartite = {
            "left":   zone_to_cubit_data(frame[:, :w // 3]),
            "center": zone_to_cubit_data(frame[:, w // 3: 2 * w // 3]),
            "right":  zone_to_cubit_data(frame[:, 2 * w // 3:]),
        }

        pixel_buffer = frame_to_mmuko_pixel_buffer(frame)
        frame_uri    = encode_frame_jpeg(
            frame, self.JPEG_WIDTH, self.JPEG_HEIGHT, self.JPEG_QUALITY
        )

        return {
            "tripartite":   tripartite,
            "pixel_buffer": pixel_buffer,
            "frame":        frame_uri,
            "synthetic":    synthetic,
            "timestamp":    time.time(),
        }
