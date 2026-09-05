"""horizon_edge_sweep.py — SAFE measurement (reads history, writes nothing to
the corpus or any decision path).

DECISIVE QUESTION. The bot was designed as a multi-timeframe liquidity /
smart-money-footprint follower (whale accumulation leaking into price over
DAYS); it drifted to a ~24-bar directional predictor that reads gross~0,
fee-dominated (docs/quant/2026-08-29_fee_dominance_diagnosis.md). Is the
original thesis ALIVE but MIS-CLOCKED — i.e. does any liquidity-footprint
feature carry forward edge at a longer (whale-accumulation) horizon that the
shipped labeling destroys?

METHOD (reconstruction). outputs/signal_history.csv logs, per evaluated
candidate, its feature vector AND the quoted entry_price at that instant.
Per asset, the sorted (ts, entry_price) triples ARE a sampled forward price
path (ts is unix seconds). For a row at (asset, t0, p0), the forward return
at horizon H is (p_H - p0)/p0 where p_H is that asset's price sample nearest
t0+H within tolerance (else the row is discarded at that horizon). fwd_ret is
MARKET-ABSOLUTE (price up = positive), independent of the side the bot chose
and independent of the label columns — so this reconstruction does NOT pool
label-era statistics (the CONFOUNDED_BASELINE class does not apply; the only
era hazard here is feature PADDING, handled by the liveness report + the
h432-only robustness cut).

FEATURE SIGN (read from ml/features.py, NOT from the dispatch grouping):
- Only ofi_dir / imbalance_dir / imbalance_delta_dir / venue_disloc_dir carry
  dir_sign (side-relative). They are UN-SIGNED back to market-absolute here
  (value * (+1 long / -1 short)) so a market-direction test is clean.
- manip_suspect is clip(x,0,1) — a [0,1] MAGNITUDE, not side-signed (the
  dispatch listed it under "sign"; the code disagrees, code wins).
- poc_dist / va_pos are signed relative to price STRUCTURE (not trade side);
  the remaining continuous features and all th_* are [0,1] magnitudes.

TWO ROUTES, MUST AGREE (double-derive the headline):
1. Information coefficient = Spearman(feature_market, fwd_ret).
2. Long-short quintile spread = mean(fwd_ret | top feature-quintile) -
   mean(fwd_ret | bottom quintile), net of the 120 bps true-fee round-trip.
Their signs must agree; a cell where they disagree is reported UNDECIDED.

EFFECTIVE-N IS THE TRAP. Forward windows of consecutive signals overlap
almost completely -> autocorrelation -> IC significance on nominal n is
garbage. The DECISIVE statistic is computed on a NON-OVERLAPPING subsample
(one observation per H-length block per asset); effective n and a z on
effective n are reported alongside the (inflated) nominal n. An IC is not
"significant" until deflated.

Stratified per-asset AND pooled (spread/liquidity differ ~20x across pairs;
pooling is per-asset-quintile then n-weighted so a high-vol asset cannot
dominate the sort).

Usage:
    python scripts/horizon_edge_sweep.py [--era triple_barrier_h432]
                                         [--json OUT.json]
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.corpus import CORPUS_PATH, is_unknown, iter_rows  # noqa: E402

# --- horizons (WALL-CLOCK seconds; bar cadence is irregular) ----------------
HORIZONS = {
    "15min": 900, "1h": 3600, "6h": 21600, "12h": 43200,
    "24h": 86400, "48h": 172800, "72h": 259200,
}
def _fee_rt_from_config() -> float:
    """Round-trip cost as a FRACTION, read from the live config.

    This was `FEE_RT = 0.012  # Kraken T1 40/80, era-5` — a struck constant at
    TWICE the real cost. Cut #9 (2026-08-30) corrected the venue tier to the
    account's true Tier 3, 22/38 bps, so the round trip is 0.006. The sweep's
    only consumer is `net_edge = abs(spread) - FEE_RT`, so an overstated fee
    biases every horizon toward "no net edge" — the exact conclusion the
    project is currently drawing, produced by the instrument rather than the
    market. That is the-method recurrence #1 in constant form, and it is the
    same shape as the error cut #9 existed to correct.

    Read, never struck: the tier has moved twice in two weeks. If config is
    unreadable this RAISES rather than falling back to a literal — a sweep
    that cannot state its own cost basis must not publish a number.
    """
    import json
    with open(ROOT / "config.json", encoding="utf-8") as fh:
        pt = json.load(fh)["pretrade"]
    return (float(pt["maker_fee_bps"]) + float(pt["taker_fee_bps"])) / 10_000.0


FEE_RT = _fee_rt_from_config()
TOL_FRAC = 0.5  # a match must land within 0.5*H of t0+H (effective H in [.5H,1.5H])

# --- feature classification (from ml/features.py, verified against the code) -
SIGNED = ("ofi_dir", "imbalance_dir", "imbalance_delta_dir", "venue_disloc_dir")
CONT = ("flow_tox", "poc_dist", "va_pos", "depth_ratio", "liq_pocket_pull",
        "fvg_pull", "fvg_liq_confluence", "book_touch_share", "manip_suspect")
TH = ("th_grid", "th_stopzone", "th_metronome", "th_clockwork", "th_barclose")
FOOTPRINT = "footprint_block"  # mean of the 5 th_* (all [0,1] market-absolute)
ALL_FEATURES = CONT + SIGNED + TH + (FOOTPRINT,)

MIN_ASSET_N = 20      # per-asset minimum for a nominal-IC contribution
MIN_ASSET_NEFF = 8    # per-asset minimum for an effective-IC contribution


def _f(v) -> Optional[float]:
    if is_unknown(v):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _rank(a: np.ndarray) -> np.ndarray:
    """Average (tie-corrected) ranks — the Spearman kernel."""
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), dtype=float)
    sa = a[order]
    i = 0
    n = len(a)
    while i < n:
        j = i
        while j + 1 < n and sa[j + 1] == sa[i]:
            j += 1
        ranks[order[i:j + 1]] = 0.5 * (i + j) + 1.0  # 1-based average rank
        i = j + 1
    return ranks


def spearman(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    """Spearman rho = Pearson on average ranks. None if degenerate."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if len(x) < 3 or len(x) != len(y):
        return None
    rx, ry = _rank(x), _rank(y)
    sx, sy = rx.std(), ry.std()
    if sx == 0 or sy == 0:  # a constant feature (e.g. dead/padded) has no IC
        return None
    return float(np.mean((rx - rx.mean()) * (ry - ry.mean())) / (sx * sy))


