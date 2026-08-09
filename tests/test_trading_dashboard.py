"""tests/test_trading_dashboard.py — the command dashboard's structural
contract, CI-enforced:

  1. the generator (scripts/build_trading_dashboard.py — the SOURCE OF TRUTH)
     and the shipped docs/grafana/liquiditybot_command.json are identical, so
     hand-edits or a stale regeneration can't drift them apart;
  2. valid UI-importable shape: unwrapped, schemaVersion at top level, stable
     uid, unique panel ids, no overlapping gridPos;
  3. EVERY liquiditybot_* metric referenced by a panel query is actually
     emitted by scripts/gc_pusher.py — a renamed/removed metric breaks the
     build instead of silently blanking a panel ("code reacts to the panels");
  4. only supported panel types (stat/state/table/gauge/bargauge/timeseries/
     piechart/text) — the deprecated "graph" plugin is never allowed.
"""
import json
import time
import re
from pathlib import Path

import scripts.build_trading_dashboard as gen
import scripts.gc_pusher as gp

ROOT = Path(__file__).resolve().parents[1]

# a synthetic status.json exercising every section the pusher exports, so the
# emitted-metric universe is complete for check 3
_SYNTH_STATUS = {
    "written_at": time.time(), "equity": 5000.0, "daily_pnl": 3.0,
    "weekly_pnl": 11.0, "savings": 20.0, "reserve": 8.0,
    "realized_total": 1.0, "drawdown_pct": 0.4, "fees_total": 2.0,
    # Honest all-time P&L (a6334162). These four status keys and their
    # gc_pusher gauges shipped WITHOUT reaching this fixture; nothing failed
    # only because no panel referenced them yet, so the staleness sat latent
    # until the hero tile was repointed. Values satisfy the identity the
    # production writer maintains:
    #   net_pnl_all_time = equity - starting_capital = 5000.0 - 5000.0 = 0.0
    #   realized_net_all_in = realized_total - entry_fees_total = 1.0 - 1.2
    "starting_capital": 5000.0, "entry_fees_total": 1.2,
    "net_pnl_all_time": 0.0, "realized_net_all_in": -0.2,
    "cycle": 10, "cycle_lifetime": 100, "feed_latency_ms": 50.0,
    "marks_age_sec": 1.0, "equity_drift_pct": 0.0, "exit_eval_failures": 0,
    "cycle_consecutive_failures": 0, "runner_state": "RUNNING",
    "halted": False, "entries_enabled": True, "audit_dropped_writes": 0,
    "audit_tail_truncations": 0,
    "positions": [{"symbol": "BTC/USD", "direction": "long", "entry": 60000.0,
                   "mark": 60600.0, "size": 0.001, "stop": 58800.0,
                   "upnl_usd": 0.6, "upnl_pct": 1.0, "tiers_fired": 1,
                   "age_h": 2.0, "p_win": 0.7}],
    # goals ledger (added to the fixture 2026-08-02). The block existed in
    # real status.json but never here, so gc_pusher emitted no goal_* metric
    # under test and test_every_query_hits_an_emitted_metric would reject any
    # panel that showed goal progress — a fixture gap reading as a dashboard
    # error. Shape mirrors the live file: attainment_pct is what makes
    # liquiditybot_goal_attainment_pct emit at all.
    "goals": {
        "week": {"period": "week", "goal": 80.0, "running": -14.4,
                 "attainment_pct": 0.0, "on_track": False},
        "month": {"period": "month", "goal": 350.0, "running": -1.83,
                  "attainment_pct": 0.0, "on_track": False}},
    "performance": {
        "overall": {"trades": 20, "win_rate": 0.55, "win_rate_lcb": 0.34,
                    "profit_factor": 1.8, "expectancy_usd": 2.3,
                    "expectancy_r": 0.4, "payoff_ratio": 1.6, "sharpe": 0.9,
                    "sortino": 1.1, "cur_loss_streak": 1, "max_loss_streak": 4,
                    "net_usd": 46.0, "gross_profit_usd": 90.0,
                    "gross_loss_usd": 44.0, "avg_win_usd": 8.0,
                    "avg_loss_usd": -4.9},
        "by_asset": {"BTC": {"trades": 8, "win_rate": 0.5,
                             "profit_factor": 1.2, "expectancy_usd": 1.0,
                             "net_usd": 5.0, "cur_loss_streak": 2,
                             "max_loss_streak": 3}},
        # probe/conviction split (2026-08-09). "unknown" holds trades
        # restored from a pre-split snapshot and drains with the window;
        # it is a real bucket PerformanceTracker.snapshot() always emits,
        # so the fixture carries all three.
        "by_conviction": {
            "conviction": {"trades": 12, "win_rate": 0.58,
                           "profit_factor": 1.9, "expectancy_usd": 3.1,
                           "payoff_ratio": 1.7, "net_usd": 37.2},
            "probe": {"trades": 6, "win_rate": 0.33,
                      "profit_factor": 0.7, "expectancy_usd": -0.4,
                      "payoff_ratio": 0.9, "net_usd": -2.4},
            "unknown": {"trades": 2, "win_rate": 0.5,
                        "profit_factor": 1.0, "expectancy_usd": 0.0,
                        "payoff_ratio": 1.0, "net_usd": 0.0}}},
    "order_manager": {"venue_rejects": 0, "deadman_failures": 0,
                      "latency_ms": 40.0, "maker_fills": 7, "taker_fills": 3,
                      "maker_share": 0.7, "maker_notional_usd": 500.0,
                      "taker_notional_usd": 200.0, "avg_slip_bps": -1.0,
                      "worst_slip_bps": 6.0,
                      # Cochran notional-weighted slip (f877de0) — added
                      # to the pusher whitelist 2026-07-29 (wave-2/3
                      # verify found it exported nowhere)
                      "slip_bps_notional_weighted": -0.4},
    "markout": {"horizons_sec": [5.0], "pending": 0, "overall": {},
                "by_asset": {"BTC": {"5": {"markout_bps": -2.0, "n": 4}}}},
    "monitor": {"level": 0, "drift_share": 0.0, "brier": 0.2,
                "baseline_brier": 0.24, "calibration_gap": 0.05,
                "window_trades": 20, "shrinkage": 0.35, "kelly_mult": 1.0,
                "stop_widen": 1.0, "edge_ratio_bump": 0.0, "use_model": True,
                "champion_brier": 0.19, "hit_rate": 0.6, "hit_rate_lcb": 0.4,
                "avg_p": 0.65},
    "ml": {"history_rows": 100, "open_candidates": 5, "pending_labels": 2,
           "model_fallbacks": 0, "infer_faults": 0, "contract_failed": 0,
           "smc_faults": 0, "retrain_failures": 0, "retrain_flag": False,
           "model_kind": "blend",
           "labels_by_source": {"live": 20, "candidate": 80},
           # AFML corpus-quality stats (history.last_load_stats via runner),
           # extended with the era-gated training exclusion + label-era
           # transition instrumentation (docs/quant/2026-07-26_era_
           # exclusion.md) — shapes copied verbatim from the brief's
           # measured example (the bot's own status.json the morning the
           # era machinery went live).
           "load_stats": {"live_clean": 20, "mean_uniqueness": 0.42,
                          "dropped_dirty": 0, "dropped_clash": 3,
                          "prior_skew": False,
                          "era_exclusion": {
                              "armed": True, "active": True,
                              "forced_off": False, "forced_on": False,
                              "min_new_era_rows": 150, "new_era_rows": 233,
                              "excluded": {
                                  "total": 4850,
                                  "by_era_source": {
                                      "exit_sim_time_stop": {"candidate": 457},
                                      "exit_sim": {"candidate": 2436,
                                                   "live": 195},
                                      "legacy": {"live": 47,
                                                 "candidate": 1715}}}},
                          "label_era": {
                              "triple_barrier": {
                                  "rows": 233, "label_rate": 0.3991,
                                  "by_reason": {
                                      "tb_pt": {"rows": 103,
                                                "label_rate": 0.8738},
                                      "tb_sl": {"rows": 122,
                                                "label_rate": 0.0},
                                      "tb_time": {"rows": 8,
                                                  "label_rate": 0.375}}},
                              "legacy": {"rows": 1762, "label_rate": 0.2611,
                                        "by_reason": {}},
                              "exit_sim": {"rows": 2436,
                                          "label_rate": 0.1345,
                                          "by_reason": {}},
                              "exit_sim_time_stop": {"rows": 457,
                                                     "label_rate": 0.0066,
                                                     "by_reason": {}}},
                          "era_mix_drift": {"tvd": 0.41, "fired": True,
                                           "n_recent": 233, "n_total": 4897}},
           # geometry-alignment T6 (spec D6, ML-082): labeled-vs-realized
           # bracket comparator, ml/history.py's bracket_divergence_
           # summary() shape — a SIBLING of load_stats (updated at close
           # time, not only on a retrain). n>0 here so check 3
           # (test_every_query_hits_an_emitted_metric) exercises the new
           # liquiditybot_bracket_divergence_rate/_n gauges.
           "bracket_divergence": {"n": 42, "agree_rate": 0.881,
                                  "mean_abs_ret_delta_pct": 0.09},
           # SPB-R probe budget (spec §8, main.probe_budget_status() via
           # runner._probe_budget_status) — populated so check 3 proves
           # every PROBE BUDGET row query against an emitted metric.
           # avg_cost_24h numeric here (None = honest absence = not
           # emitted, which would fail the panel-coverage check).
           "probe_budget": {
               "mode": "share_cap", "tokens": 2.71, "capacity": 5.0,
               "refill_per_day": 15.0, "governor_factor": 1.0,
               "tuition_24h_usd": 0.35, "tuition_cap_usd": 4.97,
               "admits_24h": 11, "refunds_24h": 2,
               "denied_exhausted_24h": 40, "rolls_failed_24h": 120,
               "avg_cost_24h": 1.27, "labels_24h": 11,
               "live_labels_per_day_7d": 10.4, "tb_era_labels": 23,
               "unlock_eta_days": 3.4, "avg_concurrent_probes": 3.7,
               "open_probes": 3,
               "per_asset": {"ETH": {"n_live": 73, "w_asset": 0.5584,
                                     "cost": 1.7908,
                                     "eff_weight": 0.0412}},
               "per_regime_live": {"range": 227, "bear": 4}},
           "gate_stats": {"enabled": True, "labeled": 100, "base_rate": 0.2,
                          "weights": {"if_1_flow_persistence": 0.9},
                          "divergence": {"if_1_flow_persistence": 0.12}}},
    "signals": {"BTC": {"confirmed": True, "confidence": 0.8, "urgency": 0.4,
                        "concentration": 0.6,
                        "gates": {"if_1_flow_persistence": True}}},
    # tangible-value ladder (regime/haven.py): the fixture must carry it or
    # the panels read as querying a never-emitted metric — the same fixture
    # gap that hid the gate_divergence instrument
    "haven": {"state": "flight_to_quality", "gradient": 1.8,
              "returns": {"PAXG": 2.1, "BTC": 0.4, "ETH": -0.6,
                          "ALT": -3.2},
              "spreads": {"PAXG-BTC": 1.7, "BTC-ETH": 1.0, "ETH-ALT": 2.6},
              "rungs_seen": 4, "detail": "fixture"},
    "manip_suspect": {"BTC": 0.1},
    "regimes": {"BTC": {"macro": "range", "momentum": 0.1, "vol": "low",
                        "vol_pct": 20.0, "liq": "liquid", "spread_bps": 0.5,
                        "spoof": 0.0, "basis_bps": -1.0}},
    "code_stats": {"by_prefix": {"PT": 9},
                   "entry_codes": {"PT-041": 6, "PT-050": 2}},
    "ws_kraken": {"connected": True, "books": 6, "reconnects": 0},
    "fault": {"state": "ARMED", "faults": {}},
    "watchdog": {"entries_blocked": False, "critical_stale": False,
                 "velocity_tripped": False, "divergent": [],
                 "stale_assets": []},
    "firewall": {"fault": None, "counters": {"FW-040": 2}},
    "circuit_breaker": {"enabled": True, "loss_streak": 4,
                        "streaks": {"BTC": 1}, "tripped": {"ETH": 3.0}},
    # drawdown_mtm_pct/hard_stop_dd_pct added 2026-08-09. The MTM drawdown is
    # the basis the catastrophe hard stop and the sizer throttle actually key
    # off; the top-level drawdown_pct measures from starting capital on
    # cash+savings only and is blind to unrealized loss. Both are emitted.
    "risk_protocols": {"daily_budget_used_frac": 0.1,
                       "weekly_budget_used_frac": 0.05, "taper_mult": 1.0,
                       "heat_frac": 0.04, "heat_cap_frac": 0.35,
                       "dd_throttle_mult": 1.0,
                       "drawdown_mtm_pct": 3.1, "hard_stop_dd_pct": 15.0},
    "skimmer": {"enabled": True, "candidates": 8, "max_extra": 6,
                "promoted": ["SOL/USD"],
                "scores": {"SOL/USD": {"score": 0.7, "spread_bps": 2.0,
                                       "depth_usd": 60000, "ts": 1.7e9}}},
    "thales": {"assets": {"BTC": {
        "grid": 0.1, "metronome": 0.2, "clockwork": 0.0, "clockwork_dir": 0,
        "stop_zone": 0.3, "barclose": 0.1, "spoof_bid": 0.05, "spoof_ask": 0.0,
        "feed_dirty": 0.0, "lapses": 0, "bar_holes": 0, "lapse_warmup_sec": 0}},
        # V2 reliability ledger (2026-07-29 shadow-grading unlock):
        # per-detector graded evidence + weight, and the shared base-
        # rate null — gc_pusher exports these for the Screening board's
        # "earning its keep" panels
        "reliability": {"grid": {"fired": 21, "vindicated": 7,
                                 "weight": 0.12}},
        "reliability_base": {"fired": 40, "vindicated": 8}},
    # Compounder Phase A conviction formula (risk/conviction.py status()) —
    # #120 telemetry: admission share + regime breakdown + denial tally.
    "conviction": {
        "enabled": True, "mode": "report", "evaluated": 42, "admitted": 30,
        "denials": {"CV-010": 8, "CV-020": 4},
        "share": 0.71, "n": 40,
        "by_regime": {"range": {"share": 0.65, "n": 20},
                      "trend": {"share": 0.8, "n": 20}},
        "alarm": "ok",
    },
    # Compounder Phase B context engine (data/context_engine.py
    # ContextFeed.status(), Task B6) — telemetry-only: halving clock,
    # macro-stress dial, flow dials, event-window state, per-source
    # ok/dark map. Shape copied verbatim from the real status() method.
    "context": {
        "enabled": True, "halving_phase": "expansion", "days_since": 300,
        "days_to_next": 500, "stress": 0.42, "stress_known": True,
        "cot_z": -0.3, "stable_wk_pct": 1.2, "flow_known": True,
        "in_event_window": False, "next_event": "cme_expiry:2026-07-31",
        "calendar_known": True,
        "sources": {"dff": True, "t10y2y": True, "vix": True, "cot": True,
                    "stablecoins": True, "calendar": True, "halving": True},
        "last_poll_age_sec": 120.5,
    },
    # Compounder Phase C long-horizon accumulation book (Task C6) —
    # runner.py's BotRunner._long_book_status() shape, copied verbatim
    # (see the real section for field provenance: rung/ceiling_frac from
    # risk/long_book.py's EvidenceLadder; book_exposure_usd/adds_placed/
    # paused_reason/context_aligned_last from main.py's engine-integration
    # attributes; pf_live already JSON-safe, None never the raw inf).
    "long_book": {
        "enabled": True, "rung": 2, "ceiling_frac": 0.2,
        "book_exposure_usd": 850.0, "positions": 1, "adds_placed": 6,
        "last_add_age_h": 3.5, "paused_reason": "",
        "closed_paper": 14, "closed_live": 16, "pf_live": 1.42,
        "context_aligned_last": True,
    },
}


