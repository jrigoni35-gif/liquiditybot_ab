"""tests/test_bracket_divergence.py — geometry-alignment Task 6: the
labeled-vs-realized bracket comparator (spec D6, ML-082).

For every BRACKET-traded close (barrier in tb_pt/tb_sl/tb_time — T5's
model-lane bracket-exit reasons), the comparator compares the position's
REALIZED net return against the LABELED counterfactual its own stamped
pt_frac/sl_frac would imply, and rolls {agree, |delta|} into a bounded
window (ml/history.py's HistoryStore._record_bracket_divergence /
bracket_divergence_summary — mirrors the ML-080 era_mix_drift window
idiom: report-only, config-lifted, honest absence).

Counterfactual approach (documented in _record_bracket_divergence's own
docstring): the live engine keeps no per-position OHLC bar history, so
this task takes the spec's own documented fallback rather than
re-running triple_barrier() on recorded bars — tb_pt/tb_sl compare
against the FIXED barrier distance net of the entry's own cost estimate,
tb_time compares against itself (no fixed distance to diverge from, so
it always agrees by construction).

Sections:
  1. comparator unit — agree/disagree/window-roll/config-lifted
     tolerance, at the HistoryStore.log_close level.
  2. status block shape — bracket_divergence_summary()'s honest-absence
     and populated shapes; the exact close-time integration through
     main.LiquidityBot._finalize_position (T5's own call site).
  3. gc_pusher — emits both gauges with the block present + n>0; emits
     NOTHING when the block is absent, n==0, or the status is stale
     (alarm-only batch).
  4. report-only proof — grep-style: no module outside the telemetry
     surface (producer + its two consumers + the registry/guard) ever
     references bracket_divergence.
"""
import json
import logging
import os
import time
import types
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

import scripts.gc_pusher as gp
from core.codes import Code
from core.state import PortfolioState, Position
from ml.features import FEATURE_NAMES
from ml.history import HistoryStore

_LOGGER = "liquiditybot.ml.history"
ROOT = Path(__file__).resolve().parents[1]


def _feats(seed):
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, 1.0, len(FEATURE_NAMES))


def _store(tmp_path):
    return HistoryStore(str(tmp_path / "hist.csv"))


def _names(metrics):
    return {m["name"] for m in metrics}


def _val(metrics, name):
    for m in metrics:
        if m["name"] == name:
            return m["gauge"]["dataPoints"][0]["asDouble"]
    return None


def _close(hs, pid, seed, net_pnl_usd, barrier="tb_pt", pt_frac=0.0,
          sl_frac=0.0, entry_usd=1000.0, cost_pct=0.05, telemetry_cfg=None):
    hs.log_entry(pid, "ETH", "long", _feats(seed))
    hs.log_close(pid, net_pnl_usd, barrier=barrier, pt_frac=pt_frac,
                sl_frac=sl_frac, entry_usd=entry_usd, cost_pct=cost_pct,
                telemetry_cfg=telemetry_cfg)


# ---------------------------------------------------------------------
# 1. comparator unit (HistoryStore.log_close -> bracket_divergence_summary)
# ---------------------------------------------------------------------

def test_summary_empty_before_any_bracket_close(tmp_path):
    hs = _store(tmp_path)
    assert hs.bracket_divergence_summary() == {
        "n": 0, "n_priced": 0, "agree_rate": None,
        "mean_abs_ret_delta_pct": None}


def test_tb_pt_close_within_tolerance_counts_agree(tmp_path):
    hs = _store(tmp_path)
    # counterfactual = pt_frac*100 - cost_pct = 1.0 - 0.05 = 0.95%
    # realized = 9.0 / 1000 * 100 = 0.90% -> delta = 0.05pp <= default 0.15
    _close(hs, "p1", 1, net_pnl_usd=9.0, barrier="tb_pt", pt_frac=0.01,
          sl_frac=0.008, entry_usd=1000.0, cost_pct=0.05)
    s = hs.bracket_divergence_summary()
    assert s["n"] == 1
    assert s["agree_rate"] == pytest.approx(1.0)
    assert s["mean_abs_ret_delta_pct"] == pytest.approx(0.05, abs=1e-6)