def quintile_spread(feat: np.ndarray, ret: np.ndarray) -> Optional[float]:
    """mean(ret | top feature-quintile) - mean(ret | bottom quintile).
    None when the feature cannot be cut into distinct top/bottom quintiles."""
    if len(feat) < 10:
        return None
    lo, hi = np.percentile(feat, 20), np.percentile(feat, 80)
    if lo == hi:  # too many ties to separate quintiles
        return None
    bot = ret[feat <= lo]
    top = ret[feat >= hi]
    if len(bot) == 0 or len(top) == 0:
        return None
    return float(top.mean() - bot.mean())


def load_priced(path=CORPUS_PATH, era: Optional[str] = None):
    """Per-asset priced observations. Returns dict asset -> dict with:
       ts, p0 (row entry_price), feats {name: array}, and the dedup price
       path (path_ts, path_px). Rows kept iff ts parses and entry_price>0
       (and label_era==era when era given)."""
    by_asset_rows = defaultdict(list)   # asset -> list of (ts, p0, {feat:val})
    path_pts = defaultdict(dict)        # asset -> {ts: [prices]} for dedup
    feat_cols = tuple(f for f in ALL_FEATURES if f != FOOTPRINT)
    n_total = n_kept = 0
    for row in iter_rows(path):
        n_total += 1
        if era is not None and str(row.get("label_era") or "").strip() != era:
            continue
        ts = _f(row.get("ts"))
        p0 = _f(row.get("entry_price"))
        if ts is None or p0 is None or p0 <= 0:
            continue
        asset = str(row.get("asset") or "").strip()
        if not asset:
            continue
        side = str(row.get("side") or "long").strip()
        dir_sign = 1.0 if side == "long" else -1.0
        feats = {}
        for f in feat_cols:
            v = _f(row.get(f))
            if v is None:
                feats[f] = math.nan
            else:
                feats[f] = v * dir_sign if f in SIGNED else v
        th_vals = [feats[t] for t in TH if not math.isnan(feats[t])]
        feats[FOOTPRINT] = (sum(th_vals) / len(th_vals)) if th_vals else math.nan
        by_asset_rows[asset].append((ts, p0, feats))
        path_pts[asset].setdefault(ts, []).append(p0)
        n_kept += 1

    out = {}
    for asset, rows in by_asset_rows.items():
        pts = sorted(path_pts[asset].items())
        path_ts = np.array([t for t, _ in pts], dtype=float)
        path_px = np.array([float(np.mean(px)) for _, px in pts], dtype=float)
        out[asset] = {"rows": rows, "path_ts": path_ts, "path_px": path_px}
    return out, n_total, n_kept


