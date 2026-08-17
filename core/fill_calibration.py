"""core/fill_calibration.py — hardened dry-run fill-model calibration.

Recommends the passive-fill base probability
(order_manager.sim_fill.passive_base_prob, a.k.a. ``sf_base``) from
OBSERVED market trade-through, by inverting the sim's forward fill model.

Forward model for one resting maker order (execution/order_manager.py):
    per-poll fill prob   p = sf_base * exp(-d_bar)      d_bar = dist_bps / sigma_bps
    per-order fill prob  F = 1 - (1 - p)^n_bar          n_bar = order_life / poll_sec

2026-08-08 (owed 40): the runtime now TTL-normalizes the per-poll hazard
(_passive_poll_prob: exponent cal_life/ttl, clamped at 1.0) so the
per-ORDER F above holds AT THE CALIBRATED LIFE for any actual ttl - a 6h
order no longer compounds the 25s-calibrated hazard into certainty. The
inversion below is unchanged: it still maps a measured per-order rate at
the recorded n_bar to sf_base; sf_base keeps its calibrated meaning.
When recordings gain long-life buckets, calibrate per-TTL (XV-023 —
RESERVED in core/codes.py's XV block for that verdict; not yet a
registered member).

Given a bucket's observed per-order fill rate ``f`` (successes ``k`` in ``n``
resting orders, measured from RECORDED market trade-through — not the sim's
own fills, which would be circular), the maximum-likelihood base prob is the
inverse map ``g``:
    g(f) = clamp( [ 1 - (1 - f)^(1/n_bar) ] * exp(d_bar), 0, 1 )

Hardening (this module ships one recommendation that could bias the whole
label distribution, so it is deliberately conservative):
  * Wilson score interval quantifies sampling uncertainty and keeps the point
    estimate off the 0/1 boundary (subsumes a smoothing prior); deterministic,
    no RNG.
  * A power gate refuses (DEFERRED) below N_min resting orders or with fewer
    than E_min in either tail — never recommend from noise.
  * Only near-touch buckets (d_bar <= D_MAX) are identifiable; the inversion
    multiplies error by exp(d_bar), so far buckets are declined.
  * NO_CHANGE when the current base prob already sits inside the band.
  * Every division/power/exp is guarded; the result is finite in [0, 1] or the
    status is DEFERRED. No NaN/inf ever escapes.
  * buckets_agree() flags MODEL-MISSPECIFICATION when per-distance buckets
    disagree beyond their bands (sf_base is meant to be distance-independent).

Pure functions only — no I/O, no config, no trading behavior. scripts/
calibrate_fills.py feeds it real data and formats the report.
"""

import math
from dataclasses import dataclass

Z_95 = 1.96
N_MIN_DEFAULT = 80          # Wilson worst-case (p=0.5) half-width ~ +/-0.11
E_MIN_DEFAULT = 10          # stable-proportion floor, applied to BOTH tails
D_MAX_DEFAULT = 2.0         # near-touch only: caps inversion amp exp(d_bar) <= 7.4x
_D_OVERFLOW_CAP = 20.0      # hard exp() overflow guard (separate from D_MAX)


@dataclass(frozen=True)
class CalibrationResult:
    """One bucket's calibration verdict."""
    status: str                        # DEFERRED | NO_CHANGE | OK
    sf_base_star: float | None         # recommended base prob (point estimate)
    band: tuple[float, float] | None   # [lo, hi] recommendation band
    n: int                             # resting orders in the bucket
    k: int                             # trade-through successes
    f_hat: float | None                # Wilson-center fill rate
    d_bar: float | None                # bucket mean normalized distance
    n_bar: float | None                # mean poll attempts per order
    reason: str                        # human-/machine-readable detail


def _finite(*xs: float) -> bool:
    return all(isinstance(x, (int, float)) and math.isfinite(x) for x in xs)


def wilson_interval(k: int, n: int, z: float = Z_95) -> tuple[float, float, float]:
    """Wilson score interval for ``k`` successes in ``n`` trials.

    Returns (center, lo, hi), each in [0, 1]. The center is shrunk off the
    0/1 boundary, so an all-hit or all-miss sample never asserts certainty.
    """
    if n <= 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return (center, max(0.0, center - half), min(1.0, center + half))


