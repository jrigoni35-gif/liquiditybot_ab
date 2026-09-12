"""scripts/walkforward_lab.py - resampling statistics on the era-4 cohort.

WHY THIS EXISTS. `2026-08-22_gate_power_analysis_mintrl.md` established two
things about the accruing era-4 cohort: the GROSS edge cleared its minimum
track record length at n=10 (the cohort has 33), and the NET edge is decided
by the fee anchor rather than by more samples. Both numbers were computed
with textbook closed forms that assume INDEPENDENT, IDENTICALLY DISTRIBUTED
per-trade returns. This corpus is neither:

  * trips overlap in time (concurrency), so they share market path;
  * the sequence is serially dependent (regime clustering); and
  * the return distribution is skewed +1.25 with kurtosis 4.51.

A closed form on a dependent sample understates its own error bars. This
module answers the same questions with methods that do not assume
independence, and adds the one question the closed forms cannot express:
**how much round-trip cost can this edge actually carry before it dies?**

WHAT IT MEASURES

  WF-1  dependence structure - autocorrelation of the ordered trip sequence
        and the concurrency effective-n (two DIFFERENT dependences; both
        reported, neither conflated).
  WF-2  stationary bootstrap (Politis & Romano 1994) CIs on mean net return
        and per-trade Sharpe, at every fee anchor, swept across block
        lengths plus the Politis & White (2004) automatic pick.
  WF-3  the iid bootstrap on the same data, as the CONTRAST - the width
        difference IS the cost of pretending independence.
  WF-4  deflated Sharpe (Bailey & Lopez de Prado 2014) recomputed on
        EFFECTIVE n across a grid of trial counts.
  WF-5  COST TOLERANCE - the largest round-trip cost at which the edge
        survives, by point estimate and by bootstrap lower bound. This is
        the fee question stated as a number the venue can be compared to.
  WF-6  anchored walk-forward within the cohort - does expectancy measured
        on the early trips survive on the later ones.

WHAT IT IS NOT. Report-only, SAFE class: it reads `outputs/fills.csv`, prints,
and exits. It does not decide the era-4 gate, does not move `MIN_COHORT_N`
(a measurement standard, not a tunable), and touches no decision path. Every
number here is a statement about the SAMPLE, and the caveats section says so
in each direction.

Deterministic: fixed seed, so two runs on one corpus produce one answer. An
instrument whose verdict moves between runs cannot settle an argument.

    python scripts/walkforward_lab.py [--fills outputs/fills.csv]
                                      [--b 20000] [--seed 7] [--json]
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# E402 waived by construction: the sys.path insert above must run before
# these resolve, so that `python scripts/walkforward_lab.py` works from a
# fresh checkout without an installed package.
from ml.overfit import _norm_ppf, deflated_sharpe  # noqa: E402
from scripts.cohort_eval import (ERA4_MIN_N,  # noqa: E402
                                 cohort_effective_n, era4_trips)

# Fee anchors. The configured stack is what the engine decides AND books at;
# the T1 rows are Kraken's published bottom tier under the two realistic fill
# mixes. The multiplier is (true stack / configured stack) applied to the
# BOOKED fee of each trip, so it rescales measurement rather than assuming a
# per-trade cost. FEE-3 (one read-only TradeVolume call) is what would
# replace "published" with "measured" here.
# The hypothetical-mix multipliers are EXACT ratios of published-tier
# stacks over the configured stack: both-legs-maker is 80/50 and
# maker-in/taker-out is 120/65.
#
# "T1 measured mix" is different in kind: it is the POPULATION-average
# repricing ratio from the exact per-leg count (448 maker + 674 taker
# fills; booked $384.18 -> true $760.13, dc107ce3, 2026-08-23) - a
# measurement, not a scenario. Applied here as a uniform per-trip
# multiplier it is still approximate (each trip's own maker/taker mix
# varies around the population average); the exact per-trip repricing
# lives in cohort_eval's true-fee section. Tier provenance: first-party
# fetch of Kraken's published schedule 2026-08-22
# (scripts/cost_attribution.py:82-90) - the ACCOUNT row via TradeVolume
# (OM-080/FEE-3) remains unfired.
FEE_ANCHORS = (
    ("configured 25/40", 1.0),
    ("T1 both-maker 40/40", 80.0 / 50.0),
    ("T1 measured mix x1.979", 760.13 / 384.18),
    ("T1 maker-in/taker-out", 120.0 / 65.0),
)


# ---------------------------------------------------------------------------
# corpus
# ---------------------------------------------------------------------------
def resolve_fills(explicit: "str | None") -> "Path | None":
    """The live ledger if present, else the newest imported bundle.

    A cloud clone has no `outputs/fills.csv` - the PC owns it and it arrives
    through `session_import`. Falling back to the bundle keeps the instrument
    runnable off-box; the resolved path is PRINTED on every run, because an
    instrument that silently changes corpus is the failure mode this repo
    keeps rediscovering.
    """
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    live = ROOT / "outputs" / "fills.csv"
    if live.exists():
        return live
    cands = sorted((ROOT / "outputs" / "imported_sessions").glob("*/fills.csv"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def trip_series(trips: list) -> dict:
    """Time-ordered gross / fee / net arrays, in percent of entry notional.

    fee = gross - net by construction in `era4_trips`, so the fee series is
    the BOOKED cost, not a reconstruction from a fee schedule. That matters:
    rescaling a booked fee is measurement; assuming one is not.
    """
    ordered = sorted(trips, key=lambda t: t["t"])
    gross = np.array([t["gross_pct"] for t in ordered], dtype=float)
    net = np.array([t["net_pct"] for t in ordered], dtype=float)
    return {"t": np.array([t["t"] for t in ordered], dtype=float),
            "gross": gross, "net": net, "fee": gross - net, "n": len(ordered)}


def net_at(series: dict, mult: float) -> np.ndarray:
    return series["gross"] - mult * series["fee"]


# ---------------------------------------------------------------------------
# WF-1  dependence structure
# ---------------------------------------------------------------------------
def autocorr(x: np.ndarray, max_lag: int) -> list:
    """Sample autocorrelation, biased (1/n) estimator - the one the
    Politis-White block selector is defined against."""
    n = x.size
    if n < 3:
        return []
    xc = x - x.mean()
    denom = float(np.dot(xc, xc))
    if denom <= 0:
        return [0.0] * max_lag
    return [float(np.dot(xc[:n - k], xc[k:]) / denom)
            for k in range(1, min(max_lag, n - 1) + 1)]


def dependence(series: dict, trips: list) -> dict:
    """Two dependences, deliberately not merged.

    SEQUENTIAL dependence is autocorrelation along the close-ordered trip
    series - what the stationary bootstrap resamples around. CONCURRENCY is
    overlap of open intervals - what average-uniqueness effective-n measures.
    They are different quantities and a corpus can have either without the
    other; reporting one number for both is how a sample gets counted twice.
    """
    net = series["net"]
    lags = autocorr(net, max_lag=min(10, max(1, series["n"] // 3)))
    # 2/sqrt(n) is the Bartlett white-noise band; at n=33 it is +/-0.35, i.e.
    # this corpus cannot resolve modest autocorrelation at all. Say so rather
    # than reading a point estimate inside the band as structure.
    band = 2.0 / math.sqrt(series["n"]) if series["n"] > 0 else float("inf")
    return {"lags": [round(v, 4) for v in lags],
            "bartlett_band": round(band, 4),
            "any_outside_band": bool(any(abs(v) > band for v in lags)),
            "concurrency": cohort_effective_n(trips)}


# ---------------------------------------------------------------------------
# WF-2/3  bootstraps
# ---------------------------------------------------------------------------
def _flat_top(t: float) -> float:
    """Politis-White flat-top lag window."""
    a = abs(t)
    if a <= 0.5:
        return 1.0
    if a <= 1.0:
        return 2.0 * (1.0 - a)
    return 0.0


def politis_white_block(x: np.ndarray) -> dict:
    """Automatic expected block length for the STATIONARY bootstrap.

    Politis & White (2004). Implemented for the STATIONARY bootstrap only:
    the flat-top lag window, the 2*sqrt(log10(n)/n) correlation threshold,
    and D_SB = 2*g(0)^2. The circular-block variant uses a different
    constant and is deliberately NOT implemented here rather than guessed
    at - one selector, stated, is worth more than two half-remembered ones.

    Returns b_opt AND the intermediates, because at this cohort size the
    selector is itself estimated from a sample too small to trust: the
    honest use of it is as ONE point in the WF-2 sweep, not as the answer.
    """
    n = x.size
    if n < 8:
        return {"available": False, "reason": f"n={n} too small"}
    xc = x - x.mean()
    # autocovariances R(0..M_max)
    kn = max(5, math.ceil(math.log10(max(n, 10))))
    m_max = math.ceil(math.sqrt(n)) + kn
    m_max = min(m_max, n - 2)
    rr = [float(np.dot(xc[:n - k], xc[k:]) / n) for k in range(m_max + 1)]
    if rr[0] <= 0:
        return {"available": False, "reason": "degenerate variance"}
    rho = [v / rr[0] for v in rr]
    thresh = 2.0 * math.sqrt(math.log10(n) / n)
    m_hat = None
    for m in range(1, m_max + 1):
        window = [abs(rho[m + k]) for k in range(1, kn + 1) if m + k <= m_max]
        if window and all(v < thresh for v in window):
            m_hat = m
            break
    if m_hat is None:
        m_hat = m_max
    big_m = min(2 * m_hat, m_max)
    g_hat = 0.0
    g0 = 0.0
    for k in range(-big_m, big_m + 1):
        lam = _flat_top(k / big_m) if big_m > 0 else (1.0 if k == 0 else 0.0)
        r = rr[abs(k)]
        g_hat += lam * abs(k) * r
        g0 += lam * r
    d_sb = 2.0 * g0 ** 2
    if d_sb <= 0 or g_hat == 0.0:
        b_opt = 1.0
    else:
        b_opt = ((2.0 * g_hat ** 2 / d_sb) ** (1.0 / 3.0)) * n ** (1.0 / 3.0)
    b_cap = max(1.0, min(3.0 * math.sqrt(n), n / 3.0))
    return {"available": True, "m_hat": m_hat, "M": big_m,
            "g_hat": round(g_hat, 6), "g0": round(g0, 6),
            "b_raw": round(float(b_opt), 3),
            "b_opt": round(float(min(max(b_opt, 1.0), b_cap)), 3),
            "b_cap": round(float(b_cap), 3),
            "under_powered": bool(n < 100)}


def sb_indices(n: int, b: float, reps: int, rng) -> np.ndarray:
    """Stationary-bootstrap index matrix (reps x n), Politis-Romano 1994.

    Geometric block lengths with mean b, circular wrap. b=1 degenerates to
    the iid bootstrap exactly, which is what makes WF-3 a controlled
    contrast rather than a second implementation.
    """
    p = 1.0 / max(b, 1.0)
    idx = np.empty((reps, n), dtype=np.int64)
    starts = rng.integers(0, n, size=(reps, n))
    newblock = rng.random((reps, n)) < p
    idx[:, 0] = starts[:, 0]
    for j in range(1, n):
        cont = (idx[:, j - 1] + 1) % n
        idx[:, j] = np.where(newblock[:, j], starts[:, j], cont)
    return idx


def _sr(x: np.ndarray) -> float:
    sd = float(x.std(ddof=1)) if x.size > 1 else 0.0
    return float(x.mean() / sd) if sd > 0 else 0.0


def bootstrap_ci(x: np.ndarray, b: float, reps: int, seed: int,
                 alpha: float = 0.05) -> dict:
    """Percentile CIs on mean and per-trade Sharpe under the stationary
    bootstrap with expected block length b."""
    n = x.size
    if n < 3:
        return {"available": False, "n": n}
    rng = np.random.default_rng(seed)
    idx = sb_indices(n, b, reps, rng)
    draws = x[idx]
    means = draws.mean(axis=1)
    sds = draws.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        srs = np.where(sds > 0, means / sds, 0.0)
    lo, hi = 100.0 * alpha / 2.0, 100.0 * (1.0 - alpha / 2.0)
    return {"available": True, "n": n, "b": round(float(b), 3), "reps": reps,
            "mean": round(float(x.mean()), 6),
            "mean_lo": round(float(np.percentile(means, lo)), 6),
            "mean_hi": round(float(np.percentile(means, hi)), 6),
            "p_mean_le_0": round(float((means <= 0).mean()), 4),
            "sr": round(_sr(x), 6),
            "sr_lo": round(float(np.percentile(srs, lo)), 6),
            "sr_hi": round(float(np.percentile(srs, hi)), 6)}


def concurrency_deflated(ci: dict, se_inflation: float,
                        alpha: float = 0.05) -> dict:
    """The bootstrap interval widened for CONCURRENCY, approximately.

    WF-1 measures two dependences. The stationary bootstrap absorbs the
    sequential one; it cannot see the concurrent one, because overlapping
    trips are separate ROWS however you resample them. Refusing to compose
    them leaves the reader to multiply in their head, which they will do
    wrongly; composing them exactly needs a joint model this corpus cannot
    support. So: take the bootstrap interval's implied SE, inflate it by
    sqrt(n / n_eff) - the same factor `cohort_effective_n` reports - and
    re-form a NORMAL interval.

    This is an APPROXIMATION and it is labelled one everywhere it is
    printed. It assumes the two deflations are independent and that the
    resampled mean is near-normal (the CLT is kind to means even when the
    underlying is skewed, which is the only reason this is defensible at
    n=33). It always WIDENS, never narrows, so its error is in the
    conservative direction.
    """
    if not ci.get("available") or se_inflation <= 0:
        return {"available": False}
    z = _norm_ppf(1.0 - alpha / 2.0)
    se_boot = (ci["mean_hi"] - ci["mean_lo"]) / (2.0 * z)
    half = z * se_boot * se_inflation
    return {"available": True, "se_boot": round(se_boot, 6),
            "se_inflation": round(float(se_inflation), 4),
            "mean": ci["mean"],
            "mean_lo": round(ci["mean"] - half, 6),
            "mean_hi": round(ci["mean"] + half, 6),
            "approximate": True}


def bootstrap_block(series: dict, reps: int, seed: int,
                    se_inflation: float = 1.0) -> dict:
    """WF-2 + WF-3: every fee anchor x {iid, automatic, sweep},
    plus the concurrency-deflated interval on the automatic pick."""
    out = {"anchors": [], "block_selector": {}}
    for label, mult in FEE_ANCHORS:
        x = net_at(series, mult)
        pw = politis_white_block(x)
        out["block_selector"][label] = pw
        b_auto = pw.get("b_opt", 1.0) if pw.get("available") else 1.0
        sweep = []
        for b in (1.0, 2.0, 3.0, 5.0, float(b_auto)):
            ci = bootstrap_ci(x, b, reps, seed)
            ci["kind"] = ("iid" if b <= 1.0 else
                          "auto" if abs(b - b_auto) < 1e-9 else "sweep")
            sweep.append(ci)
        auto_ci = next((c for c in sweep if c["kind"] == "auto"), sweep[0])
        out["anchors"].append({"anchor": label, "mult": round(mult, 5),
                               "mean": round(float(x.mean()), 6),
                               "sr": round(_sr(x), 6),
                               "b_auto": b_auto, "sweep": sweep,
                               "deflated": concurrency_deflated(
                                   auto_ci, se_inflation)})
    gross_ci = bootstrap_ci(series["gross"], 1.0, reps, seed)
    gpw = politis_white_block(series["gross"])
    gauto = bootstrap_ci(series["gross"],
                         gpw.get("b_opt", 1.0) if gpw.get("available") else 1.0,
                         reps, seed)
    out["gross"] = {"iid": gross_ci, "selector": gpw, "auto": gauto,
                    "deflated": concurrency_deflated(gauto, se_inflation)}
    return out


# ---------------------------------------------------------------------------
# WF-4  deflated Sharpe on effective n
# ---------------------------------------------------------------------------
def _moments(x: np.ndarray) -> tuple:
    n = x.size
    if n < 3:
        return 0.0, 0.0, 3.0
    sd = float(x.std(ddof=1))
    if sd <= 0:
        return 0.0, 0.0, 3.0
    z = (x - x.mean()) / sd
    return _sr(x), float((z ** 3).mean()), float((z ** 4).mean())


def dsr_grid(series: dict, eff_n: float, trials=(1, 7, 25, 100)) -> dict:
    """DSR at nominal AND effective n, across a grid of trial counts.

    The trial count is NOT measured anywhere in this repo - there is no
    ledger of how many strategy configurations were tried before this one.
    Picking a number would be inventing evidence, so the grid is the answer
    and "we cannot measure N" is the finding (docket: a trials ledger).
    Effective n enters exactly where it belongs: DSR's track-length term.
    """
    rows = []
    for label, mult in (("gross", None), *FEE_ANCHORS):
        x = series["gross"] if mult is None else net_at(series, mult)
        sr, sk, ku = _moments(x)
        for n_label, n_used in (("nominal", float(series["n"])),
                                ("effective", float(eff_n))):
            for tr in trials:
                d = deflated_sharpe(sr, round(n_used), skew=sk,
                                    kurtosis=ku, n_trials=tr)
                rows.append({"anchor": label, "n_basis": n_label,
                             "n": round(n_used), "trials": tr,
                             "sr": round(sr, 4),
                             "dsr": (round(d["dsr"], 4)
                                     if d.get("dsr") is not None else None),
                             "sr0": (round(d.get("sr0_threshold") or 0.0, 4))})
    return {"rows": rows, "trials_measured": False,
            "note": "trial count is unmeasured in this repo; grid, not pick"}


def mintrl_grid(series: dict, eff_n: float, alpha: float = 0.05) -> dict:
    """WF-4b: minimum track record length, read against BOTH sample sizes.

    MinTRL = 1 + [1 - g3*SR + (g4-1)/4*SR^2] * (Z_alpha / SR)^2   (SR* = 0)

    The tranche-1 memo computed this on nominal n and reported the gross
    edge as SETTLED (MinTRL 10, cohort 33). That reading is only valid if
    the 33 trips carry 33 trips' worth of information. WF-1 measures that
    they carry ~10, so the SAME formula against the SAME cohort has to be
    re-read against effective n - and at that point the gross leg is not a
    comfortable clearance, it is a coin-flip margin. This function prints
    both so the comparison cannot be made accidentally in one direction.
    """
    z = _norm_ppf(1.0 - alpha)
    rows = []
    for label, mult in (("gross", None), *FEE_ANCHORS):
        x = series["gross"] if mult is None else net_at(series, mult)
        sr, sk, ku = _moments(x)
        if sr <= 0:
            rows.append({"anchor": label, "sr": round(sr, 4),
                         "mintrl": None, "cleared_nominal": False,
                         "cleared_effective": False})
            continue
        bracket = max(1.0 - sk * sr + (ku - 1.0) / 4.0 * sr ** 2, 1e-9)
        mintrl = 1.0 + bracket * (z / sr) ** 2
        rows.append({"anchor": label, "sr": round(sr, 4),
                     "mintrl": round(float(mintrl), 2),
                     "cleared_nominal": bool(series["n"] >= mintrl),
                     "cleared_effective": bool(eff_n >= mintrl),
                     "margin_effective": round(float(eff_n - mintrl), 2)})
    return {"alpha": alpha, "nominal_n": series["n"],
            "effective_n": round(float(eff_n), 2), "rows": rows}


# ---------------------------------------------------------------------------
# WF-5  cost tolerance
# ---------------------------------------------------------------------------
def cost_tolerance(series: dict, reps: int, seed: int, b: float,
                   alpha: float = 0.05, se_inflation: float = 1.0) -> dict:
    """The largest round-trip cost this edge carries, two ways.

    Per trip, net(m) = gross - m*fee, so the resampled mean is linear in the
    multiplier m: mean_net_b(m) = G_b - m*F_b. That linearity is what makes
    the bootstrap-lower-bound solve exact rather than a search - for a FIXED
    resample matrix the alpha-quantile of {G_b - m*F_b} is monotone
    decreasing in m wherever the F_b are positive, so one bisection finds
    the crossing to machine precision.

    Two numbers come out, and the gap between them is the honest width of
    the fee question:
      * m_point  - where the POINT estimate of net expectancy hits zero
      * m_lower  - where the bootstrap lower bound hits zero, i.e. the
                   largest cost at which the edge is DISTINGUISHABLE from
                   zero rather than merely positive in-sample
    Both are converted to round-trip basis points against the cohort's own
    BOOKED cost, so they can be read directly against a venue fee table.
    """
    n = series["n"]
    if n < 3:
        return {"available": False, "n": n}
    fee = series["fee"]
    mean_fee = float(fee.mean())
    if mean_fee <= 0:
        return {"available": False, "reason": "non-positive booked fee"}
    booked_bps = 100.0 * mean_fee                    # percent -> bps
    m_point = float(series["gross"].mean() / mean_fee)

    rng = np.random.default_rng(seed)
    idx = sb_indices(n, b, reps, rng)
    g_b = series["gross"][idx].mean(axis=1)
    f_b = fee[idx].mean(axis=1)
    q = 100.0 * alpha

    def lower(m: float) -> float:
        return float(np.percentile(g_b - m * f_b, q))

    if lower(0.0) <= 0.0:
        m_lower = 0.0
    else:
        lo, hi = 0.0, 1.0
        # expand until the bound goes negative; f_b > 0 in every resample
        # that contains a fee-paying trip, so this terminates.
        while lower(hi) > 0.0 and hi < 1e6:
            lo, hi = hi, hi * 2.0
        if hi >= 1e6:
            m_lower = float("inf")
        else:
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                if lower(mid) > 0.0:
                    lo = mid
                else:
                    hi = mid
            m_lower = 0.5 * (lo + hi)
    # concurrency-deflated crossing: same resample matrix, but the interval
    # is re-formed as a NORMAL bound whose SE carries the sqrt(n/n_eff)
    # inflation from WF-1. Monotone decreasing in m wherever mean fee > 0,
    # so the same bisection applies. Approximate, and always stricter than
    # the percentile bound - see concurrency_deflated().
    z = _norm_ppf(1.0 - alpha / 2.0)

    def lower_defl(m: float) -> float:
        d = g_b - m * f_b
        return float(d.mean() - z * d.std(ddof=1) * se_inflation)

    if lower_defl(0.0) <= 0.0:
        m_defl = 0.0
    else:
        lo2, hi2 = 0.0, 1.0
        while lower_defl(hi2) > 0.0 and hi2 < 1e6:
            lo2, hi2 = hi2, hi2 * 2.0
        if hi2 >= 1e6:
            m_defl = float("inf")
        else:
            for _ in range(80):
                mid = 0.5 * (lo2 + hi2)
                if lower_defl(mid) > 0.0:
                    lo2 = mid
                else:
                    hi2 = mid
            m_defl = 0.5 * (lo2 + hi2)

    return {"available": True, "n": n, "b": round(float(b), 3), "reps": reps,
            "se_inflation": round(float(se_inflation), 4),
            "m_deflated": (None if m_defl == float("inf")
                           else round(float(m_defl), 4)),
            "tolerable_bps_deflated": (None if m_defl == float("inf") else
                                       round(m_defl * booked_bps, 2)),
            "booked_round_trip_bps": round(booked_bps, 2),
            "mean_gross_pct": round(float(series["gross"].mean()), 6),
            "m_point": round(m_point, 4),
            "m_lower": (None if m_lower == float("inf")
                        else round(float(m_lower), 4)),
            "tolerable_bps_point": round(m_point * booked_bps, 2),
            "tolerable_bps_lower": (None if m_lower == float("inf")
                                    else round(m_lower * booked_bps, 2)),
            "anchors": [{"anchor": a, "mult": round(m, 5),
                         "implied_bps": round(m * booked_bps, 2),
                         "under_point": bool(m < m_point),
                         "under_lower": bool(m_lower == float("inf")
                                             or m < m_lower),
                         "under_deflated": bool(m_defl == float("inf")
                                                or m < m_defl)}
                        for a, m in FEE_ANCHORS]}


# ---------------------------------------------------------------------------
# WF-6  anchored walk-forward
# ---------------------------------------------------------------------------
def anchored_walkforward(series: dict, folds: int = 4) -> dict:
    """Expectancy measured on the early trips, evaluated on the next block.

    Anchored (expanding) rather than rolling, matching the deployed
    selector's own purged expanding walk-forward. At this cohort size each
    OOS block holds a handful of trips, so the per-fold numbers are noise by
    construction; the reported quantity is the POOLED OOS mean and the
    SIGN-agreement count, which are the only things a sample this size can
    support. Reported so the degradation shape is on the record before n=50,
    not to be acted on.
    """
    n = series["n"]
    if n < 8:
        return {"available": False, "n": n}
    folds = max(2, min(folds, n // 4))
    edges = [round(i * n / folds) for i in range(folds + 1)]
    rows, oos_all = [], []
    for i in range(1, folds):
        tr_hi, te_hi = edges[i], edges[i + 1]
        if te_hi - tr_hi < 2 or tr_hi < 3:
            continue
        is_x = series["net"][:tr_hi]
        oos_x = series["net"][tr_hi:te_hi]
        oos_all.append(oos_x)
        rows.append({"fold": i, "is_n": int(is_x.size),
                     "oos_n": int(oos_x.size),
                     "is_mean": round(float(is_x.mean()), 6),
                     "oos_mean": round(float(oos_x.mean()), 6),
                     "sign_agrees": bool(np.sign(is_x.mean())
                                         == np.sign(oos_x.mean()))})
    if not rows:
        return {"available": False, "n": n, "reason": "folds too thin"}
    pooled = np.concatenate(oos_all)
    is_full = float(series["net"].mean())
    return {"available": True, "folds": rows,
            "pooled_oos_mean": round(float(pooled.mean()), 6),
            "pooled_oos_n": int(pooled.size),
            "full_sample_mean": round(is_full, 6),
            "degradation": round(float(pooled.mean()) - is_full, 6),
            "sign_agreement": f"{sum(r['sign_agrees'] for r in rows)}/"
                              f"{len(rows)}"}


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def build(fills_path: Path, reps: int, seed: int) -> dict:
    trips = era4_trips(str(fills_path))
    series = trip_series(trips)
    if series["n"] < 3:
        return {"available": False, "n": series["n"],
                "fills": str(fills_path)}
    dep = dependence(series, trips)
    eff = dep["concurrency"].get("effective_n") or float(series["n"])
    infl = dep["concurrency"].get("se_inflation") or 1.0
    if not math.isfinite(infl) or infl < 1.0:
        infl = 1.0
    boots = bootstrap_block(series, reps, seed, se_inflation=infl)
    b_auto = boots["anchors"][0]["b_auto"]
    return {"available": True, "fills": str(fills_path), "n": series["n"],
            "cohort_target": ERA4_MIN_N, "reps": reps, "seed": seed,
            "dependence": dep,
            "bootstrap": boots,
            "dsr": dsr_grid(series, eff),
            "mintrl": mintrl_grid(series, eff),
            "se_inflation": round(float(infl), 4),
            "cost_tolerance": cost_tolerance(series, reps, seed, b_auto,
                                             se_inflation=infl),
            "walkforward": anchored_walkforward(series)}


def _pct(v) -> str:
    return "n/a" if v is None else f"{v:+.4f}%"


def render(res: dict) -> None:
    if not res.get("available"):
        print(f"walkforward_lab: no cohort at {res.get('fills')} "
              f"(n={res.get('n')})")
        return
    print("WALK-FORWARD LAB - era-4 cohort resampling statistics")
    print("=" * 70)
    print(f"corpus     {res['fills']}")
    print(f"cohort     n={res['n']} of pre-registered {res['cohort_target']} "
          f"  bootstrap reps={res['reps']} seed={res['seed']}")

    dep = res["dependence"]
    print("\n[WF-1] dependence structure")
    print(f"  autocorr(net) lags 1..{len(dep['lags'])}: "
          + " ".join(f"{v:+.2f}" for v in dep["lags"]))
    _band = ("structure visible" if dep["any_outside_band"]
             else "NO lag resolvable at this n")
    print(f"  Bartlett white-noise band +/-{dep['bartlett_band']:.2f} -> "
          f"{_band}")
    c = dep["concurrency"]
    if c.get("available"):
        print(f"  concurrency: effective_n={c['effective_n']:.2f} of "
              f"{c['n']}  (mean uniqueness {c['mean_uniqueness']:.3f}, "
              f"SE inflated x{c['se_inflation']:.2f})")

    print("\n[WF-2/3] stationary bootstrap - mean net return per trip")
    print("  anchor                   b   kind    mean      95% CI"
          "                P(mean<=0)")
    g = res["bootstrap"]["gross"]["iid"]
    print(f"  {'GROSS (pre-fee)':<22} {g['b']:>4.1f} iid   {g['mean']:+.4f}%"
          f"  [{g['mean_lo']:+.4f}%, {g['mean_hi']:+.4f}%]  "
          f"{g['p_mean_le_0']:.4f}")
    for a in res["bootstrap"]["anchors"]:
        for row in a["sweep"]:
            print(f"  {a['anchor']:<22} {row['b']:>4.1f} {row['kind']:<5} "
                  f"{row['mean']:+.4f}%  [{row['mean_lo']:+.4f}%, "
                  f"{row['mean_hi']:+.4f}%]  {row['p_mean_le_0']:.4f}")

    print("\n[WF-2b] the SAME intervals widened for concurrency "
          "(approximate; always stricter)")
    gd = res["bootstrap"]["gross"].get("deflated") or {}
    if gd.get("available"):
        print(f"  {'GROSS (pre-fee)':<22} SE x{gd['se_inflation']:.2f}  "
              f"{gd['mean']:+.4f}%  [{gd['mean_lo']:+.4f}%, "
              f"{gd['mean_hi']:+.4f}%]")
    for a in res["bootstrap"]["anchors"]:
        d = a.get("deflated") or {}
        if d.get("available"):
            print(f"  {a['anchor']:<22} SE x{d['se_inflation']:.2f}  "
                  f"{d['mean']:+.4f}%  [{d['mean_lo']:+.4f}%, "
                  f"{d['mean_hi']:+.4f}%]")

    print("\n[WF-4] deflated Sharpe - nominal vs EFFECTIVE n")
    print("  anchor                  basis        n  trials      SR"
          "     SR0      DSR")
    for r in res["dsr"]["rows"]:
        if r["trials"] not in (1, 25):
            continue
        d = "n/a" if r["dsr"] is None else f"{r['dsr']:.4f}"
        print(f"  {r['anchor']:<22} {r['n_basis']:<9} {r['n']:>4} "
              f"{r['trials']:>6}  {r['sr']:+.4f}  {r['sr0']:+.4f}  {d}")
    print("  SR0 is the expected MAX Sharpe under H0 across `trials` tries.")
    print("  Trial count is UNMEASURED in this repo, and so is the trial-SR")
    print("  dispersion the deflation scales by - deflated_sharpe falls back")
    print("  to var=1/n (the null-consistent closure; it was var=SR^2 and")
    print("  inverted until 2026-09-11), which is an assumption, not a")
    print("  reading. The GRID is")
    print("  the result; any single row of it is a hypothesis about N.")

    mt = res["mintrl"]
    print("\n[WF-4b] minimum track record length - nominal vs EFFECTIVE n")
    print(f"  cohort carries n={mt['nominal_n']} trips but "
          f"n_eff={mt['effective_n']} trips' worth of information")
    print("  anchor                     SR   MinTRL(95%)  vs n   vs n_eff")
    for r in mt["rows"]:
        m = "  never" if r["mintrl"] is None else f"{r['mintrl']:>7.2f}"
        marg = ("" if r.get("margin_effective") is None
                else f"  (margin {r['margin_effective']:+.2f})")
        print(f"  {r['anchor']:<22} {r['sr']:+.4f}  {m}     "
              f"{'YES' if r['cleared_nominal'] else ' no':<5} "
              f"{'YES' if r['cleared_effective'] else ' NO'}{marg}")
    _g = next((r for r in mt["rows"] if r["anchor"] == "gross"), None)
    if _g and _g.get("mintrl") and abs(_g.get("margin_effective") or 0) < 2.0:
        print("  READ THIS CAREFULLY: the gross leg sits ON its own power")
        print("  requirement once concurrency is applied. That is not 'the")
        print("  edge failed' and it is not 'the edge is settled' - it is")
        print("  PRECISELY UNDETERMINED, and a margin this thin is noise in")
        print("  both directions. The tranche-1 memo's 'gross edge is")
        print("  established' rested on nominal n and does not survive here.")

    ct = res["cost_tolerance"]
    print("\n[WF-5] cost tolerance - how much round-trip cost the edge carries")
    if ct.get("available"):
        print(f"  booked round-trip (this cohort)      "
              f"{ct['booked_round_trip_bps']:.2f} bps")
        print(f"  mean GROSS per trip                  "
              f"{ct['mean_gross_pct']:+.4f}%")
        print(f"  point-estimate breakeven cost        "
              f"{ct['tolerable_bps_point']:.2f} bps "
              f"(x{ct['m_point']:.2f} booked)")
        lb = ("unbounded" if ct["tolerable_bps_lower"] is None
              else f"{ct['tolerable_bps_lower']:.2f} bps "
                   f"(x{ct['m_lower']:.2f} booked)")
        print(f"  bootstrap 95% lower-bound breakeven  {lb}")
        _tbd = ct.get("tolerable_bps_deflated")
        db = ("unbounded" if _tbd is None
              else "0.00 bps - the GROSS edge itself is not distinguishable "
                   "once concurrency is composed" if _tbd <= 0.0
              else f"{_tbd:.2f} bps (x{ct['m_deflated']:.2f} booked)")
        print(f"  ...same, widened for concurrency     {db}   "
              f"[approximate, SE x{ct.get('se_inflation', 1.0):.2f}]")
        print(f"  (solved on the automatic block length b={ct['b']:.1f}, "
              f"{ct['reps']} resamples)")
        for a in ct["anchors"]:
            verdict = ("SURVIVES even deflated" if a["under_deflated"]
                       else "survives the raw bound only" if a["under_lower"]
                       else "positive but INDISTINGUISHABLE"
                       if a["under_point"] else "NEGATIVE expectancy")
            print(f"    {a['anchor']:<24} {a['implied_bps']:>7.2f} bps  "
                  f"-> {verdict}")
    else:
        print(f"  unavailable: {ct.get('reason', 'n too small')}")

    wf = res["walkforward"]
    print("\n[WF-6] anchored walk-forward within the cohort")
    if wf.get("available"):
        for r in wf["folds"]:
            print(f"  fold {r['fold']}: IS n={r['is_n']:<3} "
                  f"{_pct(r['is_mean'])}  ->  OOS n={r['oos_n']:<3} "
                  f"{_pct(r['oos_mean'])}  "
                  f"{'sign holds' if r['sign_agrees'] else 'SIGN FLIPS'}")
        print(f"  pooled OOS {_pct(wf['pooled_oos_mean'])} on n="
              f"{wf['pooled_oos_n']} vs full-sample "
              f"{_pct(wf['full_sample_mean'])} "
              f"(degradation {_pct(wf['degradation'])}), "
              f"sign agreement {wf['sign_agreement']}")
        print("  at this n each fold is noise; the pooled row is the only"
              " one a sample this size supports.")
    else:
        print(f"  unavailable: {wf.get('reason', 'n too small')}")

    print("\nCAVEATS")
    print("  * Report-only. Decides no gate, moves no threshold, and does")
    print("    NOT move MIN_COHORT_N - a measurement standard, not a knob.")
    print("  * The T1 anchors rescale a BOOKED fee by Kraken's published")
    print("    bottom tier (first-party fetch 2026-08-22). 'measured mix'")
    print("    uses the exact population leg count (dc107ce3); the account")
    print("    ROW via TradeVolume (FEE-3/OM-080) is still unfired.")
    print("  * The stationary bootstrap handles SEQUENTIAL dependence only.")
    print("    WF-2b/WF-5 compose it with concurrency by a normal-SE")
    print("    approximation - conservative by construction, but an")
    print("    approximation. The raw percentile rows are the exact ones.")
    print("  * DRY_RUN fees are simulated: this is whether the MODELLED")
    print("    strategy survives live cost, not realised P&L.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fills", default=None,
                    help="fills ledger (default: outputs/fills.csv, else the "
                         "newest imported bundle)")
    ap.add_argument("--b", type=int, default=20000,
                    help="bootstrap resamples (default 20000)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args()

    path = resolve_fills(ns.fills)
    if path is None:
        print("walkforward_lab: no fills ledger found")
        return 1
    res = build(path, max(200, ns.b), ns.seed)
    if ns.json:
        print(json.dumps(res, indent=1, default=str))
        return 0
    render(res)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
