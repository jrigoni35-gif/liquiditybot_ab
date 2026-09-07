"""scripts/beta_alpha_decomposition.py — how much of each trade was the MARKET?

THE QUESTION (operator, 2026-09-07): "does the bot have a way to learn what it
is hedging against?" A professional learns it by measurement: split every
closed trade's gross return into the part the whole market moved (BETA) and
the part the coin moved relative to the market (the residual, ALPHA). A hedge
only ever earns its cost against exposure whose residual is positive; if the
residual is ~0 everywhere, "never hedge" is a measured rule, not a guess.

METHOD, deliberately simple.
  trip      one entry-opened, fully closed, single-exec_era, hedge-free round
            trip from outputs/fills.csv; r_trade = (Σsell − Σbuy) / entry
            notional, which is gross of fees and correctly signed for shorts.
  market    the equal-weight close-to-close return of the CRYPTO basket
            (BTC, ETH, LINK minus the traded asset) over the SAME
            [entry, exit] window on the stored 5m tape. Excluding the traded
            asset is what keeps this from being a tautology: an asset
            regressed on itself has beta 1 and residual 0 by construction.
            PAXG is OUT of the default basket: gold's 5m variance is ~half a
            crypto major's and it dilutes the factor (refutation 2026-09-07,
            D4). --basket overrides. STRICT membership: a trip whose window is
            missing ANY basket member is dropped and COUNTED, never measured
            against a two-member basket that happens to be present.
  anchor    the price "at" a timestamp is the close of the last bar that had
            CLOSED by then - the last price actually known before the fill.
            The first version used the close of the bar CONTAINING the fill,
            which prints up to 5 minutes AFTER it (96% of anchors did): a
            look-ahead at both ends of every window, and the pin named
            "no_look_ahead" enforced it (D2).
  signing   a short is a bet the market falls, so its market factor is
            −r_mkt; after signing, "beta" reads as the share of the bet that
            was the market regardless of direction.
  beta      OLS slope of r_trade on the signed market return, pooled and per
            asset/era/direction. alpha = the INTERCEPT (Jensen's alpha) - NOT
            the mean residual, which is zero by construction when an intercept
            is fitted; the first run printed "alpha 0.0" for every group for
            exactly that reason.
  intervals THREE, because trips cluster by UTC day of the closing fill and
            the day count G is small. (1) day-block bootstrap percentile CI of
            the refit slope/intercept - the headline, but ANTI-CONSERVATIVE by
            ~2x when G <= 15 (measured false-exclusion 4-15% at 5%, D3), so
            (2) a CR1 cluster-robust t interval with G-1 df, and (3) an
            EXACT day-level sign-flip p for alpha (all 2^G flips when G <= 16,
            else 20,000 Monte-Carlo flips). A per-group alpha is "clear of
            zero" only when the bootstrap CI, the CR1 interval AND the
            sign-flip p agree. n_eff = (Σn_d)²/Σn_d² is printed and a group
            with n_eff < 10 is FLAGGED; the leave-one-day-out range of beta and
            alpha shows how much one day carries (D5).
  dropped   every trip the tape cannot price is COUNTED by era and reason
            (beyond_tape / before_tape / basket_gap) with its mean gross. The
            first version dropped 22 recent trips silently - the losing ones
            (mean gross −52 bps, era-9 20 of 29) - and printed a cleaner book
            than the ledger holds (D1). The tape's end is printed per asset;
            if it trails the last fill, refresh the store before reading:
            scripts/kraken_trades_backfill.py -> scripts/tape_to_candles.py
            -> scripts/candle_store.py compaction.
  caution   per-asset groups are ~15 comparisons; one CI clearing zero at
            the 5% level among fifteen is what chance produces. Treat a lone
            per-asset alpha as a candidate for a pre-registered test, never
            as a finding. Resolution is ~±15 bps/trip pooled, ±40-180 per alt:
            "no measured alpha" is not "no alpha".

Report-only. SAFE under the era-8 moratorium. Every figure is as-of the
files read; re-run to refresh. No Gaussian assumption in the bootstrap or the
sign-flip; the CR1 interval uses Student t with G-1 df.

    python scripts/beta_alpha_decomposition.py [--json] [--min-trips N]
                                               [--basket BTC,ETH,LINK] [--reps N]
"""
from __future__ import annotations