def _shipped(fname: str) -> dict:
    return json.loads((ROOT / "docs" / "grafana" / fname)
                      .read_text(encoding="utf-8"))


def _all_panels(d: dict) -> list:
    """Every panel including members nested inside collapsed rows (Grafana
    moves a collapsed row's panels INTO the row object's own `panels` list)."""
    out = []
    for p in d["panels"]:
        out.append(p)
        out.extend(p.get("panels") or [])
    return out


def _row_section(d: dict, key: str) -> list:
    """Panels belonging to the row whose title contains `key` — nested list
    for a collapsed row, the slice up to the next row otherwise."""
    panels = d["panels"]
    idx = [i for i, p in enumerate(panels)
           if p["type"] == "row" and key in p["title"].upper()]
    if not idx:
        return []
    row = panels[idx[0]]
    if row.get("collapsed"):
        return list(row.get("panels") or [])
    start = idx[0] + 1
    end = next((i for i in range(start, len(panels))
                if panels[i]["type"] == "row"), len(panels))
    return panels[start:end]


def test_generator_matches_shipped_json():
    for fname, d in gen.DASHBOARDS.items():
        assert d == _shipped(fname), \
            f"{fname} differs from the generator — regenerate with " \
            "`python scripts/build_trading_dashboard.py` (never hand-edit)"


