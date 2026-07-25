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
             until=10_000, regime_floor_live=0, regime_live_counts=None,
             regime_scan_calls=None):
    b = LiquidityBot.__new__(LiquidityBot)
    b.dry_run = True
    b.explore_enabled = True
    b.explore_epsilon = epsilon
    b.explore_until_rows = until
    b.explore_max_asset_share = 1.0
    b._explore_rng = __import__("random").Random(1)
    b._corpus_target_live = corpus_target_live
    b._corpus_floor_frac = floor_frac
    # Task 4 (#103) regime-coverage hold knobs; default 0 (disabled) keeps
    # every PRE-T4 test in this module byte-identical (regime_label is
    # never passed by them either, so the branch is doubly inert).
    b._regime_floor_live = regime_floor_live
    _counts = dict(regime_live_counts or {})
    _calls = regime_scan_calls if regime_scan_calls is not None else []

    def _regime_live_count(label):
        _calls.append(label)
        return _counts.get(label, 0)

    hist = types.SimpleNamespace(row_count=lambda: live,
                                 source_counts=lambda: {"live": live},
                                 regime_live_count=_regime_live_count)
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
# P3 review fix: until_live_rows=1200 (was 500) so the trickle floor is
# actually reachable - the decay must trickle 1.0->0.25 over live 300->1200
# instead of cliffing at 500 (where effective decay was only 300/500=0.6,
# nowhere near the promised floor_frac=0.25).
# ---------------------------------------------------------------------------
def test_trickle_reachable_at_800_live_rows_still_active():
    # 800 sits strictly between the OLD cliff (500, pre-fix hard-off) and
    # the NEW one (1200) - pre-fix this asset would already be graduated
    # (exploration permanently off); post-fix it is still active, decaying
    # at base_epsilon x (300/800) = base x 0.375.
    b = _stub_bot(live=800, epsilon=1.0, until=1200)
    assert b.explore_until_rows == 1200
    assert 800 < b.explore_until_rows          # still active, not hard-off
    fires = sum(b._exploration_active(0.0) for _ in range(4000))
    expected = 4000 * 0.375
    assert abs(fires - expected) < 0.15 * expected, fires


def test_hard_off_at_1250_live_rows_past_the_new_cutoff():
    # 1250 > until_live_rows=1200: graduated, exploration off regardless of
    # epsilon/decay - the hard-off check short-circuits before any roll.
    b = _stub_bot(live=1250, epsilon=1.0, until=1200)
    assert all(not b._exploration_active(0.0) for _ in range(50))


# ---------------------------------------------------------------------------
# Task 4 (#103): regime-coverage hold on the corpus decay
#
# 234 live-labeled rows measured, 227 in ONE regime (range), bear at 4:
# the GLOBAL decay above pools every regime into one live-label count, so
# a mature corpus (live=1200) says nothing about an under-covered regime.
# While the CURRENT regime's own live count is below regime_floor_live,
# the decay term is held at 1.0 (no decay, base epsilon) for that
# regime's signals; at/above the floor the shipped decay applies
# unchanged. max_probe_share (the rolling share cap) is untouched.
# ---------------------------------------------------------------------------
def test_regime_hold_at_1_0_when_current_regime_under_floor_even_at_1200_live():
    # live=1200 -> the GLOBAL decay alone would be 0.25 (see
    # test_exploration_roll_decays_with_a_mature_corpus); "bear" has only
    # 4 live rows, well under the floor (60) - the hold overrides the
    # global decay back to 1.0, so the roll fires on (effectively) every
    # attempt, same as an undecayed epsilon=1.0.
    b = _stub_bot(live=1200, epsilon=1.0, regime_floor_live=60,
                 regime_live_counts={"bear": 4})
    fires = sum(b._exploration_active(0.0, regime_label="bear")
               for _ in range(500))
    assert fires == 500, fires


def test_shipped_decay_resumes_once_the_regime_crosses_the_floor():
    # same live=1200 GLOBAL corpus, but "range" is now AT the floor (60) -
    # the hold no longer applies, and the shipped GLOBAL decay (0.25 at
    # live=1200) takes back over exactly as if regime_label were absent.
    b = _stub_bot(live=1200, epsilon=1.0, regime_floor_live=60,
                 regime_live_counts={"range": 60})
    fires = sum(b._exploration_active(0.0, regime_label="range")
               for _ in range(3000))
    assert 600 < fires < 900, fires


