"""scripts/reset_paper_capital.py — reseat the PAPER account's equity base to
config.json's starting_capital_usd, KEEPING open positions and all learning
state.

Why this exists: the running bot restores equity from the checksummed state
snapshot, so editing starting_capital_usd in config.json alone does NOT move the
live equity — the snapshot still carries the old cash base. After re-scaling the
paper account (e.g. 800 -> 5000) run this once so the LIVE equity actually
follows. Cash is PnL-settled (equity = cash + savings + unrealized), so resetting
the base is just rewriting the money fields; positions are untouched.

Safe by construction:
  * refuses unless system.dry_run is true — never touches a live-money account;
  * stops the runner first (graceful 'stop', SIGTERM fallback) so its in-memory
    state can't clobber the write;
  * rewrites ONLY the portfolio money fields (starting_capital, cash_balance,
    savings, realized/daily pnl, fees, equity_high_water); positions AND every
    other section (ML governor, open orders, history) are preserved via the
    checksummed StateStore.write_raw;
  * does not relaunch — the supervisor / session-start hook brings the runner
    back on the reset snapshot (or run `python runner.py`).

Learning artifacts (signal_history.csv, meta_model.json, imported bundles) live
in separate files and are never touched.

    python scripts/reset_paper_capital.py                 # preview only
    python scripts/reset_paper_capital.py --yes           # apply (uses config)
    python scripts/reset_paper_capital.py --yes --capital 10000
"""
import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.persistence import StateStore  # noqa: E402

_MONEY_ZERO = ("savings_balance", "realized_pnl_total", "daily_realized_pnl",
               "fees_paid_total")


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
    # positions (pf["positions"]) intentionally left as-is
    data["portfolio"] = pf
    return data


def _runner_pids() -> list:
    pids = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            cmd = Path(f"/proc/{d}/cmdline").read_bytes().replace(
                b"\x00", b" ").decode(errors="ignore")
            if "runner.py" in cmd and "grep" not in cmd:
                pids.append(int(d))
        except OSError:
            pass
    return pids


def _stop_runner(timeout: float = 25.0) -> None:
    if not _runner_pids():
        return
    try:
        from core.runtime import ControlChannel
        ControlChannel().send("stop")
        print("sent 'stop' to the runner — waiting for graceful exit...")
    except Exception as e:  # noqa: BLE001
        print(f"could not send stop ({e}); will SIGTERM")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _runner_pids():
            print("runner stopped.")
            return
        time.sleep(1.0)
    for pid in _runner_pids():
        try:
            os.kill(pid, 15)
            print(f"SIGTERM {pid}")
        except OSError:
            pass
    time.sleep(2.0)


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

    _stop_runner()
    if _runner_pids():
        print("REFUSED: runner still alive after stop — aborting to avoid a "
              "clobbered write. Stop it and retry.")
        return 1
    ok = store.write_raw(reset_portfolio(snap, capital))
    if not ok:
        print("write failed — state left unchanged.")
        return 1
    chk = (store.load_raw() or {}).get("portfolio") or {}
    print(f"done: cash=${chk.get('cash_balance', 0):,.2f} "
          f"positions={len(chk.get('positions') or [])}. "
          f"Relaunch the runner (supervisor/hook will, or `python runner.py`).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
