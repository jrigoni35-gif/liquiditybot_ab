"""scripts/fee_correction_stage.py - cut #9, the Tier-3 fee correction, staged.

WHAT THIS IS. Cut #8 (boundary5_stage.py) booked venue-true Kraken Tier-1
40/80 bps as "conservative", assuming a zero-volume account. The operator's
Kraken app (2026-08-29) proved the account is Tier 3 = maker 0.22% / taker
0.38% = 22/38 bps, on $17,482 30-day spot volume: cut #8 OVER-stated fees ~2x
(the-method #1 recurrence - a struck fee schedule asserting itself as truth;
booked median ~65bps and OM-080 n=0 were the unheeded warnings). This cut
corrects the booking to the real tier. Decision record + re-derivation:
docs/quant/2026-08-29_fee_tier_correction_adjudication.md. Operator ARM
2026-08-30: "fee correction only", dry_run STAYS true (paper), tail-control
(ALGO-5) EXCLUDED (its net-CI spans zero on fills alone).

WHY A STAGER, NOT AN EDIT. Fee booking is COHORT-RESETTING (CLAUDE.md):
applying this mints execution-era cut #9 and restarts accrual from zero. The
stager is the auditable, drift-checked, guard-verified record of exactly what
changed - the same discipline cut #8 used.

allow_sub_floor_fees -> true is REQUIRED AND CORRECT: 22/38 sits below
config_guard's KRAKEN_SPOT_FLOOR (40/80, the venue Tier-1 tripwire), and the
account genuinely HAS a volume-tier discount (Tier 3) - which is exactly what
that flag is for ("set your real tier, or allow_sub_floor_fees if you
genuinely have volume discounts"). The FLOOR itself stays 40/80 as the
understated-fee tripwire. The entry bar is DERIVED (not a config knob): at
22/38 the sizer recomputes it 0.8335 -> ~0.6772 automatically. ml.exploration
.p_win is LEFT at 0.85 (coherent at the lower cost - the guard sweep confirms
no FATAL); reverting it is a separate exploration decision, out of this cut.

EVERY EDIT IS VERIFIED TWICE AT APPLY TIME (as cut #8):
  1. current value must equal the expected FROM (a drifted config = staged
     against a different world -> refuse, re-derive);
  2. core.config_guard.validate() must report ZERO FATALs on the result.
A backup of config.json is written before any write. AFTER --apply, mint the
EXEC_ERA code constant (core/fill_ledger.py) to "9-..." and restart the runner.

    python scripts/fee_correction_stage.py            # dry-run: show the diff
    python scripts/fee_correction_stage.py --apply    # the cut (operator only)
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

# (dotted key, expected FROM, TO). FROM is checked exactly. allow_sub_floor_fees
# is absent today (None) -> True. Real Tier-3 per the operator screenshot.
EDITS = [
    ("pretrade.maker_fee_bps",        40.0, 22.0),
    ("pretrade.taker_fee_bps",        80.0, 38.0),
    ("order_manager.maker_fee_bps",   40.0, 22.0),
    ("order_manager.taker_fee_bps",   80.0, 38.0),
    ("profit_taking.est_fee_bps",     80,   38),
    ("ml.label_round_trip_cost_pct",  1.2,  0.6),
    ("pretrade.allow_sub_floor_fees", None, True),
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
                    help="perform the cut (operator act)")
    ns = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

    print("CUT #9 - Tier-3 fee correction (40/80 -> 22/38)  [%s]"
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
        print("\nREFUSING: %d key(s) do not match the staged FROM values."
              % len(drift))
        print("The world moved since staging. Re-derive; do not force.")
        return 2

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
        print("  FATAL: %s" % m[:150])
    if fatals:
        print("REFUSING: the candidate does not pass the guard.")
        return 2
    for m in warns[:6]:
        print("  warn : %s" % m[:130])

    if not ns.apply:
        print("\nDry run - nothing written. COHORT-RESETTING: applying mints")
        print("execution-era cut #9 and restarts accrual. After --apply, mint")
        print("EXEC_ERA (core/fill_ledger.py) to 9-... and restart the runner.")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = CONFIG.with_name(f"config.json.pre-cut9-{stamp}")
    # RESTORE HAZARD (same as cut #8): restoring this backup by hand does NOT
    # revert the era - EXEC_ERA is a code constant. Restoring is itself a
    # cohort-resetting act (operator adjudication + an EXEC_ERA decision).
    # gitignored (config.json.pre-*); keep out of history.
    shutil.copy2(CONFIG, backup)
    CONFIG.write_text(json.dumps(cand, indent=2) + "\n", encoding="utf-8")
    print("\nAPPLIED. backup: %s" % backup.name)
    print("NEXT: mint EXEC_ERA -> 9-... (core/fill_ledger.py), run the DoD,")
    print("restart the runner. Accrual RESTARTS at zero from the restart.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