def test_regime_floor_live_zero_reproduces_p3_byte_identically():
    # regime_floor_live=0 disables the term entirely - a seeded roll
    # sequence WITH a regime_label supplied must consume the RNG
    # identically to (and so match) the plain P3 call with none.
    baseline = _stub_bot(live=1200, epsilon=1.0)
    held_off = _stub_bot(live=1200, epsilon=1.0, regime_floor_live=0,
                         regime_live_counts={"bear": 0})
    seq_baseline = [baseline._exploration_active(0.0) for _ in range(500)]
    seq_held_off = [held_off._exploration_active(0.0, "ETH",
                                                 regime_label="bear")
                   for _ in range(500)]
    assert seq_baseline == seq_held_off


def test_unknown_regime_label_fails_safe_holds_decay():
    # a label outside the five known REGIME_LABELS (upstream bug, or a
    # future label not yet wired here) has NO per-regime evidence
    # recorded for it either - fail SAFE: hold at 1.0, the SAME treatment
    # as under-floor, never treated as "this regime has graduated".
    b = _stub_bot(live=1200, epsilon=1.0, regime_floor_live=60,
                 regime_live_counts={})
    fires = sum(b._exploration_active(0.0, regime_label="not_a_real_regime")
               for _ in range(500))
    assert fires == 500, fires


def test_unknown_regime_label_never_queries_the_live_history_counter():
    # an unmapped label short-circuits to the hold WITHOUT ever asking
    # HistoryStore for a count that couldn't mean anything for it.
    calls: list = []
    b = _stub_bot(live=1200, epsilon=1.0, regime_floor_live=60,
                 regime_live_counts={}, regime_scan_calls=calls)
    b._exploration_active(0.0, regime_label="not_a_real_regime")
    assert calls == []


def test_regime_label_none_skips_the_branch_entirely_backward_compat():
    # every pre-T4 caller (asset given, regime_label omitted) behaves
    # exactly as before - the branch is never even consulted.
    calls: list = []
    b = _stub_bot(live=1200, epsilon=1.0, regime_floor_live=60,
                 regime_live_counts={"range": 5}, regime_scan_calls=calls)
    b._exploration_active(0.0, "ETH")
    assert calls == []


def test_regime_counter_queried_at_most_once_per_admission_roll():
    # O(1)-at-admission contract at the call-site boundary: regime_
    # live_count is called exactly once per _exploration_active roll that
    # reaches the regime check, never re-queried within the same call.
    # HistoryStore's own internal scan-avoidance is covered separately in
    # tests/test_history_regime_counts.py.
    calls: list = []
    b = _stub_bot(live=1200, epsilon=1.0, regime_floor_live=60,
                 regime_live_counts={"range": 5}, regime_scan_calls=calls)
    for _ in range(25):
        b._exploration_active(0.0, regime_label="range")
    assert calls == ["range"] * 25


def test_decision_admits_regime_held_probe_when_cap_has_headroom():
    # end-to-end wiring: _probe_admission_decision's regime_label param
    # reaches _exploration_active's regime hold for real (not stubbed).
    from collections import deque
    b = _stub_bot(live=1200, epsilon=1.0, regime_floor_live=60,
                 regime_live_counts={"bear": 0})
    b._probe_share_window = 10
    b._probe_max_share = 0.3
    b._probe_admissions = deque([], maxlen=10)
    assert b._probe_admission_decision(0.0, "ETH", regime_label="bear") \
        is True


def test_share_cap_still_binds_when_regime_hold_keeps_exploration_active():
    # regime under floor keeps _exploration_active firing on effectively
    # every roll (decay held at 1.0), but the INDEPENDENT rolling share
    # cap still denies once saturated - max_probe_share is explicitly NOT
    # touched by the regime-coverage hold (still bounds total probe flow
    # regardless of regime).
    from collections import deque
    b = _stub_bot(live=1200, epsilon=1.0, regime_floor_live=60,
                 regime_live_counts={"bear": 0})
    b._probe_share_window = 10
    b._probe_max_share = 0.3
    b._probe_admissions = deque([True, True, True] + [False] * 7, maxlen=10)
    assert b._probe_admission_decision(0.0, "ETH", regime_label="bear") \
        is False


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
    b._exploration_active = \
        lambda now, asset=None, regime_label=None: explore_active
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