import argparse
import collections
import csv
import itertools
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FILLS = ROOT / "outputs" / "fills.csv"
TAPE = ROOT / "outputs" / "candles" / "parquet"
BASKET = ("BTC", "ETH", "LINK")
BAR_S = 300.0
GAP_S = 3 * BAR_S       # an anchoring close older than this before ts = a gap
DAY = 86400.0
EXACT_MAX_DAYS = 16     # 2^16 = 65,536 sign patterns; beyond that, Monte Carlo
MC_FLIPS = 20_000
FEW_EFF_DAYS = 10.0


def _f(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _iso(s: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(s))


def load_trips(path: Path = FILLS) -> list[dict]:
    """Closed, entry-opened, single-era, hedge-free round trips."""
    trips: dict = collections.defaultdict(lambda: {
        "buy": 0.0, "sell": 0.0, "entry_notional": 0.0, "fees": 0.0,
        "entry_ts": None, "exit_ts": None, "purposes": set(), "eras": set(),
        "symbol": None, "side0": None, "rem": None})
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("purpose") == "hedge":
                continue
            t = trips[r["position_id"]]
            ts, side, pur = _f(r["ts"]), r["side"].lower(), r["purpose"]
            notl = abs(_f(r["fill_size"]) * _f(r["fill_price"]))
            t["symbol"] = r["symbol"]
            t["fees"] += _f(r["fees_delta_usd"])
            t["purposes"].add(pur)
            t["eras"].add(r.get("exec_era") or "(blank)")
            if side.startswith("b"):
                t["buy"] += notl
            else:
                t["sell"] += notl
            if pur == "entry":
                t["entry_notional"] += notl
                if t["entry_ts"] is None or ts < t["entry_ts"]:
                    t["entry_ts"], t["side0"] = ts, side
            elif pur == "exit":
                t["rem"] = _f(r["remaining"])
                if t["exit_ts"] is None or ts > t["exit_ts"]:
                    t["exit_ts"] = ts
    out = []
    for pid, t in trips.items():
        if not ({"entry", "exit"} <= t["purposes"]) or (t["rem"] or 0) > 1e-9:
            continue
        if len(t["eras"]) != 1 or t["entry_notional"] <= 0:
            continue
        direction = "long" if t["side0"].startswith("b") else "short"
        out.append({
            "position_id": pid, "symbol": t["symbol"], "direction": direction,
            "asset": t["symbol"].split("/")[0], "era": next(iter(t["eras"])),
            "entry_ts": t["entry_ts"], "exit_ts": t["exit_ts"],
            "r_trade": (t["sell"] - t["buy"]) / t["entry_notional"],
            "fees_usd": t["fees"], "entry_notional": t["entry_notional"],
        })
    return out


def load_tape(assets=BASKET, root: Path = TAPE) -> dict:
    """asset -> (t_open_s sorted ndarray, close ndarray) from the 5m parquet."""
    import pandas as pd
    tape = {}
    for a in assets:
        f = Path(root) / f"{a}_300.parquet"
        if not f.exists():
            continue
        d = pd.read_parquet(f)
        t = d["t_open_s"].astype(float).to_numpy()
        c = d["close"].astype(float).to_numpy()
        o = np.argsort(t)
        tape[a] = (t[o], c[o])
    return tape


def tape_span(tape: dict) -> dict:
    """asset -> (first close time, last close time) the tape can anchor."""
    return {a: (float(t[0]) + BAR_S, float(t[-1]) + BAR_S)
            for a, (t, _c) in tape.items() if t.size}


def _close_at(tape_a, ts: float):
    """The last price KNOWN at ts: the close of the last bar that had CLOSED
    at or before ts (bar open <= ts - BAR_S). Never the bar containing ts -
    its close prints after the fill. None outside the tape or across a gap
    wider than GAP_S."""
    t, c = tape_a
    i = int(np.searchsorted(t, ts - BAR_S, side="right")) - 1
    if i < 0 or i >= len(t):
        return None
    if ts - (t[i] + BAR_S) > GAP_S:
        return None                            # stale anchor = a gap
    return float(c[i])


def market_return(tape: dict, exclude: str, t0: float, t1: float,
                  basket=BASKET):
    """Equal-weight close-to-close return of the basket EXCLUDING `exclude`.
    STRICT: every non-excluded basket member must anchor at BOTH ends, else
    None - a two-member basket is a different factor, not a thinner one."""
    rets = []
    for a in basket:
        if a == exclude:
            continue
        series = tape.get(a)
        if series is None:
            return None
        c0, c1 = _close_at(series, t0), _close_at(series, t1)
        if not (c0 and c1 and c0 > 0):
            return None
        rets.append(c1 / c0 - 1.0)
    return float(np.mean(rets)) if rets else None


def ols(x: np.ndarray, y: np.ndarray):
    """slope, intercept, r2 of y on x."""
    if x.size < 3 or np.allclose(x, x[0]):
        return float("nan"), float(np.mean(y)) if y.size else float("nan"), float("nan")
    xm, ym = x.mean(), y.mean()
    b = float(((x - xm) * (y - ym)).sum() / ((x - xm) ** 2).sum())
    a = float(ym - b * xm)
    res = y - (a + b * x)
    ss_tot = float(((y - ym) ** 2).sum())
    r2 = 1.0 - float((res ** 2).sum()) / ss_tot if ss_tot > 0 else float("nan")
    return b, a, r2


def day_block_ci(x: np.ndarray, y: np.ndarray, days: np.ndarray,
                 reps: int = 4000, seed: int = 11):
    """Percentile CIs of the REFIT slope and intercept under a day-block
    bootstrap: (beta_ci, alpha_ci), or None below 5 distinct days. This is
    the ONLY bootstrap in the file - the first version carried a second,
    inline copy that the tests never touched (D7)."""
    ud = np.unique(days)
    if ud.size < 5:
        return None
    rng = np.random.default_rng(seed)
    groups = {u: np.flatnonzero(days == u) for u in ud}
    bb, aa = [], []
    for _ in range(reps):
        pick = rng.choice(ud, size=ud.size, replace=True)
        idx = np.concatenate([groups[u] for u in pick])
        b_, a_, _ = ols(x[idx], y[idx])
        if np.isfinite(b_) and np.isfinite(a_):
            bb.append(b_)
            aa.append(a_)
    if not bb:
        return None
    return ([float(np.percentile(bb, 2.5)), float(np.percentile(bb, 97.5))],
            [float(np.percentile(aa, 2.5)), float(np.percentile(aa, 97.5))])


# Student t 0.975 quantiles by df. scipy is NOT in the repo venv (checked
# 2026-09-07); a 1.96 fallback at 7 df (true 2.365) would rebuild the exact
# anti-conservatism CR1 is here to remove. Sparse rows above 30 are linearly
# interpolated in 1/df, which is accurate to <0.002 there.
_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
         7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179,
         13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101,
         19: 2.093, 20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064,
         25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
         40: 2.021, 60: 2.000, 120: 1.980}