def forward_ret(path_ts, path_px, t0, p0, horizon, tol):
    """Market-absolute forward return to the price sample nearest t0+horizon
    (strictly forward, within tol). Returns (fwd_ret, realized_gap) or None."""
    target = t0 + horizon
    i = bisect.bisect_left(path_ts, t0 + 1e-6)  # first sample strictly after t0
    n = len(path_ts)
    best = -1
    best_d = None
    j = i
    while j < n:
        d = abs(path_ts[j] - target)
        if best_d is None or d < best_d:
            best_d, best = d, j
        if path_ts[j] > target:  # past target; nearest already found
            break
        j += 1
    if best < 0 or best_d is None or best_d > tol:
        return None
    ph = path_px[best]
    if ph <= 0:
        return None
    return (ph - p0) / p0, path_ts[best] - t0


def sweep(data, horizon_name, horizon):
    """One horizon across all features. Returns per-feature stat dict."""
    tol = TOL_FRAC * horizon
    # Precompute matched fwd_ret + realized gap per asset row (feature-agnostic).
    matched = {}  # asset -> (row_index_kept, fwd_ret, realized)
    for asset, d in data.items():
        rows, pts, pxs = d["rows"], d["path_ts"], d["path_px"]
        recs = []
        for ridx, (t0, p0, _feats) in enumerate(rows):
            fr = forward_ret(pts, pxs, t0, p0, horizon, tol)
            if fr is None:
                continue
            recs.append((ridx, fr[0], fr[1]))
        matched[asset] = recs

    results = {}
    for feat in ALL_FEATURES:
        per_asset_ic = []       # (n, ic) nominal
        per_asset_ic_ov = []    # (n_eff, ic) non-overlapping
        per_asset_spread = []   # (n, spread) nominal
        realized = []
        pooled_nom_n = pooled_eff_n = 0
        for asset, d in data.items():
            rows = d["rows"]
            recs = matched[asset]
            if not recs:
                continue
            ridx = [r for r, _, _ in recs]
            fv_all = np.array([rows[r][2][feat] for r in ridx], float)
            fr_all = np.array([x for _, x, _ in recs], float)
            rz_all = np.array([z for _, _, z in recs], float)
            t0_all = np.array([rows[r][0] for r in ridx], float)
            good = np.isfinite(fv_all) & np.isfinite(fr_all)
            # ---- nominal (all overlapping matches) ----
            fv, fr, rz = fv_all[good], fr_all[good], rz_all[good]
            n = len(fv)
            if n >= MIN_ASSET_N:
                ic = spearman(fv, fr)
                if ic is not None:
                    per_asset_ic.append((n, ic))
                    pooled_nom_n += n
                    realized.append((n, float(np.median(rz))))
                sp = quintile_spread(fv, fr)
                if sp is not None:
                    per_asset_spread.append((n, sp))
            # ---- non-overlapping subsample: accepted t0's spaced >= H ----
            # advance the clock only on an ACCEPTED (finite) row, so the
            # kept forward windows [t0, t0+H] are pairwise disjoint.
            keep = np.zeros(len(recs), dtype=bool)
            last = -math.inf
            for k in np.argsort(t0_all):
                if good[k] and t0_all[k] - last >= horizon:
                    keep[k] = True
                    last = t0_all[k]
            fv_ov, fr_ov = fv_all[keep], fr_all[keep]
            if len(fv_ov) >= MIN_ASSET_NEFF:
                ic_ov = spearman(fv_ov, fr_ov)
                if ic_ov is not None:
                    per_asset_ic_ov.append((len(fv_ov), ic_ov))
                    pooled_eff_n += len(fv_ov)

        def wmean(pairs):
            if not pairs:
                return None
            w = sum(n for n, _ in pairs)
            return sum(n * v for n, v in pairs) / w if w else None

        ic_nom = wmean(per_asset_ic)
        ic_eff = wmean(per_asset_ic_ov)
        spread = wmean(per_asset_spread)
        rz_med = wmean(realized)
        # z on EFFECTIVE n (Spearman SE ~ 1/sqrt(n_eff-1))
        z_eff = (ic_eff * math.sqrt(pooled_eff_n - 1)
                 if ic_eff is not None and pooled_eff_n > 1 else None)
        # double-derive: IC sign must match spread sign
        agree = None
        if ic_nom is not None and spread is not None:
            agree = (ic_nom == 0 or spread == 0) or (math.copysign(1, ic_nom)
                                                     == math.copysign(1, spread))
        net_edge = (abs(spread) - FEE_RT) if spread is not None else None
        results[feat] = {
            "ic_nominal": ic_nom, "n_nominal": pooled_nom_n,
            "ic_eff": ic_eff, "n_eff": pooled_eff_n, "z_eff": z_eff,
            "spread": spread, "net_edge": net_edge, "agree": agree,
            "realized_horizon_med": rz_med, "n_assets": len(per_asset_ic),
        }
    return results


