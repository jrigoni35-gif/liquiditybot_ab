"""
scripts/quant_trials.py — rough quant simulated trials for the rev-4
risk / protection / profit protocols.

Not a backtest and not a promise of alpha. The signal here is DELIBERATELY
mediocre noise-plus-momentum; what is on trial is the RISK MACHINERY.
Two arms run over byte-identical price paths and byte-identical entry
signals, so every difference in outcome is attributable to exactly two
things:

  BASELINE   fixed-fraction entries, hard stop, the shipped 4-tier
             engine with the give-back ratchet OFF, no protocol stack.
  PROTOCOL   the same, plus RiskProtocolStack entry sizing (CVaR budget,
             gap cap, loss-budget taper, portfolio heat) and the
             give-back exit ratchet ON.

World model: 3-state regime chain (calm / trend / crisis) with
Student-t innovations and crisis jumps — fat tails, vol clustering,
and gap-through-stop risk are all present, because those are the
conditions the stack exists for.

Gates (FAIL exits nonzero — CI-bindable):
  G1  tail drawdown     p95 MaxDD(protocol) <= 0.85 * p95 MaxDD(baseline)
  G2  tail outcome      CVaR5 of terminal returns improves
  G3  upside intact     median terminal within 1.5pp of baseline
  G4  ruin rate         P(equity < 50%) does not increase
  G5  give-back capture realized/peak on winners improves

Deterministic under --seed. Uses the REAL ProfitTierEngine, the REAL
RiskProtocolStack and the REAL Position dataclass — the trial exercises
the shipped code paths, not a reimplementation.
"""
import argparse
import sys
import time
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, ".")

from core.state import Position                              # noqa: E402
from data.context_engine import ContextState                 # noqa: E402
from risk.long_book import (                                  # noqa: E402
    AddPlan, EvidenceLadder, LongBookEngine, thesis_stop_price)
from risk.profit_tiers import ProfitTierEngine               # noqa: E402
from risk.protocols import RiskProtocolStack                 # noqa: E402

BAR_SEC = 300.0            # 5-minute bars, matches _BAR_MINUTES
HARD_STOP_PCT = 2.0        # both arms: protective stop distance
ENTRY_FRAC = 0.25          # both arms: proposed fraction per entry
SIG_THRESH = 0.55          # both arms: entry threshold on the signal

# COVERAGE BOUNDARY (P3.5, 2026-07-23): TIER_CFG exercises NEITHER the P1
# tier-1 cost-multiple floor NOR the P2 time-stop (PT-060).
#   - P1 floor: inert here because the harness's Position (below, `run_arm`)
#     never sets est_cost_bps — it defaults to 0.0, which the floor treats as
#     exactly inert (0 est_cost_bps -> 0 floor, same discipline the live
#     engine/label sim both use for legacy/unavailable positions).
#   - P2 time-stop: TIER_CFG carries no "time_stop" key at all, so
#     ProfitTierEngine.__init__ reads the code default (disabled) and
#     _time_stop_hit never fires.
# This is a KNOWN, ACCEPTED gap, not an oversight: enabling either lever here
# changes G1-G5's simulated economics and is a CONSCIOUS RE-BASELINE decision,
# not something to flip in a passing commit. Do NOT enable them here.
# ADJUDICATED #103 T6 (2026-07-23): enablement was built, run at 200x1200,
# and REVERTED — the deployed geometry fails G1 in this harness's high-cost
# world (floor delays partial-take de-risking; the floor also raises the
# time-stop's scratch bar via the shared trigger1). Full numbers, ablations,
# mechanism, and the re-enablement recipe:
# docs/quant/2026-07-23_harness_enablement_finding.md. Re-enable only after
# the paper-telemetry floor review resolves, and re-baseline at 200x1200.
TIER_CFG = {
    "tier_1": {"trigger_pct_gain": 1.0, "close_pct_of_position": 25},
    "tier_2": {"trigger_pct_gain": 2.0, "close_pct_of_position": 25},
    "tier_3": {"trigger_pct_gain": 3.5, "close_pct_of_position": 25},
    "tier_4": {"trigger_pct_gain": 5.0, "close_pct_of_position": 25},
    "trailing_stop": {"enabled": True, "activate_after_tier": 2,
                      "trail_pct": 1.0},
    "be_after_tier": 1, "be_buffer_bps": 6, "est_fee_bps": 40,
    "chandelier_k": 3.0, "chandelier_bars": 6,
}
GIVE_BACK = {"enabled": True, "arm_gain_pct": 0.6,
             "arm_vol_mult": 2.0, "giveback_frac": 0.40,
             "tighten_gain_pct": 4.0, "tight_frac": 0.25}
