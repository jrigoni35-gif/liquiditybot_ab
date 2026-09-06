"""scripts/cut10_stage.py — CUT #10: the verified-defects boundary (era-7).

Stages the config half of execution-era cut #10 exactly the way cut #9 was
staged (scripts/fee_correction_stage.py): every edit names its expected FROM
value, the candidate config is swept by core.config_guard.validate before a
byte is written, and --apply is an operator act that backs up config.json
first. Refuses on any drift. Dry run by default.

WHAT THIS CUT IS. Seven CONFIRMED defects verified against the running system
on 2026-09-05 (docs/quant/2026-09-05_verified_findings_batch.md, B1-B6 plus
the S5 constant) sit behind the accrual moratorium's cohort-resetting fences
and were approved by the operator on 2026-09-06 as ONE bundled boundary. The
code half lives in the same commit; this script carries the two config edits
that belong to it, plus the fee-booking correction E1 surfaced the same day.

  B6  ml.max_open_candidates 1200 -> 1800
      Little's-law demand at the re-measured 43.7/h peak x 36h horizon is
      1574 slots; 1200 saturates and the newest-pop eviction refuses labeling
      to exactly the busy-hour signals. ~15% headroom over demand.

  E1  fee booking 22/38 -> 20/35 (the binding row at $17,482 / 30d)
      scripts/fee_drift_report.py --volume-30d 17482, 2026-09-06T21:19Z:
      "config books 22/38, which is NOT a row in the venue's schedule ...
      binding tier is 20/35 - OVER-stating the round trip by 5 bps (9.1%)".
      22/38 was cut #9's reading of a screenshot; 20/35 is the published row
      the account actually binds to. Cascade, same shape as cut #9:
        pretrade / order_manager maker,taker   22/38 -> 20/35
        profit_taking.est_fee_bps (taker)       38 -> 35
        ml.label_round_trip_cost_pct            0.60 -> 0.55  (= (20+35)/100)
      Derived entry bar (risk/position_sizer p_bar_mode=derived, same helper
      cut #9 used): 0.6772 -> 0.6642. allow_sub_floor_fees STAYS true (20/35
      is below the 25/40 zero-volume tripwire, and it is a genuine published
      discount row - which is what that flag exists for).

COHORT-RESETTING. Applying this and the code half mints exec_era 10-<sha> and
era-7 accrual restarts from zero at the runner restart. Era-6 rows stay
citable AS era-6 (accrued at 22/38 with the B1-B6 defects live); nothing may
be pooled across this cut.

    python scripts/cut10_stage.py            # dry run: show, sweep, write nothing
    python scripts/cut10_stage.py --apply    # operator act
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

# (dotted key, expected FROM, TO). FROM is checked EXACTLY; any drift refuses.
EDITS = [
    ("ml.max_open_candidates",        1200, 1800),
    ("pretrade.maker_fee_bps",        22.0, 20.0),
    ("pretrade.taker_fee_bps",        38.0, 35.0),
    ("order_manager.maker_fee_bps",   22.0, 20.0),
    ("order_manager.taker_fee_bps",   38.0, 35.0),
    ("profit_taking.est_fee_bps",     38,   35),
    ("ml.label_round_trip_cost_pct",  0.6,  0.55),
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
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="perform the cut (operator act)")
    ns = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    print("CUT #10 - verified-defects boundary + E1 fee correction  [%s]"
          % ("APPLY" if ns.apply else "DRY RUN"))
    print("=" * 70)
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
        print("  FATAL: %s" % m[:160])
    if fatals:
        print("REFUSING: the candidate does not pass the guard.")
        return 2
    for m in warns[:8]:
        print("  warn : %s" % m[:140])

    # the one derived number the operator reads first
    try:
        from risk.position_sizer import PositionSizer
        def _bar(c):
            ps = PositionSizer(c["position_sizer"], c["profit_taking"],
                               c.get("risk", {}), pretrade_cfg=c["pretrade"],
                               capital_cfg=c.get("capital_management"))
            return ps.p_bar_base
        print("\nderived entry bar p_bar_base: %.4f -> %.4f"
              % (_bar(cfg), _bar(cand)))
    except Exception as e:                       # noqa: BLE001 - report only
        print("\n(derived entry bar not computed: %r)" % (e,))

    if not ns.apply:
        print("\nDry run - nothing written. COHORT-RESETTING: applying mints")
        print("execution-era cut #10 and restarts accrual as era-7. After")
        print("--apply, mint EXEC_ERA (core/fill_ledger.py) to 10-<sha of the")
        print("decision-record commit>, run the DoD, commit, push.")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = CONFIG.with_name(f"config.json.pre-cut10-{stamp}")
    # RESTORE HAZARD (same as cuts #8/#9): restoring this backup by hand does
    # NOT revert the era - EXEC_ERA is a code constant, and the code half of
    # this cut is in the same commit. Restoring is itself a cohort-resetting
    # act. gitignored (config.json.pre-*).
    shutil.copy2(CONFIG, backup)
    CONFIG.write_text(json.dumps(cand, indent=2) + "\n", encoding="utf-8")
    print("\nAPPLIED. backup: %s" % backup.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
