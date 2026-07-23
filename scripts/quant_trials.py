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
