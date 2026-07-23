"""tests/test_probe_throttle.py — P3 corpus-aware probe throttle
(2026-07-23 P&L diagnosis: probes were 69% of live closes and -$22.87 of
-$31.68 measured net PnL; corpus 3.3k rows / 214 live).

TWO independent mechanisms, both bounding toward a floor/cap rather than
to zero (the learner keeps a trickle):

  (a) rolling SHARE CAP - probes may not exceed max_probe_share of the
      last probe_share_window entry ADMISSIONS (probes+conviction),
      tracked on a small deque fed by every entry path that actually
      places an order. Admission-COUNT keyed, never time.
  (b) CORPUS DECAY - effective_rate = base_rate x
      clip(corpus_target_live / max(live_labels, 1), floor_frac, 1.0),
      folded into _exploration_active's own epsilon roll (reuses the
      SAME live-label count _exploration_active/ML-071/ML-073 already
      compute via HistoryStore.source_counts()).

Denials emit Code.SZ_PROBE_THROTTLED (SZ-047). Conviction entries (the
`explored=False` path) are NEVER throttled by this lever: the throttle
methods take no p_win/size argument and cannot influence sizing - they
only gate whether the OPTIONAL exploration bump applies.
"""
import json
import types
from pathlib import Path

import pytest

from core.audit import get_audit
from core.codes import Code
from main import LiquidityBot, probe_corpus_decay_factor

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# (b) corpus decay - pure function
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("live_labels,expected", [
    (50, 1.0),
    (300, 1.0),
    (1200, 0.25),
])
def test_decay_math_at_measured_corpus_sizes(live_labels, expected):
    assert probe_corpus_decay_factor(live_labels, corpus_target_live=300,
                                     floor_frac=0.25) == pytest.approx(expected)


def test_decay_floor_holds_well_past_target():
    # an order of magnitude past 1200 must not fall below the floor
    assert probe_corpus_decay_factor(100_000, 300, 0.25) == pytest.approx(0.25)


def test_decay_guards_against_zero_live_labels():
    # max(live_labels, 1) - a cold corpus must not divide by zero, and a
    # tiny corpus clips to the ceiling (1.0), not an inflated multiplier
    assert probe_corpus_decay_factor(0, 300, 0.25) == pytest.approx(1.0)


def test_decay_never_exceeds_one():
    assert probe_corpus_decay_factor(1, 300, 0.25) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# corpus decay folded into _exploration_active's epsilon roll
# ---------------------------------------------------------------------------
def _stub_bot(live, epsilon=1.0, corpus_target_live=300, floor_frac=0.25,
             until=10_000):
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b.explore_enabled = True
    b.explore_epsilon = epsilon
    b.explore_until_rows = until
    b.explore_max_asset_share = 1.0
    b._explore_rng = __import__("random").Random(1)
    b._corpus_target_live = corpus_target_live
    b._corpus_floor_frac = floor_frac
    hist = types.SimpleNamespace(row_count=lambda: live,
                                 source_counts=lambda: {"live": live})
    b.history = hist
    return b


def test_exploration_roll_decays_with_a_mature_corpus():
    # epsilon=1.0 with NO decay would always fire; at live_labels=1200 the
    # effective rate is 0.25 - roughly a quarter of rolls
    b = _stub_bot(live=1200, epsilon=1.0)
    fires = sum(b._exploration_active(0.0) for _ in range(3000))
    assert 600 < fires < 900, fires


def test_exploration_roll_undecayed_below_corpus_target():
    b = _stub_bot(live=50, epsilon=1.0)
    assert all(b._exploration_active(0.0) for _ in range(200))


# ---------------------------------------------------------------------------
# (a) rolling share cap
# ---------------------------------------------------------------------------
def _throttle_bot(window=10, max_share=0.3, admissions=()):
    from collections import deque
    b = LiquidityBot.__new__(LiquidityBot)
    b._probe_share_window = window
    b._probe_max_share = max_share
    b._probe_admissions = deque(admissions, maxlen=window)
    return b


def test_share_cap_binds_exactly_at_the_boundary():
    # window=10, max_share=0.3 -> cap is 3 probes/10. 3 already recorded:
    # a 4th would be 4/10=0.4 > 0.3 -> denied.
    b = _throttle_bot(window=10, max_share=0.3,
                      admissions=[True, True, True] + [False] * 7)
    assert b._probe_share_would_deny() is True


