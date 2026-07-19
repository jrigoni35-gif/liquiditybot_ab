#!/usr/bin/env bash
# install.sh - ONE command to set everything up (macOS / Linux).
set -e
cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "python3 not found - install Python 3.10+"; exit 1; }

if [ ! -d .venv ]; then
    echo "[1/3] Creating virtual environment..."
    python3 -m venv .venv
else
    echo "[1/3] Virtual environment already exists - reusing."
fi

. .venv/bin/activate
echo "[2/3] Installing dependencies..."
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q

echo "[3/3] Verifying installation..."
python -m compileall -q .
python -c "import main, runner" >/dev/null

cat <<'DONE'

============================================
 Install complete. Everything you need:
   ./start.sh  - run the bot
   ./stop.sh   - stop the bot cleanly
 The bot starts in DRY RUN (paper trading).
 Going live requires editing config.json AND
 typing the ARM phrase (ARM LIVE) at the PC console.
============================================
DONE