def test_tb_sl_close_outside_tolerance_counts_disagree(tmp_path):
    hs = _store(tmp_path)
    # counterfactual = -sl_frac*100 - cost_pct = -2.0 - 0.05 = -2.05%
    # realized = -10.0 / 1000 * 100 = -1.00% -> delta = 1.05pp > 0.15 tol
    _close(hs, "p1", 1, net_pnl_usd=-10.0, barrier="tb_sl", pt_frac=0.03,
          sl_frac=0.02, entry_usd=1000.0, cost_pct=0.05)
    s = hs.bracket_divergence_summary()
    assert s["n"] == 1
    assert s["agree_rate"] == pytest.approx(0.0)
    assert s["mean_abs_ret_delta_pct"] == pytest.approx(1.05, abs=1e-6)


def test_tb_time_close_is_counted_but_never_priced(tmp_path):
    """tb_time has no fixed barrier distance to diverge from — the
    counterfactual IS the realized return, so delta is always 0 regardless
    of pt_frac/sl_frac/cost_pct/the realized number itself.

    THIS TEST PREVIOUSLY ASSERTED agree_rate == 1.0, i.e. it pinned the
    tautology as intended behaviour. It was correct about the mechanism
    and wrong about what should be PUBLISHED. Measured 2026-08-06 over the
    instrument's whole production lifetime: 33 of 35 records (94.3%) were
    tb_time, so the agree_rate reaching Grafana was 1.0000 and 94%
    arithmetically incapable of being anything else — a gauge that could
    only ever read "perfect". A tb_time close is still a real bracket
    close and still counts toward `n`; it just cannot contribute evidence
    about whether the traded bet resolved where the label says it should,
    so it is excluded from `n_priced` and from the rate computed over it.
    """
    hs = _store(tmp_path)
    _close(hs, "p1", 1, net_pnl_usd=-37.5, barrier="tb_time", pt_frac=0.05,
          sl_frac=0.05, entry_usd=1000.0, cost_pct=0.20)
    s = hs.bracket_divergence_summary()
    assert s["n"] == 1, "the close itself is still recorded"
    assert s["n_priced"] == 0
    assert s["agree_rate"] is None, \
        "a definitional agreement must not publish as a measured 1.0"
    assert s["mean_abs_ret_delta_pct"] is None


def test_non_bracket_barrier_never_recorded(tmp_path):
    """Only tb_pt/tb_sl/tb_time are BRACKET closes; every senior-overlay
    reason (realized/tier/trail/floor/...) must leave the window
    untouched, even with a full entry_usd/cost_pct/pt_frac/sl_frac
    payload — the comparator is scoped to bracket-traded closes only."""
    hs = _store(tmp_path)
    _close(hs, "p1", 1, net_pnl_usd=9.0, barrier="realized", pt_frac=0.01,
          sl_frac=0.01, entry_usd=1000.0, cost_pct=0.05)
    assert hs.bracket_divergence_summary()["n"] == 0


def test_zero_entry_usd_skips_recording_never_fabricates(tmp_path):
    """entry_usd<=0 (unknown notional — a legacy/test caller that never
    threads it) must skip recording entirely rather than divide by zero
    or fabricate a return."""
    hs = _store(tmp_path)
    _close(hs, "p1", 1, net_pnl_usd=9.0, barrier="tb_pt", pt_frac=0.01,
          sl_frac=0.01, entry_usd=0.0, cost_pct=0.05)
    assert hs.bracket_divergence_summary()["n"] == 0


def test_window_rolls_bounded_by_config(tmp_path):
    """Config-lifted window (ml.telemetry.bracket_divergence_window_n):
    pushing more bracket closes than the window holds must drop the
    OLDEST entries first, keeping only the most recent `window_n`.
    window_n=10 (the config_guard-enforced floor — _record_bracket_
    divergence itself floors below 10, matching the production [10,
    5000] bound) — 12 clean agreements followed by 3 clear disagreements
    (15 closes total) must leave exactly the last 10: 7 agree + 3
    disagree survive, the first 5 agreements are pushed out."""
    hs = _store(tmp_path)
    cfg = {"bracket_divergence_window_n": 10}
    for i in range(12):
        _close(hs, f"a{i}", i, net_pnl_usd=9.5, barrier="tb_pt",
              pt_frac=0.01, entry_usd=1000.0, cost_pct=0.05,
              telemetry_cfg=cfg)                                  # agree
    for i in range(3):
        _close(hs, f"d{i}", 100 + i, net_pnl_usd=-50.0, barrier="tb_sl",
              sl_frac=0.02, entry_usd=1000.0, cost_pct=0.05,
              telemetry_cfg=cfg)                                  # disagree
    s = hs.bracket_divergence_summary()
    assert s["n"] == 10
    assert s["agree_rate"] == pytest.approx(0.7)


