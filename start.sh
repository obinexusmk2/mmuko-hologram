#!/usr/bin/env bash
# ================================================================
#  MMUKO Holographic Interface — Linux / macOS launcher
# ================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo " MMUKO Holographic Interface"
echo " Trilateral Consensus Cybernetic System"
echo "================================================"

# Install deps
echo "[MMUKO] Installing Python dependencies..."
pip install -r requirements.txt -q

# Check for AnimatedTreeFree in common locations
TREE_SRC=""
for candidate in \
    "$HOME/Downloads/AnimatedTreeFree" \
    "$HOME/Desktop/AnimatedTreeFree"; do
  if [ -d "$candidate" ]; then TREE_SRC="$candidate"; break; fi
done

TREE_DST="$SCRIPT_DIR/static/assets/trees"
mkdir -p "$TREE_DST"

if [ -n "$TREE_SRC" ]; then
    echo "[MMUKO] Copying AnimatedTreeFree sprites from $TREE_SRC"
    cp -r "$TREE_SRC/"* "$TREE_DST/" 2>/dev/null || true
else
    echo "[MMUKO] AnimatedTreeFree not found — using procedural trees"
    echo "        (Place sprites in: static/assets/trees/tree_row.png)"
fi

# Open browser
(sleep 2 && xdg-open http://localhost:5000 2>/dev/null || open http://localhost:5000 2>/dev/null || true) &

echo "[MMUKO] Starting server on http://localhost:5000"
echo "[MMUKO] Press Ctrl+C to stop"
echo ""
python server.py