def _t_crit(df: int) -> tuple[float, str]:
    """0.975 Student-t quantile on `df` degrees of freedom: scipy when it is
    importable, else the exact table above (never a bare 1.96)."""
    try:
        from scipy.stats import t as _t
        return float(_t.ppf(0.975, df)), "student_t"
    except Exception:
        df = max(int(df), 1)
        if df in _T975:
            return _T975[df], "t_table"
        if df > 120:
            lo, hi = 120, None
        else:
            keys = sorted(_T975)
            lo = max(k for k in keys if k < df)
            hi = min(k for k in keys if k > df)
        if hi is None:                              # beyond the table: → 1.960
            f = (1.0 / 120 - 1.0 / df) / (1.0 / 120)
            return _T975[120] + f * (1.960 - _T975[120]), "t_table"
        f = (1.0 / lo - 1.0 / df) / (1.0 / lo - 1.0 / hi)
        return _T975[lo] + f * (_T975[hi] - _T975[lo]), "t_table"


def cr1_intervals(x: np.ndarray, y: np.ndarray, days: np.ndarray):
    """Cluster-robust (CR1, Liang-Zeger with the small-sample factor) 95%
    intervals for (beta, alpha), clusters = days, Student t on G-1 df."""
    ud = np.unique(days)
    G, n = ud.size, x.size
    if G < 3 or n < 4:
        return None
    X = np.column_stack([np.ones(n), x])
    xtx_inv = np.linalg.pinv(X.T @ X)
    coef = xtx_inv @ X.T @ y
    u = y - X @ coef
    meat = np.zeros((2, 2))
    for g in ud:
        m = days == g
        s = X[m].T @ u[m]
        meat += np.outer(s, s)
    V = xtx_inv @ meat @ xtx_inv * (G / (G - 1.0)) * ((n - 1.0) / max(n - 2.0, 1.0))
    se_a, se_b = float(np.sqrt(max(V[0, 0], 0.0))), float(np.sqrt(max(V[1, 1], 0.0)))
    tc, src = _t_crit(G - 1)
    return {"beta_ci": [float(coef[1] - tc * se_b), float(coef[1] + tc * se_b)],
            "alpha_ci": [float(coef[0] - tc * se_a), float(coef[0] + tc * se_a)],
            "df": int(G - 1), "t_crit": src}