def test_tolerance_is_config_lifted_not_hardcoded(tmp_path):
    """The same 0.20pp delta must flip agree<->disagree purely off the
    config value — proves the tolerance is a real, threaded parameter,
    never a fitted-looking literal in the decision path (it gates
    nothing, but overfit discipline still applies to any tunable).
    counterfactual = pt_frac*100 - cost_pct = 1.0 - 0.05 = 0.95%;
    realized = 7.5/1000*100 = 0.75% -> delta = |0.75 - 0.95| = 0.20pp."""
    hs_tight = _store(tmp_path)
    _close(hs_tight, "p1", 1, net_pnl_usd=7.5, barrier="tb_pt",
          pt_frac=0.01, entry_usd=1000.0, cost_pct=0.05,
          telemetry_cfg={"bracket_divergence_tolerance_pct": 0.15})
    assert hs_tight.bracket_divergence_summary()["agree_rate"] == \
        pytest.approx(0.0)          # delta 0.2 > tol 0.15 -> disagree

    hs_loose = _store(tmp_path)
    _close(hs_loose, "p1", 1, net_pnl_usd=7.5, barrier="tb_pt",
          pt_frac=0.01, entry_usd=1000.0, cost_pct=0.05,
          telemetry_cfg={"bracket_divergence_tolerance_pct": 0.25})
    assert hs_loose.bracket_divergence_summary()["agree_rate"] == \
        pytest.approx(1.0)         # delta 0.2 <= tol 0.25 -> agree


def test_log_close_default_kwargs_are_legacy_inert(tmp_path):
    """Every T6-added log_close kwarg (entry_usd/cost_pct/telemetry_cfg)
    defaults to 0.0/{} — a pre-T6 caller (bare `log_close(pid, pnl)`,
    barrier defaulting to "realized") is byte-identical: no bracket
    divergence entry, no crash."""
    hs = _store(tmp_path)
    hs.log_entry("p1", "BTC", "long", _feats(1))
    hs.log_close("p1", 5.0)                     # exactly the legacy call
    assert hs.bracket_divergence_summary()["n"] == 0


def test_bracket_divergence_logs_registered_code_one_line_per_close(
        tmp_path, caplog):
    hs = _store(tmp_path)
    with caplog.at_level(logging.INFO, logger=_LOGGER):
        _close(hs, "p1", 1, net_pnl_usd=9.0, barrier="tb_pt", pt_frac=0.01,
              entry_usd=1000.0, cost_pct=0.05)
    hits = [r for r in caplog.records
           if Code.ML_BRACKET_DIVERGENCE.value in r.getMessage()]
    assert len(hits) == 1, "exactly ONE line per bracket close"


# ---------------------------------------------------------------------
# 2. status block shape + the real close-time integration seam
#    (main.LiquidityBot._finalize_position, T5's own call site)
# ---------------------------------------------------------------------

def _finalize_bot(tmp_path, config=None):
    from main import LiquidityBot
    bot = LiquidityBot.__new__(LiquidityBot)
    bot.history = HistoryStore(str(tmp_path / "h.csv"))
    bot.perf = types.SimpleNamespace(record_close=lambda *a, **k: None)
    bot.breaker = types.SimpleNamespace(record_close=lambda *a, **k: False)
    bot.postmortem = types.SimpleNamespace(on_close=lambda *a, **k: None)
    bot.state = PortfolioState(starting_capital=10_000.0)
    bot._pos_thales = {}
    bot.thales = types.SimpleNamespace(note_outcome=lambda *a, **k: None)
    bot._stop_hit = {}
    bot._exit_attempts = {}
    bot.macro = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(label="range"))
    bot.liq = types.SimpleNamespace(
        state=lambda a: types.SimpleNamespace(label="liquid"))
    bot.ladder = types.SimpleNamespace(note_exit=lambda a: None)
    bot._asset_of = lambda s: s.split("/")[0]
    if config is not None:
        bot.config = config
    return bot


def _bracket_pos(pt_frac=0.01, sl_frac=0.01, entry=2000.0, size=1.0,
                 est_cost_bps=5.0):
    p = Position("p1", "ETH/USD", "long", entry, size, size,
                datetime.now(timezone.utc))
    p.bracket_pt_frac = pt_frac
    p.bracket_sl_frac = sl_frac
    p.est_cost_bps = est_cost_bps
    return p


