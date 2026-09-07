"""scripts/cut11_stage.py — CUT #11: the COMMIT configuration (era-8).

Operator objective, verbatim (2026-09-07): "No matter whether it's negative
or positive. Make it do things that would make it have to either end with a
positive or negative PnL." Three periods of measurement read zero-shaped: a
coin-flip model, hedge legs that cancel the bet by construction, and $18
probe tickets whose outcomes are cents of noise. This cut removes the
zero-makers that are NOT the model and leaves everything else exactly as it
was, so the next 50-100 closed trips answer one question: with the bot
COMMITTED, does the sign come out positive or negative?

  1. Universe -> the four majors. Alts are the measured loss channel: -$3.67
     on 27 trips (2026-08-26 dive), 15 of 22 era-9/10 alt exits are stop-
     losses vs 1 of 5 on majors; BTC/ETH/LINK +$4.56 on 18. LINK moves from
     skimmer promotion to core (offline pair meta already present).
  2. Skimmer OFF. Without this the runner re-widens the universe from
     outputs/skimmer_active.json at every dry-run boot (runner.py:105-121).
  3. Hedger OFF. A hedge leg opens against the bet and cancels its outcome -
     a hedged bet cannot end clearly positive or negative. Hedge legs are 159
     of 1,245 fills and 40% of ALL fees ($158 of $393), at taker rates. NO
     open position is a hedge at staging (is_hedge False x5); this script
     REFUSES to apply if one appears, because execution/hedging.py:171 returns
     no actions when disabled - including unwinds - and a stranded hedge leg
     is exempt from profit tiers (hedging.py:19).
  4. Probe ticket floor $15 -> $60. main.py:1066 clamps exploration
     size_scale to [0.01, 1.0], so 1.0 (shipped) is already the MAXIMUM;
     probes sit at max(min_ticket_usd, min_order x explore_floor_mult) =
     $18 (position_sizer.py:595). x4 on the floor makes each outcome dollars
     instead of cents; the 25%-of-capital cap ($200), Kelly cap, CVaR/heat
     stack and the manip gate still bound every ticket.

UNTOUCHED, on purpose: exploration budget (5 tokens/day - keeps ~4 fills/day
so n=50 lands in ~2 weeks), stop/TP geometry (the label-era name encodes the
horizon only, so a geometry change would mix two barrier widths under one
era - deferred with that reason), fees 20/35, the model (frozen, and no
skill to tune), give-back and time-stop (a 40h time-out closes at market, a
real +/- outcome, not a scratch).

COHORT-RESETTING. Mints exec_era 11-<sha>; era-8 accrual starts from zero at
the runner restart. Era-7 rows (2 closed trips at staging) stay citable AS
era-7. Under H0 (coin flip) the EXPECTED net is -fee/trip ~ -$0.33 at a $60
ticket, ~ -$1.3/day - LARGER in dollars than today. That is the price of a
decisive answer and the operator accepted it explicitly.

    python scripts/cut11_stage.py            # dry run: show, sweep, write nothing
    python scripts/cut11_stage.py --apply    # operator act
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.json"
STATE = ROOT / "outputs" / "state.json"

MAJORS = ["PAXG/USD", "ETH/USD", "BTC/USD", "LINK/USD"]

# (dotted key, expected FROM, TO). FROM is checked EXACTLY; any drift refuses.
EDITS = [
    ("exchanges.kraken.trading_pairs",
     ["PAXG/USD", "ETH/USD", "BTC/USD", "SUI/USD", "ARB/USD", "MINA/USD",
      "FLOW/USD"], MAJORS),
    ("skimmer.enabled",              True,  False),
    ("hedging.enabled",              True,  False),
    ("position_sizer.min_ticket_usd", 15,   60),
]


def _get(cfg: dict, dotted: str):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _set(cfg: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    cur = cfg
    for part in parts[:-1]:
        cur = cur[part]
    cur[parts[-1]] = value


def open_hedges(state_path: Path = STATE) -> list:
    """Symbols of open positions tagged is_hedge. Disabling the hedger
    strands these (no unwind actions when disabled), so the stage refuses
    while any exist. Missing/unreadable state -> [] (nothing to strand)."""
    try:
        st = json.loads(Path(state_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    ps = st.get("portfolio", {}).get("positions", {}) or st.get("positions", {})
    ps = list(ps.values()) if isinstance(ps, dict) else list(ps or [])
    return [str(p.get("symbol")) for p in ps if p.get("is_hedge")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="perform the cut (operator act)")
    ns = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    print("CUT #11 - the COMMIT configuration  [%s]"
          % ("APPLY" if ns.apply else "DRY RUN"))
    print("=" * 70)
    drift = []
    for key, frm, to in EDITS:
        cur = _get(cfg, key)
        ok = cur == frm
        if not ok:
            drift.append((key, frm, cur))
        print("  %-34s %-40s -> %s %s"
              % (key, str(frm)[:40], str(to)[:34], "" if ok else "  ** DRIFTED **"))
    if drift:
        print("\nREFUSING: %d key(s) do not match the staged FROM values."
              % len(drift))
        print("The world moved since staging. Re-derive; do not force.")
        return 2

    stranded = open_hedges()
    if stranded:
        print(f"\nREFUSING: open hedge position(s) {stranded} - disabling the "
              f"hedger would strand them (no unwind actions when disabled). "
              f"Let them unwind first, then re-run.")
        return 2
    print("  open hedge positions: none (safe to disable the hedger)")

    cand = copy.deepcopy(cfg)
    for key, _frm, to in EDITS:
        _set(cand, key, to)
    sys.path.insert(0, str(ROOT))
    from core.config_guard import validate
    findings = validate(cand)
    fatals = [m for s, m in findings if s == "FATAL"]
    warns = [m for s, m in findings if s == "WARN"]
    print("\nguard sweep on the candidate: %d FATAL, %d WARN"
          % (len(fatals), len(warns)))
    for m in fatals:
        print("  FATAL: %s" % m[:160])
    if fatals:
        print("REFUSING: the candidate does not pass the guard.")
        return 2
    for m in warns[:8]:
        print("  warn : %s" % m[:140])

    if not ns.apply:
        print("\nDry run - nothing written. COHORT-RESETTING: applying mints")
        print("execution-era cut #11 and restarts accrual as era-8. After")
        print("--apply, mint EXEC_ERA (core/fill_ledger.py) to 11-<sha of the")
        print("decision-record commit>, run the DoD, commit, push, restart.")
        return 0

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    backup = CONFIG.with_name(f"config.json.pre-cut11-{stamp}")
    # RESTORE HAZARD (same as cuts #8-#10): restoring this backup by hand
    # does NOT revert the era - EXEC_ERA is a code constant in the same
    # commit. Restoring is itself a cohort-resetting act. gitignored.
    shutil.copy2(CONFIG, backup)
    CONFIG.write_text(json.dumps(cand, indent=2) + "\n", encoding="utf-8")
    print("\nAPPLIED. backup: %s" % backup.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
