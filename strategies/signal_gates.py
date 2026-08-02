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


def concentration_conf_mult(concentration, confidence, cfg) -> float:
    """Down-only confidence multiplier for the 'averaging trap' (TH-021,
    docs/THALES.md §Evidence concentration).

    The fused evidence E = Σ wᵢ·sᵢ is a weighted SUM, so a DIFFUSE signal (many
    weak factors averaged) can clear the same |E| bar as a PINPOINTED one where
    one factor dominates. `concentration` (normalized Herfindahl, 0 diffuse .. 1
    pinpointed) separates them; this trims confidence toward a floor ONLY when a
    signal is BOTH diffuse AND marginal, leaving concentrated conviction (or an
    already-strong signal) untouched. Returns a multiplier in
    [1 - max_atten, 1.0]; never boosts (a false boost costs money, a false trim
    costs opportunity). DISABLED by default — enabling it is the gated promotion
    step, so the default return is an exact 1.0 (prior behavior)."""
    cfg = cfg or {}
    if not cfg.get("enabled", False):
        return 1.0
    conc = _f(concentration)
    conf = _f(confidence)
    if conc is None or conf is None:
        return 1.0                            # degraded input -> no-op
    conc = min(max(conc, 0.0), 1.0)

    def _cf(key: str, default: float) -> float:      # finite config float
        v = _f(cfg.get(key, default))
        return default if v is None else v
    pivot = _cf("conc_pivot", 0.35)
    max_atten = min(max(_cf("max_atten", 0.15), 0.0), 0.5)
    marg_hi = _cf("marginal_conf", 0.65)
    floor = _cf("floor_conf", 0.50)
    # diffuse: 1.0 at concentration 0, ramping to 0 once concentration >= pivot
    diffuse = max(0.0, (pivot - conc) / pivot) if pivot > 0 else 0.0
    # marginal: 1.0 at/below floor_conf, ramping to 0 at/above marginal_conf
    span = marg_hi - floor
    marginal = 1.0 if span <= 0 else min(max((marg_hi - conf) / span, 0.0), 1.0)
    return 1.0 - max_atten * min(diffuse, 1.0) * marginal


