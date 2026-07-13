#!/usr/bin/env bash
# stop.sh - stop the bot cleanly (snapshot + dead-man cancel + loop exit).
cd "$(dirname "$0")"
[ -f .venv/bin/activate ] && . .venv/bin/activate
python -c "import sys; sys.path.insert(0, '.'); from core.runtime import ControlChannel; ControlChannel('outputs/control').send('stop'); print('stop sent - the runner exits after its current cycle.')"