STACK_CFG = {
    "enabled": True,
    "vol_target": {"enabled": False},
    "cvar": {"enabled": True, "alpha": 0.975, "lookback_bars": 288,
             "min_obs": 120, "es_budget_frac": 0.010, "horizon_bars": 24},
    "gap": {"enabled": True, "gap_shock_pct": 15.0,
            "max_equity_loss_pct": 4.0},
    "budget": {"enabled": True, "daily_loss_budget_pct": 2.5,
               "weekly_loss_budget_pct": 6.0, "taper_start": 0.5,
               "floor_mult": 0.15},
    "heat": {"enabled": True, "max_portfolio_heat_frac": 0.35,
             "assumed_corr": 0.9},
    "stack_floor_mult": 0.10,
}

# regime chain: rows calm/trend/crisis; sticky, crisis rare but grabby
TRANS = np.array([[0.984, 0.012, 0.004],
                  [0.015, 0.980, 0.005],
                  [0.030, 0.010, 0.960]])
MU = np.array([0.00000, 0.00040, -0.00180])      # per-bar drift
SIG = np.array([0.0020, 0.0035, 0.0110])         # per-bar vol
TDOF = np.array([12.0, 8.0, 3.0])                # tail thickness
JUMP_P = np.array([0.000, 0.001, 0.020])         # crisis gap risk
JUMP_SCALE = np.array([0.0, 0.01, 0.05])


def make_world(T: int, rng: np.random.Generator):
    """One path: prices, per-bar sigma estimate, entry signal in [0,1]."""
    states = np.empty(T, dtype=int)
    states[0] = 0
    u = rng.random(T)
    cum = TRANS.cumsum(axis=1)
    for t in range(1, T):
        states[t] = np.searchsorted(cum[states[t - 1]], u[t])
    z = rng.standard_t(3.0, T)          # heavy base draw, rescaled per state
    z = z / np.sqrt(3.0 / (3.0 - 2.0))  # unit variance
    r = MU[states] + SIG[states] * z
    jumps = (rng.random(T) < JUMP_P[states]) * \
        rng.normal(0.0, 1.0, T) * JUMP_SCALE[states]
    r = r + jumps
    px = 2000.0 * np.exp(np.cumsum(r))
    # realized per-bar sigma (%, EWMA) — feeds vol-scaled machinery
    sig = np.empty(T)
    v = SIG[0] ** 2
    for t in range(T):
        v = 0.94 * v + 0.06 * r[t] * r[t]
        sig[t] = np.sqrt(v) * 100.0
    # mediocre momentum signal + noise, IDENTICAL across arms
    mom = np.zeros(T)
    m = 0.0
    for t in range(T):
        m = 0.97 * m + 0.03 * r[t]
        mom[t] = m
    signal = 0.5 + 0.30 * np.tanh(mom / 0.0015) + rng.normal(0, 0.05, T)
    return px, sig, signal


