"""tests/test_boards_stripped.py — pins each board's authored inventory.

Lineage: the 2026-08-15 strip deleted every visualisation panel so nothing
on screen could be a number carried over from the retired geometry, and this
module pinned the stripped state itself. The boards have since been rebuilt
in stages — the LIQUIDITY (command) board at c4272391, the alert-input
mirror at ab8ee2b4, and on 2026-08-17 the three-link rebuild: LEARNING (new
uid) and PROBLEMS authored, the injector-only screening board folded away
and its uid retired. "A green is only as big as its corpus" — so every
CONTENT board now carries the same inventory pin the command board proved
out, and the stripped-form escape hatch is kept per board.

What it pins:

  * per board, the EXACT panel inventory as (id, title, type, sorted
    metrics) QUADRUPLES — see the mutation story on _COMMAND_HERO_PANELS
    for why the metric tuple is load-bearing. Each pin also accepts the
    fully-stripped (injector-only) form, so re-stripping a board can never
    brick the deploy gate.
  * the injector exists on EVERY board, is transparent, is 1x1, is the
    bottom-most panel, and carries the WHOLE of gen.GLASS_RULES inside its
    afterRender JS (asserted against the module constant, not a copy, so a
    rewritten stylesheet cannot pass by accident).
  * the board shell: unique non-empty uid, schemaVersion 39, non-empty
    title, and nav links whose targets are exactly the four board uids.
  * shipped JSON == what the generator produces right now (the repo's
    long-standing source-of-truth invariant; same idiom as
    tests/test_trading_dashboard.py::test_generator_matches_shipped_json).
  * the panel FACTORIES still build a board — proved by actually running
    _board() over a throwaway author, not by asserting callable().
  * the LEARNING board keeps its 30-day default range — it is the
    long-term read and a silently-narrowed window would turn multi-week
    trends back into scrape noise.

Adding, removing, renaming, retyping or REPOINTING a tile is a deliberate
act and must edit the matching _*_PANELS set below in the same commit —
that edit is the review record.

Every board file is read with encoding="utf-8" — the Windows cp1252 default
CRASHES on the ⌘/⚙/🧠/🚨 nav-link glyphs.
"""
import json
import re
from pathlib import Path

import pytest

import scripts.build_trading_dashboard as gen

ROOT = Path(__file__).resolve().parents[1]

COMMAND = "liquiditybot_command.json"
EXECUTION = "liquiditybot_execution.json"
LEARNING = "liquiditybot_learning.json"
PROBLEMS = "liquiditybot_problem_solution.json"
ALL_BOARDS = (COMMAND, EXECUTION, LEARNING, PROBLEMS)

INJ_TYPE = "marcusolsson-dynamictext-panel"

# The execution board carries ONLY what the two alert rules fire on. It was
# rebuilt 2026-08-16 after a measurement: liquiditybot_ml_brier and
# _ml_baseline_brier last carried data 2026-08-06 21:42, final values 0.1133
# and 0.0586 - a 0.0547 gap, over the rule's 0.03 line - and then went absent,
# so noDataState:OK held the alert green for 10 days on an empty corpus.
# If a panel here is removed, the alert it mirrors goes back to being invisible
# until it pages, so this inventory is pinned exactly like the command board's.
_EXEC_PANELS = frozenset({
    (1, "Model health - what the alerts watch", "row", ()),
    (2, "Brier gap vs baseline", "stat",
     ("liquiditybot_ml_baseline_brier", "liquiditybot_ml_brier")),
    (3, "Model Brier", "stat", ("liquiditybot_ml_brier",)),
    (4, "Baseline Brier", "stat", ("liquiditybot_ml_baseline_brier",)),
    (5, "Champion Brier", "stat", ("liquiditybot_ml_champion_brier",)),
    (6, "Drift share", "stat", ("liquiditybot_ml_drift_share",)),
    (7, "Monitor", "stat", ("liquiditybot_monitor_level",)),
    (gen.INJ_ID, "", INJ_TYPE, ()),
})
_EXEC_STRIPPED_PANELS = frozenset({(gen.INJ_ID, "", INJ_TYPE, ())})

# The command board's authored inventory, as
# (id, title, type, sorted metrics) QUADRUPLES.
#
# Two failures of this pin, in order, both found by MUTATION rather than by
# reading it - the reason the metric tuple is in here at all:
#   1. It was an id SET. _id() assigns sequentially, so ANY 14 panels
#      satisfied `ids == range(1,15)`. A review repointed the "Equity" hero
#      at liquiditybot_savings and swapped a tile wholesale; GREEN both times.
#   2. Widened to (id, title, type) - the review's own recommendation - and
#      re-tested: STILL GREEN with "Equity" plotting liquiditybot_savings,
#      because repointing a query changes none of those three fields.
# A tile labelled "Equity" quietly plotting a different series is the exact
# plausible-looking lie this board must not be able to tell, so WHAT EACH
# PANEL QUERIES is pinned, not merely how many panels there are.
_COMMAND_HERO_PANELS = frozenset({
    (1, "Equity", "stat", ("liquiditybot_equity",)),
    (2, "Today", "stat", ("liquiditybot_daily_pnl",)),
    (3, "This week", "stat", ("liquiditybot_weekly_pnl",)),
    # RETITLED (STREAM 7c, 2026-08-28 audit top-5 #2): metric unchanged,
    # title no longer claims a lifetime figure the epoch-reanchored
    # starting_capital does not support.
    (4, "Since capital epoch", "stat", ("liquiditybot_net_pnl_all_time",)),
    (5, "Drawdown", "stat", ("liquiditybot_drawdown_pct",)),
    (6, "Equity", "timeseries", ("liquiditybot_equity",)),
    (7, "Open positions", "stat", ("liquiditybot_positions_open",)),
    (8, "Gross exposure", "gauge", ("liquiditybot_gross_exposure_pct",)),
    (9, "Fees paid", "stat", ("liquiditybot_fees_total",)),
    (10, "Entries", "stat", ("liquiditybot_entries_enabled",)),
    (11, "Halt", "stat", ("liquiditybot_halted",)),
    (12, "Data age", "stat", ("liquiditybot_status_age_sec",)),
    # liveness group. STREAM 7c (2026-08-28 audit): the "Telemetry"
    # STALE/fresh tile MERGED into Data age's own desc above (audit
    # MERGE 14->12) - one fact, one tile - so the group is now three.
    (13, "Runner", "stat", ("liquiditybot_running",)),
    (14, "Kraken feed", "stat", ("liquiditybot_ws_kraken_connected",)),
    (15, "Op state", "stat", ("liquiditybot_op_state",)),
    (16, "Paper / Live", "stat", ("liquiditybot_dry_run",)),
    (17, "Positions", "row", ()),
    (18, "Open positions", "table",
     ("liquiditybot_position_age_hours", "liquiditybot_position_conviction",
      "liquiditybot_position_notional_usd", "liquiditybot_position_r_multiple",
      "liquiditybot_position_stop_dist_pct", "liquiditybot_position_upnl_pct",
      "liquiditybot_position_upnl_usd")),
    # activity & budget. STREAM 7c (2026-08-28 audit): Exposure-by-asset
    # REMOVED (redundant with the positions table one row up), Daily/
    # Weekly loss budget gauges and Size taper REMOVED (canonical home =
    # PROBLEMS "Risk brakes", live there once), Fills so far REMOVED
    # (folded into Fill mix's own two-slice legend).
    (19, "Activity & budget", "row", ()),
    (20, "Fill mix", "piechart",
     ("liquiditybot_order_maker_fills", "liquiditybot_order_taker_fills")),
    (21, "Profit pools", "stat",
     ("liquiditybot_reserve", "liquiditybot_savings")),
    (gen.INJ_ID, "", INJ_TYPE, ()),
})
_COMMAND_STRIPPED_PANELS = frozenset({(gen.INJ_ID, "", INJ_TYPE, ())})