def invert_base_prob(f: float, d_bar: float, n_bar: float) -> float:
    """Invert the forward fill model: observed per-order rate ``f`` -> sf_base.

    Monotone increasing in ``f``; clamped to [0, 1]; every intermediate is
    guarded so a degenerate argument yields a boundary value, never NaN/inf.
    """
    f = min(max(float(f), 0.0), 1.0)
    n_bar = max(float(n_bar), 1.0)
    d_bar = min(max(float(d_bar), 0.0), _D_OVERFLOW_CAP)
    p_poll = 1.0 - (1.0 - f) ** (1.0 / n_bar)
    val = p_poll * math.exp(d_bar)
    if not math.isfinite(val):
        return 1.0
    return min(max(val, 0.0), 1.0)


def _deferred(n: int, k: int, reason: str) -> CalibrationResult:
    return CalibrationResult(status="DEFERRED", sf_base_star=None, band=None,
                             n=int(n) if _finite(n) else 0,
                             k=int(k) if _finite(k) else 0,
                             f_hat=None, d_bar=None, n_bar=None, reason=reason)


def calibrate(k: int, n: int, d_bar: float, n_bar: float,
              sf_base_current: float, *,
              n_min: int = N_MIN_DEFAULT, e_min: int = E_MIN_DEFAULT,
              d_max: float = D_MAX_DEFAULT) -> CalibrationResult:
    """Hardened calibration verdict for one near-touch distance bucket.

    Returns a CalibrationResult whose status is:
      DEFERRED  — non-finite/empty/underpowered/not-near-touch: no number;
      NO_CHANGE — sf_base_current already inside the recommendation band;
      OK        — recommend ``sf_base_star`` (band gives the uncertainty).
    """
    # ---- fail-closed input validation --------------------------------------
    if not _finite(k, n, d_bar, n_bar, sf_base_current):
        return _deferred(n, k, "non-finite input")
    k, n = int(k), int(n)
    if n <= 0 or k < 0 or k > n:
        return _deferred(n, k, f"empty/invalid sample n={n} k={k}")
    if d_bar > d_max:
        return _deferred(n, k, f"d_bar {d_bar:.2f} > D_MAX {d_max} "
                               f"(not near-touch, not identifiable)")
    # ---- power gate: never recommend from noise ----------------------------
    if n < n_min or k < e_min or (n - k) < e_min:
        return _deferred(n, k, f"underpowered n={n} (<{n_min}) or tail "
                               f"k={k}/{n - k} (<{e_min})")
    # ---- estimate + invert -------------------------------------------------
    n_bar_eff = max(float(n_bar), 1.0)
    d_bar_eff = min(max(float(d_bar), 0.0), _D_OVERFLOW_CAP)
    center, lo, hi = wilson_interval(k, n)
    star = invert_base_prob(center, d_bar_eff, n_bar_eff)
    b_lo = invert_base_prob(lo, d_bar_eff, n_bar_eff)
    b_hi = invert_base_prob(hi, d_bar_eff, n_bar_eff)
    band = (min(b_lo, b_hi), max(b_lo, b_hi))
    detail = (f"n={n} k={k} f_hat={center:.3f} d_bar={d_bar_eff:.2f} "
              f"n_bar={n_bar_eff:.1f} -> sf_base*={star:.3f} "
              f"band=[{band[0]:.3f},{band[1]:.3f}] current={sf_base_current:.3f}")
    if band[0] <= float(sf_base_current) <= band[1]:
        return CalibrationResult(status="NO_CHANGE", sf_base_star=star,
                                 band=band, n=n, k=k, f_hat=center,
                                 d_bar=d_bar_eff, n_bar=n_bar_eff,
                                 reason="current within sampling band; " + detail)
    return CalibrationResult(status="OK", sf_base_star=star, band=band, n=n,
                             k=k, f_hat=center, d_bar=d_bar_eff,
                             n_bar=n_bar_eff, reason=detail)


def buckets_agree(results: list[CalibrationResult]) -> bool:
    """True iff all actionable buckets share a COMMON overlap (max low <= min
    high) — the single-sf_base consistency test, not merely pairwise overlap.

    sf_base is supposed to be distance-independent (the exp(-d_bar) term
    carries distance), so bands with no common intersection mean the forward
    model is misspecified — the caller should report MODEL-MISSPECIFIED rather
    than a false-precise single number. DEFERRED buckets (no band) are ignored.
    """
    bands = [r.band for r in results
             if r.status in ("OK", "NO_CHANGE") and r.band is not None]
    if len(bands) < 2:
        return True
    return max(b[0] for b in bands) <= min(b[1] for b in bands)