def run_arm(px, sig, signal, use_stack: bool, use_giveback: bool,
            seed: int):
    """One arm over one path. Returns terminal_ret, maxdd, capture list."""
    T = len(px)
    cfg = dict(TIER_CFG)
    cfg["give_back"] = dict(GIVE_BACK) if use_giveback \
        else {"enabled": False}
    tiers = ProfitTierEngine(cfg)
    stack = RiskProtocolStack(STACK_CFG) if use_stack else None

    equity = 10_000.0
    peak_eq = equity
    maxdd = 0.0
    pos = None
    entry_notional = 0.0
    peak_open_gain = 0.0
    captures = []
    t0 = 1_700_000_000.0

    for t in range(T):
        now = t0 + t * BAR_SEC
        p = float(px[t])
        if stack is not None:
            stack.observe(equity, marks={"SIM/USD": p}, now=now)

        if pos is not None:
            gain = pos.unrealized_pnl_pct(p)
            peak_open_gain = max(peak_open_gain, gain)
            hard = pos.entry_price * (1.0 - HARD_STOP_PCT / 100.0)
            closed = False
            if p <= hard:                                  # gap-aware stop
                fill = min(p, hard)
                pnl = (fill - pos.entry_price) * pos.size
                equity += pnl - fill * pos.size * 0.004
                if peak_open_gain >= 1.0:
                    captures.append(0.0)       # winner surrendered to stop
                pos, closed = None, True
            else:
                act = tiers.evaluate(pos, p, sigma_bar_pct=float(sig[t]))
                if act.should_close_partial:
                    frac = act.close_pct / 100.0
                    sz = pos.size * frac
                    pnl = (p - pos.entry_price) * sz
                    equity += pnl - p * sz * 0.004
                    pos.size -= sz
                    if act.close_pct >= 100.0 or pos.size <= 1e-12:
                        realized = pos.unrealized_pnl_pct(p)
                        if peak_open_gain >= 1.0:
                            captures.append(
                                max(realized, 0.0) / peak_open_gain)
                        pos, closed = None, True
                    else:
                        pos.tier_closed = max(pos.tier_closed,
                                              act.tier_fired)
            if closed:
                peak_open_gain = 0.0

        if pos is None and signal[t] > SIG_THRESH and t < T - 10:
            frac = ENTRY_FRAC
            if stack is not None:
                heat = 0.0
                mult, _ = stack.entry_multiplier(
                    proposed_frac=frac, equity=equity,
                    sigma_ann_pct=float(sig[t]) * np.sqrt(288 * 365),
                    asset_symbol="SIM/USD", open_heat_frac=heat, now=now)
                frac *= mult
            if frac * equity >= 25.0:                      # min ticket
                size = frac * equity / p
                pos = Position(position_id=f"s{t}", symbol="SIM/USD",
                               direction="long", entry_price=p, size=size,
                               original_size=size,
                               opened_at=datetime.fromtimestamp(
                                   now, tz=timezone.utc))
                entry_notional = frac * equity
                peak_open_gain = 0.0

        mark_eq = equity if pos is None else \
            equity + (p - pos.entry_price) * pos.size
        peak_eq = max(peak_eq, mark_eq)
        maxdd = max(maxdd, (peak_eq - mark_eq) / peak_eq)

    if pos is not None:                                    # flatten at end
        equity += (float(px[-1]) - pos.entry_price) * pos.size
    del entry_notional
    term = equity / 10_000.0 - 1.0
    cap = float(np.mean(captures)) if captures else float("nan")
    return term, maxdd, cap


def run_trials(paths: int, bars: int, seed: int):
    """Run both arms over `paths` shared worlds.

    Returns (baseline_stats, protocol_stats, gates) where each stats dict
    carries med_term / cvar5 / dd_med / dd_p95 / ruin / capture and gates
    is a list of (name, passed, detail) tuples. Importable so the CI
    suite can bind the gates (tests/test_quant_trials.py); main() is just
    the CLI wrapper around this.
    """
    res = {"baseline": {"term": [], "dd": [], "cap": []},
           "protocol": {"term": [], "dd": [], "cap": []}}
    for i in range(paths):
        rng = np.random.default_rng(seed * 100_003 + i)
        px, sig, signal = make_world(bars, rng)
        for name, (st, gb) in {"baseline": (False, False),
                               "protocol": (True, True)}.items():
            term, dd, cap = run_arm(px, sig, signal, st, gb,
                                    seed=seed + i)
            res[name]["term"].append(term)
            res[name]["dd"].append(dd)
            res[name]["cap"].append(cap)

    def stats(arm):
        t = np.array(res[arm]["term"])
        d = np.array(res[arm]["dd"])
        c = np.array(res[arm]["cap"])
        c = c[np.isfinite(c)]
        k = max(int(0.05 * len(t)), 1)
        cvar5 = float(np.sort(t)[:k].mean())
        return {"med_term": float(np.median(t)), "cvar5": cvar5,
                "dd_med": float(np.median(d)),
                "dd_p95": float(np.quantile(d, 0.95)),
                "ruin": float(np.mean(t < -0.5)),
                "capture": float(np.mean(c))}

    b, p = stats("baseline"), stats("protocol")
    gates = [
        ("G1 tail drawdown", p["dd_p95"] <= 0.85 * b["dd_p95"],
         f"p95 {p['dd_p95']:.2%} vs cap {0.85 * b['dd_p95']:.2%}"),
        ("G2 tail outcome", p["cvar5"] >= b["cvar5"],
         f"CVaR5 {p['cvar5']:+.2%} vs {b['cvar5']:+.2%}"),
        ("G3 upside intact", p["med_term"] >= b["med_term"] - 0.015,
         f"median {p['med_term']:+.2%} vs floor "
         f"{b['med_term'] - 0.015:+.2%}"),
        ("G4 ruin rate", p["ruin"] <= b["ruin"],
         f"{p['ruin']:.2%} vs {b['ruin']:.2%}"),
        ("G5 capture", p["capture"] >= b["capture"],
         f"{p['capture']:.2f} vs {b['capture']:.2f}"),
    ]
    return b, p, gates