@dataclass
class SignalResult:
    symbol: str                  # Kraken-tradeable pair, e.g. 'ETH/USD'
    direction: Optional[str]     # 'long', 'short', or None if not confirmed
    confidence: float            # 0.0-1.0, fraction of gates that passed
    size: float                  # placeholder; risk/capital_manager.py sizes it before execution
    all_confirmed: bool
    gates_passed: dict = field(default_factory=dict)
    urgency: float = 0.0         # 0..1 edge-decay estimate for execution tactics
    # 0..1 evidence CONCENTRATION (normalized Herfindahl of the signed
    # component contributions): 0 = perfectly diffuse (the signal is an average
    # of many weak factors), 1 = one factor dominates (a pinpointed setup).
    # SHADOW diagnostic only - it changes no decision; it exists so the brain
    # can later tell a concentrated conviction from a blended-average signal.
    evidence_concentration: float = 0.0
    # gate-truth instrumentation (2026-07-28 audit): the informed-flow
    # engine's RAW signed component scores {flow, delta, accum, burst,
    # trend} plus the fused "evidence" (Σ w·s) and "conc" (normalized-HHI
    # concentration). Persisted per row (sg_* columns, ml/history.py) so
    # realized outcomes can grade WHICH evidence was right — the weights
    # stop being unfalsifiable. {} = legacy engine / warmup / fault path;
    # downstream writes zeros. TELEMETRY ONLY — never a feature, never a
    # decision input.
    components: dict = field(default_factory=dict)


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

        UNAVAILABLE funding (OKX perp feed down; the merge yields 0.0 for both
        "truly ~0" and "no source", so `funding_available` disambiguates) is a
        lost minor crowding filter, NOT an unhedged cost — Kraken (sole venue)
        is spot and pays no funding. Default PASSES the gate rather than
        starving all entries on a single-feed outage; set
        gate_4.pass_when_unavailable=false for strict fail-closed. (This matches
        the deployed informed_flow engine; never crashes on abs(None).)"""
        if not self.gate_4.get("enabled", True):
            return True
        pass_unavail = bool(self.gate_4.get("pass_when_unavailable", True))
        funding_rate = _f(view.get("funding_rate"))
        if not view.get("funding_available", True) or funding_rate is None:
            return pass_unavail
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
        # --- realized-outcome ledger (2026-08-02) -----------------------
        # The same shape as _stats, but keyed on whether the trade actually
        # MADE MONEY rather than whether the price touched a barrier. See
        # note_realized() for why the two are not the same thing.
        self._real: dict = {}        # gate -> [n_closed_passes, net_wins]
        self._real_total = [0, 0]    # all closed trades [n, net_wins]
        # Realized outcomes arrive far more slowly than labels (one per
        # closed trade vs one per candidate), so this defaults to a lower
        # bar than min_samples — but never lower than 20, because a gate
        # weight swung by a dozen trades is noise wearing a decimal point.
        self.real_min_samples = max(int(c.get("realized_min_samples", 25)),
                                    20)

    def note_realized(self, gates_passed, net_pct) -> None:
        """Close the loop: record whether a gate's pass actually PAID.

        THE BUG THIS FIXES (2026-08-02). note_label() below learns from the
        triple-barrier label, which is a PRICE outcome: 1 means the price
        reached the profit target before the stop. It says nothing about
        whether the trade made money, because it does not know about the
        round trip — fees, spread, slippage.

        On this feed that gap is not academic. The triple-barrier label rate
        is 0.3991 while the realized win rate is 0.038 — a 10x divergence,
        and the entire gap is cost. Measured over 239 closed trades, 87%
        reached a favourable excursion and the median loss still exceeded
        the worst adverse excursion by 0.437%, which is roughly the round
        trip. So a gate could be credited for a "win" on a trade that lost
        money, and the ledger would keep telling it that it was right.

        That is reward misspecification in its textbook form: the proxy
        (barrier touched) and the goal (money made) came apart, and the
        optimizer faithfully pursued the proxy. Weights learned this way get
        MORE confident as they lose, because every barrier touch confirms
        them.

        net_pct is the realized net return in PERCENT, after all costs —
        the same quantity as postmortem_summary.realized_pct. A win is
        strictly > 0: breaking even is not winning, and counting it as one
        is how a cost-dominated strategy talks itself into viability.

        Never raises: a stats hiccup must not break trade closing.
        """
        if not isinstance(gates_passed, dict) or not gates_passed:
            return
        try:
            v = float(net_pct)
        except (TypeError, ValueError):
            return
        if v != v or v in (float("inf"), float("-inf")):   # NaN / inf
            return
        win = 1 if v > 0.0 else 0
        self._real_total[0] += 1
        self._real_total[1] += win
        for g, passed in gates_passed.items():
            if passed:
                s = self._real.setdefault(str(g), [0, 0])
                s[0] += 1
                s[1] += win

    def realized_divergence(self, gate: str):
        """label-implied weight minus realized weight, or None if unknown.

        The tunnel-vision detector. A large POSITIVE value means the gate
        looks predictive on barriers and is not paying — precisely the
        state the bot was in, and the one no single number could previously
        show. Reported rather than acted on: it is a diagnosis, and the
        weight() switch below is the treatment.
        """
        n, _ = self._real.get(gate, (0, 0))
        if n < self.real_min_samples or self._real_total[0] < \
                self.real_min_samples:
            return None
        return round(self._label_weight(gate) - self.weight(gate), 4)

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

    def _shade(self, n, wins, tot_n, tot_wins, floor) -> float:
        """Wilson-LCB win rate vs the base rate, bounded. Shared by both
        ledgers so realized and label weights are computed identically and
        their difference means something."""
        if n < floor or tot_n < floor:
            return 1.0
        base = tot_wins / max(tot_n, 1)
        lcb = _wilson_lcb(wins, n)
        return min(max(1.0 + (lcb - base) * self.strength,
                       self.W_LO), self.W_HI)

    def _label_weight(self, gate: str) -> float:
        """The old barrier-label weight. Kept for the divergence readout."""
        n, wins = self._stats.get(gate, (0, 0))
        return self._shade(n, wins, self._total[0], self._total[1],
                           self.min_samples)

    def weight(self, gate: str) -> float:
        """Realized-outcome weight once there is enough of it, else labels.

        THE LOOP (2026-08-02). Realized P&L is the ground truth and barrier
        labels are a proxy for it, so realized wins whenever it has standing
        — but it accrues one sample per CLOSED TRADE against one per
        candidate, so it is thin for weeks and cannot simply replace the
        other. Hence the handover: below real_min_samples the behaviour is
        byte-identical to before, and past it the ledger that knows about
        costs takes over. Nothing to switch on, no fitted blend constant,
        and no window in which the gate is unweighted.

        The base rate moves with the ledger, which is the important part: a
        gate is scored against how often trades ACTUALLY pay, not how often
        barriers get touched. On a feed where those differ 10x, that is the
        whole difference between learning and confirming.
        """
        rn, rwins = self._real.get(gate, (0, 0))
        if rn >= self.real_min_samples \
                and self._real_total[0] >= self.real_min_samples:
            return self._shade(rn, rwins, self._real_total[0],
                               self._real_total[1], self.real_min_samples)
        return self._label_weight(gate)

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
        gates = sorted(set(self._stats) | set(self._real))
        div = {g: d for g in gates
               if (d := self.realized_divergence(g)) is not None}
        return {"enabled": self.enabled,
                "labeled": self._total[0],
                "base_rate": round(self._total[1] / self._total[0], 3)
                if self._total[0] else None,
                "weights": {g: round(self.weight(g), 3) for g in gates},
                # The realized loop, reported beside the labels so the two
                # can be compared at a glance. realized_base_rate next to
                # base_rate IS the reward-misspecification readout: on this
                # feed they were 0.038 and 0.3991.
                "realized_closed": self._real_total[0],
                "realized_base_rate":
                    round(self._real_total[1] / self._real_total[0], 4)
                    if self._real_total[0] else None,
                "realized_active": bool(
                    self._real_total[0] >= self.real_min_samples),
                "realized_min_samples": self.real_min_samples,
                "divergence": div}

    # --- persistence hooks (snapshot round-trip) ---
    def to_dict(self) -> dict:
        return {"stats": {g: list(s) for g, s in self._stats.items()},
                "total": list(self._total),
                "real": {g: list(s) for g, s in self._real.items()},
                "real_total": list(self._real_total)}

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
        # Restored separately so a snapshot written BEFORE the realized
        # ledger existed loads cleanly with an empty one rather than
        # discarding the label stats it does carry.
        try:
            self._real = {str(g): [int(s[0]), int(s[1])]
                          for g, s in (d.get("real") or {}).items()}
            rt = d.get("real_total") or [0, 0]
            self._real_total = [int(rt[0]), int(rt[1])]
        except (TypeError, ValueError, IndexError):
            self._real, self._real_total = {}, [0, 0]

