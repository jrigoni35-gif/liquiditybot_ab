"""
sentiment/fear_filter.py

The anti-narrative layer: makes the bot resistant to "media spoofing
market fear". Principle: narrative is only actionable when the market's
own structure confirms it.

A structural stress index in [0, 1] is computed from things influencers
cannot fake: realized vol percentile, order-book depth collapse,
funding-rate extremes, cross-asset turbulence, perp/spot basis blowout,
and (when the moomoo feed is live) a risk-equity selloff. Sentiment is then cross-referenced:

loud fear + calm structure   -> "narrative_noise": risk multiplier
                                stays 1.0. The bot does NOT get shaken
                                out by headlines.
loud fear + stressed market  -> "confirmed_stress": risk 0.6 and a
                                small negative confidence tilt - the
                                fear is real, respect it.
in between                   -> mild caution (0.85).
euphoria + calm structure    -> mild fade of the crowd (0.9): late-
                                cycle euphoria is a contrarian tell.

Outputs are hard-clamped: risk_multiplier in [0.5, 1.0], confidence
tilt in [-0.15, +0.15]. Sentiment can shade a trade; it can never
create one, veto one on its own, or flip its direction.
"""

import logging
from dataclasses import dataclass, field

log = logging.getLogger("liquiditybot.sentiment.fear_filter")


@dataclass
class StructuralInputs:
    vol_percentile: float = 50.0       # max across assets
    depth_ratio: float = 1.0           # min across assets (current/median)
    funding_rate: float = 0.0          # most extreme across assets
    turbulence_pct: float = 50.0
    basis_bps: float = 0.0             # most extreme |perp - spot|
    risk_asset_z: float = 0.0          # moomoo equity basket z (selloff < 0)
    risk_asset_available: bool = False


@dataclass
class FilterVerdict:
    risk_multiplier: float = 1.0       # multiplies position size
    confidence_tilt: float = 0.0       # added to gate confidence, clamped
    label: str = "neutral"
    stress_index: float = 0.0
    detail: dict = field(default_factory=dict)


class NarrativeFilter:
    def __init__(self, config: dict):
        cfg = config or {}
        self.stress_confirm = float(cfg.get("stress_confirm_threshold", 0.6))
        self.stress_calm = float(cfg.get("stress_calm_threshold", 0.3))
        self.funding_extreme = float(cfg.get("funding_extreme_abs", 0.0008))
        self.basis_extreme_bps = float(cfg.get("basis_extreme_bps", 40.0))
        self.max_tilt = 0.15                       # hard clamp, not configurable up
        self.floor_mult = 0.5

    def structural_stress(self, s: StructuralInputs) -> tuple:
        parts = {
            "vol": min(max((s.vol_percentile - 60.0) / 35.0, 0.0), 1.0),
            "depth": min(max((1.0 - s.depth_ratio) / 0.6, 0.0), 1.0),
            "funding": min(abs(s.funding_rate) / self.funding_extreme, 1.0)
            if self.funding_extreme > 0 else 0.0,
            "turbulence": min(max((s.turbulence_pct - 60.0) / 35.0, 0.0), 1.0),
            "basis": min(abs(s.basis_bps) / self.basis_extreme_bps, 1.0)
            if self.basis_extreme_bps > 0 else 0.0,
        }
        weights = {"vol": 0.30, "depth": 0.25, "funding": 0.15,
                "turbulence": 0.20, "basis": 0.10}
        if s.risk_asset_available:
            # equity selloff (z <= -1) is external confirmation of stress;
            # rallies contribute nothing (stress is one-sided)
            parts["equity"] = min(max((-s.risk_asset_z - 1.0) / 2.0, 0.0), 1.0)
            weights = {"vol": 0.27, "depth": 0.22, "funding": 0.13,
                    "turbulence": 0.18, "basis": 0.08, "equity": 0.12}
        idx = sum(parts[k] * weights[k] for k in parts)
        return idx, parts

    def evaluate(self, sentiment, structure: StructuralInputs) -> FilterVerdict:
        stress, parts = self.structural_stress(structure)
        v = FilterVerdict(stress_index=stress, detail=parts)

        fear = bool(getattr(sentiment, "fear_spike", False)) or \
            float(getattr(sentiment, "score", 0.0) or 0.0) <= -0.45
        euphoria = bool(getattr(sentiment, "euphoria_spike", False))

        if fear:
            if stress < self.stress_calm:
                v.label = "narrative_noise"
                v.risk_multiplier = 1.0            # do not get shaken out
                v.confidence_tilt = 0.0
                log.info(f"fear narrative NOT confirmed by structure "
                        f"(stress={stress:.2f}) - ignoring")
            elif stress >= self.stress_confirm:
                v.label = "confirmed_stress"
                v.risk_multiplier = 0.6
                v.confidence_tilt = -0.10
                log.warning(f"fear confirmed by structure (stress={stress:.2f}) "
                            f"- de-risking")
            else:
                v.label = "caution"
                v.risk_multiplier = 0.85
                v.confidence_tilt = -0.05
        elif euphoria and stress < self.stress_calm:
            v.label = "euphoria_fade"
            v.risk_multiplier = 0.9                # crowd euphoria: slight fade
            v.confidence_tilt = -0.03
        elif stress >= self.stress_confirm:
            v.label = "structural_stress"          # stress without narrative
            v.risk_multiplier = 0.7
            v.confidence_tilt = -0.05

        v.risk_multiplier = max(min(v.risk_multiplier, 1.0), self.floor_mult)
        v.confidence_tilt = max(min(v.confidence_tilt, self.max_tilt), -self.max_tilt)
        return v
