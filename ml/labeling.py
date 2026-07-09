"""
ml/labeling.py

Triple-barrier labeling (Lopez de Prado, "Advances in Financial Machine
Learning"). Given a candidate entry, the outcome is decided by whichever
of three barriers is touched first:

  upper barrier  - profit target, pt_mult * bar vol (side-adjusted)
  lower barrier  - stop, sl_mult * bar vol
vertical       - max holding period in bars

The meta-label is 1 when the primary signal's trade would have netted
more than round-trip costs, 0 otherwise. The meta-model therefore learns
"when is the 5-gate signal actually worth taking, and how big" - the
meta-labeling architecture: primary model picks the side, ML picks the
size. It is the highest-signal, lowest-overfit way to bolt learning
onto an existing rule engine.
"""

from dataclasses import dataclass

import numpy as np

EPS = 1e-12


@dataclass
class BarrierOutcome:
    label: int          # 1 = win (net of costs), 0 = loss/scratch
    ret_pct: float      # signed trade return, %
    bars_held: int
    barrier: str        # pt | sl | time


def triple_barrier(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray,
                i: int, side: int, sigma_bar: float,
                pt_mult: float = 8.0, sl_mult: float = 6.0,
                max_bars: int = 96, cost_pct: float = 0.06) -> BarrierOutcome:
    """
    closes/highs/lows : full arrays
    i                 : entry bar index (enter at closes[i])
    side              : +1 long, -1 short
    sigma_bar         : per-bar vol (fraction), scales the barriers
    cost_pct          : round-trip cost in %, subtracted before labeling
    """
    entry = closes[i]
    if entry <= EPS:
        return BarrierOutcome(0, 0.0, 0, "time")
    pt = pt_mult * sigma_bar
    sl = sl_mult * sigma_bar
    end = min(i + max_bars, len(closes) - 1)

    for j in range(i + 1, end + 1):
        if side > 0:
            up = highs[j] / entry - 1.0
            dn = 1.0 - lows[j] / entry
            if dn >= sl:           # conservative: stop checked first
                ret = -sl * 100.0
                return BarrierOutcome(0, ret - cost_pct, j - i, "sl")
            if up >= pt:
                ret = pt * 100.0
                return BarrierOutcome(int(ret - cost_pct > 0), ret - cost_pct,
                                    j - i, "pt")
        else:
            up = highs[j] / entry - 1.0
            dn = 1.0 - lows[j] / entry
            if up >= sl:
                ret = -sl * 100.0
                return BarrierOutcome(0, ret - cost_pct, j - i, "sl")
            if dn >= pt:
                ret = pt * 100.0
                return BarrierOutcome(int(ret - cost_pct > 0), ret - cost_pct,
                                    j - i, "pt")
    ret = side * (closes[end] / entry - 1.0) * 100.0
    return BarrierOutcome(int(ret - cost_pct > 0), ret - cost_pct, end - i, "time")