def test_expected_boards_present():
    assert set(gen.DASHBOARDS) == {
        "liquiditybot_command.json", "liquiditybot_execution.json",
        "liquiditybot_problem_solution.json", "liquiditybot_screening.json"}


def test_importable_shape_and_layout_per_board():
    uids = set()
    for fname in gen.DASHBOARDS:
        d = _shipped(fname)
        assert "dashboard" not in d and d["schemaVersion"] == 39, fname
        assert d["uid"] and d["uid"] not in uids, f"{fname}: uid not unique"
        uids.add(d["uid"])
        assert d["panels"] and d["panels"][0]["gridPos"]["y"] == 0, fname
        everything = _all_panels(d)
        ids = [p["id"] for p in everything]
        assert len(ids) == len(set(ids)), f"{fname}: duplicate panel ids"
        rects = [(p["gridPos"]["x"], p["gridPos"]["y"], p["gridPos"]["w"],
                  p["gridPos"]["h"], p["id"]) for p in everything]

        def ov(a, b):
            return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0]
                        or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])
        bad = [(a[4], b[4]) for i, a in enumerate(rects)
               for b in rects[i + 1:] if ov(a, b)]
        assert not bad, f"{fname}: overlapping panels: {bad}"
    # the command board keeps the desk uid so it replaces the old monolith
    assert _shipped("liquiditybot_command.json")["uid"] == "liquiditybot-trading"


