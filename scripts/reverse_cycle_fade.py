"""reverse_cycle_fade.py — SAFE measurement (reads history, writes nothing to
the corpus or any decision path).

DECISIVE QUESTION (the REVERSION-FADE lens). The bot is slow / REST-polled
(~6.2s cycle, ~95% I/O-wait), so it reads flow AFTER faster players moved
price and enters POST-OVERSHOOT. HYPOTHESIS: its momentum-following entry
rides an overshoot that mean-reverts, so FADING the entry direction (holding
the OPPOSITE side to the reversion horizon) captures the snapback. Does the
FADE produce POSITIVE gross at some horizon, NET of the real ~60 bps Tier-3
rake (maker 22 / taker 38), at EFFECTIVE n under NON-OVERLAPPING sampling?

WHAT IS FADED. The bot's OWN directional call, the `side`/`direction` column
(momentum-following by construction). follow = market_fwd_ret * (+1 long /
-1 short); fade = -follow (exact antisymmetry). A blanket fade therefore has
mean gross = -(mean follow gross); the hard arithmetic gate says pooled gross
~= 0 and SYMMETRIC, so a blanket fade is ~0 - 60 bps < 0. The reverse cycle
pays ONLY if a CONDITIONAL structure (here: the horizon reversion) makes the
fade's gross positive by MORE than 60 bps at effective n.

TWO CONFOUNDS, both handled:
  1. MARKET BETA. A raw direction-signed mean conflates the bot's timing with
     net market drift x the long/short imbalance (11,849 long vs 7,624 short).
     We report BOTH the raw fade (what a naive reverse-bot captures) AND the
     ASSET-DEMEANED fade (fwd_ret minus that asset's mean fwd_ret at this H,
     then signed) — the market-neutral TIMING component, which is the honest
     test of the overshoot-snapback thesis.
  2. THE AUTOCORRELATION MIRAGE (the #1 false-positive risk). Consecutive
     forward windows overlap ever more as H grows -> nominal n inflated ->
     any apparent horizon flip is likely spurious. The DECISIVE statistic is
     the mean + t over a NON-OVERLAPPING subsample (one accepted obs per
     H-length block per asset; kept windows pairwise disjoint). n_eff and
     t_eff are the significance basis; nominal is reported only alongside.

Reconstruction machinery (forward_ret, price path, non-overlapping subsample)
is lifted VERBATIM from scripts/horizon_edge_sweep.py (mutation-killed,
double-derived, 8 pins) so this shares that instrument's verified core.

Usage:
    python scripts/reverse_cycle_fade.py [--era triple_barrier_h432]
                                         [--entered-only] [--json OUT.json]
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

# WALL-CLOCK horizons (seconds); bar cadence is irregular.
HORIZONS = {
    "15min": 900, "1h": 3600, "6h": 21600, "12h": 43200,
    "24h": 86400, "48h": 172800, "72h": 259200,
}
FEE_1LEG_RT = 0.006  # 60 bps: the real Tier-3 rake for ONE fade round trip
                     # (maker 22 + taker 38). The dispatch: price EVERYTHING
                     # at 60 bps. A single fade position = one round trip.
TOL_FRAC = 0.5  # a match must land within 0.5*H of t0+H

MIN_ASSET_N = 20      # per-asset minimum for a nominal contribution
MIN_ASSET_NEFF = 8    # per-asset minimum for an effective contribution


def _f(v) -> Optional[float]:
    if is_unknown(v):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def load_priced(path=CORPUS_PATH, era: Optional[str] = None,
                entered_only: bool = False):
    """Per-asset priced observations: (ts, p0, dir_sign) + dedup price path.
    Rows kept iff ts parses, entry_price>0 (asset present); optional era and
    entered-only filters."""
    by_asset_rows = defaultdict(list)
    path_pts = defaultdict(dict)
    n_total = n_kept = 0
    for row in iter_rows(path):
        n_total += 1
        if era is not None and str(row.get("label_era") or "").strip() != era:
            continue
        if entered_only and str(row.get("disp") or "").strip() != "entered":
            continue
        ts = _f(row.get("ts"))
        p0 = _f(row.get("entry_price"))
        if ts is None or p0 is None or p0 <= 0:
            continue
        asset = str(row.get("asset") or "").strip()
        if not asset:
            continue
        side = str(row.get("side") or "long").strip().lower()
        dir_sign = -1.0 if side == "short" else 1.0
        by_asset_rows[asset].append((ts, p0, dir_sign))
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
    (strictly forward, within tol). Returns (fwd_ret, realized_gap) or None.
    VERBATIM from horizon_edge_sweep.py."""
    target = t0 + horizon
    i = bisect.bisect_left(path_ts, t0 + 1e-6)
    n = len(path_ts)
    best = -1
    best_d = None
    j = i
    while j < n:
        d = abs(path_ts[j] - target)
        if best_d is None or d < best_d:
            best_d, best = d, j
        if path_ts[j] > target:
            break
        j += 1
    if best < 0 or best_d is None or best_d > tol:
        return None
    ph = path_px[best]
    if ph <= 0:
        return None
    return (ph - p0) / p0, path_ts[best] - t0


def _mean_t(vals: np.ndarray):
    """(mean, t, n) for a sample. t = mean / (std_ddof1 / sqrt(n)). None t
    when n<2 or zero variance."""
    n = len(vals)
    if n == 0:
        return None, None, 0
    m = float(np.mean(vals))
    if n < 2:
        return m, None, n
    sd = float(np.std(vals, ddof=1))
    t = (m / (sd / math.sqrt(n))) if sd > 0 else None
    return m, t, n