def signflip_p(x: np.ndarray, y: np.ndarray, days: np.ndarray, b: float,
               seed: int = 5):
    """Day-level sign-flip p for alpha. With b the pooled slope held fixed,
    alpha = Σ_d n_d·m_d / n where m_d = mean over day d of (y − b·x). Under
    H0 (alpha = 0, day contributions symmetric) every sign pattern on the
    m_d is equally likely; p = share of patterns with |T| >= |alpha|. Exact
    over all 2^G patterns when G <= EXACT_MAX_DAYS, else MC_FLIPS random
    ones. Returns (p, method). The fixed-b is an approximation, named."""
    ud = np.unique(days)
    G = ud.size
    if G < 4 or not np.isfinite(b):
        return None, "too_few_days"
    resid = y - b * x
    w = np.array([np.sum(days == u) for u in ud], dtype=float)
    m = np.array([resid[days == u].mean() for u in ud])
    obs = abs(float((w * m).sum() / w.sum()))
    if G <= EXACT_MAX_DAYS:
        signs = np.array(list(itertools.product((1.0, -1.0), repeat=G)))
        method = "exact"
    else:
        rng = np.random.default_rng(seed)
        signs = rng.choice((1.0, -1.0), size=(MC_FLIPS, G))
        method = "mc"
    stats = np.abs((signs * (w * m)).sum(axis=1) / w.sum())
    p = float(np.mean(stats >= obs - 1e-15))
    return p, method


def alpha_clear(a: float, boot_ci, cr1_ci, p) -> bool | None:
    """True only when the bootstrap CI, the CR1 interval AND the sign-flip
    p all put alpha on the same side of zero as its point estimate. An
    interval excludes zero iff BOTH endpoints share alpha's sign - the first
    cut tested min(ci)*sign > 0, which every negative-alpha interval passes
    (ARB printed 'clear' on CR1 [-149, +12])."""
    if not boot_ci or not cr1_ci or p is None or not np.isfinite(a) or a == 0:
        return None
    sgn = 1.0 if a > 0 else -1.0
    return bool(all(v * sgn > 0 for v in boot_ci)
                and all(v * sgn > 0 for v in cr1_ci) and p < 0.05)


def lodo_range(x: np.ndarray, y: np.ndarray, days: np.ndarray):
    """Leave-one-day-out (min, max) of the refit beta and alpha."""
    ud = np.unique(days)
    if ud.size < 3:
        return None
    bs, as_ = [], []
    for u in ud:
        keep = days != u
        b_, a_, _ = ols(x[keep], y[keep])
        if np.isfinite(b_) and np.isfinite(a_):
            bs.append(b_)
            as_.append(a_)
    if not bs:
        return None
    return {"beta": [float(min(bs)), float(max(bs))],
            "alpha": [float(min(as_)), float(max(as_))]}


def _drop_reason(tr: dict, tape: dict, basket, span: dict) -> str:
    members = [a for a in basket if a != tr["asset"]]
    if any(a not in tape for a in members):
        return "basket_asset_missing"
    end = min(span[a][1] for a in members)
    start = max(span[a][0] for a in members)
    if tr["exit_ts"] > end:
        return "beyond_tape"
    if tr["entry_ts"] < start:
        return "before_tape"
    return "basket_gap"


