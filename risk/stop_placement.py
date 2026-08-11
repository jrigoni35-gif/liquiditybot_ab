"""risk/stop_placement.py - Osler round-number stop avoidance (ALGO-7).

THE EVIDENCE (the only stop-placement mechanism that survived both Grand
Synthesis sweeps): Osler, "Stop-Loss Orders and Price Cascades in Currency
Markets" (JIMF 24(2), 2005) - stop orders cluster at round numbers; price
response to stop triggers is larger and longer-lasting than to take-profits;
stops trigger in waves. Crypto's liquidation-cascade literature extends the
mechanism (forced liquidations ~3.5%/1.9% of OI daily, endogenous and
leverage-driven). The engineering precedent (BitMEX fair-price marking, the
2021 Kraken single-venue -63% ETH wick) covers the TRIGGER side, which this
engine already has: stops evaluate on the trusted mark with single-tick
quarantine-and-confirm. This module covers the PLACEMENT side: a stop
resting just inside a round-number cluster is hit by any sweep TO the
cluster; a stop just beyond it fires only if the level actually breaks.

Scale-free round levels: step = 10^(floor(log10(price)) - 1), i.e. the
second significant digit's granularity - 63,412 -> 1,000s (63k/64k),
1,988 -> 100s (1.9k/2.0k), 0.7423 -> 0.01s (0.74/0.75). This matches the
"00-ending" clustering Osler measured without any per-asset table.

SEMANTIC FLIP, DOCUMENTED (cut #7, operator-adjudicated 2026-08-11). The
previous implementation (main.py nudge_stop_off_round_number, retired by
this module) nudged stops to the NEAR side of the level - "exit before the
cascade detonates" - which minimizes exit slippage but means any sweep TO
the level takes the position out: exactly the shakeout ejection the
operator's bull-readiness directive names. This module rests the stop just
BEYOND the level instead: the herd's clustered stops trigger first, and
ours fires only if the level actually breaks. The cost is accepted
knowingly: when the level does break, the exit fills into the cascade, and
the existing escalation ladder (widening slip caps, final-rung market)
owns that path. The nudge only ever WIDENS (bounded by band+offset bps);
it never tightens. Callers that stamp a bracket sl leg MUST back-derive
sl_frac from the nudged price so the traded bet stays the labeled bet
(geometry-alignment law).

Config: config["risk"] -> stop_round_buffer_bps (the band) and
stop_round_offset_bps (the rest-beyond distance), read by main._nudge_stop
and range-checked by core/config_guard. (This paragraph's first version
named a nonexistent risk.stop_placement block with invented knob names -
a phantom-block doc inside the module that fixed a phantom-knob bug,
caught by the 2026-08-11 commits audit. The knob names above are pinned
by tests/test_stop_placement.py.) Pure functions, no state, no I/O.
"""
from __future__ import annotations

import math

__all__ = ["round_step", "nudge_stop_off_round"]


def round_step(price: float) -> float:
    """The local round-number lattice: HALF of the second-significant-digit
    unit (BTC ~63k -> every 500; ETH ~1.8k -> every 50; MINA ~0.45 -> every
    0.005). The half-step covers both the 00- and 50-endings Osler documents
    - the lattice the previous (tighten-side) implementation shipped, kept
    so cut #7's change is DIRECTION-ONLY."""
    if not (isinstance(price, (int, float)) and math.isfinite(price)
            and price > 0):
        return 0.0
    return 10.0 ** (math.floor(math.log10(price)) - 1) / 2.0


def nudge_stop_off_round(stop: float, direction: str,
                         band_bps: float, offset_bps: float) -> float:
    """Return `stop`, moved just beyond its nearest round level when it
    rests within band_bps of one; unchanged otherwise.

    long  -> stop sits below entry; "beyond" = below the level.
    short -> stop sits above entry; "beyond" = above the level.

    Total widening is bounded by (band_bps + offset_bps) of the stop price.
    Degenerate inputs (non-finite, non-positive, zero band) return the stop
    unchanged - fail-inert, never fail-tighter.
    """
    if not (isinstance(stop, (int, float)) and math.isfinite(stop)
            and stop > 0):
        return stop
    band = max(float(band_bps), 0.0) * 1e-4 * stop
    offset = max(float(offset_bps), 0.0) * 1e-4 * stop
    if band <= 0.0 or offset <= 0.0:
        return stop
    step = round_step(stop)
    if step <= 0.0:
        return stop
    level = round(stop / step) * step
    if abs(stop - level) > band:
        return stop
    if direction == "long":
        nudged = level - offset
        return nudged if nudged < stop else stop      # only ever widen
    if direction == "short":
        nudged = level + offset
        return nudged if nudged > stop else stop
    return stop
