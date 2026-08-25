"""scripts/boundary5_stage.py - the boundary-#5 cut, staged and inert.

WHAT THIS IS. The fee-truth package (owed 88): venue-true Tier 1 constants
into pricing, booking, the BE floor, the label cost, plus the one coherence
edit (`ml.exploration.p_win` 0.70 -> 0.85) that clears the net-Kelly FATAL
the guard correctly raises at true cost. Full rationale, measured
consequences and the geometry decision: docs/quant/
2026-08-25_boundary5_adjudication.md - read it BEFORE --apply.

WHY A STAGER AND NOT AN EDIT. Fee booking is COHORT-RESETTING (CLAUDE.md):
applying this mints execution-era boundary #5 and restarts era-4 accrual
from zero. The gate is 2 closes from its pre-registered n=50 readout, and
owed-88's adjudication is BATCH AT READOUT - so the change must be READY
without being APPLIED. Dry-run is the default; --apply is the cut and is an
OPERATOR act, performed after the readout prints, never by an unattended
session (standing rule: never touch trading config without explicit
sign-off).

EVERY EDIT IS VERIFIED TWICE AT APPLY TIME:
  1. the current value must be the expected FROM (a drifted config means
     this package was staged against a different world - refuse, re-derive);
  2. core.config_guard.validate() must report ZERO FATALs on the result
     (measured at staging: true fees alone FATAL the exploration lane at
     breakeven 0.8335; with p_win 0.85 the sweep is clean).
A backup of config.json is written beside it before any write.

    python scripts/boundary5_stage.py            # dry-run: show the diff
    python scripts/boundary5_stage.py --apply    # the cut (operator only)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.json"

# (dotted key, expected FROM, TO). FROM is checked exactly - a mismatch means
# the world moved since staging and the package must be re-derived, not
# forced. Values per first-party Kraken Tier 1 (cost_attribution.py:82-90)
# and the guard sweep of 2026-08-25.
EDITS = [
    ("pretrade.maker_fee_bps",        25.0, 40.0),
    ("pretrade.taker_fee_bps",        40.0, 80.0),
    ("order_manager.maker_fee_bps",   25.0, 40.0),
    ("order_manager.taker_fee_bps",   40.0, 80.0),
    ("profit_taking.est_fee_bps",     40,   80),
    ("ml.label_round_trip_cost_pct",  0.5,  1.2),
    ("ml.exploration.p_win",          0.7,  0.85),
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="perform the cut (operator act, post-readout)")
    ns = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

    print("BOUNDARY #5 - fee truth (owed 88)  [%s]"
          % ("APPLY" if ns.apply else "DRY RUN"))
    print("=" * 66)
    drift = []
    for key, frm, to in EDITS:
        cur = _get(cfg, key)
        ok = cur == frm
        if not ok:
            drift.append((key, frm, cur))
        print("  %-34s %-8s -> %-8s current=%s %s"
              % (key, frm, to, cur, "" if ok else "  ** DRIFTED **"))
    if drift:
        print("")
        print("REFUSING: %d key(s) do not match the staged FROM values."
              % len(drift))
        print("The world moved since this package was staged (another cut, a")
        print("hand edit). Re-derive the package; do not force it.")
        return 2

    # candidate + guard sweep, BEFORE any write
    import copy
    cand = copy.deepcopy(cfg)
    for key, _frm, to in EDITS:
        _set(cand, key, to)
    sys.path.insert(0, str(ROOT))
    from core.config_guard import validate
    findings = validate(cand)
    fatals = [m for s, m in findings if s == "FATAL"]
    warns = [m for s, m in findings if s == "WARN"]
    print("")
    print("guard sweep on the candidate: %d FATAL, %d WARN"
          % (len(fatals), len(warns)))
    for m in fatals:
        print("  FATAL: %s" % m[:150])
    if fatals:
        print("REFUSING: the candidate does not pass the guard.")
        return 2
    for m in warns[:4]:
        print("  warn : %s" % m[:130])

    if not ns.apply:
        print("")
        print("Dry run - nothing written. The cut is COHORT-RESETTING: it")
        print("mints execution-era boundary #5 and restarts era-4 accrual.")
        print("Apply only after the n=50 readout, per owed-88 (BATCH AT")
        print("READOUT). docs/quant/2026-08-25_boundary5_adjudication.md")
        print("carries the full decision record.")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = CONFIG.with_name(f"config.json.pre-boundary5-{stamp}")
    shutil.copy2(CONFIG, backup)
    CONFIG.write_text(json.dumps(cand, indent=2) + "\n", encoding="utf-8")
    print("")
    print("APPLIED. backup: %s" % backup.name)
    print("Restart the runner to take effect; the deploy stamp mints the")
    print("boundary. Era-4 accrual RESTARTS at zero from the restart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
