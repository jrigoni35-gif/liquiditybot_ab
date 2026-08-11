"""
ml/postmortem.py

Trade postmortems for the operator. Every entry records its thesis:
expected net return (from p(win) and the payoff structure), expected
cost, and the full regime context. Every close is compared against it.

Trigger: realized net return underperforms the entry-time expected
value by more than `shortfall_ratio` (default 0.10 = 10%) of |EV|,
with an absolute floor so near-zero-EV noise doesn't spam reports.
A stopped-out trade always triggers.

Finalization is DELAYED by an observation window (default 45 min) so
the report can answer the question that matters most after a stop-out:
did price recover past entry after we were flushed? If yes, that's a
whipsaw - the stop was inside the noise - and the mitigation is stop
width, not signal quality.

Attribution buckets (each quantified where measurable):
alpha_wrong    - price went straight against us: max favorable
                excursion never reached a meaningful fraction of
                target before the stop. The signal, not the plumbing.
cost_overrun   - realized fees+slippage exceeded the pre-trade
                estimate materially.
whipsaw        - stopped out, then price recovered past entry within
                the observation window.
stop_gap       - the exit realized far beyond the configured stop
                distance: the exit engine could not act when the stop
                was crossed (runner outage / observation gap - lived
                2026-07-14: a 1.8% ETH stop filled at -6.9% after the
                loop was dead for hours). Ops, not costs, not alpha -
                and it must NOT feed the cost/whipsaw governors.
regime_shift   - macro or liquidity regime changed mid-trade.
fear_event     - a confirmed-stress narrative verdict appeared during
                the hold.
Each maps to a concrete mitigation tied to a real config knob, and the
dominant cause feeds ml/monitor.py so *recurring* causes trigger the
bounded auto-adjustments.

Output: WARNING log line + markdown report in outputs/postmortems/ +
row in outputs/postmortem_summary.csv for aggregate pattern review.
"""

import csv
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

from core.runtime import durable_append

log = logging.getLogger("liquiditybot.ml.postmortem")

# Summary CSV column order. Named once so the header written at file
# creation and the row written at append time cannot drift apart - they
# used to be two separate literal lists in two different methods.
SUMMARY_COLS = ["ts", "position_id", "asset", "direction", "p_win",
                "expected_pct", "realized_pct", "shortfall_pct",
                "cause", "cost_overrun_bps", "mfe_pct", "mae_pct",
                "recovered_after_stop", "regime_entry", "regime_exit"]

# THE COMPLETE PATH LEDGER (2026-08-11, geometry-package prerequisite).
# postmortem_summary.csv records only UNDERPERFORMERS - so the excursion
# paths of WINNING trades (the MAE envelope of trades that paid: how much
# heat does a good trade take before it works) were computed by
# _excursions and then DISCARDED, the same computed-and-thrown-away class
# as the drawdown gauge. Any evidence-derived stop geometry needs the
# uncensored population; this ledger records EVERY finalized close. cause
# is empty for a trade that performed to expectation - named, not
# omitted, so the censoring stays visible. Measurement only.
PATHS_COLS = ["ts", "position_id", "asset", "direction", "p_win",
              "expected_pct", "realized_pct", "mfe_pct", "mae_pct",
              "held_h", "stopped_out", "recovered_after_stop",
              "stress_during_hold", "regime_entry", "regime_exit",
              "cause"]

EPS = 1e-9


def _fmt_pct(x: float) -> str:
    """Signed percent, or 'n/a' for a non-finite value (non-material notional
    yields NaN rather than a fabricated number)."""
    return f"{x:+.2f}%" if math.isfinite(x) else "n/a"

