"""scripts/fee_reprice.py - what the era-4 verdict reads at TRUE venue fees.

THE PROBLEM, stated exactly.

The pre-registered gate (scripts/cohort_eval.py) tests the RIGHT null: it asks
whether NET edge exceeds cost, not whether gross edge is nonzero. But the cost
it subtracts is whatever `fees_delta_usd` the engine booked, and the engine
books the config constants 25/40 bps while Kraken spot Tier 1 - this account's
tier, verified by first-party fetch on 2026-08-22 and recorded at
scripts/cost_attribution.py:82-90 - is 40/80. The booked cost is ~0.54x the
真 cost. The gate's shape is right; its cost input is understated ~1.85x.

Indicatively (assumed leg mixes over the cohort's gross +72.86 bps): booked
lands net +0.079% -> CONTINUE, true Tier 1 lands net -0.471% ->
INCONCLUSIVE. THE FEE CONSTANT MOVES THE VERDICT. This tool replaces that
indicative arithmetic with the exact repriced figure.

WHY THIS DOES NOT RESET THE COHORT - the whole point of doing it this way.

CLAUDE.md lists FEE BOOKING among the COHORT-RESETTING changes: editing the
config constants mints execution-era boundary #5 and restarts accrual from
zero, discarding every trade accrued so far. It would also trip a
config_guard FATAL (ml.exploration.p_win=0.700 sits below the net-Kelly
breakeven at true fees), so the bot would refuse to start.

None of that is necessary to learn the answer. This tool changes NOTHING the
bot does. It rewrites `fees_delta_usd` in an in-memory COPY of the fills and
hands that copy to cohort_eval's OWN era4_trips(). Same reconstruction code,
same pre-registered boundaries, exactly ONE input varied. Report-only, SAFE
class, no reset, no config change.

The live BOOKING stays wrong until the operator adjudicates boundary #5 -
which the vault already batched ("owed 88: BATCH AT READOUT with ALGO-5 as
one boundary #5"). What changes today is only that the readout can be seen
through the correct cost before n=50 arrives, instead of after.

REPRODUCE BEFORE YOU REPRICE. Feeding the ORIGINAL file through the same path
must return cohort_eval's own numbers. If it does not, this tool is wrong and
its repriced figure is worthless - so that check runs first and refuses on
mismatch, rather than printing a number nobody can trust.

    python scripts/fee_reprice.py [--fills PATH] [--maker-bps F] [--taker-bps F]
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import statistics as st
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# First-party Kraken spot Tier 1, fetched 2026-08-22. NOT the config values -
# the config books 25/40, which is the thing under test here.
TRUE_MAKER_BPS = 40.0
TRUE_TAKER_BPS = 80.0


def _load_cohort_eval():
    spec = importlib.util.spec_from_file_location(
        "cohort_eval", ROOT / "scripts" / "cohort_eval.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load cohort_eval")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cohort_eval"] = mod
    spec.loader.exec_module(mod)
    return mod


def _f(row: dict, key: str) -> float:
    try:
        return float(row.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def reprice_rows(rows: list[dict], maker_bps: float,
                 taker_bps: float) -> tuple[list[dict], dict]:
    """Rewrite fees_delta_usd at venue-true rates, per fill, using that
    fill's OWN post_only flag. No assumed leg mix anywhere."""
    out, booked_total, true_total, mk, tk = [], 0.0, 0.0, 0, 0
    for r in rows:
        r2 = dict(r)
        notional = abs(_f(r, "fill_size") * _f(r, "fill_price"))
        is_maker = str(r.get("post_only", "0")).strip() in ("1", "true", "True")
        bps = maker_bps if is_maker else taker_bps
        mk += int(is_maker)
        tk += int(not is_maker)
        booked_total += _f(r, "fees_delta_usd")
        true_fee = notional * bps / 1e4
        true_total += true_fee
        r2["fees_delta_usd"] = f"{true_fee:.6f}"
        out.append(r2)
    return out, {"booked_fees_usd": round(booked_total, 4),
                 "true_fees_usd": round(true_total, 4),
                 "ratio": (round(true_total / booked_total, 4)
                           if booked_total else float("nan")),
                 "maker_fills": mk, "taker_fills": tk}


