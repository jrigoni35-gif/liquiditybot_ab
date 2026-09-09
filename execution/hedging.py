"""
execution/hedging.py

Beta-weighted delta hedging within the Kraken universe. When net
portfolio delta (signed USD across all positions) exceeds the cap, the
excess is offset with a position in the hedge asset - `others[0]`, the
FIRST asset in the universe list that is not the dominant exposure
(picked by position concentration, NOT by correlation strength), sized
by the EWMA beta from regime/correlation.py. Hedge validity is
conditional on correlation: BOTH the open gate and the unwind test
compute corr(dominant-exposed asset, hedge asset) - the SAME pair on
both paths (the 2026-08-06 consistency fix; the two paths previously
asked about different correlations and thrashed open/unwind, see the
inline comment at the unwind loop). If that correlation decays below
the floor the position is a second bet rather than a hedge and gets
unwound. (In the historical 2-asset book this pair was simply BTC/ETH;
it is NOT hardcoded to those assets.)

Hedge positions are tagged is_hedge=True: exempt from profit tiers,
excluded from signal-side inventory, unwound when net delta normalizes
or correlation breaks.
"""

import logging
from dataclasses import dataclass
from typing import Callable

from core.codes import Code, tag

log = logging.getLogger("liquiditybot.execution.hedging")

EPS = 1e-9


@dataclass
class HedgeAction:
    kind: str          # open | unwind | trim
    asset: str         # asset to trade
    symbol: str        # Kraken symbol, e.g. BTC/USD
    direction: str     # long | short  (for open; for trim: side being reduced)
    usd: float
    position_id: str = ""
    reason: str = ""


