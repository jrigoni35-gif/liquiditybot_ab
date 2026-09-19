## Architecture (do not re-tangle what is separated)

- `main.py` = **engine** (LiquidityBot: pure decision pipeline,
  `cycle_once(now)` is step-able and deterministic under injected feeds).
- `runner.py` = **runner** (lifecycle loop, PAUSED/RUNNING/STOPPED,
  ControlChannel commands, StatusWriter). The loop lives here ONLY.
- `core/runtime.py` = **shared state layer**: atomic `status.json`,
  `events.jsonl` (structured logs), `outputs/control/` command files.
- The legacy Streamlit operator UI (`ui/dashboard.py`) has been
  **RETIRED**. Observability is **Grafana Cloud** (telemetry export reads
  the shared state files) and control is the **git remote-control plane**
  (`control/` command files via `scripts/remote_control.py`). Do not
  reintroduce an in-repo UI process; keep read/telemetry and control
  out-of-process.
- Position/inventory is quant-grade and stays that way: entries sized
  through PositionSizer Ã— RiskProtocolStack (CVaR/gap/budget/heat),
  inventory caps + hedger bound exposure, ProfitTierEngine + give-back
  ratchet own exits. New position logic goes through these, not beside.
- Logging goes through `logging` â†’ JsonlLogHandler (UI-friendly,
  level-filterable). No bare `print` in engine/runner/library code
  (scripts' human output is fine).
- All state is serializable: snapshots are checksummed JSON with backup
  generations; status schema keys (mode, positions, regimes, monitor,
  ml, equity, runner_state, sim) are load-bearing â€” extend, don't break.
- No infinite loops without an exit condition owned by the runner
  (`stop` command / `_stop` flag) or an exhaustion exception (replay).
  Anything needing operator input is documented in README â†’
  "Scripting inputs".

