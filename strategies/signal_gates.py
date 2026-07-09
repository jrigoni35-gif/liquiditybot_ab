"""
strategies/signal_gates.py

5-gate simultaneous confirmation system. A signal only fires when ALL
five gates pass in the same evaluation cycle AND the directional gates
(order book imbalance, momentum) agree on the same direction. Reads
thresholds from config.json's "signal_gates" section.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("liquiditybot.strategies.signal_gates")


def _f(value, default: Optional[float] = None) -> Optional[float]:
    """Finite float or `default` - the gate boundary never does math on
    None/NaN/inf from a degraded feed."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


@dataclass
class SignalResult:
    symbol: str                  # Kraken-tradeable pair, e.g. 'ETH/USD'
    direction: Optional[str]     # 'long', 'short', or None if not confirmed
    confidence: float            # 0.0-1.0, fraction of gates that passed
    size: float                  # placeholder; risk/capital_manager.py sizes it before execution
    all_confirmed: bool
    gates_passed: dict = field(default_factory=dict)
    urgency: float = 0.0         # 0..1 edge-decay estimate for execution tactics


class SignalGateEngine:
    def __init__(self, config: dict):
        cfg = config or {}
        # config.json nests the gate blocks under "signal_gates"; accept both
        # the full config and the already-nested block. Before this, passing
        # the full config (as main.py does on the rollback path) silently ran
        # EVERY gate on hardcoded defaults - configured thresholds ignored.
        nested = cfg.get("signal_gates")
        if isinstance(nested, dict):
            cfg = nested
        self.gate_1 = cfg.get("gate_1_liquidity_pool", {})
        self.gate_2 = cfg.get("gate_2_order_book_imbalance", {})
        self.gate_3 = cfg.get("gate_3_volume_confirmation", {})
        self.gate_4 = cfg.get("gate_4_funding_rate", {})
        self.gate_5 = cfg.get("gate_5_momentum_alignment", {})

    def _ema(self, values: list, period: int) -> Optional[float]:
        if len(values) < period:
            return None
        k = 2 / (period + 1)
        ema = sum(values[:period]) / period
        for price in values[period:]:
            ema = price * k + ema * (1 - k)
        return ema

    def _check_gate_1(self, view: dict) -> bool:
        """Liquidity pool depth must clear the configured USD minimum."""
        if not self.gate_1.get("enabled", True):
            return True
        pool = _f(view.get("liquidity_pool_usd"), 0.0) or 0.0
        return pool >= float(self.gate_1.get("min_pool_size_usd", 0))

    def _check_gate_2(self, view: dict) -> tuple:
        """Order book imbalance. Returns (passed, direction_hint)."""
        if not self.gate_2.get("enabled", True):
            return True, None
        ratio = _f(view.get("imbalance_ratio"))
        if ratio is None or ratio <= 0:
            return False, None                  # degraded feed: fail closed
        min_ratio = float(self.gate_2.get("min_imbalance_ratio", 1.5))
        if ratio >= min_ratio:
            return True, "long"
        if ratio <= (1 / min_ratio):
            return True, "short"
        return False, None

    def _check_gate_3(self, view: dict) -> bool:
        """Latest candle volume must exceed N times the recent average.
        Malformed candles (missing/non-finite volume) are excluded rather
        than raised on; too little VALID history fails closed."""
        if not self.gate_3.get("enabled", True):
            return True
        candles = view.get("candles") or []
        if len(candles) < 2:
            return False
        bar_minutes = 5  # matches default candle interval used by data feeds
        lookback = int(self.gate_3.get("avg_lookback_minutes", 60))
        lookback_bars = max(1, lookback // bar_minutes)
        history = [v for v in (_f(c.get("volume")) for c in
                               candles[-(lookback_bars + 1):-1]
                               if isinstance(c, dict)) if v is not None]
        if not history:
            return False
        avg_volume = sum(history) / len(history)
        latest_volume = _f(candles[-1].get("volume")
                           if isinstance(candles[-1], dict) else None)
        if avg_volume <= 0 or latest_volume is None:
            return False
        return (latest_volume / avg_volume) >= \
            float(self.gate_3.get("min_volume_multiple_of_avg", 2.0))

    def _check_gate_4(self, view: dict) -> bool:
        """Funding rate must stay within the configured absolute cap.
        An UNAVAILABLE rate (feed returned None/NaN) fails closed - the old
        code crashed on abs(None), taking the whole cycle down."""
        if not self.gate_4.get("enabled", True):
            return True
        funding_rate = _f(view.get("funding_rate"))
        if funding_rate is None:
            return False
        return abs(funding_rate) <= float(
            self.gate_4.get("max_abs_funding_rate", 0.01))

    def _check_gate_5(self, view: dict) -> tuple:
        """EMA fast/slow cross. Returns (passed, direction_hint)."""
        if not self.gate_5.get("enabled", True):
            return True, None
        candles = view.get("candles") or []
        closes = [v for v in (_f(c.get("close")) for c in candles
                              if isinstance(c, dict)) if v is not None]
        fast_ema = self._ema(closes, int(self.gate_5.get("fast_period", 9)))
        slow_ema = self._ema(closes, int(self.gate_5.get("slow_period", 21)))
        if fast_ema is None or slow_ema is None:
            return False, None
        if fast_ema > slow_ema:
            return True, "long"
        if fast_ema < slow_ema:
            return True, "short"
        return False, None

    def evaluate_asset(self, base_asset: str, view: dict) -> SignalResult:
        """Fail-closed wrapper: a malformed view yields an unconfirmed
        result, never an exception into the trading cycle (mirrors the
        informed_flow engine's contract)."""
        try:
            return self._evaluate_asset(base_asset, view or {})
        except Exception:
            log.exception("signal-gate evaluation fault for %s - signal "
                          "fails closed", base_asset)
            return SignalResult(
                symbol=(view or {}).get("kraken_symbol", base_asset),
                direction=None, confidence=0.0, size=0.0,
                all_confirmed=False, gates_passed={})

    def _evaluate_asset(self, base_asset: str, view: dict) -> SignalResult:
        gate_1_passed = self._check_gate_1(view)
        gate_2_passed, dir_2 = self._check_gate_2(view)
        gate_3_passed = self._check_gate_3(view)
        gate_4_passed = self._check_gate_4(view)
        gate_5_passed, dir_5 = self._check_gate_5(view)

        gates_passed = {
            "gate_1_liquidity_pool": gate_1_passed,
            "gate_2_order_book_imbalance": gate_2_passed,
            "gate_3_volume_confirmation": gate_3_passed,
            "gate_4_funding_rate": gate_4_passed,
            "gate_5_momentum_alignment": gate_5_passed,
        }

        # Directional gates must agree with each other, not just individually pass
        directional_hints = [d for d in (dir_2, dir_5) if d is not None]
        direction = None
        if directional_hints and all(d == directional_hints[0] for d in directional_hints):
            direction = directional_hints[0]

        all_confirmed = all(gates_passed.values()) and direction is not None
        confidence = sum(gates_passed.values()) / len(gates_passed)

        return SignalResult(
            symbol=view.get("kraken_symbol", base_asset),
            direction=direction if all_confirmed else None,
            confidence=confidence,
            size=0.0,
            all_confirmed=all_confirmed,
            gates_passed=gates_passed,
        )


def _wilson_lcb(wins: int, n: int, z: float = 1.96) -> float:
    """Wilson lower confidence bound on a win rate — conservative for
    small n, converges to the raw rate as evidence accrues."""
    if n <= 0:
        return 0.0
    p = wins / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = p + z2 / (2 * n)
    rad = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return max((center - rad) / denom, 0.0)


class GateStats:
    """Per-gate predictive-power ledger learned from labeled candidate
    outcomes (engine-agnostic: works on any gates_passed dict, informed-
    flow or 5-gate). For each gate it tracks labeled candidates where
    that gate PASSED; the Wilson-LCB win rate relative to the overall
    base rate becomes a bounded weight that shades gate_confidence
    toward gates that actually predict wins on THIS feed.

    Discipline: weights NEVER veto — direction and all_confirmed are
    untouched; only the confidence shading (a meta-model feature and
    the counter-trend p bar input) moves. A gate with fewer than
    min_samples labeled passes stays at weight 1.0, so the cold start
    reproduces the naive equal-weight confidence exactly."""

    W_LO, W_HI = 0.7, 1.3

    def __init__(self, cfg: dict | None = None):
        c = cfg or {}
        self.enabled = bool(c.get("enabled", False))
        self.min_samples = max(int(c.get("min_samples", 40)), 5)
        self.strength = min(max(float(c.get("strength", 2.0)), 0.0), 5.0)
        self._stats: dict = {}       # gate -> [n_labeled_passes, wins]
        self._total = [0, 0]         # all labeled candidates [n, wins]

    def note_label(self, gates_passed, label) -> None:
        """Called by the candidate labeler when a triple-barrier label
        lands. Never raises — a stats hiccup must not break labeling."""
        if not isinstance(gates_passed, dict) or not gates_passed:
            return
        try:
            win = 1 if int(label) > 0 else 0
        except (TypeError, ValueError):
            return
        self._total[0] += 1
        self._total[1] += win
        for g, passed in gates_passed.items():
            if passed:
                s = self._stats.setdefault(str(g), [0, 0])
                s[0] += 1
                s[1] += win

    def weight(self, gate: str) -> float:
        n, wins = self._stats.get(gate, (0, 0))
        if n < self.min_samples or self._total[0] < self.min_samples:
            return 1.0
        base = self._total[1] / max(self._total[0], 1)
        lcb = _wilson_lcb(wins, n)
        return min(max(1.0 + (lcb - base) * self.strength,
                       self.W_LO), self.W_HI)

    def weighted_confidence(self, gates_passed, fallback: float) -> float:
        """Weighted fraction of passing gates in [0, 1]. Equal weights
        (cold start / disabled) reproduce the naive fraction exactly."""
        if not self.enabled or not isinstance(gates_passed, dict) \
                or not gates_passed:
            return fallback
        weights = {g: self.weight(str(g)) for g in gates_passed}
        denom = sum(weights.values())
        if denom <= 0:
            return fallback
        num = sum(weights[g] for g, p in gates_passed.items() if p)
        return min(max(num / denom, 0.0), 1.0)

    def summary(self) -> dict:
        """Compact snapshot for status.json / dashboard."""
        return {"enabled": self.enabled,
                "labeled": self._total[0],
                "base_rate": round(self._total[1] / self._total[0], 3)
                if self._total[0] else None,
                "weights": {g: round(self.weight(g), 3)
                            for g in sorted(self._stats)}}

    # --- persistence hooks (snapshot round-trip) ---
    def to_dict(self) -> dict:
        return {"stats": {g: list(s) for g, s in self._stats.items()},
                "total": list(self._total)}

    def restore(self, d) -> None:
        if not isinstance(d, dict):
            return
        try:
            self._stats = {str(g): [int(s[0]), int(s[1])]
                           for g, s in (d.get("stats") or {}).items()}
            t = d.get("total") or [0, 0]
            self._total = [int(t[0]), int(t[1])]
        except (TypeError, ValueError, IndexError):
            self._stats, self._total = {}, [0, 0]