MITIGATIONS = {
    "alpha_wrong": ("Signal was wrong from the open (price never approached "
                    "target). Mitigation: monitor raises probability shrinkage "
                    "automatically if this recurs; consider raising "
                    "position_sizer.min_p_win, and check whether these cluster "
                    "in one regime (regime playbook may need direction bias "
                    "tightened)."),
    "cost_overrun": ("Execution cost materially exceeded the pre-trade "
                    "estimate. Mitigation: monitor bumps min_edge_cost_ratio "
                    "if this recurs; verify pretrade fee bps match your live "
                    "Kraken tier; consider lowering max_participation_of_depth."),
    "whipsaw": ("Stopped out, then price recovered past entry - the stop sat "
                "inside the noise. Mitigation: monitor widens stops (bounded) "
                "if this recurs; consider risk.stop_vol_mult +1 or entering "
                "smaller with a wider stop (same risk, more room)."),
    "stop_gap": ("The exit engine could not act when the stop was crossed "
                 "(runner outage / observation gap): the realized loss is an "
                 "OPERATIONS failure, not a market cost - it is excluded from "
                 "cost/whipsaw governor adjustments by cause name. Mitigation: "
                 "keep the runner supervised (session-start self-heal + "
                 "single-instance lock); for live mode prefer venue-resident "
                 "stop orders so the venue enforces the stop while we are "
                 "down. Paper fills at revival price overstate the loss a "
                 "live venue stop would have taken."),
    "regime_shift": ("Macro/liquidity regime flipped mid-trade. Mitigation: "
                    "largely irreducible - regimes lag by design. The stale-"
                    "loser purge and regime stop_mult already respond; "
                    "consider shorter inventory.stale_max_age_hours if these "
                    "cluster."),
    "fear_event": ("A structure-confirmed stress event hit during the hold. "
                "Mitigation: confirmed stress already de-risks new entries; "
                "for open positions consider tightening tiers in "
                "elevated-vol regimes (playbook tier_scale)."),
    "underperformance": ("Closed below expectation without a single dominant "
                        "cause - usually several small drags. Review the "
                        "component table."),
}


@dataclass
class TradeThesis:
    position_id: str
    asset: str
    symbol: str
    direction: str
    entry_ts: float
    p_win: float
    expected_ret_pct: float          # net of expected cost
    expected_cost_bps: float
    stop_pct: float
    target_pct: float                # first-tier-weighted expected win
    entry_regime: str
    entry_liq: str
    narrative_label: str
    fair_value: float
    quote_price: float               # AS price we asked for
    model_scored: bool
    # venue display precision for this pair, so a sub-dollar asset's prices
    # in the report aren't shown on a 2-decimal grid (default keeps old
    # behavior for callers that don't set it)
    price_decimals: int = 2
    # the model's OWN (shrunk, calibrated) probability before any
    # exploration bump: exploration forces p_win up for SIZING, and the
    # governor must grade the model on what it actually said, not on the
    # forced number. -1 = unknown (thesis predates this field).
    model_p: float = -1.0
    # the CHAMPION's armed prediction, computed even when the governor has
    # KILLED the model (use_model=False) so it never reached the sizer.
    # Telemetry-only: feeds ML-075 shadow-recovery at close so a killed model
    # can re-arm on evidence. -1 = unknown/not scored (predates field).
    shadow_p: float = -1.0
    # filled at/after close
    fill_price: float = 0.0
    marks: list = field(default_factory=list)        # (ts, price) during hold
    post_marks: list = field(default_factory=list)   # (ts, price) after close
    exit_ts: float = 0.0
    realized_net_usd: float = 0.0
    realized_ret_pct: float = 0.0
    fees_usd: float = 0.0
    exit_regime: str = ""
    exit_liq: str = ""
    stress_seen: bool = False
    stopped_out: bool = False
    entry_usd: float = 0.0


