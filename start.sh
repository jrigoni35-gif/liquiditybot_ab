#!/usr/bin/env bash
# start.sh - ONE command to run everything: bot + dashboard.
# The bot runs in the background; the dashboard opens in your browser.
# Ctrl+C closes the dashboard only; use ./stop.sh to stop the bot.
set -e
cd "$(dirname "$0")"

[ -f .venv/bin/activate ] || { echo "No .venv - running ./install.sh first..."; ./install.sh; }
. .venv/bin/activate

echo "Starting bot (background, log: outputs/runner_console.log)..."
mkdir -p outputs
nohup python runner.py > outputs/runner_console.log 2>&1 &
echo $! > outputs/runner.pid
echo "Bot PID $(cat outputs/runner.pid). Use ./stop.sh to stop it."

echo "Starting dashboard (browser opens automatically)..."
python -m streamlit run ui/dashboard.py
