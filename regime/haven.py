"""The tangible-value gradient: gold > BTC > ETH > alts.

WHAT THIS ENCODES. Crypto assets are not one asset class wearing different
tickers - they sit on a ladder of how TANGIBLE their claim on value is, and
capital moves along that ladder in a direction that is itself information:

  PAXG   gold, redeemable for an allocated bar in a vault. Its value is a
         physical thing that exists whether or not any chain, exchange or
         counterparty does. Five thousand years of monetary history, near-
         zero correlation to crypto beta, and the only asset here whose
         story does not depend on adoption.
  BTC    digital gold: a fixed supply and the deepest, oldest security
         budget in crypto, but a claim on a NETWORK, not on a bar. It is
         the tangible anchor OF crypto while remaining a risk asset TO the
         rest of finance - which is exactly why it sits below PAXG.
  ETH    productive infrastructure: cash-flow-like fee burn and staking
         yield, but its value is contingent on people actually using the
         platform. A claim on future usage.
  ALTS   venture bets. High beta, thin books, and a value proposition that
         is mostly narrative until proven. The pump-and-dump surface the
         long book already refuses to touch.

THE PSYCHOLOGY, stated as mechanism rather than mood. Fear travels DOWN
this ladder and greed travels UP it, and both travel in a specific order:
under stress, capital abandons the least tangible claim first (alts bleed
before ETH, ETH before BTC, BTC before gold) because in a drawdown the
question stops being "what could this become" and becomes "what is this,
actually". In froth the same ladder runs in reverse - money that has
already won in gold and BTC reaches down for beta, and alts outrun
everything on the way up. This is why the relative SPREADS down the ladder
are a cleaner read on regime than any single asset's return: BTC up 2% is
ambiguous, BTC up 2% while alts are down 4% is a flight to quality already
in progress.

WHAT THIS MODULE DOES, AND DOES NOT. It measures where capital sits on
that ladder right now, from the bot's OWN venue-grounded Kraken candles -
no new feed, no new dependency, no external "sentiment" vendor. It emits a
STATE (flight-to-quality / neutral / risk-on), a signed gradient, and the
per-rung returns behind them.

It does NOT size, gate, veto or direct a single trade. Report-only, in the
house style: the skimmer, the conviction formula and the context engine
all shipped as instruments first and earned their decision wiring later
with measured evidence. A dial that has never been watched is not evidence
- it is a guess with a number on it. When the gradient has a track record
against realized outcomes, THAT is the conversation about wiring it in.

DELIBERATE NON-GOALS. No feature-vector change: the model's schema is
frozen mid-migration (the 432-bar cohort), and widening it here would
invalidate the in-flight experiment for a signal with zero track record.
No gold-specific bracket geometry: PAXG's low volatility flows through the
existing vol-scaled machinery by construction - the brackets tighten on
their own, which is the entire point of scaling by sigma rather than by
hardcoded percentages.
"""
from dataclasses import dataclass, field
from typing import Optional

# The ladder, most tangible first. Position in this list IS the claim
# about tangibility; the spreads below are computed between adjacent rungs.
RUNGS = ("PAXG", "BTC", "ETH", "ALT")

# A gradient beyond this magnitude is a REGIME read rather than noise.
# Convention, not a fitted constant: 1% of relative move per rung over the
# lookback is the scale at which the ladder's own ordering is visible above
# a normal session's chop. Deliberately round - a fitted threshold on an
# unvalidated instrument would be a curve-fit dressed as a discovery.
DEFAULT_BAND_PCT = 1.0

FLIGHT = "flight_to_quality"
RISK_ON = "risk_on"
NEUTRAL = "neutral"
UNKNOWN = "unknown"