def test_all_boards_use_supported_panel_types():
    # professional mix: stat (sparkline) / gauge / bargauge / timeseries /
    # color-coded table. The deprecated "graph" plugin is never allowed.
    # marcusolsson-dynamictext-panel: the Business Text CSS injector —
    # deliberately supported since 2026-07-23 (operator installed the
    # signed plugin; test_glass_suite pins exactly one per board)
    allowed = {"row", "stat", "table", "gauge", "timeseries", "bargauge",
               "text", "piechart", "marcusolsson-dynamictext-panel"}
    for fname in gen.DASHBOARDS:
        kinds = {p["type"] for p in _all_panels(_shipped(fname))}
        assert "graph" not in kinds, f"{fname}: deprecated graph panel"
        assert kinds <= allowed, f"{fname}: unexpected panel type {kinds}"


def test_timeseries_never_spans_an_outage():
    # 2026-07-26: the bot was dark 03:05->14:55 UTC and the equity + Brier
    # panels drew SMOOTH GLIDES across the whole 11.8h hole, because every
    # timeseries carried spanNulls=True (connect any gap, however long).
    # The outage read as a gentle downward trend. Feed latency, a `stat`
    # sparkline that never spanned, showed the same gap honestly — so the
    # board was simultaneously telling the truth and lying about one event.
    # spanNulls must be a BOUNDED millisecond budget, never True.
    period_ms = 30 * 1000        # gc_pusher GC_PERIOD_SEC default
    seen = 0
    for fname in gen.DASHBOARDS:
        for p in _all_panels(_shipped(fname)):
            if p["type"] != "timeseries":
                continue
            seen += 1
            span = p["fieldConfig"]["defaults"]["custom"]["spanNulls"]
            assert span is not True, (
                f"{fname}/{p['title']}: spanNulls=True draws a line across "
                "an outage of ANY length — an 11.8h hole renders as a trend")
            assert isinstance(span, int) and not isinstance(span, bool), \
                f"{fname}/{p['title']}: spanNulls must be a ms budget"
            # tolerate restart jitter, break on real downtime
            assert 2 * period_ms <= span <= 30 * period_ms, (
                f"{fname}/{p['title']}: spanNulls={span}ms outside "
                f"[{2*period_ms}, {30*period_ms}] — too tight breaks on a "
                "routine restart, too loose hides an outage")
            # a bounded budget can leave isolated samples either side of a
            # gap; showPoints="never" would render those as literally
            # nothing, and a blank panel reads as "fine", not "no data"
            assert p["fieldConfig"]["defaults"]["custom"]["showPoints"] \
                != "never", (
                f"{fname}/{p['title']}: with bounded spanNulls, showPoints "
                "must not be 'never' — isolated samples would be invisible")
    assert seen >= 5, f"expected the known timeseries panels, saw {seen}"