# The LEARNING board (2026-08-17, uid liquiditybot-learning) — the operator's
# long-term "is it getting smarter" read. Same pin philosophy as the command
# board's: WHAT EACH PANEL QUERIES is pinned, because a tile labelled
# "Model edge over naive guess" quietly plotting something else is exactly
# the plausible lie a learning board must not be able to tell.
_LEARNING_PANELS = frozenset({
    (1, 'Model edge over naive guess', 'stat', ('liquiditybot_ml_baseline_brier', 'liquiditybot_ml_brier')),
    (2, 'Corpus rows (all eras, archive)', 'stat', ('liquiditybot_ml_history_rows',)),
    (3, 'Rows teaching the model', 'stat', ('liquiditybot_ml_loaded_rows',)),
    (4, 'Clean live labels', 'stat', ('liquiditybot_ml_live_clean',)),
    (5, 'Model in use', 'stat', ('liquiditybot_ml_use_model',)),
    (6, 'Learning health', 'stat', ('liquiditybot_monitor_level',)),
    (7, 'Data age', 'stat', ('liquiditybot_status_age_sec',)),
    (8, 'Is it getting smarter?', 'row', ()),
    (9, 'Prediction error - model vs naive vs champion', 'timeseries', ('liquiditybot_ml_baseline_brier', 'liquiditybot_ml_brier', 'liquiditybot_ml_champion_brier')),
    (10, 'Trades the judge has scored', 'stat', ('liquiditybot_ml_window_trades',)),
    # STREAM 7c (2026-08-28 audit MERGE 13->11): Calibration gap now rides
    # as a fourth line on this panel instead of its own timeseries.
    (11, 'Hit rate vs claimed probability', 'timeseries', ('liquiditybot_ml_avg_p', 'liquiditybot_ml_calibration_gap', 'liquiditybot_ml_hit_rate', 'liquiditybot_ml_hit_rate_lcb')),
    (12, 'Feature drift share', 'timeseries', ('liquiditybot_ml_drift_share',)),
    (13, 'Is the pipeline filling?', 'row', ()),
    # STREAM 7c: the raw/loaded gauges (old ids 15/16) MERGED into ids
    # 2/3's own descriptions above (same metrics, same 640-floor caveat
    # prose, one tile each instead of two).
    (14, 'New-era rows toward re-arm', 'gauge', ('liquiditybot_era_excl_new_rows',)),
    (15, 'Labels per day', 'stat', ('liquiditybot_probe_budget_live_labels_per_day_7d',)),
    (16, 'Label uniqueness', 'stat', ('liquiditybot_ml_mean_uniqueness',)),
    # STREAM 7c (audit MERGE 22->21): Where-labels-come-from rides as a
    # third target instead of its own panel.
    (17, 'Corpus growth', 'timeseries', ('liquiditybot_ml_history_rows', 'liquiditybot_ml_labels', 'liquiditybot_ml_live_clean')),
    (18, 'Labels by era (fence view)', 'timeseries', ('liquiditybot_era_rows',)),
    (19, 'What the labels say', 'row', ()),
    (20, "How this era's trades ended", 'piechart', ('liquiditybot_era_reason_rows',)),
    (21, 'Label rate this era', 'stat', ('liquiditybot_era_label_rate',)),
    (22, 'Corpus drift distance', 'stat', ('liquiditybot_era_mix_tvd',)),
    (23, 'Rows excluded from training', 'stat', ('liquiditybot_era_excl_dropped',)),
    (24, 'Which model is driving', 'row', ()),
    (25, 'Deployed model over time', 'timeseries', ('liquiditybot_ml_model_info',)),
    (26, 'Retrain queued', 'stat', ('liquiditybot_ml_retrain_flag',)),
    (27, 'Retrain failures', 'stat', ('liquiditybot_ml_retrain_failures',)),
    (28, 'Model fallbacks', 'stat', ('liquiditybot_ml_model_fallbacks',)),
    (29, 'Model lifecycle events', 'bargauge', ('liquiditybot_ml_lineage_events',)),
    (30, 'Is the model orphaned?', 'stat', ('liquiditybot_ml_orphan_ratio',)),
    (31, 'The verdict clock', 'row', ()),
    (32, 'Era-4 verdict progress', 'bargauge', ('liquiditybot_cohort_closes', 'liquiditybot_cohort_min_n')),
    (33, 'The cost of learning', 'row', ()),
    (34, 'Probe tokens in the tank', 'gauge', ('liquiditybot_probe_budget_tokens',)),
    # STREAM 7c (audit MERGE 42->41): Tuition cap folded into this desc.
    (35, 'Tuition spent in 24h', 'stat', ('liquiditybot_probe_budget_tuition_24h_usd',)),
    (36, 'Unlock ETA', 'stat', ('liquiditybot_probe_budget_unlock_eta_days',)),
    (37, 'Probes open now', 'stat', ('liquiditybot_probe_budget_open_probes',)),
    (38, 'Denied - budget empty', 'stat', ('liquiditybot_probe_budget_denied_exhausted_24h',)),
    (39, 'Probe governor', 'stat', ('liquiditybot_probe_budget_governor_factor',)),
    # STREAM 7c: Refunds in 24h REMOVED (audit: "not actionable").
    (40, 'Gate learning', 'row', ()),
    (41, 'Learned gate weights', 'bargauge', ('liquiditybot_gate_weight',)),
    # STREAM 7c (audit MERGE 52->50): Base win rate folded into this desc.
    (42, 'Is any gate lying?', 'bargauge', ('liquiditybot_gate_divergence',)),
    (43, 'Labeled rows feeding the gates', 'stat', ('liquiditybot_gate_labeled',)),
    (990, '', 'marcusolsson-dynamictext-panel', ()),
})
_LEARNING_STRIPPED_PANELS = frozenset({(gen.INJ_ID, "", INJ_TYPE, ())})

