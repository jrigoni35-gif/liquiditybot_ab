"""scripts/cut12_stage.py — CUT #12: FEE-4, book the row the account actually holds (era-9).

Operator, 2026-09-08, verbatim: "Re-book now: era-8 has 2 entries and 0 closed
trips — a boundary today resets about one day of accrual, nearly free, and
era-8 then runs at the fees you actually pay. Yes do a reset".

THE FACT (three routes, all filed): the account is **Tier 5 = maker 0.15% /
taker 0.30%** — operator's Kraken-app screenshot 2026-09-08 (30-day spot
volume $69,652.65, assets on platform $822.24; vault
raw/quant/2026-09-08_kraken_fee_tier_reading.md); the venue's fee page read as
raw text 2026-09-08T20:15:29Z (core/venue_fees.py); and the app's own
next-tier distances (30,348.35 more volume / 199,178.76 more AoP), which
reproduce from the table to the cent. `binding_row(69652.65, aop_usd=822.24)`
= (15, 30). The booked 20/35 is Tier 4 — cut #10's E1 booked it on a legacy
ladder (docs/quant/2026-09-08_fee_ladder_correction.md) — and OVER-states the
round trip by 10 bps (22.2%), $0.06 per $60 ticket.

THE CASCADE, the same shape as cuts #9 and #10 (fee_correction_stage,
cut10_stage): pricing AND booking fees, the profit-taking break-even fee, and
the label's round-trip cost. Nothing else moves: universe, hedger OFF,
skimmer OFF, $60 probe floor, geometry, budget, time-stop, give-back, the
model — all exactly as cut #11 left them. The derived entry bar
(position_sizer p_bar_mode=derived) FALLS with the cost, printed below.

COHORT-RESETTING. Mints exec_era 12-<sha>; era-9 accrual starts from zero at
the runner restart. Era-8 rows (2 entries, 0 closed trips at staging) stay
citable AS era-8. Open positions carry across; their exits book at the new
fees, as at cut #10.

THE TIER ROLLS. It is granted by the best of the operator's real 30-day spot
volume and assets on platform; the bot's paper fills count toward neither.
It was Tier 3 on 08-29 and Tier 5 on 09-08. Rule: book from a FRESH reading
at the boundary that adopts it (this one), never chase it mid-era; re-read
it at every cohort readout and name the drift.

    python scripts/cut12_stage.py            # dry run: show, sweep, write nothing
    python scripts/cut12_stage.py --apply    # operator act
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

# The operator's reading, as staged. Re-derive at the boundary; never recall.
READING = {"tier": 5, "volume_30d_usd": 69_652.65, "aop_usd": 822.24,
           "read": "2026-09-08 17:51 device time (Kraken app)"}

# (dotted key, expected FROM, TO). FROM is checked EXACTLY; any drift refuses.
EDITS = [
    ("pretrade.maker_fee_bps",        20.0, 15.0),
    ("pretrade.taker_fee_bps",        35.0, 30.0),
    ("order_manager.maker_fee_bps",   20.0, 15.0),
    ("order_manager.taker_fee_bps",   35.0, 30.0),
    ("profit_taking.est_fee_bps",     35,   30),
    ("ml.label_round_trip_cost_pct",  0.55, 0.45),      # = (15 + 30) / 100
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


def drifted(cfg: dict) -> list:
    """Keys whose current value is not the staged FROM value."""
    return [(k, frm, _get(cfg, k)) for k, frm, _to in EDITS if _get(cfg, k) != frm]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="perform the cut (operator act)")
    ns = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    print("CUT #12 - FEE-4, the row the account holds  [%s]"
          % ("APPLY" if ns.apply else "DRY RUN"))
    print("=" * 70)
    sys.path.insert(0, str(ROOT))
    from core.venue_fees import binding_row, is_a_published_row
    row = binding_row(READING["volume_30d_usd"], aop_usd=READING["aop_usd"])
    print("  reading: tier %d, 30d spot $%s, AoP $%s (%s)"
          % (READING["tier"], f"{READING['volume_30d_usd']:,.2f}",
             f"{READING['aop_usd']:,.2f}", READING["read"]))
    print("  core.venue_fees.binding_row -> %s" % (row,))
    to_m = [to for k, _f, to in EDITS if k == "pretrade.maker_fee_bps"][0]
    to_t = [to for k, _f, to in EDITS if k == "pretrade.taker_fee_bps"][0]
    if row != (to_m, to_t) or not is_a_published_row(to_m, to_t):
        print("\nREFUSING: the staged TO row %s/%s is not what the schedule "
              "binds at the reading (%s). Re-derive; do not force."
              % (to_m, to_t, row))
        return 2
    # THE CASCADE IS ONE NUMBER. A half-applied fee stage (fees moved, label
    # cost not) is the hazard risk/profit_tiers.py names; the guard only
    # WARNs for it. Refuse here unless every staged TO agrees: order_manager
    # == pretrade, est_fee_bps == taker, label cost == (maker + taker)/100.
    to = {k: t for k, _f, t in EDITS}
    coherent = (to["order_manager.maker_fee_bps"] == to_m
                and to["order_manager.taker_fee_bps"] == to_t
                and float(to["profit_taking.est_fee_bps"]) == to_t
                and abs(to["ml.label_round_trip_cost_pct"] - (to_m + to_t) / 100.0) < 1e-9)
    if not coherent:
        print("\nREFUSING: the staged cascade is incoherent (%s). The four "
              "fee-derived keys move together or not at all." % to)
        return 2
    print()
    drift = drifted(cfg)
    for key, frm, to in EDITS:
        cur = _get(cfg, key)
        ok = cur == frm
        print("  %-34s %-10s -> %-8s %s"
              % (key, str(frm), str(to), "" if ok else "  ** DRIFTED **"))
    if drift:
        print("\nREFUSING: %d key(s) do not match the staged FROM values."
              % len(drift))
        print("The world moved since staging. Re-derive; do not force.")
        return 2

    cand = copy.deepcopy(cfg)
    for key, _frm, to in EDITS:
        _set(cand, key, to)
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
        print("execution-era cut #12 and restarts accrual as era-9. After")
        print("--apply, mint EXEC_ERA (core/fill_ledger.py) to 12-<sha of the")
        print("decision-record commit>, run the DoD, merge, push, restart.")
        return 0

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    backup = CONFIG.with_name(f"config.json.pre-cut12-{stamp}")
    # RESTORE HAZARD (same as cuts #8-#11): restoring this backup by hand
    # does NOT revert the era - EXEC_ERA is a code constant in the same
    # commit. Restoring is itself a cohort-resetting act. gitignored.
    shutil.copy2(CONFIG, backup)
    CONFIG.write_text(json.dumps(cand, indent=2) + "\n", encoding="utf-8")
    print("\nAPPLIED. backup: %s" % backup.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