def test_share_cap_allows_up_to_and_including_the_boundary():
    # only 2 probes recorded: a 3rd is 3/10=0.3 <= 0.3 -> allowed
    b = _throttle_bot(window=10, max_share=0.3,
                      admissions=[True, True] + [False] * 8)
    assert b._probe_share_would_deny() is False


def test_share_cap_releases_as_the_window_rolls():
    # 3 probes recorded at the cap (4th would deny) - append CONVICTION
    # admissions until the oldest probe rolls off the maxlen window
    b = _throttle_bot(window=10, max_share=0.3,
                      admissions=[True, True, True] + [False] * 7)
    assert b._probe_share_would_deny() is True
    b._record_probe_admission(False)      # pushes the oldest (a probe) out
    assert b._probe_share_would_deny() is False


def test_share_cap_denominator_is_the_fixed_window_not_deque_fill():
    # a freshly-reset (or just-started) window with only 2 admissions ever
    # recorded must be at MOST as restrictive as a full window - the
    # denominator is the configured window size, never len(deque). This is
    # exactly why a restart-reset can only ever ADMIT more probes, never
    # deny more (see LiquidityBot.__init__ restart-state note).
    b = _throttle_bot(window=10, max_share=0.3, admissions=[True, True])
    assert b._probe_share_would_deny() is False    # (2+1)/10 == 0.3, allowed


def test_record_probe_admission_appends_bool():
    b = _throttle_bot(window=3, max_share=1.0, admissions=[])
    b._record_probe_admission(True)
    b._record_probe_admission(False)
    assert list(b._probe_admissions) == [True, False]


# ---------------------------------------------------------------------------
# combined decision point + registered-code denial
# ---------------------------------------------------------------------------
def _decision_bot(explore_active, window=10, max_share=0.3, admissions=()):
    from collections import deque
    b = LiquidityBot.__new__(LiquidityBot)
    b._probe_share_window = window
    b._probe_max_share = max_share
    b._probe_admissions = deque(admissions, maxlen=window)
    b._exploration_active = lambda now, asset=None: explore_active
    return b


def test_decision_admits_probe_when_cap_has_headroom():
    b = _decision_bot(True, admissions=[])
    assert b._probe_admission_decision(0.0, "ETH") is True


def test_decision_denies_probe_when_cap_saturated():
    b = _decision_bot(True, admissions=[True, True, True] + [False] * 7)
    assert b._probe_admission_decision(0.0, "ETH") is False


def test_decision_short_circuits_when_exploration_itself_is_inactive():
    # _exploration_active already said no (dry_run/enabled/epsilon/graduation)
    # - the share cap must not even be consulted, and no denial is logged
    b = _decision_bot(False, admissions=[True, True, True] + [False] * 7)
    path = get_audit().path
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    assert b._probe_admission_decision(0.0, "ETH") is False
    after = path.read_text(encoding="utf-8") if path.exists() else ""
    assert after == before, "no throttle disposition when explore never fired"


def test_denial_emits_the_registered_code():
    b = _decision_bot(True, admissions=[True, True, True] + [False] * 7)
    path = get_audit().path
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    assert b._probe_admission_decision(0.0, "ETH") is False
    after = path.read_text(encoding="utf-8") if path.exists() else ""
    new_lines = after[len(before):].strip().splitlines()
    records = [json.loads(line) for line in new_lines if line.strip()]
    assert any(r["code"] == Code.SZ_PROBE_THROTTLED.value for r in records)


# ---------------------------------------------------------------------------
# conviction entries are NEVER throttled - structural pin
# ---------------------------------------------------------------------------
def test_decision_method_takes_no_sizing_argument():
    """The throttle decision cannot mutate p_win/explore_scale by
    construction - its signature carries only (now, asset). A conviction
    entry's own p_win is decided entirely outside this call; this method
    can only gate whether the OPTIONAL exploration bump is applied."""
    import inspect
    sig = inspect.signature(LiquidityBot._probe_admission_decision)
    params = list(sig.parameters)
    assert params == ["self", "now", "asset"]


def test_engine_wires_the_throttle_at_the_explore_decision_point():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    # the ONLY call site that can set explored=True is gated on the
    # combined decision (exploration-active AND not throttled) - the raw
    # _exploration_active() call no longer appears at the entry-loop site
    assert "if can_enter and self._probe_admission_decision(now, asset):" \
        in src
    # every entry path that actually places an order feeds the rolling
    # window (both conviction and probe admissions) - one call per path
    assert src.count("self._record_probe_admission(explored)") == 3