def test_every_board_surfaces_telemetry_age():
    # The companion to the spanNulls fix. Value tiles reduce with
    # "lastNotNull", so while the bot is dead they keep displaying the last
    # push — during the 2026-07-26 outage the execution board showed a
    # confident Brier, model rung and fill stats for 11.8h with NO cue that
    # the runner was gone (it had zero staleness panels). gc_pusher is
    # honest at the source (past STALE_AFTER_SEC it pushes running=0 +
    # stale=1 and withholds market/PnL gauges) — the board has to be honest
    # too. Every board carries a red-at-300s age tile.
    for fname in gen.DASHBOARDS:
        exprs = " ".join(
            t.get("expr", "")
            for p in _all_panels(_shipped(fname))
            for t in (p.get("targets") or []))
        assert "liquiditybot_status_age_sec" in exprs, (
            f"{fname}: no telemetry-age panel — every value tile on this "
            "board reduces with lastNotNull and will show pre-outage "
            "numbers as if they were live")


def test_refresh_cadence_matches_push_period():
    # gc_pusher exports every 30s (GC_PERIOD_SEC default); a 30s dashboard
    # refresh doubles the query/render churn for zero extra information.
    # 1m still surfaces every push within one refresh — the client-side
    # load halves (2026-07-25 slow-dashboard diagnosis).
    for fname in gen.DASHBOARDS:
        assert _shipped(fname)["refresh"] == "1m", \
            f"{fname}: refresh must be 1m (push cadence is 30s)"