# =======================================================================
# Compounder Phase C, task C5: the long-horizon accumulation book's OWN
# quant-trial harness. A SEPARATE function with a SEPARATE gate list -
# run_trials/G1-G5 above are NOT touched (task-C5-brief.md's T6 warning:
# "the long book gets its OWN harness function + OWN test file").
#
#   BASELINE   plain periodic-buy accumulation: buys a fixed USD amount
#              every add_min_spacing_hours, UNCONDITIONALLY (no ladder,
#              no thesis stop, no tiers, no ceiling) - just keeps
#              accumulating and holds every unit to the horizon's end.
#              The naive "DCA forever, never think about it" strategy.
#   PROTOCOL   the REAL LongBookEngine.decide_add gate chain (spacing /
#              event-window / context / ceiling headroom, via a REAL
#              EvidenceLadder), the REAL thesis_stop_price structural
#              stop, and the REAL ProfitTierEngine (long-book profit_
#              taking geometry: wider absolute-pct tiers + give-back,
#              vol_scaled off) - same "REAL engines, not a
#              reimplementation" discipline run_trials above uses for
#              ProfitTierEngine/RiskProtocolStack.
#
# Both arms run over the SAME shared world (make_world, reused byte-
# for-byte from the 5m harness above) and the SAME per-path seed, so any
# difference in outcome is attributable to the accumulation GEOMETRY,
# not the price path. Context is held ALIGNED/KNOWN throughout (a
# calm-context accumulation trial) - context/event-window/contraction
# CADENCE gating is a separate, already-unit-tested concern
# (tests/test_long_book_engine.py's own event_window/context_unknown/
# contraction-spacing tests); this harness isolates the ladder-ceiling +
# thesis-stop + tier geometry's economics, exactly the brief's ask.
#
# Config mirrors config.json's SHIPPED long_book block (the deployed
# geometry) as harness-owned literals - same convention as TIER_CFG/
# GIVE_BACK/STACK_CFG above being independent of config.json so this
# harness can never drift with unrelated config tuning, yet still
# tests what actually ships.
# =======================================================================

LONG_REF_EQUITY = 10_000.0        # starting account value, both arms
LONG_EXIT_FRICTION = 0.004        # same round-trip haircut run_arm applies

