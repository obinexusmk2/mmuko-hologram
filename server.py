"""
MMUKO Holographic Interface — Flask + SocketIO Server
=====================================================
Serves the HTML5 Canvas UI (static/index.html) and bridges the
Python MMUKO subsystems to the browser via WebSocket.

Endpoints
---------
  GET  /            → static/index.html
  GET  /<path>      → static/<path>
  WS   connect      → starts MmukoCamera stream
  WS   boot_mmuko   → runs mmuko_boot() and returns phase log + nodes
  WS   lattice_op   → performs meet/join on the L2 direct-product lattice

Run
---
  python server.py
  # then open http://localhost:5000 in your browser
"""

import os
import sys

# Make sure sibling modules resolve correctly when invoked from any cwd
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from flask import Flask, send_from_directory
from flask_socketio import SocketIO, emit

from mmuko_boot_sim import mmuko_boot
from mmuko_camera import MmukoCamera

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR)
app.config["SECRET_KEY"] = "mmuko-trilateral-consensus-2026"

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=False,
    engineio_logger=False,
)

camera = MmukoCamera(socketio)


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(STATIC_DIR, path)


# ---------------------------------------------------------------------------
# WebSocket events
# ---------------------------------------------------------------------------

@socketio.on("connect")
def on_connect():
    print("[MMUKO-SERVER] Client connected")
    if not camera.is_alive():
        camera.start()


@socketio.on("disconnect")
def on_disconnect():
    print("[MMUKO-SERVER] Client disconnected")


# ------------------------------------------------------------------
# Boot sequence
# ------------------------------------------------------------------

@socketio.on("boot_mmuko")
def on_boot(data):
    """
    Client payload:
        { bytes: [int, ...], bases: [int, ...] | null }
    """
    try:
        raw_bytes = [int(b) & 0xFF for b in data.get("bytes", [0x00, 0xFF, 0x2A])]
        bases     = data.get("bases") or None
        if bases:
            bases = [int(b) for b in bases]

        status, logs, nodes = mmuko_boot(raw_bytes, bases)

        emit("boot_result", {
            "status": status.ok,
            "reason": status.reason,
            "logs":   logs,
            "nodes": [
                {
                    "byte":      n.raw_value,
                    "hex":       f"0x{n.raw_value:02X}",
                    "base":      n.base_index,
                    "primary":   n.superposition_state.primary.value,
                    "secondary": n.superposition_state.secondary.value,
                    "cubits": [
                        {
                            "index":          c.index,
                            "value":          c.value,
                            "direction":      c.direction.value,
                            "state":          c.state.value,
                            "spin":           round(c.spin, 4),
                            "superposed":     c.superposed,
                            "entangled_with": c.entangled_with,
                        }
                        for c in n.cubit_ring
                    ],
                }
                for n in nodes
            ],
        })
    except Exception as exc:
        emit("boot_result", {"status": False, "reason": str(exc), "logs": [], "nodes": []})


# ------------------------------------------------------------------
# Lattice operations on L2 = {1,2} × {1,2}
# ------------------------------------------------------------------

@socketio.on("lattice_op")
def on_lattice_op(data):
    """
    Client payload:
        { op: 'meet'|'join', a: [x,y], b: [x,y] }

    L2 ordering: (x1,y1) ≤ (x2,y2)  iff  x1 ≤ x2 AND y1 ≤ y2
    meet (∧) = component-wise min
    join (∨) = component-wise max
    """
    try:
        op = data.get("op", "meet")
        a  = tuple(int(v) for v in data.get("a", [1, 1]))
        b  = tuple(int(v) for v in data.get("b", [2, 2]))

        if op == "meet":
            result = (min(a[0], b[0]), min(a[1], b[1]))
        else:
            result = (max(a[0], b[0]), max(a[1], b[1]))

        emit("lattice_result", {"op": op, "a": a, "b": b, "result": result})
    except Exception as exc:
        emit("lattice_result", {"error": str(exc)})


# ------------------------------------------------------------------
# On-demand cubit query (from browser byte input)
# ------------------------------------------------------------------

@socketio.on("cubit_query")
def on_cubit_query(data):
    """
    Client payload:  { byte: int, base: int }
    Returns full cubit ring + superposition for the given byte.
    """
    try:
        from mmuko_boot_sim import init_cubit_ring, lookup_superposition
        byte_val = int(data.get("byte", 0)) & 0xFF
        base     = int(data.get("base", 6))
        ring     = init_cubit_ring(byte_val)
        sp       = lookup_superposition(base)
        emit("cubit_result", {
            "byte":      byte_val,
            "hex":       f"0x{byte_val:02X}",
            "primary":   sp.primary.value,
            "secondary": sp.secondary.value,
            "cubits": [
                {
                    "index":          c.index,
                    "value":          c.value,
                    "direction":      c.direction.value,
                    "state":          c.state.value,
                    "spin":           round(c.spin, 4),
                    "superposed":     c.superposed,
                    "entangled_with": c.entangled_with,
                }
                for c in ring
            ],
        })
    except Exception as exc:
        emit("cubit_result", {"error": str(exc)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    host = os.environ.get("MMUKO_HOST", "0.0.0.0")
    port = int(os.environ.get("MMUKO_PORT", 5000))
    print(f"""
╔══════════════════════════════════════════════════════╗
║   MMUKO Holographic Interface Server                 ║
║   Trilateral Consensus Cybernetic System             ║
╠══════════════════════════════════════════════════════╣
║   http://localhost:{port:<34}║
║   Press Ctrl+C to stop                               ║
╚══════════════════════════════════════════════════════╝
""")
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)
