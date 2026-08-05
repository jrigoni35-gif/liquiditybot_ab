"""
scripts/sweep.py

Parameter sweep over recorded sessions - the vectorbt role, but running
the REAL engine on REAL recorded microstructure instead of a bar-based
approximation of the logic. Every combination is a full deterministic
replay; results rank by realized PnL and land in outputs/sweeps/.

    python scripts/sweep.py --recording outputs/recordings/session_X.jsonl \\
        --grid "position_sizer.min_p_win=0.52,0.55,0.60" \\
        --grid "position_sizer.kelly_fraction=0.15,0.25" \\
        --grid "risk.stop_vol_mult=3,4,5"

Grid values are JSON-parsed (numbers stay numbers). Combos multiply -
3x2x3 = 18 replays above. Keep grids small and targeted; the honest use
of this tool is sensitivity analysis (does the edge survive a knob
moving?), not squeezing the single best backtest number out of one
session - that's curve-fitting and it will not survive contact with
the next week of market.
"""

import argparse
import csv
import itertools
import json
import logging
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import load_config  # noqa: E402
from scripts.replay import run_replay, set_dotted  # noqa: E402

log = logging.getLogger("sweep")


def parse_grid(specs: list) -> list:
    """[('a.b', [v1, v2]), ...] from repeated --grid path=v1,v2,..."""
    grid = []
    for spec in specs:
        path, raw = spec.split("=", 1)
        vals = []
        for tok in raw.split(","):
            try:
                vals.append(json.loads(tok))
            except json.JSONDecodeError:
                vals.append(tok)
        grid.append((path.strip(), vals))
    return grid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recording", required=True)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--grid", action="append", required=True,
                    metavar="path.to.key=v1,v2,...")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # keep swept dispositions/models out of the production trail: sweep
    # builds real engines via run_replay, which redirects config paths but
    # not the process-wide audit/registry singletons
    from core.audit import configure_audit
    from ml.registry import configure_registry
    tmp = Path(tempfile.gettempdir())
    configure_audit(tmp / "liqbot_sweep_audit.jsonl")
    configure_registry(tmp / "liqbot_sweep_models")

    base = load_config(args.config)
    grid = parse_grid(args.grid)
    paths = [g[0] for g in grid]
    combos = list(itertools.product(*[g[1] for g in grid]))
    log.info(f"{len(combos)} combos over {paths}")

    rows = []
    for i, combo in enumerate(combos, 1):
        cfg = json.loads(json.dumps(base))
        for path, val in zip(paths, combo):
            set_dotted(cfg, path, json.dumps(val))
        t0 = time.time()
        s = run_replay(cfg, args.recording, quiet=True)
        row = {**{p: v for p, v in zip(paths, combo)},
               "realized_pnl": s["realized_pnl"],
               "final_equity": s["final_equity"],
               "entries": s["entries_filled"], "fees": s["fees"],
               "open_at_end": s["open_positions_end"],
               "cycles": s["cycles"]}
        rows.append(row)
        log.info(f"[{i}/{len(combos)}] {dict(zip(paths, combo))} -> "
                 f"pnl={s['realized_pnl']:+.2f} entries={s['entries_filled']} "
                 f"({time.time() - t0:.1f}s)")

    rows.sort(key=lambda r: -r["realized_pnl"])
    out = Path("outputs/sweeps")
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"sweep_{int(time.time())}.csv"
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    log.info(f"results -> {dest}")
    log.info("top 5:")
    for r in rows[:5]:
        log.info(f"  {r}")
    log.info("Sensitivity check: if the top combos cluster and neighbors "
             "perform similarly, the edge is robust. If one lonely spike "
             "wins, that's noise - do not deploy it.")


if __name__ == "__main__":
    main()