LONG_TIER_CFG = {
    "tier_1": {"trigger_pct_gain": 8.0, "close_pct_of_position": 20},
    "tier_2": {"trigger_pct_gain": 15.0, "close_pct_of_position": 20},
    "tier_3": {"trigger_pct_gain": 25.0, "close_pct_of_position": 25},
    "tier_4": {"trigger_pct_gain": 40.0, "close_pct_of_position": 25},
    "vol_scaled": False,
    "trailing_stop": {"enabled": True, "activate_after_tier": 2,
                      "trail_pct": 8.0},
    "give_back": {"enabled": True, "arm_gain_pct": 5.0,
                 "giveback_frac": 0.35},
    "time_stop": {"enabled": False},
}
LONG_LADDER_CFG = {
    "r1": {"ceiling_frac": 0.10, "min_closed_paper": 10},
    "r2": {"ceiling_frac": 0.20, "min_closed_live": 15, "pf_floor": 1.2},
    "r3": {"ceiling_frac": 0.30, "min_closed_live": 30,
          "adverse_transitions_survived": 1},
    "dd_downgrade_pct": 6.0,
}
LONG_ENGINE_CFG = {
    "add_usd_frac_of_ceiling": 0.2,
    "add_min_spacing_hours": 24.0,
    "add_offset_pct": 0.5,
    "zone_tol_pct": 0.15,
    "zone_buffer_pct": 0.20,
    "context": {"stress_max_for_add": 1.0, "require_known": True,
               "pause_in_event_window": True,
               "contraction_spacing_mult": 2.0, "pause_in_crisis": True},
    "ladder": LONG_LADDER_CFG,
}
LONG_THESIS_STOP_PCT = 12.0        # matches config.json's shipped default
_LONG_CTX = ContextState(halving_phase="expansion", stress=0.2,
                         stress_known=True, in_event_window=False,
                         calendar_known=True)


def run_long_baseline_arm(px, add_every_bars: int, add_usd: float):
    """Plain periodic-buy accumulation: buys `add_usd` every
    `add_every_bars`, unconditionally (no gates of any kind), holds
    every unit to the horizon's end - never sells, so it pays no exit
    friction and has no ladder/thesis-stop/tier geometry at all. Returns
    (terminal_value, maxdd) in the SAME REF_EQUITY-denominated units the
    protocol arm below uses."""
    T = len(px)
    equity_cash = LONG_REF_EQUITY
    units = 0.0
    peak = LONG_REF_EQUITY
    maxdd = 0.0
    for t in range(T):
        p = float(px[t])
        if t % add_every_bars == 0 and equity_cash >= add_usd:
            units += add_usd / p
            equity_cash -= add_usd
        value = equity_cash + units * p
        peak = max(peak, value)
        maxdd = max(maxdd, (peak - value) / peak if peak > 0 else 0.0)
    term_value = equity_cash + units * float(px[-1])
    return term_value, maxdd


