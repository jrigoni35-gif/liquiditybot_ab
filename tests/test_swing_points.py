"""strategies/swing_points.py — the shared swing-extreme primitive used
by both thales.py (TH-013) and smc.py."""

from strategies.swing_points import swing_high_low


def _bars(vals):
    """vals: list of (hi, lo) -> (ts, o, hi, lo, c) tuples."""
    return [(float(i), hi, hi, lo, hi) for i, (hi, lo) in enumerate(vals)]


def test_returns_none_below_min_bars():
    bars = _bars([(101.0, 99.0)] * 7)     # 7 < MIN_BARS (8)
    assert swing_high_low(bars, lookback=48) == (None, None)


def test_finds_max_high_min_low_over_window():
    bars = _bars([(100.0, 95.0), (110.0, 96.0), (101.0, 90.0),
                  (102.0, 97.0), (103.0, 98.0), (104.0, 99.0),
                  (105.0, 94.0), (106.0, 93.0)])
    hi, lo = swing_high_low(bars, lookback=48)
    assert hi == 110.0
    assert lo == 90.0


def test_lookback_restricts_to_trailing_window():
    # first bar has the extreme high/low but lookback=8 excludes it
    bars = _bars([(200.0, 1.0)] + [(105.0, 95.0)] * 9)
    hi, lo = swing_high_low(bars, lookback=8)
    assert hi == 105.0
    assert lo == 95.0


def test_zero_lookback_uses_full_history():
    bars = _bars([(200.0, 1.0)] + [(105.0, 95.0)] * 9)
    hi, lo = swing_high_low(bars, lookback=0)
    assert hi == 200.0
    assert lo == 1.0


def test_empty_history_degrades_to_none():
    assert swing_high_low([], lookback=48) == (None, None)
