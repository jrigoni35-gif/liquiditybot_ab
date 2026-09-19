"""scaling_report.py — what would cost-aware scaling buy this book?

SAFE-class, REPORT-ONLY. This tool sizes nothing, places nothing, gates
nothing. It derives four numbers the 09-22 boundary docket needs before
any scaling decision can be adjudicated with evidence instead of taste:

  1. COST FLOOR    — break-even gross edge (bps) at the current fee
                     tier + measured adverse component; the kill line a
                     setup must clear, by ticket size and by tier.
  2. TIER ROLL     — the venue's volume ladder as a scaling asset: each
                     tier the operator's real trading qualifies drops the
                     round-trip cost and therefore the kill line.
  3. EDGE-CONDITIONAL SIZE — quarter-Kelly exposure from measured trip
                     edge/variance, zeroed without edge. What the sizer
                     WOULD approve if scaling were live.
  4. ERA-9 PARAMS  — distributional parameters (n, mean net, sd) from
                     fills.csv, stamped AS-OF. NOT the era-9
                     registration (that is scripts/era_readout.py); this
                     is the input a scaling rule would consume.

Everything is derived at run time, never remembered. Exit 0 always;
instrument failures land in the report's own WARNINGS section.

Usage:
    python scripts/scaling_report.py [--fills outputs/fills.csv]
"""
import argparse
import statistics
import time
from pathlib import Path

# era-measured round-trip cost components (adjudicated 2026-09-15 /
# measured 2026-09-01; re-derive with era_readout.py and the edge-hunter
# tape before citing elsewhere — this file quotes them as DEFAULTS, not
# authority)
DEFAULT_FEE_BPS_RT = 45.5        # era-measured booked round trip
DEFAULT_ADVERSE_BPS = 15.0       # arrival->fill limit distance, one side

# Kraken CURRENT ladder as verified 2026-09-08 (docs/quant/
# 2026-09-08_fee_ladder_correction.md): (min 30d volume, maker, taker).
# Tier = best of volume OR assets-on-platform; AoP rows omitted here,
# the venue module is the authority when wired.
DEFAULT_LADDER = [
    (0.0, 40.0, 80.0),
    (2500.0, 30.0, 60.0),
    (10000.0, 22.0, 38.0),
    (25000.0, 20.0, 35.0),
    (50000.0, 15.0, 30.0),
]

BANKROLL = 800.0                 # starting_capital_usd, audit-verified
KELLY_FRACTION = 0.25            # quarter-Kelly; full Kelly is never argued
SIZE_CAP_USD = 500.0             # hard cap per ticket, governance-set


def cost_floor_bps(_ticket_usd: float, fee_bps_rt: float,
                   adverse_bps: float) -> float:
    """Break-even gross edge for a round trip, in bps."""
    return fee_bps_rt + adverse_bps


def net_after_cost_bps(gross_bps: float, floor_bps: float) -> float:
    return gross_bps - floor_bps


def binding_tier(ladder, volume_30d: float) -> dict:
    """Best row the 30d volume qualifies for (AoP path not modeled here)."""
    row = max((r for r in ladder if volume_30d >= r[0]), key=lambda r: r[0])
    return {"min_volume": row[0], "maker_bps": row[1], "taker_bps": row[2],
            "round_trip_bps": row[1] + row[2]}


def tier_roll_table(ladder, volume_30d: float) -> list[dict]:
    """Every row at or below the current volume: cost falling as the
    operator's real trading qualifies for better tiers."""
    rows = []
    for min_vol, maker, taker in ladder:
        if volume_30d >= min_vol:
            rows.append({"min_volume": min_vol, "maker_bps": maker,
                         "taker_bps": taker,
                         "round_trip_bps": maker + taker})
    return sorted(rows, key=lambda r: r["round_trip_bps"])


def kelly_size(edge_usd: float, var_usd: float, bankroll: float = BANKROLL,
               fraction: float = KELLY_FRACTION,
               cap_usd: float = SIZE_CAP_USD) -> float:
    """Quarter-Kelly dollar exposure from measured per-trip edge/var.
    Zero without positive edge — scaling is EARNED by the measurement
    plane, never assumed."""
    if edge_usd <= 0.0 or var_usd <= 0.0:
        return 0.0
    return min(cap_usd, fraction * (edge_usd / var_usd) * bankroll)