def run(era: Optional[str] = None):
    data, n_total, n_kept = load_priced(era=era)
    all_res = {}
    for hname, h in HORIZONS.items():
        all_res[hname] = sweep(data, hname, h)
    return {
        "corpus": str(CORPUS_PATH),
        "read_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "era_filter": era,
        "n_total_rows": n_total,
        "n_priced_rows": n_kept,
        "fee_rt": FEE_RT, "tol_frac": TOL_FRAC,
        "results": all_res,
    }


def _fmt(v, nd=4):
    return "  n/a" if v is None else f"{v:+.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--era", default=None,
                    help="restrict to one label_era (e.g. triple_barrier_h432)")
    ap.add_argument("--json", default=None, help="write full results JSON here")
    args = ap.parse_args()
    out = run(era=args.era)
    print(f"corpus={out['corpus']} read={out['read_time_utc']} "
          f"era={out['era_filter']} priced={out['n_priced_rows']}"
          f"/{out['n_total_rows']} fee_rt={out['fee_rt']}")
    for feat in ALL_FEATURES:
        print(f"\n=== {feat} ===")
        print(f"{'H':>6} {'IC_nom':>9} {'n_nom':>6} {'IC_eff':>9} "
              f"{'n_eff':>6} {'z_eff':>7} {'spread':>9} {'net-fee':>9} "
              f"{'agree':>6} {'realizH_s':>10}")
        for hname in HORIZONS:
            r = out["results"][hname][feat]
            print(f"{hname:>6} {_fmt(r['ic_nominal'])} {r['n_nominal']:>6} "
                  f"{_fmt(r['ic_eff'])} {r['n_eff']:>6} {_fmt(r['z_eff'],2):>7} "
                  f"{_fmt(r['spread'])} {_fmt(r['net_edge'])} "
                  f"{str(r['agree']):>6} "
                  f"{'' if r['realized_horizon_med'] is None else int(r['realized_horizon_med']):>10}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