# The PROBLEMS board (2026-08-17, keeps uid liquiditybot-problem-solution so
# the operator's link survives) — what needs attention; looking empty is
# good. Includes the two pager conditions rendered as the SAME arithmetic
# the alert rules run (the execution board's lesson, ab8ee2b4).
_PROBLEM_PANELS = frozenset({
    (1, "Overall posture", "stat", ("liquiditybot_op_state",)),
    (2, "Halted?", "stat", ("liquiditybot_halted",)),
    (3, "New trades blocked?", "stat",
     ("liquiditybot_watchdog_entries_blocked",)),
    (4, "Active faults", "stat", ("liquiditybot_fault_count",)),
    (5, "Risk firewall", "stat", ("liquiditybot_firewall_fault",)),
    (6, "Data age", "stat", ("liquiditybot_status_age_sec",)),
    (7, "What the pager watches", "row", ()),
    (8, "Model worse than naive by", "stat",
     ("liquiditybot_ml_baseline_brier", "liquiditybot_ml_brier")),
    # the judge-window disambiguator: the tile that says whether an empty
    # Brier tile means "filling" or "judge dead"
    (9, "Trades the judge has scored", "stat",
     ("liquiditybot_ml_window_trades",)),
    (10, "Drift stuck while degraded", "stat",
     ("liquiditybot_ml_drift_share", "liquiditybot_monitor_level")),
    (11, "Model governor", "stat", ("liquiditybot_monitor_level",)),
    (12, "Faults & rejections", "row", ()),
    # FIXED (STREAM 7c, 2026-08-28 audit top-5 #4): filtered to actual
    # trip codes (code=~"FW-.*"); the unfiltered form also plotted four
    # always-present lifecycle counters under a "by code" title.
    (13, "Firewall trips by code", "timeseries",
     ("liquiditybot_firewall_count",)),
    (14, "Decisions by family", "timeseries", ("liquiditybot_code_count",)),
    (15, "Venue rejects", "stat", ("liquiditybot_order_venue_rejects",)),
    (16, "Dead-man failures", "stat",
     ("liquiditybot_order_deadman_failures",)),
    (17, "Exit-check failures", "stat",
     ("liquiditybot_exit_eval_failures",)),
    (18, "Cycle failures in a row", "stat",
     ("liquiditybot_cycle_consecutive_failures",)),
    # MERGED (audit id=19+20): one tile, two series.
    (19, "Model & feature faults", "bargauge",
     ("liquiditybot_ml_contract_failed", "liquiditybot_ml_infer_faults")),
    (20, "Staleness & feeds", "row", ()),
    (21, "Feed latency", "stat", ("liquiditybot_feed_latency_ms",)),
    (22, "Price marks age", "stat", ("liquiditybot_marks_age_sec",)),
    (23, "Kraken feed", "stat", ("liquiditybot_ws_kraken_connected",)),
    (24, "Feed reconnects", "stat", ("liquiditybot_ws_kraken_reconnects",)),
    # MERGED (audit id=26+27+28, "the watchdog trio"): one bargauge.
    (25, "Feed watchdog", "bargauge",
     ("liquiditybot_watchdog_critical_stale", "liquiditybot_watchdog_divergent",
      "liquiditybot_watchdog_stale_assets")),
    # renamed from "Do the books add up?" — the recompute runs in LIVE
    # mode only — on a dry-run bot the old title over a green 0.00
    # rendered a check that never ran as a check that passed. Gated on
    # the bot's own mode report (`and dry_run == 0`): in paper mode the
    # expression returns EMPTY and the tile shows its honest no_value
    # text instead of the initializer 0.00.
    (26, "Books cross-check (live mode)", "stat",
     ("liquiditybot_dry_run", "liquiditybot_equity_drift_pct")),
    # MERGED (STREAM 7c, audit): "Telemetry" folded into id=6 Data age.
    (27, "Runner", "stat", ("liquiditybot_running",)),
    (28, "Risk brakes", "row", ()),
    (29, "Daily loss budget used", "gauge",
     ("liquiditybot_rp_daily_budget_used_frac",)),
    (30, "Weekly loss budget used", "gauge",
     ("liquiditybot_rp_weekly_budget_used_frac",)),
    (31, "Drawdown vs the hard stop", "timeseries",
     ("liquiditybot_rp_drawdown_mtm_pct", "liquiditybot_rp_hard_stop_dd_pct")),
    (32, "Size taper", "stat", ("liquiditybot_rp_taper_mult",)),
    (33, "Drawdown throttle", "stat", ("liquiditybot_rp_dd_throttle_mult",)),
    (34, "Portfolio heat", "stat", ("liquiditybot_rp_heat_frac",)),
    (35, "Assets circuit-broken", "stat", ("liquiditybot_cb_tripped_count",)),
    (36, "Circuit-breaker cooldown left", "bargauge",
     ("liquiditybot_cb_paused_hours_left",)),
    (37, "Loss streak by asset", "bargauge",
     ("liquiditybot_perf_asset_cur_loss_streak",)),
    (38, "Audit & self-health", "row", ()),
    (39, "Audit writes dropped", "stat",
     ("liquiditybot_audit_dropped_writes",)),
    (40, "Audit tail truncations", "stat",
     ("liquiditybot_audit_tail_truncations",)),
    (41, "Bad values dropped by exporter", "stat",
     ("liquiditybot_gauges_dropped_nonfinite",)),
    (42, "Cycles since restart", "stat", ("liquiditybot_cycle",)),
    # the entry/order funnel: liquiditybot_code_count_detail consumed by a
    # panel, and the OM-040 timeout-cancel share of clean terminals on
    # glass (report-only; the TTL/maker-offset levers it informs are
    # execution-geometry fenced). STREAM 7c (2026-08-28 audit + operator
    # instruction "keep per-hour, drop cumulative"): the cumulative
    # "Why entries die" timeseries is RETIRED — its own per-hour
    # companion (below) answers the same question with no slope-reading,
    # and is now the sole "why" chart with a roster fixed to the codes
    # that actually fire (SZ-021/SZ-030/SZ-049 in, never-fired PT-040/
    # PT-041 out).
    (43, "Why entries die", "row", ()),
    (44, "Timeout-cancel share", "stat",
     ("liquiditybot_order_terminal_orders",
      "liquiditybot_order_timeout_cancels")),
    (45, "Why entries die (per hour)", "timeseries",
     ("liquiditybot_code_count_detail",)),
    (46, "Were the vetoes right?", "bargauge",
     ("liquiditybot_veto_cf_rate",)),
    (47, "Anti-selective gates", "stat",
     ("liquiditybot_veto_anti_selective",)),
    (48, "Candidate baseline win rate", "stat",
     ("liquiditybot_veto_baseline_rate",)),
    # MUTATED (STREAM 7c, 2026-08-28 — the audit's one permitted new
    # element, landed as a mutation of the existing "Confounded verdicts"
    # tile): per-code label-era overlap bargauge at the report's own
    # 0.05/0.5 policy thresholds, plus the admitted-vs-baseline headline
    # (liquiditybot_admitted_era_overlap, EXTEND-ONLY exporter addition)
    # riding as an extra bar. Replaces a bare count with which codes and
    # how far from readable.
    (49, "Verdict comparability (label-era overlap vs baseline)",
     "bargauge",
     ("liquiditybot_admitted_era_overlap", "liquiditybot_veto_era_overlap")),
    (gen.INJ_ID, "", INJ_TYPE, ()),
})
_PROBLEM_STRIPPED_PANELS = frozenset({(gen.INJ_ID, "", INJ_TYPE, ())})