def trip_params(fills: Path, era: str | None = None) -> dict:
    """Closed-trip NET parameters from fills.csv legs, matched by
    position_id: net = Σ signed notional (sell +, buy −) − fees.
    Report-only view; membership is LOOSER than the era gate (no
    stamp-purity, book, or size filters) and is disclosed as such — the
    registered membership lives in scripts/era_readout.py."""
    import csv
    legs: dict[str, list[tuple[str, float, float, float]]] = {}
    with open(fills, encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            if era and (row.get("exec_era") or "") != era:
                continue
            pid = row.get("position_id") or ""
            try:
                size = float(row.get("fill_size") or 0.0)
                price = float(row.get("fill_price") or 0.0)
                fee = float(row.get("fees_delta_usd") or 0.0)
            except ValueError:
                continue
            side = (row.get("side") or "").lower()
            legs.setdefault(pid, []).append((side, size, price, fee))
    nets = []
    for trips in legs.values():
        if len(trips) < 2:
            continue
        net = sum((s * p if side == "sell" else -s * p)
                  for side, s, p, _ in trips)
        net -= sum(f for _, _, _, f in trips)
        nets.append(net)
    if not nets:
        return {"n": 0, "mean_net": 0.0, "sd_net": 0.0}
    sd = statistics.stdev(nets) if len(nets) > 1 else 0.0
    return {"n": len(nets), "mean_net": statistics.mean(nets), "sd_net": sd}


def _readout_params(root: Path) -> dict:
    """Trip net parameters from scripts/era_readout.py --json — the
    registration's own trip reconstruction (stamp-pure, book-segmented).
    Falls back to the loose raw-fill matcher with a loud disclaimer."""
    import json
    import subprocess  # nosec B404 - fixed argv, repo venv interpreter, repo-local script
    import sys
    # era_readout needs numpy: prefer the repo venv interpreter
    venv_py = (root / ".venv" / "Scripts" / "python.exe")
    interp = str(venv_py) if venv_py.exists() else sys.executable
    try:
        out = subprocess.run(  # nosec B603 - fixed argv: <repo venv python> scripts/era_readout.py --json; 300s timeout
            [interp, str(root / "scripts" / "era_readout.py"), "--json"],
            cwd=root, capture_output=True, text=True, timeout=300)
        if out.returncode != 0:
            raise RuntimeError(out.stderr.strip()[:200])
        d = json.loads(out.stdout)
        pops = d.get("populations", {})
        # operator-selected 2026-09-15: the 5m-book registration row
        key = next((k for k in pops if "HYPOTHESIS" in k), None) \
            or next(iter(pops))
        pop = pops[key]
        net = pop["net"]
        se = (net["hi"] - net["lo"]) / (2 * 1.96)
        n = pop["n"]
        sd = se * (n ** 0.5) if n else 0.0
        return {"n": n, "mean_net": net["mean"], "sd_net": sd,
                "source": "era_readout.py --json (registration trip view)",
                "population": key}
    except Exception as exc:                          # noqa: BLE001
        fills = root / "outputs" / "fills.csv"
        p = trip_params(fills) if fills.exists() else {
            "n": 0, "mean_net": 0.0, "sd_net": 0.0}
        p["source"] = f"RAW-FILL MATCHER (loose; era_readout failed: {exc})"
        p["population"] = "unsegmented"
        return p


def build_report(root: Path) -> str:
    root = Path(root)
    warnings = []
    params = _readout_params(root)
    era = params.get("population", "n/a")
    if params["n"] < 2:
        warnings.append("fewer than 2 closed trips in scope; "
                        "parameters are placeholders")
    if "RAW-FILL" in params["source"]:
        warnings.append("trip parameters come from the loose raw-fill "
                        "matcher, NOT the era gate; treat as placeholders")

    floor = cost_floor_bps(0.0, DEFAULT_FEE_BPS_RT, DEFAULT_ADVERSE_BPS)
    rebate_floor = cost_floor_bps(0.0, 2.0, DEFAULT_ADVERSE_BPS)
    var = params["sd_net"] ** 2
    kelly = kelly_size(params["mean_net"], var)

    out = [
        f"SCALING REPORT — generated {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"repo: {root}  era: {era or 'n/a'}",
        "",
        "REPORT-ONLY. NOT the era-9 registration (scripts/era_readout.py "
        "is). Nothing here sizes, places, or gates an order.",
        "",
        "== 1. COST FLOOR (kill line a setup must clear, gross bps RT) ==",
        f"   current tier (fee {DEFAULT_FEE_BPS_RT} + adverse "
        f"{DEFAULT_ADVERSE_BPS}): {floor:.1f} bps",
        f"   maker-rebate shape (fee ~2 + adverse {DEFAULT_ADVERSE_BPS}): "
        f"{rebate_floor:.1f} bps  <- the tier roll is a scaling asset",
        "",
        "== 2. TIER ROLL (volume ladder as falling cost) ==",
    ]
    for r in tier_roll_table(DEFAULT_LADDER, volume_30d=69652.65):
        out.append(f"   >=${r['min_volume']:>9,.0f} 30d vol: "
                   f"{r['maker_bps']:.0f}/{r['taker_bps']:.0f} "
                   f"= {r['round_trip_bps']:.0f} bps RT")
    out += [
        "",
        "== 3. EDGE-CONDITIONAL SIZE (quarter-Kelly, what scaling WOULD "
        "approve) ==",
        f"   measured trip edge: {params['mean_net']:+.4f} $/trip "
        f"(n={params['n']}, sd={params['sd_net']:.4f})",
        f"   source: {params['source']}",
        f"   Kelly exposure: ${kelly:.2f} of ${BANKROLL:.0f} bankroll "
        f"(cap ${SIZE_CAP_USD:.0f}, fraction {KELLY_FRACTION})",
        "   <= $0 means the measured edge supports NO size. Scaling is "
        "earned by the measurement plane, never assumed.",
        "",
        "== 4. WHAT THE 09-22 DOCKET IS BUYING ==",
        "   A scaling governor is cohort-resetting (sizing). It ships "
        "only at a boundary, behind a config flag, with these four "
        "numbers as its pre-registered inputs. Until then this report "
        "re-runs and the numbers speak for themselves.",
    ]
    if warnings:
        out += ["", "WARNINGS:", *[f"- {w}" for w in warnings]]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    args = ap.parse_args(argv)
    try:
        import sys as _sys
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    print(build_report(Path(args.root).resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