def run_long_protocol_arm(px, sig, seed: int):
    """One path, the REAL long-book geometry: LongBookEngine.decide_add
    (ladder ceiling + spacing, context held aligned/known throughout) +
    thesis_stop_price (structural stop, full close) + ProfitTierEngine
    (long-book tier/give-back geometry, partial banks). Single asset
    ("SIM"), dry_run=True throughout (paper evidence track only - the
    shipped system is paper-first; live evidence requires a realized
    live track record this synthetic world has no way to earn). Returns
    (terminal_value, maxdd)."""
    T = len(px)
    ladder = EvidenceLadder(LONG_LADDER_CFG)
    tiers = ProfitTierEngine(LONG_TIER_CFG)
    equity_cash = LONG_REF_EQUITY
    pos = None                 # core.state.Position | None
    pos_realized = 0.0         # running net PnL of the CURRENT open position
    last_add_ts = None
    peak = LONG_REF_EQUITY
    maxdd = 0.0
    t0 = 1_700_000_000.0

    for t in range(T):
        now = t0 + t * BAR_SEC
        p = float(px[t])

        # ---- exits (always allowed, checked every bar) ----
        if pos is not None:
            if p <= pos.stop_price:                     # LB-031 thesis stop
                proceeds = pos.size * p * (1.0 - LONG_EXIT_FRICTION)
                pos_realized += proceeds - pos.entry_price * pos.size
                equity_cash += proceeds
                ladder.note_close(pos_realized, is_live=False)
                pos, pos_realized = None, 0.0
            else:
                act = tiers.evaluate(pos, p, sigma_bar_pct=float(sig[t]),
                                     now=now)
                if act.should_close_partial:
                    frac = act.close_pct / 100.0
                    sz = pos.size * frac
                    proceeds = sz * p * (1.0 - LONG_EXIT_FRICTION)
                    pos_realized += proceeds - pos.entry_price * sz
                    equity_cash += proceeds
                    pos.size -= sz
                    if act.close_pct >= 100.0 or pos.size <= 1e-12:
                        ladder.note_close(pos_realized, is_live=False)
                        pos, pos_realized = None, 0.0
                    else:
                        pos.tier_closed = max(pos.tier_closed, act.tier_fired)

        # ---- add decision (the real gate chain) ----
        book_exposure_usd = 0.0 if pos is None else pos.size * p
        plan_or_deny = LongBookEngine.decide_add(
            now=now, asset="SIM", mark=p, sigma_bar_pct=float(sig[t]),
            context_state=_LONG_CTX, ladder=ladder, position=pos,
            last_add_ts=last_add_ts, dry_run=True, halted=False,
            entries_enabled=True,
            equity=equity_cash + book_exposure_usd,
            book_exposure_usd=book_exposure_usd, cfg=LONG_ENGINE_CFG)
        if isinstance(plan_or_deny, AddPlan):
            usd = min(plan_or_deny.usd, equity_cash)
            if usd > 0:
                units = usd / plan_or_deny.price
                if pos is None:
                    pos = Position(
                        position_id=f"l{t}", symbol="SIM/USD",
                        direction="long", entry_price=plan_or_deny.price,
                        size=units, original_size=units,
                        opened_at=datetime.fromtimestamp(now, tz=timezone.utc))
                    pos.stop_price = thesis_stop_price(
                        pos.entry_price, LONG_THESIS_STOP_PCT)
                else:
                    total = pos.size + units
                    pos.entry_price = (pos.entry_price * pos.size +
                                       plan_or_deny.price * units) / total
                    pos.size = total
                    pos.original_size = max(pos.original_size, total)
                    pos.stop_price = thesis_stop_price(
                        pos.entry_price, LONG_THESIS_STOP_PCT)
                equity_cash -= usd
                last_add_ts = now

        value = equity_cash + (0.0 if pos is None else pos.size * p)
        peak = max(peak, value)
        maxdd = max(maxdd, (peak - value) / peak if peak > 0 else 0.0)

    term_value = equity_cash + (0.0 if pos is None else pos.size * float(px[-1]))
    return term_value, maxdd


def run_long_trials(paths: int, bars: int, seed: int):
    """Run both accumulation arms over `paths` shared worlds (SAME
    make_world reused from the 5m harness above, SAME per-path seed).

    Returns (baseline_stats, protocol_stats, gates) - gates is a list of
    (name, passed, detail) tuples, same shape as run_trials's own return
    so tests/test_long_trials.py can iterate it generically exactly like
    tests/test_quant_trials.py does for G1-G5. Importable so the CI
    suite can bind G-L1..3; main_long() is the CLI wrapper.
    """
    ecfg_spacing_hours = LONG_ENGINE_CFG["add_min_spacing_hours"]
    add_every_bars = max(int(ecfg_spacing_hours * 3600.0 / BAR_SEC), 1)
    baseline_add_usd = (LONG_ENGINE_CFG["add_usd_frac_of_ceiling"]
                        * LONG_LADDER_CFG["r1"]["ceiling_frac"]
                        * LONG_REF_EQUITY)

    res = {"baseline": {"term_value": [], "dd": []},
           "protocol": {"term_value": [], "dd": []}}
    for i in range(paths):
        rng = np.random.default_rng(seed * 100_003 + i)
        px, sig, _signal = make_world(bars, rng)
        b_val, b_dd = run_long_baseline_arm(px, add_every_bars,
                                            baseline_add_usd)
        p_val, p_dd = run_long_protocol_arm(px, sig, seed=seed + i)
        res["baseline"]["term_value"].append(b_val)
        res["baseline"]["dd"].append(b_dd)
        res["protocol"]["term_value"].append(p_val)
        res["protocol"]["dd"].append(p_dd)

    def stats(arm):
        v = np.array(res[arm]["term_value"])
        d = np.array(res[arm]["dd"])
        term_ret = v / LONG_REF_EQUITY - 1.0
        return {"term_value_med": float(np.median(v)),
                "term_ret_med": float(np.median(term_ret)),
                "dd_med": float(np.median(d)),
                "dd_p95": float(np.quantile(d, 0.95)),
                "ruin": float(np.mean(term_ret < -0.5))}

    b, p = stats("baseline"), stats("protocol")
    gates = [
        ("G-L1 tail drawdown", p["dd_p95"] <= 1.0 * b["dd_p95"],
         f"p95 {p['dd_p95']:.2%} vs cap {b['dd_p95']:.2%}"),
        ("G-L2 ruin", p["ruin"] == 0.0,
         f"protocol ruin {p['ruin']:.2%} (baseline {b['ruin']:.2%})"),
        ("G-L3 terminal capture", p["term_value_med"] >= 0.9 * b["term_value_med"],
         f"${p['term_value_med']:,.2f} vs floor "
         f"${0.9 * b['term_value_med']:,.2f} "
         f"(baseline ${b['term_value_med']:,.2f})"),
    ]
    return b, p, gates