_MET_RE = re.compile(r"liquiditybot_[a-z0-9_]+")


def _identity(p: dict) -> tuple:
    """(id, title, type, sorted metrics) — what the panel IS and what it
    ACTUALLY QUERIES. Titles lie; queries do not."""
    mets = sorted({m for t in (p.get("targets") or [])
                   for m in _MET_RE.findall(t.get("expr", ""))})
    return (p["id"], p.get("title", ""), p["type"], tuple(mets))

# Panels that execute JavaScript in the operator's browser. The glass
# injector is the only sanctioned one; a second such panel is how a board
# would grow script execution without anyone noticing.
_JS_PANEL_TYPES = (INJ_TYPE,)


def _shipped(fname: str) -> dict:
    return json.loads((ROOT / "docs" / "grafana" / fname)
                      .read_text(encoding="utf-8"))


def _all_panels(d: dict) -> list:
    """Every panel including members nested inside collapsed rows (Grafana
    moves a collapsed row's panels INTO the row object's own `panels`)."""
    out = []
    for p in d["panels"]:
        out.append(p)
        out.extend(p.get("panels") or [])
    return out


def _injector_of(d: dict) -> dict:
    inj = [p for p in _all_panels(d) if p.get("id") == gen.INJ_ID]
    assert len(inj) == 1, f"expected exactly one id-{gen.INJ_ID} panel"
    return inj[0]


# --------------------------------------------------------------------------
# the shipped == generator invariant (source of truth is the generator)
# --------------------------------------------------------------------------
def test_generator_matches_shipped_json():
    for fname, d in gen.DASHBOARDS.items():
        assert d == _shipped(fname), \
            f"{fname} differs from the generator — regenerate with " \
            "`python scripts/build_trading_dashboard.py` (never hand-edit)"


def test_expected_boards_present():
    assert set(gen.DASHBOARDS) == set(ALL_BOARDS)


# --------------------------------------------------------------------------
# per-board inventory pins (the regrow detectors)
# --------------------------------------------------------------------------
def test_command_board_has_not_silently_regrown():
    """Change-detector on the command board. Accepts the stripped form too,
    so re-stripping the board does not brick the deploy gate; anything else
    means panels appeared or disappeared without this pin being updated."""
    got = frozenset(_identity(p) for p in _all_panels(_shipped(COMMAND)))
    assert got in (_COMMAND_HERO_PANELS, _COMMAND_STRIPPED_PANELS), (
        f"{COMMAND} inventory does not match either pinned form.\n"
        f"  unexpected: {sorted(got - _COMMAND_HERO_PANELS)}\n"
        f"  missing:    {sorted(_COMMAND_HERO_PANELS - got)}\n"
        "If you deliberately added, removed, renamed or retyped a panel, "
        "update _COMMAND_HERO_PANELS in this file in the SAME commit — that "
        "edit is the review record.")