def decompose(trips: list[dict], tape: dict, min_trips: int = 10,
              basket=BASKET, reps: int = 4000) -> dict:
    span = tape_span(tape)
    rows, dropped = [], []
    for tr in trips:
        rm = market_return(tape, tr["asset"], tr["entry_ts"], tr["exit_ts"], basket)
        if rm is None:
            dropped.append({**tr, "reason": _drop_reason(tr, tape, basket, span)})
            continue
        signed = rm if tr["direction"] == "long" else -rm
        rows.append({**tr, "r_mkt_signed": signed,
                     "day": int(tr["exit_ts"] // DAY)})
    by_era: dict = collections.defaultdict(lambda: collections.Counter())
    for d in dropped:
        by_era[d["era"]][d["reason"]] += 1
    out = {"read_utc": _iso(time.time()),
           "basket": list(basket),
           "tape_end_utc": {a: _iso(span[a][1]) for a in basket if a in span},
           "trips_total": len(trips), "trips_on_tape": len(rows),
           "dropped": len(dropped),
           "dropped_by_era": {e: dict(c) for e, c in sorted(by_era.items())},
           "dropped_mean_gross_bps": (round(float(np.mean([d["r_trade"] for d in dropped])) * 1e4, 2)
                                      if dropped else None),
           "last_fill_utc": _iso(max(t["exit_ts"] for t in trips)) if trips else None,
           "method": "OLS of gross trip return on the signed EW return of the "
                     "basket minus the traded asset over the same window, prior-"
                     "close anchors; day-block bootstrap + CR1 + exact sign-flip",
           "groups": {}}
    if not rows:
        return out

    def group(label, sel):
        if len(sel) < min_trips:
            return {"n": len(sel), "skipped": f"< {min_trips} trips"}
        x = np.array([r["r_mkt_signed"] for r in sel])
        y = np.array([r["r_trade"] for r in sel])
        d = np.array([r["day"] for r in sel])
        b, a, r2 = ols(x, y)
        # ALPHA IS THE INTERCEPT, NOT THE MEAN RESIDUAL (see module doc).
        ud, counts = np.unique(d, return_counts=True)
        n_eff = float(counts.sum() ** 2 / (counts ** 2).sum())
        boot = day_block_ci(x, y, d, reps=reps)
        cr1 = cr1_intervals(x, y, d)
        p, pmeth = signflip_p(x, y, d, b)
        lodo = lodo_range(x, y, d)
        bps = lambda v: [round(u * 1e4, 2) for u in v] if v else None  # noqa: E731
        alpha_ci = boot[1] if boot else None
        clear = alpha_clear(a, alpha_ci, cr1["alpha_ci"] if cr1 else None, p)
        return {
            "n": len(sel), "days": int(ud.size), "n_eff": round(n_eff, 1),
            "few_eff_days": n_eff < FEW_EFF_DAYS,
            "beta": round(b, 4), "beta_ci": boot[0] if boot else None,
            "beta_ci_cr1": cr1["beta_ci"] if cr1 else None,
            "r2": round(r2, 4) if np.isfinite(r2) else None,
            "mean_gross_bps": round(float(y.mean()) * 1e4, 2),
            "market_part_bps": round(float((b * x).mean()) * 1e4, 2),
            "alpha_bps": round(float(a) * 1e4, 2),
            "alpha_ci_bps": bps(alpha_ci),
            "alpha_ci_cr1_bps": bps(cr1["alpha_ci"]) if cr1 else None,
            "cr1_t": cr1["t_crit"] if cr1 else None,
            "alpha_signflip_p": p, "signflip_method": pmeth,
            "alpha_clear_of_zero": clear,
            "lodo_beta": lodo["beta"] if lodo else None,
            "lodo_alpha_bps": bps(lodo["alpha"]) if lodo else None,
            "share_of_variance_market": round(r2, 3) if np.isfinite(r2) else None,
        }

    out["groups"]["ALL"] = group("ALL", rows)
    for era in sorted({r["era"] for r in rows}):
        out["groups"][f"era:{era}"] = group(era, [r for r in rows if r["era"] == era])
    for a in sorted({r["asset"] for r in rows}):
        out["groups"][f"asset:{a}"] = group(a, [r for r in rows if r["asset"] == a])
    for dr in ("long", "short"):
        out["groups"][f"dir:{dr}"] = group(dr, [r for r in rows if r["direction"] == dr])
    return out


def _fmt_ci(ci, nd=1):
    return f"[{ci[0]:.{nd}f},{ci[1]:.{nd}f}]" if ci else "(n/a)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-trips", type=int, default=10)
    ap.add_argument("--basket", default=",".join(BASKET),
                    help="comma list of factor assets (default crypto-only)")
    ap.add_argument("--reps", type=int, default=4000, help="bootstrap reps")
    ns = ap.parse_args()
    basket = tuple(s.strip().upper() for s in ns.basket.split(",") if s.strip())
    trips = load_trips()
    tape = load_tape(basket)
    res = decompose(trips, tape, ns.min_trips, basket=basket, reps=ns.reps)
    if ns.json:
        print(json.dumps(res, indent=2))
        return 0
    print("=" * 100)
    print(f"BETA / ALPHA DECOMPOSITION — read {res['read_utc']}   basket {'+'.join(basket)}")
    print("=" * 100)
    print(f"  closed single-era hedge-free trips: {res['trips_total']}  "
          f"| priced on the tape: {res['trips_on_tape']}  | DROPPED: {res['dropped']}"
          + (f"  (mean gross of dropped {res['dropped_mean_gross_bps']:+.1f} bps)"
             if res["dropped"] else ""))
    print(f"  last fill {res['last_fill_utc']}   tape ends "
          + "  ".join(f"{a} {e}" for a, e in res["tape_end_utc"].items()))
    if res["dropped_by_era"]:
        print("  dropped by era: " + json.dumps(res["dropped_by_era"]))
        if any("beyond_tape" in c for c in res["dropped_by_era"].values()):
            print("  ** trips lie BEYOND the tape's end - refresh the store before reading "
                  "(kraken_trades_backfill -> tape_to_candles -> candle_store) **")
    print()
    print(f"  {'group':16s} {'n':>4s} {'days':>4s} {'n_eff':>5s} {'beta':>6s} {'CR1 beta':>13s} "
          f"{'R2':>5s} {'gross':>7s} {'=mkt':>7s} {'+alpha':>7s} {'boot CI':>16s} "
          f"{'CR1 CI':>16s} {'p_flip':>7s} clear")
    for k, g in res["groups"].items():
        if "skipped" in g:
            print(f"  {k:16s} {g['n']:4d}   {g['skipped']}")
            continue
        flag = "!" if g["few_eff_days"] else " "
        p = g["alpha_signflip_p"]
        print(f"  {k:16s} {g['n']:4d} {g['days']:4d} {g['n_eff']:5.1f}{flag}{g['beta']:6.3f} "
              f"{_fmt_ci(g['beta_ci_cr1'], 2):>13s} "
              f"{(g['r2'] if g['r2'] is not None else float('nan')):5.3f} "
              f"{g['mean_gross_bps']:7.1f} {g['market_part_bps']:7.1f} {g['alpha_bps']:7.1f} "
              f"{_fmt_ci(g['alpha_ci_bps']):>16s} {_fmt_ci(g['alpha_ci_cr1_bps']):>16s} "
              f"{(p if p is not None else float('nan')):7.3f} "
              f"{'YES' if g['alpha_clear_of_zero'] else ('no' if g['alpha_clear_of_zero'] is False else '?')}")
    print()
    print(f"READ: 'beta' is the slope of the trip's gross return on the {'+'.join(basket)}")
    print("basket (minus the traded coin) - the share of the bet that was the market,")
    print("relative to THAT factor. '=mkt' is the part of mean gross the market")
    print("delivered; '+alpha' is what the coin did relative to the market. n_eff is")
    print("the day-clustered effective sample; '!' marks n_eff < 10, where the boot CI")
    print("is ~2x too narrow - read CR1 and p_flip instead. 'clear' = boot CI, CR1 and")
    print("p_flip < 0.05 all agree alpha is off zero. A hedge earns its cost only where")
    print("alpha is clear AND positive; a clear NEGATIVE alpha is a selection or exit")
    print("problem (the hedge would strip the market part and keep the loss).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