def test_finalize_position_stub_bot_without_config_self_heals(tmp_path):
    """The stub-bot unit-test harness (test_bracket_exits.py's own
    pattern) never sets bot.config — _finalize_position's
    getattr(self, "config", {}) must self-heal, not raise, exactly like
    the codebase's other self-healing getattr conventions
    (_long_book_realized_pnl_total, est_cost_bps)."""
    bot = _finalize_bot(tmp_path)                # no bot.config at all
    assert not hasattr(bot, "config")
    pos = _bracket_pos(pt_frac=0.01, sl_frac=0.01, entry=2000.0)
    bot.history.log_entry(pos.position_id, "ETH", "long",
                          np.zeros(len(FEATURE_NAMES)))
    bot._finalize_position(pos, 19.0, 1000.0, close_reason="tb_pt")
    s = bot.history.bracket_divergence_summary()
    assert s["n"] == 1


def test_finalize_position_threads_entry_usd_and_cost_from_position(
        tmp_path):
    """entry_usd (entry_price*original_size) and cost_pct (est_cost_bps/
    100) must come from the POSITION's own stamped fields, not a
    hardcoded stand-in — pin the exact arithmetic end-to-end."""
    bot = _finalize_bot(tmp_path)
    # entry_usd = 2000*1 = 2000; cost_pct = 5.0/100 = 0.05
    # counterfactual = pt_frac*100 - cost_pct = 1.0 - 0.05 = 0.95%
    # realized = 19.0/2000*100 = 0.95% -> delta = 0.0 -> agree
    pos = _bracket_pos(pt_frac=0.01, sl_frac=0.01, entry=2000.0, size=1.0,
                       est_cost_bps=5.0)
    bot.history.log_entry(pos.position_id, "ETH", "long",
                          np.zeros(len(FEATURE_NAMES)))
    bot._finalize_position(pos, 19.0, 1000.0, close_reason="tb_pt")
    s = bot.history.bracket_divergence_summary()
    assert s["n"] == 1
    assert s["mean_abs_ret_delta_pct"] == pytest.approx(0.0, abs=1e-6)


def test_finalize_position_threads_telemetry_cfg_from_bot_config(tmp_path):
    """bot.config's ml.telemetry block (when present) must reach the
    comparator — a tight configured tolerance flips an otherwise-agreeing
    close to disagree, proving the config path is live end-to-end."""
    bot = _finalize_bot(tmp_path, config={
        "ml": {"telemetry": {"bracket_divergence_tolerance_pct": 0.001}}})
    # counterfactual 0.95%, realized 0.90% -> delta 0.05pp > tol 0.001
    pos = _bracket_pos(pt_frac=0.01, sl_frac=0.01, entry=1000.0, size=1.0,
                       est_cost_bps=5.0)
    bot.history.log_entry(pos.position_id, "ETH", "long",
                          np.zeros(len(FEATURE_NAMES)))
    bot._finalize_position(pos, 9.0, 1000.0, close_reason="tb_pt")
    s = bot.history.bracket_divergence_summary()
    assert s["agree_rate"] == pytest.approx(0.0)


def test_finalize_position_overlay_reason_never_records_bracket_divergence(
        tmp_path):
    """A senior-overlay close on a bracket position (give-back/trail/
    hard stop/...) falls back to barrier="realized" (T5) and must NOT
    feed the comparator — only the exact tb_pt/tb_sl/tb_time strings
    ever do, mirroring T5's own label_era scoping."""
    bot = _finalize_bot(tmp_path)
    pos = _bracket_pos(pt_frac=0.01, sl_frac=0.01)
    bot.history.log_entry(pos.position_id, "ETH", "long",
                          np.zeros(len(FEATURE_NAMES)))
    bot._finalize_position(pos, 19.0, 1000.0, close_reason="tier trail")
    assert bot.history.bracket_divergence_summary()["n"] == 0


def test_runner_status_wires_bracket_divergence_into_ml_block():
    """Structural pin on the status-assembly seam (runner.py's
    build_status, the "ml" dict brief-mandated to carry status["ml"]
    ["bracket_divergence"]) — a sibling of load_stats, sourced from
    HistoryStore.bracket_divergence_summary(), not nested inside
    load_stats (which only refreshes on a retrain)."""
    src = Path(ROOT / "runner.py").read_text(encoding="utf-8")
    assert "bot.history.bracket_divergence_summary()" in src
    # it must be assembled inside the "ml": {...} dict, not some other
    # top-level status key — pin it between the "ml" dict's own open
    # brace and its sibling "gate_stats" entry.
    ml_start = src.index('"ml": {')
    gate_stats_idx = src.index('"gate_stats"', ml_start)
    assert "bracket_divergence" in src[ml_start:gate_stats_idx]


# ---------------------------------------------------------------------
# 3. gc_pusher — honest-absence gauges, no labels
# ---------------------------------------------------------------------