def test_learning_board_matches_its_pin():
    """Same contract as the command pin, for the operator's long-term
    'is it getting smarter' link."""
    got = frozenset(_identity(p) for p in _all_panels(_shipped(LEARNING)))
    assert got in (_LEARNING_PANELS, _LEARNING_STRIPPED_PANELS), (
        f"{LEARNING} inventory does not match either pinned form.\n"
        f"  unexpected: {sorted(got - _LEARNING_PANELS)}\n"
        f"  missing:    {sorted(_LEARNING_PANELS - got)}\n"
        "Deliberate change? Update _LEARNING_PANELS in the SAME commit.")


def test_learning_board_keeps_the_long_range():
    """LEARNING is the long-term read: the default window is 30 days so
    multi-week trends are legible the moment the link opens. A narrowed
    default silently turns the board back into scrape noise."""
    d = _shipped(LEARNING)
    assert d["time"]["from"] == "now-30d", d["time"]
    assert d["time"]["to"] == "now", d["time"]


def test_problem_board_matches_its_pin():
    """Same contract as the command pin, for the operator's 'what needs
    attention' link."""
    got = frozenset(_identity(p) for p in _all_panels(_shipped(PROBLEMS)))
    assert got in (_PROBLEM_PANELS, _PROBLEM_STRIPPED_PANELS), (
        f"{PROBLEMS} inventory does not match either pinned form.\n"
        f"  unexpected: {sorted(got - _PROBLEM_PANELS)}\n"
        f"  missing:    {sorted(_PROBLEM_PANELS - got)}\n"
        "Deliberate change? Update _PROBLEM_PANELS in the SAME commit.")


ALERT_YAMLS = ("liquiditybot_brier_alert.yaml", "liquiditybot_drift_alert.yaml")


def _alert_rule_facts(yaml_name):
    """(metrics, thresholds) parsed from ONE alert YAML's query/math lines.

    DEGRADES CLOSED (2026-08-17): a YAML rewrite into block scalars would
    silently empty a line-based extraction and turn the mirror tests into
    green no-ops — so parsing ZERO metrics or ZERO thresholds from a rule
    file is itself a failure, never a pass.

    SCOPE, stated because the old assertion overclaimed: these facts are
    the REPO's copy of the rule. The live Grafana instance's rule can be
    edited out from under the repo, and that drift is out of this test's
    reach — the pin guarantees board == repo rule, nothing more.
    """
    txt = (ROOT / "docs" / "grafana" / yaml_name).read_text(encoding="utf-8")
    metrics, thresholds = set(), set()
    for line in txt.splitlines():
        if "expr:" in line:
            metrics |= set(_MET_RE.findall(line))
        if "expression:" in line:
            # math lines: "$RA - $RB > 0.03" / "$RA > 0.3 && $RB > 0"
            thresholds |= {float(v) for v in
                           re.findall(r">\s*([0-9]+(?:\.[0-9]+)?)", line)}
    assert metrics, (
        f"{yaml_name}: extracted ZERO metrics from expr lines — the rule "
        "file changed shape and this mirror test can no longer see it. "
        "Fix the extraction before trusting any mirror pin.")
    assert thresholds, (
        f"{yaml_name}: extracted ZERO numeric thresholds from expression "
        "lines — same degradation as above, for the firing lines.")
    return metrics, thresholds


def test_anti_selective_desc_carries_the_confound_caveat():
    """C6 (2026-08-27 fix-wave): the 'Anti-selective gates' description
    asserted a bare, undated 'SZ-021 won at 0.51 against a 0.27 baseline'
    claim that the SAME DAY's era-confound guard made false (that
    comparison is now CONFOUNDED_BASELINE, docs/HANDOFF.md REG-6
    CAVEAT). Pins BOTH sides staying on record - the 08-26 read is not
    deleted, and the 08-27 supersession is not silently omitted - so a
    future desc rewrite cannot drop the caveat without going red here."""
    d = _shipped(PROBLEMS)
    hits = [p for p in _all_panels(d) if p.get("title") == "Anti-selective gates"]
    assert hits, f"{PROBLEMS}: no panel titled 'Anti-selective gates'"
    desc = hits[0].get("description", "")
    assert "2026-08-26" in desc, f"desc lost the dated 08-26 read: {desc!r}"
    assert "SUPERSEDED 2026-08-27" in desc, (
        f"desc lost the 08-27 confound caveat: {desc!r}")
    assert "CONFOUNDED_BASELINE" in desc, (
        f"desc does not name the actual verdict: {desc!r}")


def test_problem_board_mirrors_both_pager_conditions():
    """The PROBLEMS board must render the SAME arithmetic the two alert
    rules run (the ab8ee2b4 lesson: an alert whose inputs are on no board
    is discovered by being paged). Checked against the REPO's alert YAML
    (see _alert_rule_facts for the scope caveat), not a hand-copied list."""
    got = frozenset(_identity(p) for p in _all_panels(_shipped(PROBLEMS)))
    if got == _PROBLEM_STRIPPED_PANELS:
        pytest.skip("problems board is in the fully-stripped form")
    fired_on = set()
    for y in ALERT_YAMLS:
        fired_on |= _alert_rule_facts(y)[0]
    on_board = set()
    for p in _all_panels(_shipped(PROBLEMS)):
        on_board |= set(_identity(p)[3])
    missing = fired_on - on_board
    assert not missing, (
        f"alert rules fire on {sorted(missing)} but no PROBLEMS panel "
        "queries them — the 'what needs attention' board would go quiet on "
        "the exact inputs the pager watches.")