@dataclass
class HavenState:
    """One reading of the ladder. `state` is UNKNOWN whenever the evidence
    is insufficient - a state, never a guessed number (the context
    engine's rule, kept)."""
    state: str = UNKNOWN
    gradient: Optional[float] = None      # signed: + = capital moving DOWN
                                          # the ladder toward tangibility
    returns: dict = field(default_factory=dict)   # rung -> % over lookback
    spreads: dict = field(default_factory=dict)   # "PAXG-BTC" -> % spread
    rungs_seen: int = 0
    detail: str = ""

    def to_dict(self) -> dict:
        return {"state": self.state,
                "gradient": (None if self.gradient is None
                             else round(self.gradient, 4)),
                "returns": {k: round(v, 4) for k, v in self.returns.items()},
                "spreads": {k: round(v, 4) for k, v in self.spreads.items()},
                "rungs_seen": self.rungs_seen,
                "detail": self.detail}


def classify_asset(asset: str) -> str:
    """Which rung an asset sits on. Everything that is not gold or one of
    the two majors is a venture bet, which is the honest default: an
    unknown ticker on a thin book is an alt until proven otherwise."""
    a = str(asset or "").upper().strip()
    if a in ("PAXG", "XAUT", "GOLD"):
        return "PAXG"
    if a in ("BTC", "XBT"):
        return "BTC"
    if a == "ETH":
        return "ETH"
    return "ALT"


def _pct_return(closes) -> Optional[float]:
    """Percent change across a close series; None when the series cannot
    support one (too short, non-positive base, non-finite values)."""
    try:
        seq = [float(c) for c in closes]
    except (TypeError, ValueError):
        return None
    if len(seq) < 2:
        return None
    first, last = seq[0], seq[-1]
    if not (first > 0 and last > 0):
        return None
    if first != first or last != last:            # NaN
        return None
    return (last - first) / first * 100.0


def rung_returns(closes_by_asset: dict, lookback: int = 288) -> dict:
    """Mean percent return per LADDER RUNG over the last `lookback` bars.

    Averaging within a rung (rather than picking one representative) keeps
    the ALT rung honest: one alt ripping is a coin story, the whole rung
    moving together is a regime. 288 5m bars = 24h by default - the span
    over which a rotation is a rotation rather than a candle.
    """
    buckets: dict = {}
    for asset, closes in (closes_by_asset or {}).items():
        window = list(closes or [])[-int(lookback):]
        r = _pct_return(window)
        if r is None:
            continue
        buckets.setdefault(classify_asset(asset), []).append(r)
    return {rung: sum(v) / len(v) for rung, v in buckets.items() if v}


def evaluate(closes_by_asset: dict, lookback: int = 288,
             band_pct: float = DEFAULT_BAND_PCT) -> HavenState:
    """Read the ladder. Needs at least two adjacent rungs to say anything.

    The gradient is the mean spread between ADJACENT rungs, signed so that
    POSITIVE means the more tangible rung is outperforming the less
    tangible one - capital moving down the ladder toward what is real,
    i.e. fear. Negative means the reach for beta is on.

    Adjacent-only is the point: comparing PAXG to alts directly would let
    one blown-out microcap dominate a reading about gold. The ladder's
    claim is about ORDER, so the measurement is about order too.
    """
    rets = rung_returns(closes_by_asset, lookback=lookback)
    st = HavenState(returns=dict(rets), rungs_seen=len(rets))
    spreads = {}
    # strict=False is CORRECT here, not a silenced warning: pairing a
    # sequence with its own tail is deliberately ragged (4 rungs -> 3
    # adjacent pairs), which is what "adjacent" means.
    for upper, lower in zip(RUNGS, RUNGS[1:], strict=False):
        if upper in rets and lower in rets:
            spreads[f"{upper}-{lower}"] = rets[upper] - rets[lower]
    st.spreads = spreads
    if not spreads:
        st.detail = (f"insufficient rungs: {sorted(rets) or 'none'} - need "
                     f"two ADJACENT rungs of the ladder")
        return st
    st.gradient = sum(spreads.values()) / len(spreads)
    if st.gradient >= band_pct:
        st.state = FLIGHT
    elif st.gradient <= -band_pct:
        st.state = RISK_ON
    else:
        st.state = NEUTRAL
    st.detail = (f"gradient {st.gradient:+.2f}% over {len(spreads)} adjacent "
                 f"spread(s), band +/-{band_pct:.2f}%")
    return st
