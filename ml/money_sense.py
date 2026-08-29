"""Money sense — the proportional WEIGHT of a gain or loss, never raw dollars.

SHADOW INSTRUMENT (operator directive 2026-08-29). Measurement only, wired into
no decision path (freeze-safe; nothing in main.py/runner.py/risk/execution
imports it). Its job is to give the bot the thing a raw P&L number cannot: a
sense of PROPORTION and CONTEXT.

The teaching examples, made mechanical:
  - $20 lost on a $100 account is -20% — near-catastrophic. It takes ruinous
    compounding to recover from, and a handful of them ends the account.
  - $100 won on a $100,000 account is +0.1% — trivial in weight, AND if a real
    move was on the table it is a badly MISSED capitalization, not a "win".
The same dollars mean opposite things depending on the account they land on.

Three ideas, all PROPORTIONAL (operator unit directive: nothing without context
and proportion — every function REQUIRES the account/achievable context, you
cannot get a weight from dollars alone):

1. PROPORTION. return_frac = pnl / equity. $20/$100 = -0.20; $100/$100k = 0.001.
   Dollars are meaningless until divided by the account they moved.

2. ASYMMETRIC WEIGHT (log / geometric utility). The FELT weight of a
   proportional return is log(1+r): losses hurt MORE than symmetric gains
   (a -20% weighs -0.2231, a +20% only +0.1823) because compounding punishes
   drawdown, and total ruin (r = -1) is -infinity. This is why "-20% is worse
   than 2x a -10%", and why a small account cannot afford the losses a large
   one shrugs off. It is the same log scale the return analysis uses — a
   sequence of weights ADDS to the log of the cumulative multiple.

3. CAPITALIZATION EFFICIENCY. captured / achievable. A +0.1% win when the move
   and deployable capital offered +5% is efficiency 0.02 — a 50x
   under-capitalization. A "win" that leaves most of an achievable move on the
   table is a soft loss of opportunity, and money sense must see it as one.
"""
from __future__ import annotations

import math

# A single loss can never be weighted as literal total ruin from a modelling
# artifact, but a real -100% (or worse, a blown account) must read as the worst
# possible. Clamp the log-utility floor so a >=100% loss is a large finite
# penalty, not a NaN/-inf that poisons an aggregate.
RUIN_WEIGHT = math.log(1e-4)  # ~ -9.21: a wipeout, finite for bookkeeping


def proportional_return(pnl_usd: float, equity_usd: float) -> float:
    """P&L as a fraction of the account it moved. Raises without a positive
    equity context — dollars alone have no weight."""
    if not (math.isfinite(pnl_usd) and math.isfinite(equity_usd)):
        raise ValueError("pnl and equity must be finite")
    if equity_usd <= 0.0:
        raise ValueError("equity must be > 0 to weigh a P&L against it")
    return pnl_usd / equity_usd


def log_utility_weight(return_frac: float) -> float:
    """The felt weight of a proportional return under log/geometric utility:
    log(1+r). Asymmetric (losses heavier), and a wipeout (r <= -1) reads as
    RUIN_WEIGHT rather than -inf so aggregates stay finite."""
    if not math.isfinite(return_frac):
        raise ValueError("return_frac must be finite")
    if 1.0 + return_frac <= 1e-4:
        return RUIN_WEIGHT
    return math.log(1.0 + return_frac)


def capitalization_efficiency(captured_frac: float,
                              achievable_frac: float) -> "float | None":
    """captured / achievable — did it capitalize on what was there? None when
    nothing was achievable (no opportunity to miss). A value < 1 is
    under-capitalization (a +0.1% capture of a +5% move = 0.02)."""
    if not (math.isfinite(captured_frac) and math.isfinite(achievable_frac)):
        raise ValueError("captured and achievable must be finite")
    if achievable_frac == 0.0:
        return None
    return captured_frac / achievable_frac


def ruin_distance(return_frac: float) -> "float | None":
    """How many identical losses of this size end the account (equity -> 0).
    A -20% loss => 1/0.20 = 5 such losses to ruin; a gain => None (never
    ruins). The blunt weight of a loss on a small account."""
    if not math.isfinite(return_frac):
        raise ValueError("return_frac must be finite")
    if return_frac >= 0.0:
        return None
    return 1.0 / abs(return_frac)


def weigh(pnl_usd: float, equity_usd: float,
          achievable_frac: "float | None" = None) -> dict:
    """The full proportional weight of one outcome: the fraction, its felt
    (log-utility) weight, ruin distance if a loss, and capitalization
    efficiency if an achievable move is supplied. One call = the money-sense
    picture the raw dollars hide."""
    r = proportional_return(pnl_usd, equity_usd)
    return {
        "pnl_usd": pnl_usd,
        "equity_usd": equity_usd,
        "return_frac": r,
        "log_utility_weight": log_utility_weight(r),
        "ruin_distance": ruin_distance(r),
        "capitalization_efficiency": (
            None if achievable_frac is None
            else capitalization_efficiency(r, achievable_frac)),
    }
