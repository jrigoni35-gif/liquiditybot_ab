"""
strategies/swing_points.py — shared swing-extreme primitive.

Range-based swing high/low (max high / min low over a trailing
lookback window of (ts, open, high, low, close) bars). This is the
one definition of "where the recent extremes are" shared by:

  * strategies/thales.py   TH-013 stop-cluster proximity/sweep detection
  * strategies/smc.py      premium/discount zones, liquidity-pocket pull

Kept intentionally dumb (no fractal/pivot logic) so both modules agree
on the same primitive rather than drifting into two different
definitions of "swing" over time.
"""

from typing import Optional, Sequence, Tuple

MIN_BARS = 8

# The shared bar shape, named once. `Sequence[tuple]` was a BARE generic:
# correct at runtime and silent under the repo's basic pyright profile, but
# it erased the element type, so every `h`/`lo` unpacked from a window came
# back Unknown and any caller checking under a stricter profile inherited
# that. Producers append exactly this 5-tuple (strategies/thales.py's
# `st.candle_hist.append((ts, o, hi, lo, c))`), so the annotation is a
# statement of existing fact, not a new constraint.
Candle = Tuple[float, float, float, float, float]   # (ts, open, high, low, close)


def swing_high_low(candle_hist: Sequence[Candle], lookback: int
                   ) -> Tuple[Optional[float], Optional[float]]:
    """candle_hist: sequence of (ts, open, high, low, close) tuples,
    oldest first. Returns (swing_high, swing_low) over the trailing
    `lookback` bars, or (None, None) if fewer than MIN_BARS are
    available - callers must treat that as "no swing context yet",
    never as a zero-width range."""
    window = list(candle_hist)[-lookback:] if lookback else list(candle_hist)
    if len(window) < MIN_BARS:
        return None, None
    return (max(h for _, _, h, _, _ in window),
            min(lo for _, _, _, lo, _ in window))
