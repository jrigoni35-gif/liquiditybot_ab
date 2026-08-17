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
    (4, "All time", "stat", ("liquiditybot_net_pnl_all_time",)),
    (5, "Drawdown", "stat", ("liquiditybot_drawdown_pct",)),
    (6, "Equity", "timeseries", ("liquiditybot_equity",)),
    (7, "Open positions", "stat", ("liquiditybot_positions_open",)),
    (8, "Gross exposure", "gauge", ("liquiditybot_gross_exposure_pct",)),
    (9, "Fees paid", "stat", ("liquiditybot_fees_total",)),
    (10, "Entries", "stat", ("liquiditybot_entries_enabled",)),
    (11, "Halt", "stat", ("liquiditybot_halted",)),
    (12, "Data age", "stat", ("liquiditybot_status_age_sec",)),
    # liveness group - restored after review; see the generator's comment on
    # why a frozen runner otherwise reads as a calm, profitable book
    (13, "Runner", "stat", ("liquiditybot_running",)),
    (14, "Telemetry", "stat", ("liquiditybot_status_stale",)),
    (15, "Kraken feed", "stat", ("liquiditybot_ws_kraken_connected",)),
    (16, "Op state", "stat", ("liquiditybot_op_state",)),
    (17, "Positions", "row", ()),
    (18, "Open positions", "table",
     ("liquiditybot_position_age_hours", "liquiditybot_position_conviction",
      "liquiditybot_position_notional_usd", "liquiditybot_position_r_multiple",
      "liquiditybot_position_stop_dist_pct", "liquiditybot_position_upnl_pct",
      "liquiditybot_position_upnl_usd")),
    # activity & budget (2026-08-17, vault docket D1/55's panel half):
    # appended AFTER the table so ids 1-18 above are byte-identical
    (19, "Activity & budget", "row", ()),
    (20, "Exposure by asset", "piechart",
     ("liquiditybot_position_notional_usd",)),
    (21, "Fill mix", "piechart",
     ("liquiditybot_order_maker_fills", "liquiditybot_order_taker_fills")),
    (22, "Daily loss budget used", "gauge",
     ("liquiditybot_rp_daily_budget_used_frac",)),
    (23, "Weekly loss budget used", "gauge",
     ("liquiditybot_rp_weekly_budget_used_frac",)),
    (24, "Fills so far", "stat",
     ("liquiditybot_order_maker_fills", "liquiditybot_order_taker_fills")),
    (25, "Size taper", "stat", ("liquiditybot_rp_taper_mult",)),
    (26, "Profit pools", "stat",
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
    (1, "Model edge over naive guess", "stat",
     ("liquiditybot_ml_baseline_brier", "liquiditybot_ml_brier")),
    (2, "Training rows", "stat", ("liquiditybot_ml_history_rows",)),
    (3, "Clean live labels", "stat", ("liquiditybot_ml_live_clean",)),
    (4, "Model in use", "stat", ("liquiditybot_ml_use_model",)),
    (5, "Learning health", "stat", ("liquiditybot_monitor_level",)),
    (6, "Data age", "stat", ("liquiditybot_status_age_sec",)),
    (7, "Is it getting smarter?", "row", ()),
    (8, "Prediction error - model vs naive vs champion", "timeseries",
     ("liquiditybot_ml_baseline_brier", "liquiditybot_ml_brier",
      "liquiditybot_ml_champion_brier")),
    (9, "Hit rate vs claimed probability", "timeseries",
     ("liquiditybot_ml_avg_p", "liquiditybot_ml_hit_rate",
      "liquiditybot_ml_hit_rate_lcb")),
    (10, "Feature drift share", "timeseries",
     ("liquiditybot_ml_drift_share",)),
    (11, "Calibration gap", "timeseries",
     ("liquiditybot_ml_calibration_gap",)),
    (12, "Is the pipeline filling?", "row", ()),
    (13, "Corpus rows toward honest testing", "gauge",
     ("liquiditybot_ml_history_rows",)),
    (14, "New-era rows toward re-arm", "gauge",
     ("liquiditybot_era_excl_new_rows",)),
    (15, "Labels per day", "stat",
     ("liquiditybot_probe_budget_live_labels_per_day_7d",)),
    (16, "Labels in the last 24h", "stat",
     ("liquiditybot_probe_budget_labels_24h",)),
    (17, "Label uniqueness", "stat", ("liquiditybot_ml_mean_uniqueness",)),
    (18, "Corpus growth", "timeseries",
     ("liquiditybot_ml_history_rows", "liquiditybot_ml_live_clean")),
    (19, "Where labels come from", "timeseries", ("liquiditybot_ml_labels",)),
    (20, "What the labels say", "row", ()),
    (21, "How this era's trades ended", "piechart",
     ("liquiditybot_era_reason_rows",)),
    (22, "Label rate this era", "stat", ("liquiditybot_era_label_rate",)),
    (23, "Corpus drift distance", "stat", ("liquiditybot_era_mix_tvd",)),
    (24, "Corpus matches live?", "stat", ("liquiditybot_era_mix_alarm",)),
    (25, "Rows excluded from training", "stat",
     ("liquiditybot_era_excl_dropped",)),
    (26, "Which model is driving", "row", ()),
    (27, "Deployed model over time", "timeseries",
     ("liquiditybot_ml_model_info",)),
    (28, "Retrain queued", "stat", ("liquiditybot_ml_retrain_flag",)),
    (29, "Retrain failures", "stat", ("liquiditybot_ml_retrain_failures",)),
    (30, "Model fallbacks", "stat", ("liquiditybot_ml_model_fallbacks",)),
    (31, "The cost of learning", "row", ()),
    (32, "Probe tokens in the tank", "gauge",
     ("liquiditybot_probe_budget_tokens",)),
    (33, "Tuition spent in 24h", "stat",
     ("liquiditybot_probe_budget_tuition_24h_usd",)),
    (34, "Tuition cap", "stat",
     ("liquiditybot_probe_budget_tuition_cap_usd",)),
    (35, "Unlock ETA", "stat",
     ("liquiditybot_probe_budget_unlock_eta_days",)),
    (36, "Probes open now", "stat",
     ("liquiditybot_probe_budget_open_probes",)),
    (37, "Denied - budget empty", "stat",
     ("liquiditybot_probe_budget_denied_exhausted_24h",)),
    (38, "Probe governor", "stat",
     ("liquiditybot_probe_budget_governor_factor",)),
    (39, "Refunds in 24h", "stat",
     ("liquiditybot_probe_budget_refunds_24h",)),
    (40, "Gate learning", "row", ()),
    (41, "Learned gate weights", "bargauge", ("liquiditybot_gate_weight",)),
    (42, "Is any gate lying?", "bargauge",
     ("liquiditybot_gate_divergence",)),
    (43, "Labeled rows feeding the gates", "stat",
     ("liquiditybot_gate_labeled",)),
    (44, "Base win rate the gates see", "stat",
     ("liquiditybot_gate_base_rate",)),
    (gen.INJ_ID, "", INJ_TYPE, ()),
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
    (9, "Drift stuck while degraded", "stat",
     ("liquiditybot_ml_drift_share", "liquiditybot_monitor_level")),
    (10, "Model governor", "stat", ("liquiditybot_monitor_level",)),
    (11, "Faults & rejections", "row", ()),
    (12, "Firewall trips by code", "timeseries",
     ("liquiditybot_firewall_count",)),
    (13, "Decisions by family", "timeseries", ("liquiditybot_code_count",)),
    (14, "Venue rejects", "stat", ("liquiditybot_order_venue_rejects",)),
    (15, "Dead-man failures", "stat",
     ("liquiditybot_order_deadman_failures",)),
    (16, "Exit-check failures", "stat",
     ("liquiditybot_exit_eval_failures",)),
    (17, "Cycle failures in a row", "stat",
     ("liquiditybot_cycle_consecutive_failures",)),
    (18, "Model inference faults", "stat", ("liquiditybot_ml_infer_faults",)),
    (19, "Feature-contract failures", "stat",
     ("liquiditybot_ml_contract_failed",)),
    (20, "Staleness & feeds", "row", ()),
    (21, "Feed latency", "stat", ("liquiditybot_feed_latency_ms",)),
    (22, "Price marks age", "stat", ("liquiditybot_marks_age_sec",)),
    (23, "Kraken feed", "stat", ("liquiditybot_ws_kraken_connected",)),
    (24, "Feed reconnects", "stat", ("liquiditybot_ws_kraken_reconnects",)),
    (25, "Stale assets", "stat", ("liquiditybot_watchdog_stale_assets",)),
    (26, "Diverging feeds", "stat", ("liquiditybot_watchdog_divergent",)),
    (27, "Critical data stale", "stat",
     ("liquiditybot_watchdog_critical_stale",)),
    (28, "Do the books add up?", "stat", ("liquiditybot_equity_drift_pct",)),
    (29, "Telemetry", "stat", ("liquiditybot_status_stale",)),
    (30, "Runner", "stat", ("liquiditybot_running",)),
    (31, "Risk brakes", "row", ()),
    (32, "Daily loss budget used", "gauge",
     ("liquiditybot_rp_daily_budget_used_frac",)),
    (33, "Weekly loss budget used", "gauge",
     ("liquiditybot_rp_weekly_budget_used_frac",)),
    (34, "Drawdown vs the hard stop", "timeseries",
     ("liquiditybot_rp_drawdown_mtm_pct", "liquiditybot_rp_hard_stop_dd_pct")),
    (35, "Size taper", "stat", ("liquiditybot_rp_taper_mult",)),
    (36, "Drawdown throttle", "stat", ("liquiditybot_rp_dd_throttle_mult",)),
    (37, "Portfolio heat", "stat", ("liquiditybot_rp_heat_frac",)),
    (38, "Assets circuit-broken", "stat", ("liquiditybot_cb_tripped_count",)),
    (39, "Circuit-breaker cooldown left", "bargauge",
     ("liquiditybot_cb_paused_hours_left",)),
    (40, "Loss streak by asset", "bargauge",
     ("liquiditybot_perf_asset_cur_loss_streak",)),
    (41, "Audit & self-health", "row", ()),
    (42, "Audit writes dropped", "stat",
     ("liquiditybot_audit_dropped_writes",)),
    (43, "Audit tail truncations", "stat",
     ("liquiditybot_audit_tail_truncations",)),
    (44, "Bad values dropped by exporter", "stat",
     ("liquiditybot_gauges_dropped_nonfinite",)),
    (45, "Cycles since restart", "stat", ("liquiditybot_cycle",)),
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


def test_problem_board_mirrors_both_pager_conditions():
    """The PROBLEMS board must render the SAME arithmetic the two alert
    rules run (the ab8ee2b4 lesson: an alert whose inputs are on no board
    is discovered by being paged). Checked against the alert YAML like the
    execution-board mirror below, not against a hand-copied metric list."""
    got = frozenset(_identity(p) for p in _all_panels(_shipped(PROBLEMS)))
    if got == _PROBLEM_STRIPPED_PANELS:
        pytest.skip("problems board is in the fully-stripped form")
    fired_on = set()
    for y in ("liquiditybot_brier_alert.yaml", "liquiditybot_drift_alert.yaml"):
        txt = (ROOT / "docs" / "grafana" / y).read_text(encoding="utf-8")
        for line in txt.splitlines():
            if "expr:" in line:
                fired_on |= set(_MET_RE.findall(line))
    on_board = set()
    for p in _all_panels(_shipped(PROBLEMS)):
        on_board |= set(_identity(p)[3])
    missing = fired_on - on_board
    assert not missing, (
        f"alert rules fire on {sorted(missing)} but no PROBLEMS panel "
        "queries them — the 'what needs attention' board would go quiet on "
        "the exact inputs the pager watches.")


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

    alert_dir = ROOT / "docs" / "grafana"
    fired_on = set()
    for y in ("liquiditybot_brier_alert.yaml", "liquiditybot_drift_alert.yaml"):
        txt = (alert_dir / y).read_text(encoding="utf-8")
        for line in txt.splitlines():
            # only the query EXPRESSIONS, not prose in comments/annotations
            if "expr:" in line:
                fired_on |= set(_MET_RE.findall(line))
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
