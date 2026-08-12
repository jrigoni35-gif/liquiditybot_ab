"""scripts/reset_paper_capital.py — reseat the PAPER account's equity base to
config.json's starting_capital_usd, KEEPING open positions and all learning
state.

Why this exists: the running bot restores equity from the checksummed state
snapshot, so editing starting_capital_usd in config.json alone does NOT move the
live equity — the snapshot still carries the old cash base. After re-scaling the
paper account (e.g. 800 -> 5000) run this once so the LIVE equity actually
follows. Cash is PnL-settled (equity = cash + savings + unrealized), so resetting
the base is just rewriting the money fields; positions are untouched.

Cross-platform + supervisor-safe:
  * refuses unless system.dry_run is true — never touches a live-money account;
  * stops the runner with the graceful 'stop' control command (a file drop, so
    it works identically on Windows and Linux — no /proc, no signals) and
    confirms it stopped by watching status.json's heartbeat go stale, so its
    in-memory state can't clobber the write;
  * rewrites ONLY the portfolio money fields via the checksummed
    StateStore.write_raw; positions AND every other section (ML governor, open
    orders, history) are preserved;
  * does NOT relaunch — the pc_supervisor / session hook brings the runner back
    on the reset snapshot (or run `python runner.py`).

Learning artifacts (signal_history.csv, meta_model.json, imported bundles) live
in separate files and are never touched.

    python scripts/reset_paper_capital.py                 # preview only
    python scripts/reset_paper_capital.py --yes           # apply (uses config)
    python scripts/reset_paper_capital.py --yes --capital 10000
"""
import argparse
import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.persistence import StateStore  # noqa: E402

_MONEY_ZERO = ("savings_balance", "reserve_balance", "weekly_realized_pnl",
               "realized_pnl_total", "daily_realized_pnl",
               "fees_paid_total",
               # 2026-08-11 completeness audit (the $800 stressor reset).
               # monthly_realized_pnl predates this script and was never
               # in the list - the monthly counter survived every prior
               # reset. entry_fees_total was born 2026-08-09 (a6334162);
               # left unzeroed it would carry the OLD regime's opening-leg
               # fees into a fresh base and break the equity identity
               # (net_pnl_all_time = equity - starting_capital) on day one,
               # and core/persistence's backfill only fires when the key is
               # ABSENT, so a stale persisted value would win.
               "monthly_realized_pnl", "entry_fees_total")
_HEARTBEAT_STALE_SEC = 12.0     # a status.json older than this => runner is gone


def reset_portfolio(snapshot: dict, capital: float) -> dict:
    """Return a COPY of `snapshot` with the portfolio money base reset to
    `capital` — positions and every other section preserved. Pure + testable."""
    data = copy.deepcopy(snapshot)
    pf = dict(data.get("portfolio") or {})
    pf["starting_capital"] = float(capital)
    pf["cash_balance"] = float(capital)     # cash is PnL-settled -> this IS equity
    pf["equity_high_water"] = float(capital)  # drawdown now measured from here
    for k in _MONEY_ZERO:
        pf[k] = 0.0
    # RP-072 goal ladder: a fresh capital regime starts at the BASE goal.
    # 1.0, not 0.0 - it is a multiplier, and zeroing it would disable
    # monthly grading entirely (goal 0 = "untracked").
    pf["goal_ladder_mult"] = 1.0
    # positions (pf["positions"]) intentionally left as-is
    data["portfolio"] = pf
    # LOSS-BUDGET RE-ANCHOR (2026-08-12, the 25-hour no-trade incident):
    # risk_protocols measures the day/week loss budgets from persisted
    # EQUITY ANCHORS, and the ISO week key only rolls on Monday - so the
    # $800 reset left week_anchor at the pre-reset 4614.22 and RP-041 read
    # the reset itself as an 82.7% trading loss (1378% of the 6% weekly
    # budget), hard-vetoing ALL new risk for the rest of the week. 118
    # candidates died without a single entry order. A capital reset is a
    # REGIME CHANGE, not a loss: every calendar-anchored budget must
    # re-anchor at the new base in the same sweep (the live repair used
    # the audited budget_reanchor_week control verb; this makes the next
    # reset self-contained). Keys are preserved - the natural rollover
    # keeps working.
    rp = dict(data.get("risk_protocols") or {})
    if rp:
        for k in ("day_anchor", "week_anchor"):
            if k in rp:
                rp[k] = float(capital)
        data["risk_protocols"] = rp
    # PERFORMANCE WINDOW SWEEP (2026-08-11 full-sweep audit): the rolling
    # perf ledger is DOLLAR-denominated (expectancy_usd, net_usd, avg win/
    # loss). Carrying a $5000-regime window into an $800 regime blends
    # populations whose dollar scale differs 6.25x - the pooled-populations
    # defect, live on every board tile. Money figures, so the full sweep
    # takes them; the corpus and fills ledger are files, untouched.
    if "performance" in data:
        data["performance"] = {"trades": []}
    return data