def _write_status(tmp_path, ml_extra=None, written_at=None):
    status = {"written_at": written_at if written_at is not None
             else time.time(),
             "ml": {"bracket_divergence": ml_extra} if ml_extra is not None
             else {}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    return p


def test_gc_pusher_emits_rate_and_n_when_block_present_and_n_positive(
        tmp_path):
    p = _write_status(tmp_path, ml_extra={
        "n": 42, "agree_rate": 0.881, "mean_abs_ret_delta_pct": 0.09})
    m = gp.collect(str(p))
    names = _names(m)
    assert "liquiditybot_bracket_divergence_rate" in names
    assert "liquiditybot_bracket_divergence_n" in names
    assert _val(m, "liquiditybot_bracket_divergence_rate") == \
        pytest.approx(0.881)
    assert _val(m, "liquiditybot_bracket_divergence_n") == 42.0
    # no labels — the metric name carries no attributes
    hit = [x for x in m if x["name"] == "liquiditybot_bracket_divergence_n"]
    assert hit and "attributes" not in hit[0]["gauge"]["dataPoints"][0]


def test_gc_pusher_emits_nothing_when_block_absent(tmp_path):
    p = _write_status(tmp_path, ml_extra=None)
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_bracket_")]


def test_gc_pusher_emits_nothing_when_n_is_zero(tmp_path):
    p = _write_status(tmp_path, ml_extra={
        "n": 0, "agree_rate": None, "mean_abs_ret_delta_pct": None})
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_bracket_")]


def test_gc_pusher_emits_nothing_on_stale_status(tmp_path):
    """Past STALE_AFTER_SEC the pusher returns the alarm-only batch
    (age/running=0/stale=1) and withholds EVERY market/ml gauge — the
    new bracket-divergence gauges must not be an exception."""
    old_ts = time.time() - (gp.STALE_AFTER_SEC + 30.0)
    p = _write_status(tmp_path, ml_extra={
        "n": 42, "agree_rate": 0.881, "mean_abs_ret_delta_pct": 0.09},
        written_at=old_ts)
    m = gp.collect(str(p))
    names = _names(m)
    assert _val(m, "liquiditybot_status_stale") == 1.0
    assert not [n for n in names if n.startswith("liquiditybot_bracket_")]


def test_gc_pusher_ml_block_empty_dict_emits_nothing(tmp_path):
    """ml.bracket_divergence == {} (an intermediate/older shape) must
    also degrade to nothing — a plain-falsy dict is treated exactly like
    the key being absent."""
    status = {"written_at": time.time(), "ml": {"bracket_divergence": {}}}
    p = tmp_path / "status.json"
    p.write_text(json.dumps(status), encoding="utf-8")
    names = _names(gp.collect(str(p)))
    assert not [n for n in names if n.startswith("liquiditybot_bracket_")]


# ---------------------------------------------------------------------
# 4. report-only proof: no decision path reads status["ml"]
#    ["bracket_divergence"] or calls bracket_divergence_summary()
# ---------------------------------------------------------------------

_ALLOWED_REL = {
    "ml/history.py", "runner.py", "scripts/gc_pusher.py",
    "scripts/build_trading_dashboard.py", "core/codes.py",
    "core/config_guard.py", "config.json",
}
_SKIP_DIRS = {".venv", "__pycache__", ".git", "node_modules", "tests",
             "docs", ".superpowers", ".claude", "outputs"}
# outputs added 2026-09-08 (same reason as tests/test_ofi_feature.py): it is
# gitignored runtime state and agent scratch, never the decision path.
# .claude added 2026-07-30: agent worktrees (.claude/worktrees/<id>/) are
# full repo CHECKOUTS living under the repo root — walking into one finds
# that checkout's own legitimate telemetry-surface files and fails this
# grep with phantom hits. Same class as .venv/.git: not our tree.


def test_bracket_divergence_report_only_grep():
    hits = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        rel_dir = Path(dirpath).relative_to(ROOT)
        for fn in filenames:
            if not (fn.endswith(".py") or fn == "config.json"):
                continue
            rel = str((rel_dir / fn)).replace("\\", "/")
            if rel.startswith("./"):
                rel = rel[2:]
            if rel in _ALLOWED_REL:
                continue
            fpath = Path(dirpath) / fn
            try:
                text = fpath.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "bracket_divergence" in text:
                hits.append(rel)
    assert not hits, (
        f"bracket_divergence referenced outside the telemetry surface "
        f"(producer ml/history.py, its status/gc_pusher/dashboard "
        f"consumers, and the registry/guard): {hits}")
