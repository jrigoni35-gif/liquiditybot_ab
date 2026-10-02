"""core/target_book.py - target-inventory basket book (SHADOW; decides nothing).

WHAT THIS IS. A trip-free decision layer: hold a target inventory of each
asset, and trade only when the held weight has drifted far enough from it
to be worth the fee. Four pieces, each from the transaction-cost literature
rather than from a fit:

  target weights   base weights (equal, or inverse-volatility) tilted by a
                   bounded signal: w_i = b_i * (1 + clamp(t_i, -k, +k)),
                   renormalised to the invested fraction.
  aim blend        Garleanu & Pedersen (2013): do not jump to today's
                   target; move a fraction `aim_rate` of the way from what
                   is held. Fast signals decay before they pay their fee.
  no-trade band    Janecek & Shreve (2004) / Rogers (2004) small-cost
                   asymptotics for proportional cost lam and CRRA gamma:
                       delta = (3 / (2 gamma) * lam * w^2 (1 - w)^2) ^ (1/3)
                   in fraction-of-equity units around the Merton weight w.
                   Inside the band: do nothing. Outside: trade to the band
                   EDGE nearest the holding, never to the centre.
  netting          one net order per asset per cycle; sells fund buys in
                   the same cycle; buys are clamped to available cash.

A pressure overlay reads how the market is treating the book (unfilled
orders, adverse markouts, drawdown, volatility shock) and can only make the
book do LESS: widen bands, slow the aim, halt buys. It never adds activity,
and sells (de-risking) are never blocked by it.

CLASSIFICATION - SAFE (shadow). Pure functions, no I/O, no audit writes.
Imported by no decision module (main.py, runner.py, execution/, risk/,
regime/, strategies/, ml/); tests/test_target_book_shadow_pin.py enforces
that and keeps the `target_book` config section out of the decision
fingerprint only while it holds. Wiring this into the order path forks the
decision cohort and needs an operator decision record in docs/quant/.
Reason codes are registered in core/codes.py (TB family).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from core.codes import Code


@dataclass(frozen=True)
class BookParams:
    """Structural knobs. Defaults mirror config.json `target_book`; the
    config section is the authority (core/config_guard.py checks it)."""
    gamma: float = 3.0              # CRRA risk aversion in the band formula
    aim_rate: float = 0.5           # fraction of the gap closed per rebalance
    tilt_cap: float = 0.5           # |tilt| cap as a fraction of base weight
    weighting: str = "equal"        # "equal" | "inverse_vol"
    invest_frac: float = 0.9        # share of equity held as inventory
    min_order_usd: float = 10.0     # venue minimum; smaller trades are skipped
    maker_fee_bps: float = 15.0     # proportional cost lam in the band formula
    vol_target_ann: float = 0.0     # 0 = off; else per-asset annualised vol target
    vol_cap: float = 1.0            # max scale-up of a base weight (<= 1: no leverage)


@dataclass(frozen=True)
class Pressure:
    """Multipliers the pressure overlay hands to plan(). Neutral = (1, 1, False)."""
    band_mult: float = 1.0          # >= 1: widens every band
    aim_mult: float = 1.0           # <= 1: slows the aim
    halt_buys: bool = False         # True: no new inventory this cycle
    reasons: tuple = ()


@dataclass
class Order:
    asset: str
    side: str                       # "buy" | "sell"
    notional_usd: float
    target_w: float
    held_w: float
    new_w: float
    code: str


@dataclass
class Plan:
    equity_usd: float
    orders: list = field(default_factory=list)
    holds: dict = field(default_factory=dict)      # asset -> code string
    bands: dict = field(default_factory=dict)      # asset -> half-width
    aims: dict = field(default_factory=dict)       # asset -> aim weight
    pressure: str = ""                             # TB-020/TB-021 when active


# --------------------------------------------------------------- weights
def base_weights(assets: list, sigma: dict, weighting: str,
                 invest_frac: float) -> dict:
    """Weights summing to invest_frac. inverse_vol falls back to equal for
    any asset with a missing/non-positive sigma (it is not guessed)."""
    if not assets:
        return {}
    if weighting == "inverse_vol":
        inv = {a: 1.0 / sigma[a] for a in assets
               if a in sigma and _pos(sigma[a])}
        if len(inv) == len(assets):
            s = sum(inv.values())
            return {a: invest_frac * inv[a] / s for a in assets}
    return {a: invest_frac / len(assets) for a in assets}


def vol_target_scale(weights: dict, sigma_ann: dict, target: float,
                     cap: float) -> dict:
    """Volatility targeting (Moreira & Muir 2017): scale each base weight by
    min(cap, target / sigma_i). With cap <= 1 it only ever SHRINKS a weight,
    so the freed share sits in cash - a risk lever, not an alpha claim.

    Measured 2026-10-02 on independent Binance daily data 2023-2026 (40%
    target, no leverage): max drawdown fell 13-22 points on ETH/SOL/LINK/XRP
    with the Sharpe difference not distinguishable from zero
    (docs/quant/2026-10-02_feature_program.md). An asset with no measured
    sigma is left unscaled - not guessed."""
    if target <= 0:
        return dict(weights)
    out = {}
    for a, w in weights.items():
        s = sigma_ann.get(a)
        out[a] = w * min(cap, target / s) if _pos(s) else w
    return out


def tilted_targets(base: dict, tilts: dict, tilt_cap: float) -> dict:
    """Bounded multiplicative tilt, renormalised so the invested total is
    unchanged (tilts move weight BETWEEN assets, never in or out of cash)."""
    if not base:
        return {}
    raw = {a: b * (1.0 + _clamp(tilts.get(a, 0.0), -tilt_cap, tilt_cap))
           for a, b in base.items()}
    s, tot = sum(raw.values()), sum(base.values())
    if s <= 0:
        return dict(base)
    return {a: v * tot / s for a, v in raw.items()}


def aim_weights(held: dict, target: dict, aim_rate: float) -> dict:
    return {a: held.get(a, 0.0) + aim_rate * (t - held.get(a, 0.0))
            for a, t in target.items()}


def band_halfwidth(cost_frac: float, w: float, gamma: float) -> float:
    """Janecek-Shreve no-trade half-width in fraction-of-equity units.
    Zero at w in {0, 1}: a book that should hold none (or all) of an asset
    has no reason to tolerate drift."""
    w = _clamp(w, 0.0, 1.0)
    if cost_frac <= 0 or gamma <= 0:
        return 0.0
    return (3.0 / (2.0 * gamma) * cost_frac * w * w * (1.0 - w) ** 2) ** (1.0 / 3.0)


# ------------------------------------------------------------------ plan
def plan(units: dict, cash_usd: float, prices: dict, target_w: dict,
         params: BookParams, pressure: Pressure | None = None) -> Plan:
    """One rebalance decision. Pure: same inputs, same Plan.

    units/prices are per asset; an asset without a positive price is held
    as-is (TB-060) - no price, no trade. Long-only: never sells more than
    held, never spends more cash than the sells in this cycle free up."""
    pr = pressure or Pressure()
    priced = {a for a in target_w if _pos(prices.get(a))}
    inv_usd = sum(units.get(a, 0.0) * prices[a] for a in priced)
    equity = cash_usd + inv_usd
    out = Plan(equity_usd=equity)
    if pr.halt_buys:
        out.pressure = Code.TB_PRESSURE_HALT.value
    elif pr.band_mult > 1.0 or pr.aim_mult < 1.0:
        out.pressure = Code.TB_PRESSURE_WIDEN.value
    if equity <= 0:
        return out
    for a in target_w:
        if a not in priced:
            out.holds[a] = Code.TB_NO_PRICE.value
    held = {a: units.get(a, 0.0) * prices[a] / equity for a in priced}
    tgt = {a: target_w[a] for a in priced}
    aims = aim_weights(held, tgt, params.aim_rate * pr.aim_mult)
    lam = params.maker_fee_bps / 1e4
    raw: list = []
    for a in sorted(priced):
        band = band_halfwidth(lam, tgt[a], params.gamma) * pr.band_mult
        out.bands[a], out.aims[a] = band, aims[a]
        gap = held[a] - aims[a]
        if abs(gap) <= band:
            out.holds[a] = Code.TB_IN_BAND.value
            continue
        new_w = aims[a] + band if gap > 0 else aims[a] - band
        new_w = max(new_w, 0.0)
        raw.append((a, new_w, (new_w - held[a]) * equity))
    sells = [(a, w, n) for a, w, n in raw if n < 0]
    buys = [(a, w, n) for a, w, n in raw if n > 0]
    freed = 0.0
    for a, w, n in sells:
        if -n < params.min_order_usd:
            out.holds[a] = Code.TB_BELOW_MIN.value
            continue
        freed += -n
        out.orders.append(Order(a, "sell", -n, tgt[a], held[a], w,
                                Code.TB_REBALANCE.value))
    if pr.halt_buys:
        for a, _, _ in buys:
            out.holds[a] = Code.TB_PRESSURE_HALT.value
        return out
    spendable = max(cash_usd + freed, 0.0)
    want = sum(n for _, _, n in buys)
    scale = 1.0 if want <= spendable else spendable / want
    for a, _w, n in buys:
        n_eff = n * scale
        if n_eff < params.min_order_usd:
            out.holds[a] = Code.TB_BELOW_MIN.value
            continue
        code = Code.TB_CASH_CLAMP if scale < 1.0 else Code.TB_REBALANCE
        out.orders.append(Order(a, "buy", n_eff, tgt[a], held[a],
                                held[a] + n_eff / equity, code.value))
    return out


# -------------------------------------------------------------- pressure
@dataclass(frozen=True)
class PressureLimits:
    """Thresholds where each pressure term starts to bite (config authority)."""
    min_fill_ratio: float = 0.3       # below: orders are not getting filled
    adverse_markout_bps: float = 15.0  # beyond: fills are being picked off
    vol_shock_ratio: float = 2.0      # short/long sigma above: regime shock
    drawdown_brake: float = 0.25      # equity drawdown at which buys halt
    max_band_mult: float = 3.0
    min_aim_mult: float = 0.25


def pressure_from(fill_ratio: float | None, markout_bps: float | None,
                  vol_ratio: float | None, drawdown: float | None,
                  lim: PressureLimits) -> Pressure:
    """Map observed stress to a de-risking-only overlay.

    Each term contributes its fractional excess over its threshold; the sum
    widens bands (capped at max_band_mult) and slows the aim (floored at
    min_aim_mult). None = not observed = no contribution (never guessed)."""
    excess, reasons = 0.0, []
    if fill_ratio is not None and fill_ratio < lim.min_fill_ratio:
        excess += (lim.min_fill_ratio - fill_ratio) / lim.min_fill_ratio
        reasons.append(f"fill_ratio {fill_ratio:.2f}<{lim.min_fill_ratio}")
    if markout_bps is not None and markout_bps < -lim.adverse_markout_bps:
        excess += (-markout_bps - lim.adverse_markout_bps) / lim.adverse_markout_bps
        reasons.append(f"markout {markout_bps:.1f}bps")
    if vol_ratio is not None and vol_ratio > lim.vol_shock_ratio:
        excess += (vol_ratio - lim.vol_shock_ratio) / lim.vol_shock_ratio
        reasons.append(f"vol_ratio {vol_ratio:.2f}>{lim.vol_shock_ratio}")
    halt = drawdown is not None and drawdown >= lim.drawdown_brake
    if halt:
        reasons.append(f"drawdown {drawdown:.2%}>={lim.drawdown_brake:.0%}")
    band_mult = min(1.0 + excess, lim.max_band_mult)
    aim_mult = max(1.0 / (1.0 + excess), lim.min_aim_mult)
    return Pressure(band_mult, aim_mult, halt, tuple(reasons))


# --------------------------------------------------------------- helpers
def asset_floor_breached(closes: list, floor_drawdown: float) -> bool:
    """True when the last close sits more than floor_drawdown below the
    window's high: the rebalancer stops buying a collapsing asset (the
    rebalancing premium assumes relative mean reversion; a trend to zero
    breaks it)."""
    if not closes or floor_drawdown <= 0:
        return False
    hi = max(closes)
    return hi > 0 and closes[-1] < (1.0 - floor_drawdown) * hi


def _pos(x) -> bool:
    try:
        return x is not None and math.isfinite(float(x)) and float(x) > 0
    except (TypeError, ValueError):
        return False


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x