def test_command_detail_rows_collapsed_by_default():
    # 2026-07-25 slow-dashboard diagnosis: the Command board reached 76
    # querying panels; Grafana runs NO queries for panels inside collapsed
    # rows, so the deep-dive rows ship collapsed and the operator expands
    # on demand. The hero rows (vitals / money / positions & risk) stay
    # open — they are the daily-driver read. Each collapsed row must CARRY
    # its member panels (an empty nested list means the nesting transform
    # silently dropped them — the board would lose those panels entirely).
    d = _shipped("liquiditybot_command.json")
    rows = {p["title"]: p for p in d["panels"] if p["type"] == "row"}
    open_keys = ("VITALS", "MONEY", "POSITIONS & RISK")
    collapsed_keys = ("PROFIT POOLS", "LEARNING BRAIN", "EDGE", "CONVICTION",
                      "CONTEXT", "LONG BOOK", "THALES")
    for title, row in rows.items():
        up = title.upper()
        if any(k in up for k in open_keys):
            assert not row["collapsed"], f"hero row collapsed: {title}"
        elif any(k in up for k in collapsed_keys):
            assert row["collapsed"], f"detail row not collapsed: {title}"
            assert row.get("panels"), \
                f"collapsed row lost its panels: {title}"
    # no member panel may ALSO appear at top level (double-render/dup ids)
    nested_ids = {p["id"] for r in rows.values()
                  for p in (r.get("panels") or [])}
    top_ids = {p["id"] for p in d["panels"]}
    assert not nested_ids & top_ids, "panel present both nested and top-level"


def test_reason_codes_decoded_on_panels():
    # "decode them" (2026-07-25): reason codes render with plain-language
    # labels on every code-keyed panel. Two-sided contract:
    #   1. COVERAGE — every SZ/CV/PT member of core.codes.Code has an entry
    #      in gen.CODE_LABELS (a new code without a label breaks the build,
    #      same philosophy as the emitted-metric check), and every label
    #      keeps its code visible as the prefix;
    #   2. WIRING — the shipped panels actually carry the decode (dropping
    #      the mapping/override plumbing fails HERE, not silently on the
    #      wall).
    from core.codes import Code
    fam = {m.value for m in Code if m.value[:2] in ("SZ", "CV", "PT")}
    missing = fam - set(gen.CODE_LABELS)
    assert not missing, f"codes without decode labels: {missing}"
    for code, label in gen.CODE_LABELS.items():
        assert label.startswith(code) and len(label) > len(code) + 3, \
            f"label must be 'CODE · meaning': {label!r}"

    def code_mappings(panel):
        for o in panel["fieldConfig"]["overrides"]:
            if o["matcher"] == {"id": "byName", "options": "code"}:
                for pr in o["properties"]:
                    if pr["id"] == "mappings":
                        return pr["value"][0]["options"]
        return {}

    cmd = _shipped("liquiditybot_command.json")
    ex = _shipped("liquiditybot_execution.json")
    entry_tbl = [p for p in _all_panels(cmd)
                 if p.get("title") == "Entry-decision reason codes"]
    assert entry_tbl, "entry-decision table missing"
    opts = code_mappings(entry_tbl[0])
    assert opts.get("SZ-030", {}).get("text") == gen.CODE_LABELS["SZ-030"]
    assert set(opts) == set(gen.CODE_LABELS), "table mappings incomplete"
    detail_tbl = [p for p in _all_panels(ex)
                  if p.get("title") == "Denials by code (detail)"]
    assert detail_tbl, "denials detail table missing"
    opts = code_mappings(detail_tbl[0])
    assert opts.get("CV-010", {}).get("text") == gen.CODE_LABELS["CV-010"]
    # the CV denials bargauge decodes its series names via displayName
    # (on the models board since the 2026-08-05 redesign, with the rest of
    # the admission mechanics)
    bar = [p for p in _all_panels(ex)
           if p.get("title") == "Denials by code" and p["type"] == "bargauge"]
    assert bar, "denials bargauge missing"
    names = {o["matcher"]["options"]: pr["value"]
             for o in bar[0]["fieldConfig"]["overrides"]
             for pr in o["properties"] if pr["id"] == "displayName"}
    cv = {c for c in gen.CODE_LABELS if c.startswith("CV")}
    assert set(names) >= cv, "bargauge missing CV displayName decodes"
    assert names["CV-020"] == gen.CODE_LABELS["CV-020"]