def test_mirror_tiles_carry_the_rules_own_thresholds():
    """Metric NAMES alone are half the mirror: a rule whose firing line
    moves (0.03 -> 0.05) with the boards left behind shows a green tile
    while the pager fires. The numeric thresholds parsed from the YAML
    must appear in the mirror tiles' threshold steps / expressions."""
    brier_metrics, brier_thr = _alert_rule_facts(ALERT_YAMLS[0])
    drift_metrics, drift_thr = _alert_rule_facts(ALERT_YAMLS[1])
    assert 0.03 in brier_thr, (
        f"brier rule thresholds changed to {sorted(brier_thr)} — update the "
        "mirror tiles' steps AND this pin in the same commit")
    assert 0.3 in drift_thr, (
        f"drift rule thresholds changed to {sorted(drift_thr)} — update the "
        "mirror state expr AND this pin in the same commit")

    def _panel(board, title):
        hits = [p for p in _all_panels(_shipped(board))
                if p.get("title") == title]
        assert hits, f"{board}: no panel titled {title!r}"
        return hits[0]

    # EXECUTION is retired to its stripped form (STREAM 7c, 2026-08-28
    # audit): its mirror duty moved entirely to PROBLEMS
    # ("Model worse than naive by"), proven independently by
    # test_problem_board_mirrors_both_pager_conditions. Only check the
    # EXECUTION copy when it exists — the stripped form has no panels to
    # carry a threshold, by design, not by regression.
    checks = [(PROBLEMS, "Model worse than naive by")]
    exec_shipped = _shipped(EXECUTION)
    if frozenset(_identity(p) for p in _all_panels(exec_shipped)) != \
            _EXEC_STRIPPED_PANELS:
        checks.append((EXECUTION, "Brier gap vs baseline"))
    for board, title in checks:
        p = _panel(board, title)
        steps = (p["fieldConfig"]["defaults"]["thresholds"]["steps"])
        vals = {s.get("value") for s in steps}
        assert 0.03 in vals, (
            f"{board}/{title}: steps {sorted(v for v in vals if v is not None)} "
            "do not include the rule's 0.03 firing line")
    drift_tile = _panel(PROBLEMS, "Drift stuck while degraded")
    exprs = " ".join(t.get("expr", "") for t in drift_tile["targets"])
    assert "> bool 0.3" in exprs, (
        f"PROBLEMS drift mirror expr {exprs!r} lost the rule's 0.3 line")


def test_learning_stat_tiles_are_instant():
    """THE INSTANT-TILE IDIOM (see _author_learning's docstring): on the
    30-day board a range-queried stat renders a dead producer's last
    value, in its healthy color, for up to a MONTH — the Brier-incident
    mechanism rebuilt. Every stat tile on LEARNING must therefore be an
    instant query (graphMode none), so absence surfaces at Prometheus'
    ~5m lookback instead of the window width."""
    d = _shipped(LEARNING)
    got = frozenset(_identity(p) for p in _all_panels(d))
    if got == _LEARNING_STRIPPED_PANELS:
        pytest.skip("learning board is in the fully-stripped form")
    bad = []
    for p in _all_panels(d):
        if p.get("type") != "stat":
            continue
        if (p.get("options") or {}).get("graphMode") != "none":
            bad.append((p["id"], p.get("title"), "graphMode"))
        for t in p.get("targets") or []:
            if t.get("instant") is not True:
                bad.append((p["id"], p.get("title"), "range target"))
    assert not bad, (
        f"range-queried stat tiles on the 30d board: {bad} — a dead "
        "producer would render its last value in healthy color for up to "
        "30 days before the empty-state text could fire.")


def test_learning_era_panels_query_the_config_derived_era():
    """The era donut/stat must query the CURRENT era, derived from config
    — never the retired un-suffixed 'triple_barrier' (the exact defect
    gc_pusher._era_label's docstring narrates: the 432-bar migration made
    the bare name a dead series) and never a hardcoded h432 (the next
    horizon migration would re-poison it). Pinned against the REAL
    runtime derivation, ml.history.triple_barrier_era, so generator-side
    formula drift reds this test instead of darkening panels."""
    from ml.history import triple_barrier_era
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    expected = triple_barrier_era(int(cfg["ml"]["label_max_bars"]))
    assert gen.TB_ERA == expected, (
        f"generator TB_ERA {gen.TB_ERA!r} != ml.history derivation "
        f"{expected!r} for label_max_bars={cfg['ml']['label_max_bars']}")
    d = _shipped(LEARNING)
    got = frozenset(_identity(p) for p in _all_panels(d))
    if got == _LEARNING_STRIPPED_PANELS:
        pytest.skip("learning board is in the fully-stripped form")
    era_exprs = [t.get("expr", "")
                 for p in _all_panels(d)
                 for t in (p.get("targets") or [])
                 if "liquiditybot_era_reason_rows" in t.get("expr", "")
                 or "liquiditybot_era_label_rate" in t.get("expr", "")]
    assert era_exprs, "the era outcome panels are gone — update this pin"
    for e in era_exprs:
        assert f'era="{expected}"' in e, (
            f"era panel queries {e!r}, not the config-derived era "
            f"{expected!r}")


def test_confound_thresholds_track_the_reports_policy_constants():
    """The 'Verdict comparability' bargauge's thresholds (ERA_OVERLAP_FLOOR
    /ERA_OVERLAP_MAJORITY) must equal scripts/gate_efficacy_report.py's
    OWN policy floors (:111-112) — not re-derived, not hand-copied and
    left to drift. Same cross-check idiom as
    test_learning_era_panels_query_the_config_derived_era: the generator
    keeps a light-dependency local copy (the TB_ERA/JUDGE_MIN precedent),
    and a TEST — not the generator's own import graph — proves it tracks
    the real constant."""
    import scripts.gate_efficacy_report as ger
    assert gen.ERA_OVERLAP_FLOOR == ger.ERA_OVERLAP_FLOOR
    assert gen.ERA_OVERLAP_MAJORITY == ger.ERA_OVERLAP_MAJORITY
    steps = gen.ERA_OVERLAP_STEPS
    vals = {s["value"] for s in steps if s["value"] is not None}
    assert ger.ERA_OVERLAP_FLOOR in vals and ger.ERA_OVERLAP_MAJORITY in vals
    d = _shipped(PROBLEMS)
    got = frozenset(_identity(p) for p in _all_panels(d))
    if got == _PROBLEM_STRIPPED_PANELS:
        pytest.skip("problems board is in the fully-stripped form")
    hits = [p for p in _all_panels(d)
            if p.get("title", "").startswith("Verdict comparability")]
    assert hits, f"{PROBLEMS}: no 'Verdict comparability' panel"
    shipped_steps = hits[0]["fieldConfig"]["defaults"]["thresholds"]["steps"]
    shipped_vals = {s["value"] for s in shipped_steps if s["value"] is not None}
    assert ger.ERA_OVERLAP_FLOOR in shipped_vals
    assert ger.ERA_OVERLAP_MAJORITY in shipped_vals