def test_conviction_never_reaches_the_share_cap_or_decay():
    # a conviction (non-explored) admission just appends False - it is
    # RECORDED for others' cap math but never itself gated by the cap/decay
    b = _throttle_bot(window=3, max_share=0.01, admissions=[True])
    # cap is saturated for probes (1/3 > 1%) - a conviction admission is
    # unaffected because it never calls _probe_share_would_deny at all
    b._record_probe_admission(False)
    assert list(b._probe_admissions) == [True, False]


# ---------------------------------------------------------------------------
# config surface
# ---------------------------------------------------------------------------
def test_shipped_config_carries_the_throttle_knobs():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    ex = cfg["ml"]["exploration"]
    assert ex["max_probe_share"] == 0.35
    assert ex["probe_share_window"] == 40
    assert ex["corpus_decay"]["corpus_target_live"] == 300
    assert ex["corpus_decay"]["floor_frac"] == 0.25


def test_engine_parses_the_throttle_config():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    b = LiquidityBot.__new__(LiquidityBot)
    _ex = cfg["ml"]["exploration"]
    b._probe_max_share = min(max(float(_ex.get("max_probe_share", 0.35)),
                                 0.0), 1.0)
    b._probe_share_window = max(int(_ex.get("probe_share_window", 40)), 1)
    assert b._probe_max_share == 0.35
    assert b._probe_share_window == 40


# ---------------------------------------------------------------------------
# persistence: restart-reset is an accepted, reasoned decision (see
# LiquidityBot.__init__), but the codebase's own precedent (the
# auto-updater restarts the bot on every deploy - core/persistence.py's
# "RESTART-COUPLING continuity" note) means anything living only in
# memory resets EVERY deploy, not just rare crashes - a 40-admission
# rolling window would then almost never bind in production. Persisted
# exactly like _stop_hit / pos_realized (plain list, best-effort section).
# ---------------------------------------------------------------------------
def _persist_stub_bot(rows_at_last_train=0):
    from core.state import PortfolioState
    b = types.SimpleNamespace()
    b.dry_run = True
    b.state = PortfolioState(starting_capital=800)
    b.orders = types.SimpleNamespace(open_orders=lambda: [], _orders={})
    b.history = types.SimpleNamespace(_pending={})
    b.sizer = types.SimpleNamespace(_last_entry={})
    b._pos_realized = {}
    b._halted = False
    b._stop_hit = {}
    b._rows_at_last_train = rows_at_last_train
    hollow = types.SimpleNamespace(to_dict=lambda: {}, restore=lambda d: None)
    b.monitor = hollow
    b.postmortem = hollow
    b.candidates = hollow
    b.gate_stats = hollow
    b.risk_protocols = None
    return b


def test_probe_admissions_survive_snapshot_roundtrip(tmp_path):
    from collections import deque

    from core.persistence import StateStore
    store = StateStore(str(tmp_path / "state.json"))
    bot = _persist_stub_bot()
    bot._probe_admissions = deque([True, False, True], maxlen=40)
    assert store.snapshot(bot)

    revived = _persist_stub_bot()
    revived._probe_admissions = deque(maxlen=40)
    assert store.restore(revived)
    assert list(revived._probe_admissions) == [True, False, True]


def test_probe_admissions_malformed_does_not_crash_restore(tmp_path):
    from collections import deque

    from core.persistence import SNAPSHOT_VERSION, StateStore
    store = StateStore(str(tmp_path / "state.json"))
    snap = {"version": SNAPSHOT_VERSION, "dry_run": True,
           "portfolio": {"starting_capital": 800.0, "cash_balance": 800.0,
                        "savings_balance": 0.0, "realized_pnl_total": 0.0,
                        "daily_realized_pnl": 0.0},
           "probe_admissions": "corrupt-string"}
    assert store.write_raw(snap)

    revived = _persist_stub_bot()
    revived._probe_admissions = deque(maxlen=40)
    assert store.restore(revived) is True
    assert list(revived._probe_admissions) == []    # skipped, not crashed


def test_old_snapshot_without_probe_admissions_key_stays_empty(tmp_path):
    from collections import deque

    from core.persistence import StateStore
    store = StateStore(str(tmp_path / "state.json"))
    bot = _persist_stub_bot()
    assert store.snapshot(bot)          # no _probe_admissions attr at all
    data = store.load_raw()
    assert data is not None
    assert data.get("probe_admissions") == []

    revived = _persist_stub_bot()
    revived._probe_admissions = deque(maxlen=40)
    assert store.restore(revived)
    assert list(revived._probe_admissions) == []