def test_gate_divergence_watch_keeps_per_gate_series():
    # The watch's entire point is spotting ONE gate trending away from its
    # realized outcomes; a bare max() collapse plots only the least-diverged
    # gate and masks the diverging one (round-2 review, 2026-08-05). The
    # query must group by the gate label and the legend must name it.
    d = _shipped("liquiditybot_problem_solution.json")
    panels = [p for p in _all_panels(d)
              if "gate_divergence" in " ".join(
                  t["expr"] for t in p.get("targets", []))]
    assert panels, "gate-divergence watch panel missing"
    expr = " ".join(t["expr"] for p in panels for t in p["targets"])
    assert "by (gate)" in expr, "per-gate series collapsed by bare max()"


def test_screening_open_slots_relabeled():
    # the tile displays liquiditybot_positions_open — "Open slots" read as
    # slots AVAILABLE (backwards when 0 positions are open); it is titled
    # by what it shows (2026-07-25 operator screenshot review)
    d = _shipped("liquiditybot_screening.json")
    titles = {p.get("title") for p in _all_panels(d)}
    assert "Open slots" not in titles, "backwards label resurrected"
    assert "Positions open" in titles


def test_has_per_asset_comparison_table():
    d = _shipped("liquiditybot_command.json")
    tables = [p for p in _all_panels(d) if p["type"] == "table"]
    # a table joined on the `asset` label = the decision-comparison scorecard
    asset_tbl = [t for t in tables if any(
        "asset" in str(tr.get("expr", "")) or
        tr.get("expr", "").find("perf_asset") >= 0 for tr in t["targets"])]
    assert asset_tbl, "per-asset comparison table is the decision centrepiece"


def test_execution_board_has_conviction_row():
    # #120, relocated by the 2026-08-05 trading-desk redesign: admission
    # mechanics live on the models board beside the decision model. The row
    # pins admit-share, window-n, alarm-state, per-regime share,
    # denials-by-code — every target of which must query an actually-emitted
    # liquiditybot_conviction_* metric
    # (test_every_query_hits_an_emitted_metric enforces that globally).
    d = _shipped("liquiditybot_execution.json")
    section = _row_section(d, "CONVICTION")
    assert section, "no Conviction row (or an empty one) on the models board"
    exprs = " ".join(t["expr"] for p in section for t in p.get("targets", []))
    for expect in ("liquiditybot_conviction_share",
                   "liquiditybot_conviction_evaluated",
                   "liquiditybot_conviction_admitted",
                   "liquiditybot_conviction_alarm",
                   "liquiditybot_conviction_regime_share",
                   "liquiditybot_conviction_denials"):
        assert expect in exprs, f"Conviction row missing {expect}"


def test_command_board_has_context_row():
    # Task B6, relocated by the 2026-08-05 trading-desk redesign: macro
    # cycle context is a market-screening concern, so the row lives on the
    # screening board — halving phase + days-since/to-next, the macro-stress
    # dial, flow stats, event-window state, per-source ok/dark — every
    # target of which must query an actually-emitted liquiditybot_context_*
    # metric (test_every_query_hits_an_emitted_metric enforces that
    # globally; this pins the row's existence and its metric coverage).
    d = _shipped("liquiditybot_screening.json")
    # needle avoids the board's own "REGIME CONTEXT & ADVERSE SELECTION" row
    section = _row_section(d, "CYCLE & MACRO")
    assert section, "no Context row (or an empty one) on the screening board"
    exprs = " ".join(t["expr"] for p in section for t in p.get("targets", []))
    for expect in ("liquiditybot_context_phase",
                   "liquiditybot_context_days_since_halving",
                   "liquiditybot_context_days_to_next_halving",
                   "liquiditybot_context_stress",
                   "liquiditybot_context_cot_z",
                   "liquiditybot_context_stable_wk_pct",
                   "liquiditybot_context_event_window",
                   "liquiditybot_context_source_ok"):
        assert expect in exprs, f"Context row missing {expect}"
    # stress dial gauge is bounded [-2, 2] (clip_z's symmetric clip), never
    # the default [0, mx] shape a bounded-ratio gauge normally gets
    stress_gauges = [p for p in section if p["type"] == "gauge"
                      and "liquiditybot_context_stress" in
                      " ".join(t["expr"] for t in p["targets"])]
    assert stress_gauges, "no stress dial gauge in the Context row"
    for g in stress_gauges:
        fld = g["fieldConfig"]["defaults"]
        assert fld["min"] == -2 and fld["max"] == 2, \
            "stress gauge must be bounded [-2, 2]"
    # no hardcoded lookback window on any Context-row query (glass contract)
    assert "[24h]" not in exprs and "[48h]" not in exprs and \
        "[6h]" not in exprs, "Context row must not hardcode a lookback"


