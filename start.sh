#!/usr/bin/env bash
# start.sh - ONE command to run the bot.
# The bot runs in the background; use ./stop.sh to stop it.
# Observability lives in Grafana Cloud (see docs/PHONE_SESSIONS.md);
# control is the git remote-control plane (scripts/remote_control.py).
set -e
cd "$(dirname "$0")"

[ -f .venv/bin/activate ] || { echo "No .venv - running ./install.sh first..."; ./install.sh; }
. .venv/bin/activate

echo "Starting bot (background, log: outputs/runner_console.log)..."
mkdir -p outputs
nohup python runner.py > outputs/runner_console.log 2>&1 &
echo $! > outputs/runner.pid
echo "Bot PID $(cat outputs/runner.pid). Use ./stop.sh to stop it."