def test_denial_bumps_code_stats():
    # SZ-047's siblings (SZ_CIRCUIT_BREAKER/SZ_MANIP_SUSPECT/SZ_DD_THROTTLE)
    # all reach core.code_stats via tag() - the denial branch must too, not
    # just get_audit().log() directly (which never touches the tally).
    from core import code_stats
    code_stats.reset()
    b = _decision_bot(True, admissions=[True, True, True] + [False] * 7)
    assert b._probe_admission_decision(0.0, "ETH") is False
    assert code_stats.snapshot().get(Code.SZ_PROBE_THROTTLED.value, 0) == 1


# ---------------------------------------------------------------------------
# conviction entries are NEVER throttled - structural pin
# ---------------------------------------------------------------------------
def test_decision_method_takes_no_sizing_argument():
    """The throttle decision cannot mutate p_win/explore_scale by
    construction - its signature carries only (now, asset[, regime_label]).
    A conviction entry's own p_win is decided entirely outside this call;
    this method can only gate whether the OPTIONAL exploration bump is
    applied. regime_label (Task 4, #103) is a REGIME TAG, not a sizing
    value - it cannot mutate p_win/explore_scale, it only selects which
    regime's live-label evidence the corpus-decay hold reads; the
    "no sizing argument" invariant this pin exists to protect is
    unaffected by its addition."""
    import inspect
    sig = inspect.signature(LiquidityBot._probe_admission_decision)
    params = list(sig.parameters)
    assert params == ["self", "now", "asset", "regime_label"]


def test_engine_wires_the_throttle_at_the_explore_decision_point():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    # the ONLY call site that can set explored=True is gated on the
    # combined decision (exploration-active AND not throttled) - the raw
    # _exploration_active() call no longer appears at the entry-loop site
    assert "if can_enter and self._probe_admission_decision(" in src
    # the current macro regime is threaded into the throttle (Task 4, #103)
    assert "regime_label=macro_state.label" in src
    # every entry path that actually places an order feeds the rolling
    # window (both conviction and probe admissions) - one call per path.
    # The direct and ladder paths record inline on their own successful
    # submit; the algo path (T5 admission-asymmetry fix) instead records
    # inside _submit_algo_child, gated on the parent's FIRST successful
    # child submit ("_admission_recorded" flag) rather than at parent
    # creation before any child could be rejected.
    assert src.count("self._record_probe_admission(explored)") == 2
    assert "_admission_recorded" in src


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
    # Task 4 (#103): corpus_target_live (300) / 5 regime classes = 60
    assert ex["corpus_decay"]["regime_floor_live"] == 60


def test_engine_parses_the_throttle_config():
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    b = LiquidityBot.__new__(LiquidityBot)
    _ex = cfg["ml"]["exploration"]
    b._probe_max_share = min(max(float(_ex.get("max_probe_share", 0.35)),
                                 0.0), 1.0)
    b._probe_share_window = max(int(_ex.get("probe_share_window", 40)), 1)
    _cd = _ex.get("corpus_decay", {})
    b._regime_floor_live = int(_cd.get("regime_floor_live", 60))
    assert b._probe_max_share == 0.35
    assert b._probe_share_window == 40
    assert b._regime_floor_live == 60


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


# ---------------------------------------------------------------------------
# F0b drought floor (SZ-048) - grill C2 livelock repair. The share cap
# above can FREEZE: once the window is saturated with probes and no
# conviction entry ever lands (no proven edge -> the sizer vetoes every
# non-probe), nothing new is appended, the oldest probe never rolls off,
# and the cap denies forever - a livelock that starves the label stream.
# The floor admits ONE rate-bounded probe despite the cap, but ONLY when
# the ML-073 drought clock proves >= drought_hours with zero admissions
# of ANY kind. Outside a drought the floor is unreachable and behavior
# is byte-identical to P3.
# ---------------------------------------------------------------------------
def _floor_bot(*, window_probes=14, drought_sec=9 * 3600.0):
    """Bot in the EXACT livelock state: a frozen window (14/40 probes ->
    the next probe would be 15/40 = 0.375 > 0.35, so the cap denies) and
    a stale ML-073 drought clock. Built on _throttle_bot, this file's
    minimal-bot factory."""
    b = _throttle_bot(window=40, max_share=0.35,
                      admissions=[True] * window_probes
                      + [False] * (40 - window_probes))
    b._drought_floor_enabled = True
    b._drought_min_sec = 8 * 3600.0
    b._floor_spacing_sec = 2 * 3600.0
    b._last_floor_admit_ts = None
    b._last_entry_admit_ts = 1_000_000.0
    b._now_probe = 1_000_000.0 + drought_sec
    return b