def test_absence_never_borrows_a_verdict_color():
    """Grafana paints a stat's noValue string with the BASE threshold
    step's color, so a green base renders ABSENCE as an all-clear and a
    red base renders "window filling" as an alarm. Every palette whose
    tiles carry honest-absence text must anchor on the neutral "text"
    base; signed-gap palettes park their real colors above an
    unreachable sentinel so values still read true.

    Verified-by-precedent renderer claim (the state() tiles already pair
    base-text with mappings); the one-tile live injection remains the
    deploy-time check."""
    assert gen.ZERO_BAD[0] == {"color": "text", "value": None}, gen.ZERO_BAD
    assert gen.EQ_DRIFT[0] == {"color": "text", "value": None}, gen.EQ_DRIFT
    for pal in (gen.GAP_GOOD_POS, gen.GAP_BAD_POS):
        assert pal[0] == {"color": "text", "value": None}, pal
        # the sentinel keeps real values colored: everything reachable
        # sits above the second step
        assert pal[1]["value"] == -100, pal
    # and the shipped judge tiles anchor neutral too
    for board in (LEARNING, PROBLEMS):
        for p in _all_panels(_shipped(board)):
            if p.get("title") == "Trades the judge has scored":
                base = p["fieldConfig"]["defaults"]["thresholds"]["steps"][0]
                assert base["color"] == "text", (board, base)


def test_judge_floor_text_tracks_config():
    """The '<N scored closes' empty-state text and the judge tiles' green
    line must equal ml.monitor.min_trades_to_judge — a hardcoded 15 would
    turn into a lie on the first config change."""
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    floor = int(cfg["ml"]["monitor"]["min_trades_to_judge"])
    assert gen.JUDGE_MIN == floor
    assert f"<{floor} " in gen._NV_JUDGE, gen._NV_JUDGE
    for board in (LEARNING, PROBLEMS):
        hits = [p for p in _all_panels(_shipped(board))
                if p.get("title") == "Trades the judge has scored"]
        if not hits:      # stripped form
            continue
        steps = hits[0]["fieldConfig"]["defaults"]["thresholds"]["steps"]
        assert any(s.get("value") == floor for s in steps), (
            f"{board}: judge tile's green line is not the config floor "
            f"{floor}")


def test_execution_board_still_mirrors_the_alert_rules():
    """The execution board exists to make the alert inputs visible.

    Every metric the two rules fire on must be ON this board. Pinning the
    inventory is not enough by itself, so the metric set is ALSO checked
    against the alert YAML: if someone adds a metric to a rule, or drops a
    panel from here, the board and the rule silently diverge and the first
    notice is a page with nothing on screen to explain it.
    """
    got = frozenset(_identity(p) for p in _all_panels(_shipped(EXECUTION)))
    assert got in (_EXEC_PANELS, _EXEC_STRIPPED_PANELS), (
        f"{EXECUTION} inventory does not match either pinned form.\n"
        f"  unexpected: {sorted(got - _EXEC_PANELS)}\n"
        f"  missing:    {sorted(_EXEC_PANELS - got)}\n"
        "Update _EXEC_PANELS in the SAME commit if the change is deliberate.")
    if got == _EXEC_STRIPPED_PANELS:
        pytest.skip("execution board is in the fully-stripped form")

    fired_on = set()
    for y in ALERT_YAMLS:
        # _alert_rule_facts degrades CLOSED: zero extracted metrics is a
        # failure, so a YAML rewrite cannot hollow this mirror silently
        fired_on |= _alert_rule_facts(y)[0]
    on_board = set()
    for p in _all_panels(_shipped(EXECUTION)):
        on_board |= set(_identity(p)[3])
    missing = fired_on - on_board
    assert not missing, (
        f"alert rules fire on {sorted(missing)} but no panel on {EXECUTION} "
        "queries them. An alert whose inputs are on no board can only be "
        "discovered by being paged. Add the panel or drop it from the rule.")


@pytest.mark.parametrize("fname", ALL_BOARDS)
def test_only_the_glass_injector_executes_javascript(fname):
    """The Business Text plugin runs arbitrary JS in the operator's browser
    via its afterRender hook. Exactly one panel per board may do that, and it
    must be the injector at the pinned id — otherwise a board could grow a
    second script-executing tile while every other pin stayed green."""
    js = [p for p in _all_panels(_shipped(fname))
          if p.get("type") in _JS_PANEL_TYPES]
    assert len(js) == 1, (
        f"{fname}: expected exactly ONE JavaScript-executing panel, found "
        f"{len(js)}: {[(p.get('id'), p.get('title')) for p in js]}")
    assert js[0]["id"] == gen.INJ_ID, (
        f"{fname}: the JS panel is id {js[0]['id']}, not the sanctioned "
        f"injector id {gen.INJ_ID}")


@pytest.mark.parametrize("fname", (COMMAND, LEARNING, PROBLEMS))
def test_operator_boards_surface_telemetry_age(fname):
    """Whatever else an operator board shows, it must show how OLD the
    data is.

    Every other number is a snapshot republished by scripts/gc_pusher.py.
    If the pusher stops, the tiles do not blank - they keep displaying the
    last value they saw, indefinitely and confidently. A stale equity (or
    Brier, or fault) figure is indistinguishable from a live one, so the
    age reading is what makes the rest of the board falsifiable.

    2026-08-17: re-widened from the command-only form back to every board
    the operator screen-snips (the narrowing was itself a narrowing of the
    original board-wide sweep, retired only because the other boards were
    empty). The execution mirror is exempt: it is not an operator link and
    its pinned inventory is exactly the alert inputs.
    """
    d = _shipped(fname)
    got = frozenset(_identity(p) for p in _all_panels(d))
    if got == frozenset({(gen.INJ_ID, "", INJ_TYPE, ())}):
        pytest.skip(f"{fname} is in the fully-stripped form")
    exprs = " ".join(t.get("expr", "")
                     for p in _all_panels(d)
                     for t in (p.get("targets") or []))
    assert "liquiditybot_status_age_sec" in exprs, (
        f"{fname} has content but no panel queries "
        "liquiditybot_status_age_sec. Without it a dead exporter looks "
        "exactly like a quiet market: every tile keeps showing its last "
        "value and nothing on screen says the data stopped moving.")