def sweep_horizon(data, horizon):
    """One horizon. Returns follow/fade stats, raw and asset-demeaned, for
    both the nominal (overlapping) and effective (non-overlapping) samples."""
    tol = TOL_FRAC * horizon
    # Collect matched (t0, follow_raw, asset) plus per-asset mean fwd for demean.
    # follow_raw = fwd_ret * dir_sign (market-absolute, direction-signed).
    per_asset = {}   # asset -> list of (t0, fwd_ret, dir_sign)
    for asset, d in data.items():
        rows, pts, pxs = d["rows"], d["path_ts"], d["path_px"]
        recs = []
        for (t0, p0, dsign) in rows:
            fr = forward_ret(pts, pxs, t0, p0, horizon, tol)
            if fr is None:
                continue
            recs.append((t0, fr[0], dsign))
        if recs:
            per_asset[asset] = recs

    # Pool: nominal uses ALL matched rows; effective uses the non-overlapping
    # subsample (accepted t0 spaced >= H) PER ASSET so windows are disjoint.
    follow_nom, fade_nom = [], []
    follow_nom_dm, fade_nom_dm = [], []      # demeaned
    follow_eff, fade_eff = [], []
    follow_eff_dm, fade_eff_dm = [], []
    n_assets_nom = n_assets_eff = 0
    for _asset, recs in per_asset.items():
        fr = np.array([r[1] for r in recs], float)
        ds = np.array([r[2] for r in recs], float)
        t0 = np.array([r[0] for r in recs], float)
        asset_mean = float(np.mean(fr))  # per-asset, per-H drift (beta)
        follow = fr * ds
        fade = -follow
        follow_dm = (fr - asset_mean) * ds
        fade_dm = -follow_dm
        if len(recs) >= MIN_ASSET_N:
            n_assets_nom += 1
            follow_nom.extend(follow.tolist())
            fade_nom.extend(fade.tolist())
            follow_nom_dm.extend(follow_dm.tolist())
            fade_nom_dm.extend(fade_dm.tolist())
        # non-overlapping subsample (chronological, gap >= H)
        keep = np.zeros(len(recs), dtype=bool)
        last = -math.inf
        for k in np.argsort(t0):
            if t0[k] - last >= horizon:
                keep[k] = True
                last = t0[k]
        if keep.sum() >= MIN_ASSET_NEFF:
            n_assets_eff += 1
            # demean the EFFECTIVE subsample by ITS OWN mean (honest beta
            # removal within the independent sample)
            fr_e = fr[keep]
            am_e = float(np.mean(fr_e))
            fe = fr_e * ds[keep]
            fe_dm = (fr_e - am_e) * ds[keep]
            follow_eff.extend(fe.tolist())
            fade_eff.extend((-fe).tolist())
            follow_eff_dm.extend(fe_dm.tolist())
            fade_eff_dm.extend((-fe_dm).tolist())

    def pack(vals):
        m, t, n = _mean_t(np.array(vals, float))
        net = (m - FEE_1LEG_RT) if m is not None else None
        return {"mean": m, "t": t, "n": n, "net_fee": net}

    return {
        "follow_nom": pack(follow_nom), "fade_nom": pack(fade_nom),
        "follow_nom_dm": pack(follow_nom_dm), "fade_nom_dm": pack(fade_nom_dm),
        "follow_eff": pack(follow_eff), "fade_eff": pack(fade_eff),
        "follow_eff_dm": pack(follow_eff_dm), "fade_eff_dm": pack(fade_eff_dm),
        "n_assets_nom": n_assets_nom, "n_assets_eff": n_assets_eff,
    }


def run(era: Optional[str] = None, entered_only: bool = False):
    data, n_total, n_kept = load_priced(era=era, entered_only=entered_only)
    res = {h: sweep_horizon(data, sec) for h, sec in HORIZONS.items()}
    return {
        "corpus": str(CORPUS_PATH),
        "read_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "era_filter": era, "entered_only": entered_only,
        "n_total_rows": n_total, "n_priced_rows": n_kept,
        "fee_1leg_rt": FEE_1LEG_RT, "tol_frac": TOL_FRAC,
        "results": res,
    }


def _fmt(v, nd=4):
    return "   n/a" if v is None else f"{v:+.{nd}f}"


def _row(label, s):
    return (f"{label:>16} {_fmt(s['mean']):>10} {_fmt(s['net_fee']):>10} "
            f"{_fmt(s['t'],2):>7} {s['n']:>7}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--era", default=None)
    ap.add_argument("--entered-only", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    out = run(era=args.era, entered_only=args.entered_only)
    print(f"corpus={out['corpus']} read={out['read_time_utc']} "
          f"era={out['era_filter']} entered_only={out['entered_only']} "
          f"priced={out['n_priced_rows']}/{out['n_total_rows']} "
          f"fee_1leg={out['fee_1leg_rt']}")
    print("\nfade payoff per horizon. DECISIVE row = 'fade_eff_dm' (fade, "
          "market-neutral, NON-OVERLAPPING). Edge iff net_fee>0 AND |t|>2.\n")
    for h in HORIZONS:
        r = out["results"][h]
        print(f"=== {h}  (n_assets nom={r['n_assets_nom']} eff={r['n_assets_eff']}) ===")
        print(f"{'series':>16} {'mean':>10} {'net-60bps':>10} {'t':>7} {'n':>7}")
        for k in ("follow_nom", "fade_nom", "follow_nom_dm", "fade_nom_dm",
                  "follow_eff", "fade_eff", "follow_eff_dm", "fade_eff_dm"):
            print(_row(k, r[k]))
        print()
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