def _floor_decision_bot(**kw):
    """_floor_bot + the _decision_bot idiom: _exploration_active stubbed
    True so the share cap is, by position, the binding denial."""
    b = _floor_bot(**kw)
    b._exploration_active = \
        lambda now, asset=None, regime_label=None: True
    return b


def test_floor_fires_only_under_drought_and_binding_cap():
    bot = _floor_bot()
    assert bot._probe_share_would_deny()          # cap IS binding
    assert bot._drought_floor_admit(bot._now_probe) is True


def test_floor_silent_without_drought():
    bot = _floor_bot(drought_sec=3600.0)          # 1h < 8h
    assert bot._drought_floor_admit(bot._now_probe) is False


def test_floor_rate_bounded_by_spacing():
    bot = _floor_bot()
    now = bot._now_probe
    assert bot._drought_floor_admit(now) is True
    bot._last_floor_admit_ts = now                # a floor probe just fired
    assert bot._drought_floor_admit(now + 3600.0) is False   # 1h < 2h spacing
    assert bot._drought_floor_admit(now + 7201.0) is True    # spacing elapsed


def test_floor_disabled_is_byte_identical():
    bot = _floor_bot()
    bot._drought_floor_enabled = False
    assert bot._drought_floor_admit(bot._now_probe) is False


def test_floor_never_fires_with_unseeded_clock():
    # W2-18: _last_entry_admit_ts is None until the first cycle seeds it -
    # an unseeded clock cannot PROVE a drought, so the floor stays silent
    bot = _floor_bot()
    bot._last_entry_admit_ts = None
    assert bot._drought_floor_admit(bot._now_probe) is False


def test_admission_decision_admits_via_floor_with_sz048():
    bot = _floor_decision_bot()
    path = get_audit().path
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    admitted = bot._probe_admission_decision(bot._now_probe, "BTC")
    assert admitted is True
    # the floor admission is RECORDED into the window at decision time
    # (unlike the normal path, which records at the submit sites) - the
    # window stays honest about floor USE and self-bounds repeat fires
    assert bot._probe_admissions[-1] is True
    assert bot._last_floor_admit_ts == bot._now_probe
    after = path.read_text(encoding="utf-8") if path.exists() else ""
    new_lines = after[len(before):].strip().splitlines()
    records = [json.loads(line) for line in new_lines if line.strip()]
    assert any(r["code"] == Code.SZ_PROBE_FLOOR.value for r in records)


def test_admission_decision_denies_sz047_when_no_drought():
    bot = _floor_decision_bot(drought_sec=60.0)
    assert bot._probe_admission_decision(bot._now_probe, "BTC") is False


def test_floor_is_engine_time_only(monkeypatch):
    # replay determinism: wall clock must never enter the decision
    import time as _time
    bot = _floor_bot()
    monkeypatch.setattr(_time, "time",
                        lambda: (_ for _ in ()).throw(AssertionError(
                            "wall clock read in drought-floor path")))
    assert bot._drought_floor_admit(bot._now_probe) is True


def test_floor_state_round_trips(tmp_path):
    from collections import deque

    from core.persistence import StateStore
    store = StateStore(str(tmp_path / "state.json"))
    bot = _persist_stub_bot()
    bot._probe_admissions = deque(maxlen=40)
    bot._last_floor_admit_ts = 1_234_567.0
    assert store.snapshot(bot)

    revived = _persist_stub_bot()
    revived._probe_admissions = deque(maxlen=40)
    revived._last_floor_admit_ts = None
    assert store.restore(revived)
    assert revived._last_floor_admit_ts == 1_234_567.0