def main_long():
    import tempfile
    from pathlib import Path
    from core.audit import configure_audit
    from ml.registry import configure_registry
    configure_audit(Path(tempfile.gettempdir()) / "liqbot_long_trials_audit.jsonl")
    configure_registry(Path(tempfile.gettempdir()) / "liqbot_long_trials_models")
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", type=int, default=60)
    ap.add_argument("--bars", type=int, default=6000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    t_start = time.time()
    b, p, gates = run_long_trials(a.paths, a.bars, a.seed)
    hdr = f"{'':16s}{'baseline':>14s}{'protocol':>14s}"
    rows = [("terminal value", "term_value_med", "${:,.2f}"),
            ("terminal return", "term_ret_med", "{:+.2%}"),
            ("MaxDD median", "dd_med", "{:.2%}"),
            ("MaxDD p95", "dd_p95", "{:.2%}"),
            ("ruin rate", "ruin", "{:.2%}")]
    print(f"long-book quant trials: {a.paths} paths x {a.bars} bars, "
         f"seed {a.seed} ({time.time() - t_start:.1f}s)")
    print(hdr)
    for label, key, fmt in rows:
        print(f"{label:16s}{fmt.format(b[key]):>14s}{fmt.format(p[key]):>14s}")

    print()
    ok = True
    for name, passed, detail in gates:
        ok &= passed
        print(f"  {'ok  ' if passed else 'FAIL'}  {name:22s} {detail}")
    print(f"\n{'ALL GATES PASS' if ok else 'GATE FAILURE'}")
    return 0 if ok else 1


def main():
    # sim components may audit dispositions or record model lifecycle
    # events; keep synthetic records out of the production trail/ledger
    import tempfile
    from pathlib import Path
    from core.audit import configure_audit
    from ml.registry import configure_registry
    configure_audit(Path(tempfile.gettempdir()) / "liqbot_trials_audit.jsonl")
    configure_registry(Path(tempfile.gettempdir()) / "liqbot_trials_models")
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", type=int, default=200)
    ap.add_argument("--bars", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    t_start = time.time()
    b, p, gates = run_trials(a.paths, a.bars, a.seed)
    hdr = f"{'':14s}{'baseline':>12s}{'protocol':>12s}"
    rows = [("median terminal", "med_term", "{:+.2%}"),
            ("CVaR5 terminal", "cvar5", "{:+.2%}"),
            ("MaxDD median", "dd_med", "{:.2%}"),
            ("MaxDD p95", "dd_p95", "{:.2%}"),
            ("ruin rate", "ruin", "{:.2%}"),
            ("gain capture", "capture", "{:.2f}")]
    print(f"quant trials: {a.paths} paths x {a.bars} bars, seed {a.seed} "
          f"({time.time() - t_start:.1f}s)")
    print(hdr)
    for label, key, fmt in rows:
        print(f"{label:14s}{fmt.format(b[key]):>12s}"
              f"{fmt.format(p[key]):>12s}")

    print()
    ok = True
    for name, passed, detail in gates:
        ok &= passed
        print(f"  {'ok  ' if passed else 'FAIL'}  {name:18s} {detail}")
    print(f"\n{'ALL GATES PASS' if ok else 'GATE FAILURE'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
