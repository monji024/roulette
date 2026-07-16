#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo " ROULETTE — Installer"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 was not found on PATH. Please install Python 3.10+."
    exit 1
fi
echo "-> Found $(python3 --version)"
if command -v ruby >/dev/null 2>&1; then
    echo "-> Found $(ruby --version)"
else
    echo "-> WARNING: Ruby was not found on PATH."
    echo "   The game will still run, but atmospheric narration and ASCII"
    echo "   effects will fall back to a minimal built-in text set."
    echo "   Install Ruby (e.g. 'sudo apt install ruby' or 'brew install ruby')"
    echo "   for the full experience."
fi

if [ ! -d ".venv" ]; then
    echo "-> Creating virtual environment (.venv)..."
    python3 -m venv .venv
else
    echo "-> Virtual environment already exists, reusing it."
fi

echo "-> Installing Python dependencies..."
".venv/bin/pip" install --upgrade pip >/dev/null
".venv/bin/pip" install -r requirements.txt

mkdir -p data
[ -f data/scores.json ] || echo '{"wins":0,"losses":0,"best_score":0,"current_streak":0,"best_streak":0,"total_games":0,"history":[]}' > data/scores.json
touch data/deaths.log

echo
echo " Installation complete."
echo
echo " To play:"
echo "   source .venv/bin/activate"
echo "   python3 client/main.py"