def _runner_alive(status_path: Path) -> bool:
    """Heartbeat liveness, same signal the supervisor uses: a fresh status.json
    written_at means the runner loop is turning. Cross-platform, no PID."""
    try:
        s = json.loads(status_path.read_text(encoding="utf-8"))
        return (time.time() - float(s.get("written_at", 0.0))) < _HEARTBEAT_STALE_SEC
    except (OSError, ValueError, TypeError):
        return False


def _stop_runner(status_path: Path, timeout: float = 30.0) -> bool:
    """Ask the runner to stop and confirm it did (heartbeat goes stale). Returns
    True if the runner is stopped, False if it's still alive after `timeout`."""
    if not _runner_alive(status_path):
        return True
    try:
        from core.runtime import ControlChannel
        ControlChannel().send("stop")
        print("sent 'stop' to the runner — waiting for it to halt...")
    except Exception as e:  # noqa: BLE001
        print(f"could not send the stop command: {e}")
        return False
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(1.0)
        if not _runner_alive(status_path):
            print("runner stopped.")
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="reseat the paper account equity base")
    ap.add_argument("--yes", action="store_true",
                    help="apply the reset (without this, preview only)")
    ap.add_argument("--capital", type=float, default=None,
                    help="target base (default: config starting_capital_usd)")
    ap.add_argument("--config", default=str(ROOT / "config.json"))
    ap.add_argument("--state", default=str(ROOT / "outputs" / "state.json"))
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if not bool(cfg.get("system", {}).get("dry_run", True)):
        print("REFUSED: system.dry_run is false — this only resets PAPER capital.")
        return 2
    capital = args.capital if args.capital is not None else float(
        cfg.get("capital_management", {}).get("starting_capital_usd", 0.0))
    if not (capital > 0):
        print("REFUSED: target capital must be positive.")
        return 2

    store = StateStore(args.state)
    status_path = Path(args.state).parent / "status.json"
    snap = store.load_raw()
    if snap is None:
        print(f"no snapshot at {args.state} — nothing to reset (a fresh runner "
              f"will cold-start at ${capital:,.0f}).")
        return 0
    pf = snap.get("portfolio") or {}
    npos = len(pf.get("positions") or [])
    print(f"current: starting_capital=${pf.get('starting_capital', 0):,.2f} "
          f"cash=${pf.get('cash_balance', 0):,.2f} positions={npos}")
    print(f"target : ${capital:,.2f} base (positions kept, learning untouched)")
    if not args.yes:
        print("\npreview only — re-run with --yes to apply.")
        return 0

    if not _stop_runner(status_path):
        print("REFUSED: the runner is still alive after the stop request. Stop it "
              "(and pc_supervisor, so it can't relaunch mid-reset) and retry.")
        return 1
    ok = store.write_raw(reset_portfolio(snap, capital))
    if not ok:
        print("write failed — state left unchanged.")
        return 1
    chk = (store.load_raw() or {}).get("portfolio") or {}
    print(f"done: cash=${chk.get('cash_balance', 0):,.2f} "
          f"positions={len(chk.get('positions') or [])}. Relaunch the runner — "
          f"the supervisor will within ~2 min, or run `python runner.py`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
