"""scripts/alpha_decay_report.py - how much edge does a signal carry, and how
fast does it fade? (SAFE: measurement only; places nothing; reads only
public, read-only market data.)

    python scripts/alpha_decay_report.py                 # full run
    python scripts/alpha_decay_report.py --reps 500      # faster bootstrap

THE QUESTION (docs/quant/2026-10-02_alpha_decay_mu0_tau.md). A round trip
pinned to the market at entry A and exit B has positive action only if the
signal's total edge mu0*tau exceeds the round-trip cost 2c, whatever the
timing. This tool estimates mu0*tau with honest uncertainty.

REGISTERED BEFORE THE FIRST RUN (2026-10-02). Changing anything here after
looking is a new registration and must say so.

  (AMENDMENT 1, disclosed: the tau grid is bounded to the measured window
   [h_min/2, h_max] - see fit_decay. Nothing else was changed after looking.)
  Primary statistic   A = mu0*tau, the asymptote of the DRIFT-ADJUSTED
                      cumulative signed return CAR(h) = A(1 - exp(-h/tau)),
                      fitted by weighted least squares on a tau grid.
                      Drift adjustment subtracts each asset's EXPANDING
                      (past-only) mean return x h, so a long-biased signal
                      is not credited with the market's drift.
  Inference           week-block bootstrap (events clustered by UTC week;
                      overlapping forward windows make event-level errors
                      wrong), 2,000 reps, seed 7; the fit is redone inside
                      every rep, so the CI covers the tau choice too.
                      Effective n = number of weeks, printed.
  Tradeable as trips  CI95_low(A) > 2c, 2c = 45 bps (Kraken Tier 5: 15 maker
                      in + 30 taker out); sensitivity 30 (maker both legs)
                      and 65 (the measured historical median round trip).
                      Must hold in BOTH time halves and survive Holm across
                      the registered family.
  Exists (any edge)   Holm-adjusted one-sided p(A <= 0) < 0.05.
  Units               panel: one EVENT = one asset-hour with a non-zero
                      signal; bot: one LABEL ROW of signal_history.csv
                      (counting standard CS-1, reconcile line printed).

  INDEPENDENT PANEL - signals the bot did not generate, on prices the bot
  did not record. Binance spot 1h klines 2023-01 .. 2026-08, universe fixed
  by a rule stated before data: the 20 largest non-stablecoin assets by
  market cap on 2023-01-01 (from memory of the public ranking; an asset
  later delisted or renamed keeps the history it has - no survivorship cut).
  Registered priors (external, not the bot's):
    P1 tsmom_168   sign(past 168h return), expect +  [Liu & Tsyvinski 2021]
    P2 tsmom_24    sign(past 24h return),  expect +  [large caps: daily
                   momentum, not reversal]
    P3 rev_large   -sign(last 1h return) when |r| > 2 sigma (past 168h),
                   expect +                          [BTC 1-4h reversal]
    P4 flow_rev    -sign(taker imbalance) on flow-driven bars in the top
                   decile of |imbalance| (past 720h), expect +
                                                     [reversal after
                                                      aggressive flow]
    P5 xs_mom_168  +1 top third / -1 bottom third of past-168h return
                   across assets each hour, expect +  [crypto momentum
                   factor]
  Horizons 1, 2, 4, 8, 12, 24, 48, 72, 168 h.

  BOT PANEL - the bot's own signals on INDEPENDENT prices (Binance 5m, the
  bot's own entry_price used only as an alignment check), 2026-07-13 ..
  2026-10-01; Coinbase 5m cross-venue check on BTC and ETH.
    B1 every candidate's direction   B2 live (taken) rows only
    B3 candidates in the top third of gate_confidence
  Horizons 5m .. 72h. Exploratory, NOT registered, Holm within its own
  family and never a decision: the sign of each *_dir feature as a signal.

  CONTROLS (the instrument is tested before its readings are used):
    null_gbm      every panel signal on iid-normal returns with each asset's
                  own vol, R replications -> false-positive rate of
                  "A > 0 at 95%" must be ~5%.
    null_shuffle  hourly returns permuted within asset -> same.
    planted       a known A and tau added to null forward returns ->
                  the estimator must recover them inside its CI.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import json
import math
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SEED = 7
REPS = 2000
TWO_C = 45.0
TWO_C_SENS = (30.0, 45.0, 65.0)
ALPHA = 0.05
H_PANEL = (1, 2, 4, 8, 12, 24, 48, 72, 168)            # hours
H_BOT = (1, 3, 6, 12, 24, 48, 96, 144, 288, 432, 864)  # 5m bars
PANEL_UNIVERSE = ("BTC", "ETH", "BNB", "XRP", "DOGE", "ADA", "MATIC", "DOT",
                  "LTC", "SHIB", "TRX", "AVAX", "UNI", "ATOM", "LINK", "ETC",
                  "XLM", "BCH", "FIL", "SOL")
PANEL_MONTHS = ("2023-01", "2026-08")
BOT_MONTHS = ("2026-04", "2026-10")      # warm-up for the expanding drift
WEEK = 7 * 86400
BV = "https://data.binance.vision/data/spot"


# ================================================================= data
def to_seconds(x: np.ndarray) -> tuple:
    """Binance archives moved from ms to MICROSECONDS in 2025. Normalise per
    value and COUNT each unit - a silent unit change reads as an empty join."""
    x = np.asarray(x, dtype=np.float64)
    us, ms = x > 1e15, (x > 1e12) & (x <= 1e15)
    out = np.where(us, x / 1e6, np.where(ms, x / 1e3, x))
    return out, {"us": int(us.sum()), "ms": int(ms.sum()),
                 "s": int((~us & ~ms).sum())}


def _get(url: str, tries: int = 4) -> bytes | None:
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "liquiditybot-research"})
            with urllib.request.urlopen(req, timeout=60) as r:  # nosec B310 - fixed https hosts
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 ** k)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(2 ** k)
    return None


def _months(a: str, b: str) -> list:
    y, m = map(int, a.split("-"))
    y2, m2 = map(int, b.split("-"))
    out = []
    while (y, m) <= (y2, m2):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def _parse_zip(blob: bytes) -> list:
    rows = []
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for name in z.namelist():
            for line in z.read(name).decode("utf-8").splitlines():
                p = line.split(",")
                if not p or not p[0].strip().isdigit():
                    continue
                rows.append((float(p[0]), float(p[2]), float(p[3]), float(p[4]),
                             float(p[5]), float(p[9])))
    return rows


def binance_klines(sym: str, interval: str, months: tuple, cache: Path) -> dict:
    """{t (s, bar OPEN), high, low, close, vol, taker_buy, units} from the
    public archive; a month with no monthly file falls back to daily files."""
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / f"{sym}_{interval}_{months[0]}_{months[1]}.npz"
    if f.exists():
        d = dict(np.load(f, allow_pickle=True))
        d["units"] = d["units"].item()
        return d
    rows: list = []
    for mo in _months(*months):
        blob = _get(f"{BV}/monthly/klines/{sym}/{interval}/{sym}-{interval}-{mo}.zip")
        if blob is not None:
            rows += _parse_zip(blob)
            continue
        y, m = map(int, mo.split("-"))
        for day in range(1, 32):
            b = _get(f"{BV}/daily/klines/{sym}/{interval}/{sym}-{interval}-{y:04d}-{m:02d}-{day:02d}.zip", tries=2)
            if b is not None:
                rows += _parse_zip(b)
    if not rows:
        d = {"t": np.array([]), "high": np.array([]), "low": np.array([]),
             "close": np.array([]), "vol": np.array([]), "taker_buy": np.array([]),
             "units": {"us": 0, "ms": 0, "s": 0}}
    else:
        a = np.array(sorted(set(rows)))
        t, units = to_seconds(a[:, 0])
        _, keep = np.unique(t, return_index=True)
        d = {"t": t[keep], "high": a[keep, 1], "low": a[keep, 2],
             "close": a[keep, 3], "vol": a[keep, 4], "taker_buy": a[keep, 5],
             "units": units}
    np.savez(f, **{k: (np.array(v, dtype=object) if k == "units" else v)
                   for k, v in d.items()})
    return d


def coinbase_5m(product: str, t0: float, t1: float, cache: Path) -> dict:
    cache.mkdir(parents=True, exist_ok=True)
    f = cache / f"cb_{product}_{int(t0)}_{int(t1)}.npz"
    if f.exists():
        return dict(np.load(f))
    rows = []
    s = t0
    while s < t1:
        e = min(s + 300 * 300, t1)
        url = (f"https://api.exchange.coinbase.com/products/{product}/candles?granularity=300"
               f"&start={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(s))}"
               f"&end={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(e))}")
        b = _get(url)
        if b:
            rows += [(r[0], r[4]) for r in json.loads(b)]
        s = e
        time.sleep(0.35)
    a = np.array(sorted(set(rows))) if rows else np.zeros((0, 2))
    d = {"t": a[:, 0] if len(a) else a, "close": a[:, 1] if len(a) else a}
    np.savez(f, **d)
    return d


# ============================================================ statistics
def forward(lp: np.ndarray, H: tuple) -> np.ndarray:
    """(n, len(H)) forward log returns lp[t+h] - lp[t]; NaN past the end."""
    n = len(lp)
    F = np.full((n, len(H)), np.nan)
    for k, h in enumerate(H):
        if h < n:
            F[: n - h, k] = lp[h:] - lp[: n - h]
    return F


def expanding_drift(lp: np.ndarray, H: tuple, warm: int) -> np.ndarray:
    """Past-only drift x h: (lp[t]-lp[0])/t * h, NaN before `warm` bars."""
    n = len(lp)
    idx = np.arange(n, dtype=float)
    mu1 = np.where(idx >= warm, (lp - lp[0]) / np.maximum(idx, 1), np.nan)
    return mu1[:, None] * np.asarray(H, float)[None, :]


def week_sums(t: np.ndarray, X: np.ndarray) -> tuple:
    """Per-UTC-week sums and counts of the (n, H) matrix X (NaN = absent)."""
    wk = np.floor(t / WEEK).astype(np.int64)
    uniq, inv = np.unique(wk, return_inverse=True)
    W, Hn = len(uniq), X.shape[1]
    ok = np.isfinite(X)
    S = np.zeros((W, Hn))
    N = np.zeros((W, Hn))
    np.add.at(S, inv, np.where(ok, X, 0.0))
    np.add.at(N, inv, ok.astype(float))
    return S, N


def boot_car(S: np.ndarray, N: np.ndarray, reps: int, rng) -> np.ndarray:
    W = S.shape[0]
    idx = rng.integers(0, W, size=(reps, W))
    s = S[idx].sum(axis=1)
    n = N[idx].sum(axis=1)
    return s / np.maximum(n, 1)


TAU_GRID_N = 121


def fit_decay(car: np.ndarray, h: np.ndarray, w: np.ndarray) -> tuple:
    """CAR(h) = A(1 - exp(-h/tau)): closed-form A for every tau on the grid,
    pick min weighted SSE. car may be (H,) or (reps, H). Returns (A, tau).

    AMENDMENT 1 (2026-10-02, after the first smoke run, BEFORE any decision
    read; disclosed in the record): tau is bounded to the MEASURED window
    [h_min/2, h_max]. The registered grid ran to 31.6 x h_max; on curves
    still drifting at h_max it put tau on the grid edge (5,313 h) and
    extrapolated A to +-2,000 bps from CARs that never exceeded 45 bps - an
    asymptote the data cannot identify. With the bound, A <= CAR(h_max) /
    (1 - 1/e): the edge collectable within ~h_max, which is the quantity a
    trip can actually harvest."""
    taus = np.geomspace(h.min() / 2, h.max(), TAU_GRID_N)
    G = 1.0 - np.exp(-h[None, :] / taus[:, None])                  # (T, H)
    c = np.atleast_2d(car)                                          # (R, H)
    num = (c * w) @ G.T                                             # (R, T)
    den = (G * G * w).sum(axis=1)                                   # (T,)
    A = num / den
    sse = ((c[:, None, :] - A[:, :, None] * G[None, :, :]) ** 2 * w).sum(axis=2)
    j = np.argmin(sse, axis=1)
    r = np.arange(len(c))
    return A[r, j], taus[j]


def analyse(t: np.ndarray, X: np.ndarray, H: tuple, reps: int, rng,
            bar_hours: float) -> dict:
    """Full read of one signal: CAR curve, decay fit, bootstrap CIs."""
    S, N = week_sums(t, X)
    car = S.sum(axis=0) / np.maximum(N.sum(axis=0), 1)
    B = boot_car(S, N, reps, rng)
    var = B.var(axis=0) + 1e-18
    w = 1.0 / var
    h = np.asarray(H, float) * bar_hours
    A0, tau0 = fit_decay(car, h, w)
    Ab, taub = fit_decay(B, h, w)
    best = B.max(axis=1)                       # selection-aware best horizon
    q = lambda x: [float(np.quantile(x, 0.025)), float(np.quantile(x, 0.975))]  # noqa: E731
    return {"events": int(N[:, 0].sum()), "weeks": int(S.shape[0]),
            "h_hours": h.tolist(), "car_bps": (car * 1e4).tolist(),
            "car_ci_bps": [[a * 1e4, b * 1e4] for a, b in
                           zip(np.quantile(B, 0.025, axis=0), np.quantile(B, 0.975, axis=0), strict=True)],
            "A_bps": float(A0[0] * 1e4), "A_ci_bps": [x * 1e4 for x in q(Ab)],
            "tau_h": float(tau0[0]), "tau_ci_h": q(taub),
            "mu0_bps_per_h": float(A0[0] * 1e4 / tau0[0]),
            "p_A_le_0": float((Ab <= 0).mean()),
            "p_A_le_2c": {str(c): float((Ab * 1e4 <= c).mean()) for c in TWO_C_SENS},
            "best_h_car_ci_bps": [x * 1e4 for x in q(best)],
            "_A_boot": Ab}


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, run = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


# =============================================================== signals
def _sign(x):
    return np.sign(np.nan_to_num(x))


def rolling_std_past(r: np.ndarray, n: int) -> np.ndarray:
    """std of r[t-n .. t-1] (excludes t) - past only."""
    out = np.full(len(r), np.nan)
    c1 = np.concatenate([[0.0], np.cumsum(np.nan_to_num(r))])
    c2 = np.concatenate([[0.0], np.cumsum(np.nan_to_num(r) ** 2)])
    for_t = np.arange(len(r))
    lo = for_t - n
    ok = lo >= 0
    s1 = c1[for_t[ok]] - c1[lo[ok]]
    s2 = c2[for_t[ok]] - c2[lo[ok]]
    out[ok] = np.sqrt(np.maximum(s2 / n - (s1 / n) ** 2, 0) * n / (n - 1))
    return out


def rolling_quantile_past(x: np.ndarray, n: int, q: float) -> np.ndarray:
    import pandas as pd
    return pd.Series(x).shift(1).rolling(n, min_periods=n).quantile(q).to_numpy()


def panel_signals(lp: dict, vol: dict, tb: dict, common_t: np.ndarray) -> dict:
    """{name: {asset: s array}} on each asset's own hourly grid. Every value
    at t uses bars <= t only (pinned by a poisoned-future test)."""
    out = {k: {} for k in ("tsmom_168", "tsmom_24", "rev_large", "flow_rev", "xs_mom_168")}
    for a, x in lp.items():
        r1 = np.concatenate([[np.nan], np.diff(x)])
        for L, name in ((168, "tsmom_168"), (24, "tsmom_24")):
            s = np.zeros(len(x))
            s[L:] = _sign(x[L:] - x[:-L])
            out[name][a] = s
        sd = rolling_std_past(r1, 168)
        big = np.abs(r1) > 2 * sd
        out["rev_large"][a] = np.where(big, -_sign(r1), 0.0)
        v = vol[a]
        imb = np.where(v > 0, (2 * tb[a] - v) / np.where(v > 0, v, 1), 0.0)
        thr = rolling_quantile_past(np.abs(imb), 720, 0.9)
        driven = (_sign(r1) == _sign(imb)) & (np.abs(imb) > thr)
        out["flow_rev"][a] = np.where(driven, -_sign(imb), 0.0)
    # cross-sectional momentum on the common hourly grid
    names = sorted(lp)
    idx = {a: {int(tt): i for i, tt in enumerate(common_t[a])} for a in names}
    all_t = sorted(set().union(*[set(idx[a]) for a in names]))
    for a in names:
        out["xs_mom_168"][a] = np.zeros(len(lp[a]))
    for tt in all_t:
        rets = {}
        for a in names:
            i = idx[a].get(tt)
            if i is not None and i >= 168:
                rets[a] = lp[a][i] - lp[a][i - 168]
        if len(rets) < 6:
            continue
        order = sorted(rets, key=lambda k: rets[k])
        third = len(order) // 3
        for a in order[:third]:
            out["xs_mom_168"][a][idx[a][tt]] = -1.0
        for a in order[-third:]:
            out["xs_mom_168"][a][idx[a][tt]] = 1.0
    return out


def signed_events(t: np.ndarray, s: np.ndarray, F: np.ndarray,
                  D: np.ndarray) -> tuple:
    """Event rows where s != 0: drift-adjusted signed forward returns."""
    m = (s != 0) & np.isfinite(D[:, 0])
    return t[m], s[m, None] * (F[m] - D[m])


# =========================================================== panel run
def run_panel(cache: Path, reps: int, rng, null: str | None = None,
              plant: tuple | None = None, data: dict | None = None,
              null_seed: int = 0) -> dict:
    data = data or {a: binance_klines(f"{a}USDT", "1h", PANEL_MONTHS, cache)
                    for a in PANEL_UNIVERSE}
    lp, vol, tb, tt = {}, {}, {}, {}
    nrng = np.random.default_rng(SEED + 101 + null_seed)
    for a, d in data.items():
        if len(d["close"]) < 2000:
            continue
        x = np.log(d["close"])
        if null == "gbm":
            r = np.diff(x)
            x = np.concatenate([[x[0]], x[0] + np.cumsum(nrng.normal(0, r.std(), len(r)))])
        elif null == "shuffle":
            r = np.diff(x)
            x = np.concatenate([[x[0]], x[0] + np.cumsum(nrng.permutation(r))])
        lp[a], vol[a], tb[a], tt[a] = x, d["vol"], d["taker_buy"], d["t"]
    sig = panel_signals(lp, vol, tb, tt)
    res = {}
    for name, per in sig.items():
        T_, X_ = [], []
        for a, s in per.items():
            F = forward(lp[a], H_PANEL)
            D = expanding_drift(lp[a], H_PANEL, 720)
            te, xe = signed_events(tt[a], s, F, D)
            if plant is not None and name == "tsmom_168":
                A_true, tau_true = plant
                xe = xe + A_true * (1 - np.exp(-np.asarray(H_PANEL, float) / tau_true))
            T_.append(te)
            X_.append(xe)
        t_all = np.concatenate(T_)
        X_all = np.vstack(X_)
        r = analyse(t_all, X_all, H_PANEL, reps, rng, 1.0)
        mid = np.median(t_all)
        r["halves"] = {}
        for half, m in (("first", t_all < mid), ("second", t_all >= mid)):
            rh = analyse(t_all[m], X_all[m], H_PANEL, max(reps // 4, 200), rng, 1.0)
            r["halves"][half] = {"A_bps": rh["A_bps"], "A_ci_bps": rh["A_ci_bps"],
                                 "weeks": rh["weeks"]}
        res[name] = r
    res["_assets"] = sorted(lp)
    res["_units"] = {a: data[a]["units"] for a in data}
    return res


# ============================================================= bot run
def entry_index(bar_open_t: np.ndarray, signal_ts: np.ndarray) -> np.ndarray:
    """Index of the bar the bot ACTED on: the bar that OPENS at signal_ts
    (its close, bar_open + 300 s, is the entry price).

    AMENDMENT 2 (2026-10-02, instrument defect found in the first full run,
    disclosed): signal_ts is a bar-OPEN stamp (Kraken OHLC convention). The
    first aligner priced each row at the close of the bar ENDING at
    signal_ts - one bar early - and credited the bot with a move it had
    already seen (+8 bps at tau 0.1 h, all in the first bar). Evidence: the
    bot's own entry_price matches the close of the bar STARTING at signal_ts
    3-6x better (median |gap| BTC 27.8 -> 9.2, ETH 13.8 -> 4.4, SOL 31.2 ->
    6.0 bps). Pinned by tests/test_alpha_decay_report.py."""
    return np.searchsorted(bar_open_t, signal_ts, side="right") - 1


def load_bot_rows(cache: Path) -> tuple:
    """Align every signal_history label row to independent Binance 5m bars.
    Returns (rows dict, reconcile line, bars). A row is priced at the CLOSE
    of the last bar completed at or before its signal_ts (data the bot could
    have seen); a row more than 15 min past the last bar is outside data."""
    import pandas as pd
    from core.cohort import reconcile
    sh = pd.read_csv(ROOT / "outputs" / "signal_history.csv", low_memory=False)
    n_rows = len(sh)
    dir_cols = sorted(c for c in sh.columns if c.endswith("_dir") and c != "direction")
    sig_ts = to_seconds(sh["signal_ts"].to_numpy())[0]
    bars, unavailable = {}, []
    for a in sorted(sh["asset"].dropna().unique()):
        d = binance_klines(f"{a}USDT", "5m", BOT_MONTHS, cache)
        if len(d["close"]) < 1000:
            unavailable.append(a)
            continue
        bars[a] = d
    buckets = {"used": 0, "asset_not_on_binance": 0, "outside_price_data": 0,
               "no_direction": 0}
    T, U, DIR, ASSET, SRC, CONF, ALIGN = [], [], [], [], [], [], []
    FEAT = {c: [] for c in dir_cols}
    asset = sh["asset"].to_numpy()
    direction = sh["direction"].to_numpy(float)
    for a in sorted(set(asset)):
        rows = np.where(asset == a)[0]
        if a not in bars:
            buckets["asset_not_on_binance"] += len(rows)
            continue
        d = bars[a]
        lp = np.log(d["close"])
        F = forward(lp, H_BOT)
        D = expanding_drift(lp, H_BOT, 288 * 14)
        j_all = entry_index(d["t"], sig_ts[rows])
        for r, j in zip(rows, j_all, strict=True):
            dr = direction[r]
            if not np.isfinite(dr) or dr == 0:
                buckets["no_direction"] += 1
                continue
            if j < 0 or sig_ts[r] - d["t"][j] > 900:
                buckets["outside_price_data"] += 1
                continue
            buckets["used"] += 1
            T.append(sig_ts[r])
            U.append(F[j] - D[j])
            DIR.append(float(np.sign(dr)))
            ASSET.append(a)
            SRC.append(sh["source"].iat[r])
            CONF.append(float(sh["gate_confidence"].iat[r]))
            for c in dir_cols:
                FEAT[c].append(float(sh[c].iat[r]) if pd.notna(sh[c].iat[r]) else 0.0)
            ep = float(sh["entry_price"].iat[r])
            if ep > 0:
                ALIGN.append(abs(math.log(ep / d["close"][j])) * 1e4)
    import pandas as pd
    mk = {}
    for a, d in bars.items():
        lp = np.log(d["close"])
        mk[a] = pd.DataFrame(forward(lp, H_BOT) - expanding_drift(lp, H_BOT, 288 * 14),
                             index=d["t"])
    mkt = pd.concat(mk.values()).groupby(level=0).mean()
    Tn = np.array(T)
    UM = mkt.reindex([float(x) for x in _bar_open_of(Tn, bars, ASSET)]).to_numpy()
    rows = {"t": Tn, "U": np.array(U), "UM": UM, "dir": np.array(DIR),
            "asset": np.array(ASSET), "src": np.array(SRC), "conf": np.array(CONF),
            "feat": {c: np.array(v) for c, v in FEAT.items()},
            "align_bps": np.array(ALIGN), "unavailable": unavailable}
    return rows, reconcile(n_rows, buckets)["line"]


def _bar_open_of(t: np.ndarray, bars: dict, assets: list) -> list:
    out = []
    for tt, a in zip(t, assets, strict=True):
        bt = bars[a]["t"]
        out.append(bt[entry_index(bt, np.array([tt]))[0]])
    return out


def _with_halves(t, X, H, reps, rng, bar_h) -> dict:
    r = analyse(t, X, H, reps, rng, bar_h)
    mid = np.median(t)
    r["halves"] = {}
    for half, m in (("first", t < mid), ("second", t >= mid)):
        rh = analyse(t[m], X[m], H, max(reps // 4, 200), rng, bar_h)
        r["halves"][half] = {"A_bps": rh["A_bps"], "A_ci_bps": rh["A_ci_bps"],
                             "weeks": rh["weeks"]}
    return r


def run_bot(cache: Path, reps: int, rng, audit: Path | None) -> dict:
    rows, rec = load_bot_rows(cache)
    t, U, dr = rows["t"], rows["U"], rows["dir"]
    X = dr[:, None] * U                                   # bot-direction-signed
    cand = rows["src"] == "candidate"
    conf = rows["conf"]
    hi = cand & (conf >= np.nanquantile(conf[cand], 2 / 3))
    al = rows["align_bps"]
    res = {"reconcile": rec, "unavailable_assets": rows["unavailable"],
           "alignment_bps_median": float(np.median(al)) if len(al) else None,
           "alignment_bps_p95": float(np.quantile(al, 0.95)) if len(al) else None}
    XR = dr[:, None] * (U - rows["UM"])                    # market-relative
    for name, m in (("B1_all_candidates", cand), ("B2_live", rows["src"] == "live"),
                    ("B3_top_confidence", hi)):
        if m.sum() < 30:
            res[name] = {"events": int(m.sum()), "note": "too few"}
            continue
        res[name] = _with_halves(t[m], X[m], H_BOT, reps, rng, 5 / 60)
        ok = m & np.isfinite(XR[:, 0])
        res[name + "_mkt_rel"] = _with_halves(t[ok], XR[ok], H_BOT, reps, rng, 5 / 60)
    expl, pv = {}, {}
    for c, v in rows["feat"].items():
        s = np.sign(v)
        mm = s != 0
        if mm.sum() < 200:
            continue
        r = analyse(t[mm], s[mm, None] * U[mm], H_BOT, max(reps // 4, 200), rng, 5 / 60)
        expl[c] = {"events": r["events"], "weeks": r["weeks"], "A_bps": r["A_bps"],
                   "A_ci_bps": r["A_ci_bps"], "tau_h": r["tau_h"]}
        pv[c] = min(1.0, 2 * min(r["p_A_le_0"], 1 - r["p_A_le_0"]))
    hp = holm(pv) if pv else {}
    for c in expl:
        expl[c]["p_holm_two_sided"] = hp[c]
    res["exploratory_features"] = expl
    cv = {}
    for a in ("BTC", "ETH"):
        mm = cand & (rows["asset"] == a)
        if mm.sum() < 30:
            continue
        cb = coinbase_5m(f"{a}-USD", float(t.min()) - 30 * 86400,
                         float(t.max()) + 4 * 86400, cache)
        if len(cb["close"]) < 1000:
            cv[a] = {"note": "coinbase data unavailable"}
            continue
        clp = np.log(cb["close"])
        cU = forward(clp, H_BOT) - expanding_drift(clp, H_BOT, 288 * 14)
        j = entry_index(cb["t"], t[mm])
        ok = (j >= 0) & (t[mm] - cb["t"][np.maximum(j, 0)] <= 900)
        rb = analyse(t[mm][ok], dr[mm][ok, None] * cU[j[ok]], H_BOT,
                     max(reps // 4, 200), rng, 5 / 60)
        rn = analyse(t[mm][ok], X[mm][ok], H_BOT, max(reps // 4, 200), rng, 5 / 60)
        cv[a] = {"events": int(ok.sum()), "binance_A_bps": rn["A_bps"],
                 "coinbase_A_bps": rb["A_bps"],
                 "binance_car_bps": rn["car_bps"], "coinbase_car_bps": rb["car_bps"]}
    res["cross_venue"] = cv
    if audit is not None and audit.exists():
        from collections import Counter

        from core.cohort import fp_at, fp_timeline
        tl = fp_timeline(audit)
        res["cohorts_pooled_disclosed"] = dict(Counter(fp_at(x, tl) for x in t).most_common())
    return res


# ============================================================== controls
def controls(cache: Path, reps: int, rng, n_null: int) -> dict:
    data = {a: binance_klines(f"{a}USDT", "1h", PANEL_MONTHS, cache) for a in PANEL_UNIVERSE}
    out = {}
    for kind in ("gbm", "shuffle"):
        fp, rows = 0, []
        for k in range(n_null):
            r = run_panel(cache, max(reps // 4, 200), np.random.default_rng(1000 + k),
                          null=kind, data=data, null_seed=k)
            for name in ("tsmom_168", "tsmom_24", "rev_large", "flow_rev", "xs_mom_168"):
                lo = r[name]["A_ci_bps"][0]
                rows.append((name, r[name]["A_bps"], lo))
                fp += lo > 0
        out[kind] = {"tests": len(rows), "false_positives_A_gt_0": fp,
                     "rate": fp / max(len(rows), 1),
                     "A_bps_mean": float(np.mean([x[1] for x in rows]))}
    # planted: known A, tau added to the null forward returns of tsmom_168
    A_true, tau_true = 0.0060, 24.0
    r = run_panel(cache, reps, rng, null="gbm", plant=(A_true, tau_true), data=data)
    p = r["tsmom_168"]
    out["planted"] = {"A_true_bps": A_true * 1e4, "tau_true_h": tau_true,
                      "A_hat_bps": p["A_bps"], "A_ci_bps": p["A_ci_bps"],
                      "tau_hat_h": p["tau_h"], "tau_ci_h": p["tau_ci_h"],
                      "recovered": p["A_ci_bps"][0] <= A_true * 1e4 <= p["A_ci_bps"][1]}
    return out


# ================================================================== main
def _verdict(r: dict, hp_exist: float, hp_trade: float) -> str:
    lo = r["A_ci_bps"][0]
    halves = r.get("halves", {})
    both = all(h["A_bps"] > TWO_C for h in halves.values()) if halves else False
    if lo > TWO_C and both and hp_trade < ALPHA:
        return "TRADEABLE AS TRIPS"
    if hp_exist < ALPHA and all(h["A_bps"] > 0 for h in halves.values()):
        return "EDGE EXISTS, BELOW ROUND TRIP"
    return "NO EDGE"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--reps", type=int, default=REPS)
    ap.add_argument("--nulls", type=int, default=10)
    ap.add_argument("--out", default=None)
    ap.add_argument("--skip-bot", action="store_true")
    ap.add_argument("--skip-controls", action="store_true")
    args = ap.parse_args(argv)
    out_dir = Path(args.out) if args.out else ROOT / "outputs" / "reports" / "alpha_decay"
    cache = out_dir / "cache"
    rng = np.random.default_rng(SEED)
    t0 = time.time()
    with cf.ThreadPoolExecutor(6) as ex:                  # warm the cache
        list(ex.map(lambda a: binance_klines(f"{a}USDT", "1h", PANEL_MONTHS, cache),
                    PANEL_UNIVERSE))
    rep = {"registered": {"two_c_bps": TWO_C, "sens": TWO_C_SENS, "reps": args.reps,
                          "seed": SEED, "alpha": ALPHA, "h_panel": H_PANEL,
                          "h_bot_5m": H_BOT, "universe": PANEL_UNIVERSE,
                          "panel_months": PANEL_MONTHS}}
    rep["controls"] = None if args.skip_controls else controls(cache, args.reps, rng, args.nulls)
    panel = run_panel(cache, args.reps, rng)
    names = [k for k in panel if not k.startswith("_")]
    he = holm({k: panel[k]["p_A_le_0"] for k in names})
    ht = holm({k: panel[k]["p_A_le_2c"][str(TWO_C)] for k in names})
    for k in names:
        panel[k]["p_holm_exists"], panel[k]["p_holm_tradeable"] = he[k], ht[k]
        panel[k]["verdict"] = _verdict(panel[k], he[k], ht[k])
    rep["panel"] = panel
    if not args.skip_bot:
        audit = ROOT / "outputs" / "imported_sessions" / "pc-live" / "audit.jsonl"
        bot = run_bot(cache, args.reps, rng, audit)
        bn = [k for k in bot if k.startswith("B") and "A_bps" in bot[k]]  # incl. _mkt_rel
        he = holm({k: bot[k]["p_A_le_0"] for k in bn})
        ht = holm({k: bot[k]["p_A_le_2c"][str(TWO_C)] for k in bn})
        for k in bn:
            bot[k]["p_holm_exists"], bot[k]["p_holm_tradeable"] = he[k], ht[k]
            bot[k]["verdict"] = _verdict(bot[k], he[k], ht[k])
        rep["bot"] = bot
    rep["secs"] = time.time() - t0
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"alpha_decay_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"
    path.write_text(json.dumps(_strip(rep), indent=1, default=_json), encoding="utf-8")
    _print(rep)
    print(f"wrote {path}")
    return 0


def _strip(o):
    if isinstance(o, dict):
        return {k: _strip(v) for k, v in o.items() if not str(k).startswith("_A_boot")}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def _json(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return str(o)


def _row(name: str, r: dict) -> str:
    h = r.get("halves", {})
    hs = " ".join(f"{k[:1]}:{v['A_bps']:+.1f}" for k, v in h.items())
    return (f"  {name:<20} ev {r['events']:>7} wk {r['weeks']:>4}  A {r['A_bps']:+7.1f} "
            f"[{r['A_ci_bps'][0]:+7.1f},{r['A_ci_bps'][1]:+7.1f}] bps  tau {r['tau_h']:6.1f}h "
            f"[{r['tau_ci_h'][0]:.1f},{r['tau_ci_h'][1]:.1f}]  halves {hs}  "
            f"pHolm(A>0) {r.get('p_holm_exists', float('nan')):.3f}  -> {r.get('verdict', '')}")


def _print(rep: dict) -> None:
    c = rep.get("controls")
    if c:
        print("CONTROLS (instrument first)")
        for k in ("gbm", "shuffle"):
            print(f"  null {k:<8} {c[k]['false_positives_A_gt_0']}/{c[k]['tests']} "
                  f"CIs exclude 0 upward (rate {c[k]['rate']:.3f}, expect ~0.025-0.05); "
                  f"mean A {c[k]['A_bps_mean']:+.2f} bps")
        p = c["planted"]
        print(f"  planted  A {p['A_true_bps']:.0f} bps tau {p['tau_true_h']:.0f}h -> "
              f"A^ {p['A_hat_bps']:.1f} [{p['A_ci_bps'][0]:.1f},{p['A_ci_bps'][1]:.1f}] "
              f"tau^ {p['tau_hat_h']:.1f}h  recovered={p['recovered']}")
    print(f"INDEPENDENT PANEL ({len(rep['panel']['_assets'])} assets, Binance 1h "
          f"{PANEL_MONTHS[0]}..{PANEL_MONTHS[1]}; 2c = {TWO_C:g} bps)")
    for k, r in rep["panel"].items():
        if not k.startswith("_"):
            print(_row(k, r))
    b = rep.get("bot")
    if b:
        print(f"BOT SIGNALS on independent prices: {b['reconcile']}")
        print(f"  alignment vs bot entry_price: median {b['alignment_bps_median']:.1f} bps, "
              f"p95 {b['alignment_bps_p95']:.1f} bps; not on Binance: {b['unavailable_assets']}")
        for k in ("B1_all_candidates", "B1_all_candidates_mkt_rel", "B2_live",
                  "B2_live_mkt_rel", "B3_top_confidence", "B3_top_confidence_mkt_rel"):
            if "A_bps" in b.get(k, {}):
                print(_row(k[:20], b[k]))
                print("      CAR bps " + " ".join(f"{h:g}h:{c:+.1f}" for h, c in
                                                zip(b[k]["h_hours"], b[k]["car_bps"], strict=True)))
        for a, v in b.get("cross_venue", {}).items():
            if "binance_A_bps" in v:
                print(f"  cross-venue {a}: A binance {v['binance_A_bps']:+.1f} vs coinbase "
                      f"{v['coinbase_A_bps']:+.1f} bps (n={v['events']})")
        ex = b.get("exploratory_features", {})
        print(f"  exploratory features (Holm within {len(ex)}; never a decision):")
        for c_, v in sorted(ex.items(), key=lambda kv: -kv[1]["A_bps"]):
            print(f"    {c_:<22} ev {v['events']:>6} A {v['A_bps']:+7.1f} "
                  f"[{v['A_ci_bps'][0]:+7.1f},{v['A_ci_bps'][1]:+7.1f}] tau {v['tau_h']:6.1f}h "
                  f"pHolm {v['p_holm_two_sided']:.3f}")
        if "cohorts_pooled_disclosed" in b:
            print(f"  decision cohorts pooled (signal measurement, not a cohort read): "
                  f"{b['cohorts_pooled_disclosed']}")
    print(f"({rep['secs']:.0f}s)")


if __name__ == "__main__":
    raise SystemExit(main())