# --------------------------------------------------------------------------
# the glass framework survives on every board
# --------------------------------------------------------------------------
@pytest.mark.parametrize("fname", ALL_BOARDS)
def test_every_board_carries_a_transparent_glass_injector(fname):
    d = _shipped(fname)
    inj = _injector_of(d)
    assert inj["type"] == INJ_TYPE, f"{fname}: {inj['type']}"
    assert inj["transparent"] is True, f"{fname}: injector must be transparent"
    assert inj["gridPos"]["w"] == 1 and inj["gridPos"]["h"] == 1, \
        f"{fname}: injector must stay 1x1, found {inj['gridPos']}"
    # it must be TOP-LEVEL: a panel nested in a collapsed row never renders,
    # and the skin would vanish until someone expanded that row
    assert any(p["id"] == gen.INJ_ID for p in d["panels"]), \
        f"{fname}: injector nested inside a row — it would never render"
    # and bottom-most, so it never pushes content down a grid row
    ys = [p["gridPos"]["y"] for p in d["panels"]]
    assert inj["gridPos"]["y"] == max(ys), \
        f"{fname}: injector at y={inj['gridPos']['y']}, max y={max(ys)}"
    assert min(ys) == 0, f"{fname}: no panel at y=0 — dead band at the top"


@pytest.mark.parametrize("fname", ALL_BOARDS)
def test_injector_embeds_the_whole_glass_stylesheet(fname):
    after = _injector_of(_shipped(fname))["options"]["afterRender"]
    assert gen.GLASS_RULES.strip(), "GLASS_RULES is empty — the skin is gone"
    # distinctive fragments, asserted BOTH ends: present in the module
    # constant AND in the shipped JS. A fragment that drifts out of
    # GLASS_RULES fails here rather than silently weakening the check.
    for frag in ("-webkit-text-size-adjust: 100%", "backdrop-filter",
                 f"panel-{gen.INJ_ID}"):
        assert frag in gen.GLASS_RULES, f"stale fragment {frag!r}"
        assert frag in after, f"{fname}: {frag!r} missing from afterRender"
    # the whole stylesheet, embedded as a JS string literal by _injector()
    assert json.dumps(gen.GLASS_RULES) in after, (
        f"{fname}: afterRender does not carry GLASS_RULES verbatim — the "
        "shipped skin has drifted from the generator constant")
    assert "document.getElementById('lb-glass')" in after, \
        f"{fname}: the duplicate-<style> guard is gone"


# --------------------------------------------------------------------------
# the board shell
# --------------------------------------------------------------------------
def test_board_shell_survives_the_strip():
    uids, link_targets = set(), set()
    for fname in ALL_BOARDS:
        d = _shipped(fname)
        assert "dashboard" not in d, f"{fname}: wrapped export, not importable"
        assert d["schemaVersion"] == 39, f"{fname}: {d['schemaVersion']}"
        assert d["uid"], f"{fname}: empty uid"
        assert d["uid"] not in uids, f"{fname}: uid {d['uid']} not unique"
        uids.add(d["uid"])
        assert d["title"].strip(), f"{fname}: empty title"
        assert d["tags"], f"{fname}: no tags — board is unfindable"
        links = d["links"]
        assert links, f"{fname}: nav links gone — the boards are unreachable"
        link_targets |= {ln["url"] for ln in links}
    assert link_targets == {f"/d/{u}" for u in uids}, (
        "nav links and board uids disagree — a link points at a board that "
        f"does not exist, or a board is unreachable: {sorted(link_targets)} "
        f"vs {sorted(uids)}")


# --------------------------------------------------------------------------
# a rebuild has to remain possible
# --------------------------------------------------------------------------
def test_panel_factories_still_build_a_board():
    """Not `callable()` — that proves nothing. Actually run the factories
    through _board() and check a real multi-panel board comes out, so the
    day the boards are rebuilt the framework is known to work."""
    for name in ("row", "stat", "state", "gauge", "timeseries", "bargauge",
                 "donut", "table", "text"):
        assert callable(getattr(gen, name, None)), f"factory {name} is gone"

    def _author():
        # gen.USD ("prefix:$"), never Grafana's built-in "currencyUSD": that
        # unit SI-abbreviates at >=$1k and renders $4,997.92 as "$5.00K", so
        # the number shown is not the number the bot holds. Nothing in the
        # battery enforces this, which is exactly why the worked example a
        # rebuilder copies from must not demonstrate the wrong one.
        gen.stat("Equity", gen.M("liquiditybot_equity"), 6, 6, unit=gen.USD)
        gen.gauge("Exposure", gen.M("liquiditybot_gross_exposure_pct"), 6, 6)
        gen.timeseries("Equity", gen.M("liquiditybot_equity"), 12, 7)
        gen.row("Positions")
        gen.table("Open", 24, 9,
                  cols=[("liquiditybot_position_upnl_usd", "uP&L", gen.USD,
                         2, None, "text")],
                  label_keys=["symbol"])

    saved = (list(gen.panels), dict(gen._cur), dict(gen._pid))
    try:
        built = gen._board("throwaway-uid", "throwaway", "probe", _author,
                           "probe")
    finally:  # _board leaves the module buffers dirty; put them back
        gen.panels.clear()
        gen.panels.extend(saved[0])
        gen._cur.clear()
        gen._cur.update(saved[1])
        gen._pid.clear()
        gen._pid.update(saved[2])

    built_panels = built["panels"]
    assert len(built_panels) > 1, "factories produced no content panels"
    types = {p["type"] for p in built_panels} | {
        m["type"] for p in built_panels for m in (p.get("panels") or [])}
    assert {"stat", "gauge", "timeseries", "table", INJ_TYPE} <= types, \
        f"rebuilt board is missing panel types: {sorted(types)}"
    assert built["schemaVersion"] == 39
    assert any(p["id"] == gen.INJ_ID for p in built_panels), \
        "a rebuilt board would ship without the glass injector"