def test_command_board_has_long_book_row():
    # Task C6: the Command board surfaces ONE Long Book row — rung
    # (value-mapped 0-3), ceiling gauge, book exposure, adds placed,
    # paused state, live profit factor, closed-count-by-track — every
    # target of which must query an actually-emitted
    # liquiditybot_longbook_* metric (test_every_query_hits_an_emitted_
    # metric enforces that globally; this pins the row's existence and
    # its specific metric coverage).
    d = _shipped("liquiditybot_command.json")
    section = _row_section(d, "LONG BOOK")
    assert section, "no Long Book row (or an empty one) on the Command board"
    exprs = " ".join(t["expr"] for p in section for t in p.get("targets", []))
    for expect in ("liquiditybot_longbook_rung",
                   "liquiditybot_longbook_ceiling_frac",
                   "liquiditybot_longbook_exposure_usd",
                   "liquiditybot_longbook_adds_placed",
                   "liquiditybot_longbook_paused",
                   "liquiditybot_longbook_pf_live",
                   "liquiditybot_longbook_closed"):
        assert expect in exprs, f"Long Book row missing {expect}"
    # ceiling gauge bounded [0, 0.35] (the shared portfolio heat cap,
    # expressed in the gauge()-standard *100/percent convention every
    # other fraction-valued gauge on this board already uses — e.g.
    # Gross exposure / Portfolio heat, both mx=35.0 for the identical cap)
    ceiling_gauges = [p for p in section if p["type"] == "gauge"
                      and "liquiditybot_longbook_ceiling_frac" in
                      " ".join(t["expr"] for t in p["targets"])]
    assert ceiling_gauges, "no ceiling gauge in the Long Book row"
    for g in ceiling_gauges:
        fld = g["fieldConfig"]["defaults"]
        assert fld["min"] == 0 and fld["max"] == 35.0, \
            "ceiling gauge must be bounded [0, 0.35] (35% heat cap)"
    # rung is a value-mapped state tile (0-3), not a raw number
    rung_panels = [p for p in section
                   if "liquiditybot_longbook_rung" in
                   " ".join(t["expr"] for t in p.get("targets", []))]
    assert rung_panels, "no rung panel in the Long Book row"
    for p in rung_panels:
        mappings = p["fieldConfig"]["defaults"].get("mappings")
        assert mappings and len(mappings[0]["options"]) == 4, \
            "rung panel must value-map exactly 0-3"
    # no hardcoded lookback window on any Long Book row query (glass contract)
    assert "[24h]" not in exprs and "[48h]" not in exprs and \
        "[6h]" not in exprs, "Long Book row must not hardcode a lookback"


def test_every_query_hits_an_emitted_metric(tmp_path):
    p = tmp_path / "status.json"
    # written_at stamped at USE time, not module import: the DL-6 stale
    # guard returns the alarm-only batch for a status older than 120s, and
    # a full-suite run takes longer than that to reach this test
    p.write_text(json.dumps({**_SYNTH_STATUS, "written_at": time.time()}),
                 encoding="utf-8")
    emitted = {m["name"] for m in gp.collect(str(p))}
    referenced = set()
    # digits included ([a-z0-9_]): SPB-R metric names carry trailing-window
    # suffixes (liquiditybot_probe_budget_admits_24h) — the old [a-z_]
    # class truncated them mid-name and compared a nonexistent prefix
    for d in gen.DASHBOARDS.values():
        for panel in _all_panels(d):
            for t in panel.get("targets", []):
                referenced |= set(re.findall(r"liquiditybot_[a-z0-9_]+",
                                             t["expr"]))
    missing = referenced - emitted
    assert not missing, f"panels query metrics gc_pusher never emits: {missing}"