class PostmortemEngine:
    def __init__(self, config: dict):
        cfg = config or {}
        self.shortfall_ratio = float(cfg.get("shortfall_ratio", 0.10))
        self.min_abs_shortfall_pct = float(cfg.get("min_abs_shortfall_pct", 0.25))
        # realized loss beyond this multiple of the configured stop means
        # the exit engine could not act at the stop (ops gap), not costs
        self.stop_gap_factor = float(cfg.get("stop_gap_factor", 2.0))
        self.observe_min = float(cfg.get("observe_minutes", 45.0))
        self.mark_every_s = float(cfg.get("mark_sample_sec", 30.0))
        self.out_dir = Path(cfg.get("report_dir", "outputs/postmortems"))
        self.summary_path = Path(cfg.get("summary_path",
                                        "outputs/postmortem_summary.csv"))
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._open: dict = {}       # position_id -> TradeThesis (live)
        self._closed: dict = {}     # position_id -> TradeThesis (observing)
        self._last_mark: dict = {}
        # Header creation belongs to durable_append at the append site (it
        # treats a zero-length file as new); doing it here on `not exists()`
        # alone left a size-0 file headerless, and csv.DictReader then reads
        # the first POSTMORTEM as its column names.
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        # complete-population path ledger (see PATHS_COLS)
        self.paths_path = Path(cfg.get("paths_path",
                                       "outputs/trade_paths.csv"))
        self.paths_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    def register_entry(self, thesis: TradeThesis):
        self._open[thesis.position_id] = thesis

    def note_fill(self, position_id: str, fill_price: float):
        t = self._open.get(position_id)
        if t and t.fill_price <= 0:
            t.fill_price = fill_price

    def note_stress(self, confirmed: bool):
        if confirmed:
            for t in self._open.values():
                t.stress_seen = True

    def record_marks(self, marks_by_symbol: dict, now: float):
        for t in self._open.values():
            px = marks_by_symbol.get(t.symbol)
            if px and now - self._last_mark.get(t.position_id, 0) >= self.mark_every_s:
                t.marks.append((now, px))
                if len(t.marks) > 2000:
                    t.marks = t.marks[::2]
                self._last_mark[t.position_id] = now
        for t in self._closed.values():
            px = marks_by_symbol.get(t.symbol)
            if px:
                key = "post_" + t.position_id
                if now - self._last_mark.get(key, 0) >= self.mark_every_s:
                    t.post_marks.append((now, px))
                    self._last_mark[key] = now

    def on_close(self, position_id: str, realized_net_usd: float,
                fees_usd: float, entry_usd: float, stopped_out: bool,
                exit_regime: str, exit_liq: str, now: float,
                asset: str = "", direction: str = ""):
        t = self._open.pop(position_id, None)
        if t is None:
            # ORPHAN CLOSE (2026-08-11 ledger audit): a close with no
            # registered thesis used to vanish silently - two long-book
            # flatten_all closes (ETH d5513dd5, BTC e35c0a59) left no row
            # anywhere, the mechanism behind cohort_eval's 85-93% coverage
            # caveat. The paths ledger is the UNCENSORED population by
            # contract (ALGO-5's ~30-path amendment trigger accrues on it),
            # so a lost thesis must degrade the row, never delete it:
            # excursions/thesis fields print nan, cause says what happened.
            log.warning("postmortem: close for unregistered position %s - "
                        "writing degraded orphan_close path row",
                        position_id[:12])
            self._write_orphan_path(position_id, realized_net_usd,
                                    entry_usd, stopped_out, exit_regime,
                                    now, asset=asset, direction=direction)
            return
        t.exit_ts = now
        t.realized_net_usd = realized_net_usd
        t.fees_usd = fees_usd
        # A non-positive notional is not a real fill. The old code defaulted
        # entry_usd to 1.0, which turned a sub-dollar PnL into a fabricated
        # double-digit realized% (e.g. -$0.18 -> -18.47%) that then contradicted
        # the trade's own MAE and fed the monitor a phantom loss. Emit NaN
        # instead: honest "unknown", and NaN propagates through poll()'s
        # shortfall so a non-material trade never triggers a cause adjustment.
        if entry_usd > EPS:
            t.entry_usd = entry_usd
            t.realized_ret_pct = realized_net_usd / entry_usd * 100.0
        else:
            t.entry_usd = 0.0
            t.realized_ret_pct = float("nan")
        t.stopped_out = stopped_out
        t.exit_regime = exit_regime
        t.exit_liq = exit_liq
        self._closed[position_id] = t
        self._last_mark.pop(position_id, None)

    # ------------------------------------------------------------------
    ORPHAN_MAX_AGE_S = 6 * 3600.0    # no fill by then = order never executed

    def poll(self, now: float) -> list:
        """Finalize theses whose observation window elapsed.
        Returns [(cause, thesis)] for the monitor."""
        # expire orphaned theses: register_entry() fires before order submit,
        # so a rejected/never-filled entry leaves a thesis in _open forever
        # (accruing marks, serialized into every snapshot). Entry orders die
        # in ~25s and algo parents in ~10min; 6h with no fill means no trade.
        for pid, t in list(self._open.items()):
            if t.fill_price <= 0 and now - t.entry_ts > self.ORPHAN_MAX_AGE_S:
                del self._open[pid]
                self._last_mark.pop(pid, None)
                log.info("postmortem: dropped orphaned thesis %s (%s) - "
                         "entry never filled", pid[:8], t.symbol)
        done = []
        for pid, t in list(self._closed.items()):
            if now - t.exit_ts < self.observe_min * 60.0:
                continue
            del self._closed[pid]
            self._last_mark.pop("post_" + pid, None)
            shortfall = t.expected_ret_pct - t.realized_ret_pct
            trigger = t.stopped_out or (
                shortfall > max(self.shortfall_ratio * abs(t.expected_ret_pct),
                                self.min_abs_shortfall_pct))
            cause = self._attribute(t) if trigger else ""
            if trigger:
                self._write_report(t, cause, shortfall)
            # EVERY finalized close reaches the path ledger - winners
            # included. The summary keeps its underperformer semantics
            # untouched (extend, never redefine).
            self._write_path(t, cause)
            done.append((cause, t))
        return done

    # ------------------------------------------------------------------
    def _excursions(self, t: TradeThesis):
        if not t.marks or t.fill_price <= 0:
            return 0.0, 0.0
        sgn = 1.0 if t.direction == "long" else -1.0
        prices = [px for _, px in t.marks]
        # A single anomalous print that slipped past the live mark filter
        # must NOT define a trade's best/worst excursion (observed: a lone
        # up-spike drove MFE to 17-24% on minute-scale BTC scalps while MAE
        # stayed sane, because max() latches the outlier). Reject bad ticks
        # by robust median-absolute-deviation distance before taking the
        # extremes. Telemetry only - _excursions never feeds a decision.
        med = sorted(prices)[len(prices) // 2]
        devs = sorted(abs(p - med) for p in prices)
        mad = devs[len(devs) // 2] or (med * 1e-4)
        clean = [p for p in prices if abs(p - med) <= 8.0 * mad] or prices
        rel = [sgn * (p - t.fill_price) / t.fill_price * 100.0 for p in clean]
        return max(rel + [0.0]), min(rel + [0.0])     # MFE, MAE (pct)

    def _recovered(self, t: TradeThesis) -> bool:
        if not t.stopped_out or not t.post_marks or t.fill_price <= 0:
            return False
        if t.direction == "long":
            return max(px for _, px in t.post_marks) >= t.fill_price
        return min(px for _, px in t.post_marks) <= t.fill_price

    def _cost_overrun_bps(self, t: TradeThesis) -> float:
        # a defensively-floored zero-notional trade (entry_usd==0, set in
        # record()) has no meaningful cost-in-bps: never divide by zero, and
        # never let it be blamed as cost_overrun (0.0 fails the line-307 gate).
        if t.entry_usd <= EPS:
            return 0.0
        realized_fee_bps = t.fees_usd / t.entry_usd * 1e4
        slip_bps = 0.0
        if t.quote_price > 0 and t.fill_price > 0:
            slip = (t.fill_price - t.quote_price) / t.quote_price
            slip_bps = abs(slip) * 1e4
        return (realized_fee_bps + slip_bps) - t.expected_cost_bps

    def _attribute(self, t: TradeThesis) -> str:
        mfe, mae = self._excursions(t)
        overrun = self._cost_overrun_bps(t)
        if self._recovered(t):
            return "whipsaw"
        # checked BEFORE cost_overrun: a stop that realized far beyond its
        # configured distance means the exit engine could not act when the
        # stop was crossed (runner outage / observation gap). The gap loss
        # dwarfs any fee quirk on the same trade, and it must not feed the
        # cost governor (lived 2026-07-14: 1.8% ETH stop filled at -6.9%
        # after dead hours, classified cost_overrun by its 54bps fee tail,
        # 8 false causes holding the entry bump up).
        if (t.stopped_out and t.stop_pct > 0
                and math.isfinite(t.realized_ret_pct)
                and -t.realized_ret_pct > self.stop_gap_factor * t.stop_pct):
            return "stop_gap"
        if overrun > max(10.0, 0.5 * t.expected_cost_bps):
            return "cost_overrun"
        if t.stopped_out and mfe < 0.3 * t.target_pct:
            return "alpha_wrong"
        if t.exit_regime and t.exit_regime != t.entry_regime:
            return "regime_shift"
        if t.stress_seen:
            return "fear_event"
        if t.stopped_out:
            return "alpha_wrong"
        return "underperformance"

    def _write_orphan_path(self, position_id: str, realized_net_usd: float,
                           entry_usd: float, stopped_out: bool,
                           exit_regime: str, now: float,
                           asset: str = "", direction: str = ""):
        """Degraded PATHS_COLS row for a close whose thesis was lost (never
        registered, or dropped by a failed state restore). Same column
        order as _write_path; unknowable fields are nan/0, cause is
        'orphan_close' so the ALGO-5 replay can include or exclude these
        rows EXPLICITLY instead of never seeing them."""
        try:
            if entry_usd > EPS:
                realized_pct = realized_net_usd / entry_usd * 100.0
                realized_s = f"{realized_pct:.3f}"
            else:
                realized_s = "nan"
            row = [f"{now:.0f}", position_id, asset, direction,
                   "nan", "nan", realized_s, "nan", "nan", "nan",
                   int(bool(stopped_out)), 0, 0, "", exit_regime,
                   "orphan_close"]
            durable_append(self.paths_path,
                           lambda f: csv.writer(f).writerow(row),
                           header=",".join(PATHS_COLS) + "\r\n")
        except Exception:
            log.exception("orphan path row append failed - row lost, "
                          "close unaffected")

    def _write_path(self, t: TradeThesis, cause: str):
        """One row per finalized close, WINNERS INCLUDED - the uncensored
        excursion ledger (PATHS_COLS). Guarded like every capture path:
        losing a telemetry row must never break the close that produced
        it."""
        try:
            mfe, mae = self._excursions(t)
            row = [f"{t.exit_ts:.0f}", t.position_id, t.asset, t.direction,
                   f"{t.p_win:.3f}", f"{t.expected_ret_pct:.3f}",
                   f"{t.realized_ret_pct:.3f}", f"{mfe:.3f}", f"{mae:.3f}",
                   f"{(t.exit_ts - t.entry_ts) / 3600.0:.3f}",
                   int(t.stopped_out), int(self._recovered(t)),
                   int(t.stress_seen), t.entry_regime, t.exit_regime, cause]
            durable_append(self.paths_path,
                           lambda f: csv.writer(f).writerow(row),
                           header=",".join(PATHS_COLS) + "\r\n")
        except Exception:
            log.exception("trade-path ledger append failed - row lost, "
                          "close unaffected")

    def _write_report(self, t: TradeThesis, cause: str, shortfall: float):
        mfe, mae = self._excursions(t)
        overrun = self._cost_overrun_bps(t)
        recovered = self._recovered(t)
        held_h = (t.exit_ts - t.entry_ts) / 3600.0
        shortfall_str = f"{shortfall:.2f}pp" if math.isfinite(shortfall) else "n/a"
        name = f"{time.strftime('%Y%m%d_%H%M%S', time.gmtime(t.exit_ts))}_" \
            f"{t.asset}_{t.position_id[:8]}.md"
        body = f"""# Postmortem — {t.direction} {t.symbol} ({t.position_id[:8]})

**Verdict: {cause.upper().replace('_', ' ')}** — realized {_fmt_pct(t.realized_ret_pct)} vs expected {t.expected_ret_pct:+.2f}% (shortfall {shortfall_str})

## Thesis at entry
p(win) {t.p_win:.2f} ({'model' if t.model_scored else 'prior'}) | expected cost {t.expected_cost_bps:.0f}bps | stop {t.stop_pct:.2f}% | target {t.target_pct:.2f}% | regime {t.entry_regime}/{t.entry_liq} | narrative {t.narrative_label} | fv {t.fair_value:.{t.price_decimals}f} | quoted {t.quote_price:.{t.price_decimals}f}

## What happened
filled {t.fill_price:.{t.price_decimals}f} | held {held_h:.1f}h | MFE {mfe:+.2f}% / MAE {mae:+.2f}% | fees ${t.fees_usd:.2f} | cost overrun {overrun:+.0f}bps | exit regime {t.exit_regime}/{t.exit_liq} | stopped_out={t.stopped_out} | recovered_after_stop={recovered} | stress_during_hold={t.stress_seen}

## Mitigation
{MITIGATIONS.get(cause, MITIGATIONS['underperformance'])}
"""
        try:
            (self.out_dir / name).write_text(body, encoding="utf-8")
            row = [f"{t.exit_ts:.0f}", t.position_id, t.asset, t.direction,
                   f"{t.p_win:.3f}", f"{t.expected_ret_pct:.3f}",
                   f"{t.realized_ret_pct:.3f}", f"{shortfall:.3f}", cause,
                   f"{overrun:.1f}", f"{mfe:.3f}", f"{mae:.3f}",
                   int(recovered), t.entry_regime, t.exit_regime]
            durable_append(self.summary_path,
                           lambda f: csv.writer(f).writerow(row),
                           header=",".join(SUMMARY_COLS) + "\r\n")
        except OSError:
            log.exception("postmortem write failed")
        log.warning(
            f"POSTMORTEM {t.symbol} {t.position_id[:8]}: {cause} — realized "
            f"{_fmt_pct(t.realized_ret_pct)} vs expected "
            f"{t.expected_ret_pct:+.2f}% -> {self.out_dir / name}")

    # --- persistence hooks -------------------------------------------
    def to_dict(self) -> dict:
        def ser(t: TradeThesis) -> dict:
            d = dict(t.__dict__)
            d["marks"] = t.marks[-400:]
            d["post_marks"] = t.post_marks[-200:]
            return d
        return {"open": {k: ser(v) for k, v in self._open.items()},
                "closed": {k: ser(v) for k, v in self._closed.items()}}

    def restore(self, d: dict):
        if not d:
            return
        for bucket, store in (("open", self._open), ("closed", self._closed)):
            for pid, td in d.get(bucket, {}).items():
                td = dict(td)
                td["marks"] = [tuple(m) for m in td.get("marks", [])]
                td["post_marks"] = [tuple(m) for m in td.get("post_marks", [])]
                store[pid] = TradeThesis(**td)