class HedgeEngine:
    def __init__(self, config: dict, symbol_map: dict):
        cfg = config or {}
        # FAIL-SAFE DEFAULT (was True). The hedger is COHORT-RESETTING under
        # the era-8 moratorium and has run OFF since cut #11 (2026-09-07) —
        # but that OFF state lived entirely in one config literal, so
        # deleting or renaming the `hedging` block re-armed it with no code
        # diff and no failing test. No config now means no hedging; turning
        # it ON is an explicit act. core/config_guard.py additionally refuses
        # a block that is present but silent about `enabled`.
        self.enabled = bool(cfg.get("enabled", False))
        self.max_net_delta_pct = float(cfg.get("max_net_delta_pct_of_equity", 20.0))
        self.rebalance_band_pct = float(cfg.get("rebalance_band_pct", 8.0))
        self.min_corr = float(cfg.get("min_hedge_correlation", 0.55))
        self.min_hedge_usd = float(cfg.get("min_hedge_usd", 15.0))
        # betas below beta_floor are treated as unreliable -> hedge 1:1;
        # a single hedge never exceeds max_equity_frac of equity.
        # Lifted to config (identical defaults) per overfit discipline.
        self.beta_floor = float(cfg.get("beta_floor", 0.1))
        self.max_equity_frac = float(cfg.get("max_equity_frac", 0.5))
        # 2026-08-07 churn fix (docs/quant/2026-08-07_ada_hedge_churn_
        # HANDOFF.md): three guards on the OPEN side only - the unwind is
        # never gated (invariant 5; the -$318 came from RE-OPENING 147
        # times against a cold estimator, not from closing).
        #   corr_min_samples     open needs this many EWMA observations
        #                        behind the pair's rho (a 2-sample EWMA
        #                        reads |rho|~1; a missing pair reads 0.0 -
        #                        the churn flapped between exactly those)
        #   rehedge_cooldown_sec after ANY unwind of asset A, no new
        #                        hedge on A for this long
        #   churn_max_unwinds /  >= N unwinds of one asset inside the
        #   churn_window_sec     window latches it (FW-070, opens only)
        #                        and AUTO-releases on warm + window
        #                        elapsed - the release depends on time
        #                        and evidence, never on the gated action
        self.corr_min_samples = int(cfg.get("corr_min_samples", 12))
        self.rehedge_cooldown_sec = float(
            cfg.get("rehedge_cooldown_sec", 900.0))
        self.churn_max_unwinds = int(cfg.get("churn_max_unwinds", 3))
        self.churn_window_sec = float(cfg.get("churn_window_sec", 900.0))
        # restart state - persisted via to_dict/from_dict (median PC
        # uptime is 0.5h; an amnesiac cooldown would reset every deploy)
        self._last_unwind: dict = {}     # asset -> ts of last unwind emit
        self._unwind_ts: dict = {}       # asset -> recent unwind ts list
        self._latched: dict = {}         # asset -> latch ts (FW-070)
        self.symbol_map = symbol_map   # asset -> Kraken symbol

    # ---- churn-guard restart state (rides the snapshot) -----------------
    def to_dict(self) -> dict:
        return {"last_unwind": dict(self._last_unwind),
                "unwind_ts": {a: list(v) for a, v in self._unwind_ts.items()},
                "latched": dict(self._latched)}

    def from_dict(self, d: "dict | None") -> None:
        d = d or {}
        self._last_unwind = {str(a): float(t)
                             for a, t in (d.get("last_unwind") or {}).items()}
        self._unwind_ts = {str(a): [float(t) for t in v]
                           for a, v in (d.get("unwind_ts") or {}).items()}
        self._latched = {str(a): float(t)
                         for a, t in (d.get("latched") or {}).items()}

    def _record_unwind(self, asset: str, now: float) -> None:
        self._last_unwind[asset] = now
        w = [t for t in self._unwind_ts.get(asset, [])
             if now - t <= self.churn_window_sec]
        w.append(now)
        self._unwind_ts[asset] = w
        if len(w) >= self.churn_max_unwinds and asset not in self._latched:
            self._latched[asset] = now
            log.warning(tag(
                Code.FW_HEDGE_CHURN_LATCH,
                f"hedge churn latch - {len(w)} unwinds of {asset} inside "
                f"{self.churn_window_sec:.0f}s; re-hedging frozen until "
                f"estimator warm + {self.churn_window_sec:.0f}s elapsed "
                f"(unwinds stay allowed)"))

    def note_external_unwind(self, asset: str, now: float) -> None:
        """Account a hedge close this engine did NOT emit (SWEEP-0).

        `inventory.derisk_actions` force-closes positions straight through
        main.py's derisk loop, which never consults the hedge engine. A
        derisk-forced close of a HEDGE position therefore armed no cooldown
        and never reached the FW-070 counter — leaving the churn backstop
        blind to precisely the loop it exists to stop: derisk closes the
        hedge -> net delta breaches the cap -> evaluate() re-opens it ->
        derisk closes it again, at cycle cadence, which is the 2026-08-07
        ADA shape with the guard bypassed.

        Routing such a close through the same accounting as an emitted
        unwind closes that hole. It gates OPENS only; the unwind path never
        consults any of this (invariant 5 — escapes are never blocked,
        whoever initiated them), and the FW-070 latch still auto-releases on
        warm + window, independent of the action it gates.
        """
        self._record_unwind(asset, now)

    def _open_blocked(self, asset: str, warm: bool, now: float) -> "str | None":
        """None = open allowed; else the (logged-by-caller) block reason.
        BLOCKS OPENS ONLY - never consulted on the unwind path. `warm` is
        computed by the caller for the exact pair the open would gate on."""
        latch_ts = self._latched.get(asset)
        if latch_ts is not None:
            if now - latch_ts >= self.churn_window_sec and warm:
                del self._latched[asset]     # auto-release, logged below
                log.warning(tag(
                    Code.FW_HEDGE_CHURN_LATCH,
                    f"hedge churn latch RELEASED for {asset} "
                    f"(window elapsed, estimator warm)"))
            else:
                return "churn-latched"
        last = self._last_unwind.get(asset)
        if last is not None and now - last < self.rehedge_cooldown_sec:
            return "re-hedge cooldown"
        return None

    @staticmethod
    def _asset_of(symbol: str) -> str:
        return symbol.split("/")[0] if "/" in symbol else symbol

    def net_delta_usd(self, state, marks: dict, include_hedges: bool = True) -> float:
        total = 0.0
        for pos in state.open_positions():
            if not include_hedges and getattr(pos, "is_hedge", False):
                continue
            px = marks.get(pos.symbol) or pos.entry_price
            sgn = 1.0 if pos.direction == "long" else -1.0
            total += sgn * pos.size * px
        return total

    def _exposure_by_asset(self, state, marks: dict) -> dict:
        """Signed SIGNAL-side USD exposure per asset (hedges excluded).
        Extracted so the unwind test and the open condition read the same
        book - they used to compute 'which asset matters' two different
        ways and disagreed, which is what produced the open/unwind
        thrash."""
        by_asset: dict = {}
        for pos in state.open_positions():
            if getattr(pos, "is_hedge", False):
                continue
            a = self._asset_of(pos.symbol)
            px = marks.get(pos.symbol) or pos.entry_price
            sgn = 1.0 if pos.direction == "long" else -1.0
            by_asset[a] = by_asset.get(a, 0.0) + sgn * pos.size * px
        return by_asset

    def evaluate(self, state, marks: dict, equity: float, corr_state,
                 now: float = 0.0) -> list:
        """`now` (2026-08-07): the churn guards' clock, threaded from the
        cycle so replay stays deterministic. The 0.0 default preserves
        every legacy caller: with no unwinds ever recorded, every guard
        is a no-op at now=0."""
        if not self.enabled or equity <= EPS:
            return []
        actions = []
        assets = sorted(self.symbol_map)
        if len(assets) < 2:
            return []

        net = self.net_delta_usd(state, marks)
        # unwind decisions must read SIGNAL-only delta (exclude the hedge
        # itself): a correctly-sized hedge is exactly what pulls TOTAL net into
        # the band, so testing total net would unwind the hedge the moment it
        # worked -> net back out of band -> re-open -> perpetual open/unwind
        # thrash (whenever beta >= 1, the common ETH-hedged-with-BTC case). The
        # OPEN check below deliberately keeps TOTAL net (we cap real exposure).
        signal_net = self.net_delta_usd(state, marks, include_hedges=False)
        cap = equity * self.max_net_delta_pct / 100.0
        band = equity * self.rebalance_band_pct / 100.0

        hedges = [p for p in state.open_positions() if getattr(p, "is_hedge", False)]

        # The SIGNAL-side concentration, computed once: the open path picks
        # its hedge against the dominant exposed asset, and the unwind test
        # below must ask about the SAME pair or the two paths disagree.
        exposure = self._exposure_by_asset(state, marks)
        dominant = (max(exposure, key=lambda a: abs(exposure[a]))
                    if exposure else None)

        # --- unwind conditions ---
        for pos in hedges:
            a = self._asset_of(pos.symbol)
            # corr(DOMINANT EXPOSURE, this hedge's asset) - the exact
            # quantity the open path gated on (see `corr` at the open
            # condition below). It used to be corr(a, others[0]), i.e. the
            # hedge asset against the first OTHER asset alphabetically,
            # which is a different pair entirely and usually an unrelated
            # one. Measured 2026-08-06: a hedge opened on corr(ETH,ADA) >=
            # 0.55 was unwound one cycle later on corr(ADA,ARB) = 0.00,
            # then re-opened because net delta was still over cap - 246
            # fills and ~$143 of spread in 21 minutes, the same open/unwind
            # thrash the signal_net comment above documents a PREVIOUS
            # instance of. Two paths testing two different correlations is
            # the general shape; asking the same question is the fix.
            # No dominant exposure (signal book empty) means the hedge has
            # nothing left to hedge - the "signal delta normalized" arm
            # below owns that case, so correlation must not force it here.
            corr = (abs(corr_state.corr(dominant, a))
                    if corr_state and dominant and dominant != a else 1.0)
            if corr < self.min_corr:
                actions.append(HedgeAction("unwind", a, pos.symbol, pos.direction,
                                           usd=pos.size * (marks.get(pos.symbol) or pos.entry_price),
                                        position_id=pos.position_id,
                                        reason=f"correlation {corr:.2f} below floor"))
            elif abs(signal_net) <= band:
                actions.append(HedgeAction("unwind", a, pos.symbol, pos.direction,
                                           usd=pos.size * (marks.get(pos.symbol) or pos.entry_price),
                                        position_id=pos.position_id,
                                        reason="signal delta normalized"))
        if actions:
            for act in actions:
                if act.kind == "unwind":
                    self._record_unwind(act.asset, now)
            return actions

        # --- open condition ---
        if abs(net) <= cap:
            return []
        # exposure concentrated where? hedge with the other asset. Same
        # helper the unwind test above uses, so "which asset are we
        # actually exposed to" has ONE definition in this file.
        by_asset = self._exposure_by_asset(state, marks)
        if not by_asset:
            return []
        exposed = max(by_asset, key=lambda a: abs(by_asset[a]))
        others = [a for a in assets if a != exposed]
        if not others:
            return []
        hedge_asset = others[0]
        # ---- churn guards (2026-08-07): OPENS only, exits untouched ----
        warm = True
        # typing note: callable() narrows to a callable returning bare
        # `object`, so declare the duck-typed seam's real shape instead -
        # a stub without pair_samples resolves to None (legacy: warm)
        ps: "Callable[[str, str], int] | None" = getattr(
            corr_state, "pair_samples", None)
        if ps is not None:
            warm = int(ps(exposed, hedge_asset)) >= self.corr_min_samples
        if not warm:
            log.info("hedge open skipped: corr(%s,%s) has insufficient "
                     "evidence (< %d samples) - a cold EWMA reads |rho|~1 "
                     "or 0.0 and both are artifacts", exposed, hedge_asset,
                     self.corr_min_samples)
            return []
        blocked = self._open_blocked(hedge_asset, warm, now)
        if blocked:
            log.info("hedge open skipped for %s: %s", hedge_asset, blocked)
            return []
        excess = abs(net) - band

        # ---- trim-over-hedge: if the book already holds the hedge asset on
        # the side the hedge would offset, opening the offsetting order means
        # carrying long AND short in the same asset - two spreads, two fee
        # legs, zero extra protection. Reducing the existing position moves
        # net delta 1:1 (no beta estimate needed) with half the transactions.
        # Genuine one-sided concentration (hedge asset not held) still gets
        # the beta-weighted hedge below.
        overlap_side = "long" if net > 0 else "short"
        trims, remaining = [], excess
        overlaps = [p for p in state.open_positions()
                    if not getattr(p, "is_hedge", False)
                    and self._asset_of(p.symbol) == hedge_asset
                    and p.direction == overlap_side]
        overlaps.sort(key=lambda p: -(p.size * (marks.get(p.symbol)
                                                or p.entry_price)))
        for pos in overlaps:
            if remaining < self.min_hedge_usd:
                break
            px = marks.get(pos.symbol) or pos.entry_price
            cut = min(remaining, pos.size * px)
            if cut < self.min_hedge_usd:
                continue
            trims.append(HedgeAction(
                "trim", hedge_asset, pos.symbol, pos.direction, usd=cut,
                position_id=pos.position_id,
                reason=f"net delta {net:+,.0f} beyond cap {cap:,.0f}; "
                       f"reducing held {overlap_side} beats opening the "
                       f"offsetting hedge"))
            remaining -= cut
        if trims:
            # one corrective step per cycle: re-evaluate on the reduced book
            # next cycle instead of also opening a hedge against stale marks
            return trims

        corr = abs(corr_state.corr(exposed, hedge_asset)) if corr_state else 0.0
        if corr < self.min_corr:
            log.info(f"hedge skipped: corr({exposed},{hedge_asset})={corr:.2f} < floor")
            return []
        beta = corr_state.beta(exposed, hedge_asset) if corr_state else 1.0
        beta = beta if abs(beta) > self.beta_floor else 1.0
        hedge_usd = min(excess * abs(beta), equity * self.max_equity_frac)
        if hedge_usd < self.min_hedge_usd:
            return []
        direction = "short" if net > 0 else "long"
        actions.append(HedgeAction(
            "open", hedge_asset, self.symbol_map[hedge_asset], direction,
            usd=hedge_usd,
            reason=f"net delta {net:+,.0f} beyond cap {cap:,.0f}, beta={beta:.2f}"))
        return actions