def _write_tmp(rows: list[dict], fieldnames: list[str]) -> Path:
    fh = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv",
                                     delete=False, encoding="utf-8")
    w = csv.DictWriter(fh, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    fh.close()
    return Path(fh.name)


def _summ(ce, trips: list) -> dict:
    net = [t["net_pct"] for t in trips]
    gross = [t["gross_pct"] for t in trips]
    n = len(trips)
    if not n:
        return {"n": 0}
    return {"n": n,
            "mean_net_pct": st.fmean(net), "median_net_pct": st.median(net),
            "mean_gross_pct": st.fmean(gross),
            "wins": sum(1 for x in net if x > 0)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fills", default=str(ROOT / "outputs" / "fills.csv"))
    ap.add_argument("--maker-bps", type=float, default=TRUE_MAKER_BPS)
    ap.add_argument("--taker-bps", type=float, default=TRUE_TAKER_BPS)
    ns = ap.parse_args()

    ce = _load_cohort_eval()
    src = Path(ns.fills)
    try:
        with src.open(newline="", encoding="utf-8") as fh:
            rdr = csv.DictReader(fh)
            rows = list(rdr)
            fields = list(rdr.fieldnames or [])
    except OSError as e:
        print("cannot read %s: %s" % (src, e))
        return 2
    if not rows:
        print("no fills - NOT a clean result, the check could not run")
        return 2

    # --- STEP 1: reproduce. Same path, ORIGINAL fees. --------------------
    base_trips = ce.era4_trips(str(src))
    round_trip = _write_tmp(rows, fields)
    echo_trips = ce.era4_trips(str(round_trip))
    round_trip.unlink(missing_ok=True)
    if len(base_trips) != len(echo_trips):
        print("REPRODUCTION FAILED: %d trips direct vs %d through the copy."
              % (len(base_trips), len(echo_trips)))
        print("The rewrite path is lossy; the repriced figure would be")
        print("meaningless, so it is NOT printed.")
        return 2
    b, e = _summ(ce, base_trips), _summ(ce, echo_trips)
    drift = abs(b.get("mean_net_pct", 0.0) - e.get("mean_net_pct", 0.0))
    if drift > 1e-9:
        print("REPRODUCTION FAILED: mean net drifted %.12f through a "
              "no-op rewrite." % drift)
        return 2

    # --- STEP 2: reprice. ONE input varied. ------------------------------
    rep_rows, fee = reprice_rows(rows, ns.maker_bps, ns.taker_bps)
    rep_path = _write_tmp(rep_rows, fields)
    rep_trips = ce.era4_trips(str(rep_path))
    rep_path.unlink(missing_ok=True)
    r = _summ(ce, rep_trips)

    print("ERA-4 COHORT REPRICED AT VENUE-TRUE FEES")
    print("=" * 72)
    print("reproduction check: %d trips, mean net identical through a "
          "no-op rewrite - OK" % b["n"])
    print("")
    print("fills: %d maker + %d taker" % (fee["maker_fills"], fee["taker_fills"]))
    print("fees:  booked $%.2f -> true $%.2f  (x%.3f)"
          % (fee["booked_fees_usd"], fee["true_fees_usd"], fee["ratio"]))
    print("")
    print("%-22s %10s %12s %12s" % ("", "n", "mean net %", "median net %"))
    print("-" * 72)
    print("%-22s %10d %12.4f %12.4f"
          % ("BOOKED (25/40)", b["n"], b["mean_net_pct"], b["median_net_pct"]))
    print("%-22s %10d %12.4f %12.4f"
          % ("TRUE (%g/%g)" % (ns.maker_bps, ns.taker_bps), r["n"],
             r["mean_net_pct"], r["median_net_pct"]))
    print("-" * 72)
    print("gross (unchanged by fees): %.4f%%" % b["mean_gross_pct"])
    print("")
    stop, cont = ce.STOP_IF_NET_PCT_BELOW, ce.CONTINUE_IF_NET_PCT_ABOVE
    print("PRE-REGISTERED BANDS: STOP < %.1f%% ... %.1f%% < CONTINUE"
          % (stop, cont))
    for label, m in (("booked", b["mean_net_pct"]),
                     ("true  ", r["mean_net_pct"])):
        band = ("CONTINUE" if m > cont
                else "STOP" if m < stop else "INCONCLUSIVE")
        print("  %s  mean net %+.4f%%  ->  %s" % (label, m, band))
    if b["n"] < ce.MIN_COHORT_N:
        print("")
        print("NO VERDICT EITHER WAY: n=%d is below the pre-registered %d."
              % (b["n"], ce.MIN_COHORT_N))
        print("Both rows above are ACCRUING numbers, not verdicts. The")
        print("registration is the law; this tool only shows which cost the")
        print("law will be read through.")
    print("")
    print("WHAT THIS DOES NOT DO: it does not change what the bot books, and")
    print("the live pretrade EV gate still admits trades priced at 25/40.")
    print("Correcting THAT is fee booking - cohort-resetting, boundary #5,")
    print("operator adjudication, already batched as owed item 88.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
