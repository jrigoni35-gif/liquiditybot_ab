"""Pins for five VERIFIED defects fixed 2026-09-05.

Each was produced by reading, then CONFIRMED by making the running system
demonstrate it, then adversarially re-verified by an independent agent. Each pin
below was mutation-checked: the fix was reverted, the pin was watched go red,
the fix was restored.

  S12  data/kraken_feed.py       — invariant #4's ONLY enforcement point tested
                                   the raw string; 56 of 56 respellings passed.
  S1   core/persistence.py       — a REJECTED snapshot was deleted, not kept,
                                   and the reachable trigger is the armed-live
                                   restart.
  S4   scripts/auto_update.py    — a repo ModuleNotFoundError was classified
                                   "TOOL UNAVAILABLE" and ADMITTED the deploy.
  S7   scripts/auto_update.py    — lock staleness 7800s under a real in-lock
                                   ceiling of 14100s: two updaters.
  S6   ml/history.py             — restore() re-minted every candidate id,
                                   orphaning 42.2% of the corpus join key.
"""
from __future__ import annotations

import json
import time
from pathlib import Path


# ---------------------------------------------------------------- S12
def test_withdrawal_denylist_is_not_a_raw_string_match():
    """THE HARD-INVARIANT PIN. Invariant #4 says withdrawals are impossible.
    Its enforcement was `endpoint in FORBIDDEN_PRIVATE_ENDPOINTS` against the
    caller's raw string, so every one of these reached `requests`."""
    from data.kraken_feed import _endpoint_is_forbidden
    for spelling in ("Withdraw", "withdraw", "WITHDRAW", "WiThDrAw",
                     "Withdraw ", " Withdraw", "Withdraw\n", "\tWithdraw",
                     "walletTransfer", "wallettransfer", "WITHDRAWADDRESSES",
                     "Balance/../Withdraw", "private/Withdraw",
                     "Withdraw?x=1", "Withdraw#f", "Withdraw%20"):
        assert _endpoint_is_forbidden(spelling), (
            f"{spelling!r} was NOT blocked - invariant #4 has exactly one "
            f"mechanical enforcement point and this spelling walks past it")


def test_the_denylist_does_not_block_legitimate_endpoints():
    """ANTI-RUBBER-STAMP: a guard that blocks everything is not a guard, it is
    an outage. Every real private endpoint the repo calls must still pass."""
    from data.kraken_feed import _endpoint_is_forbidden
    for ok in ("AddOrder", "CancelOrder", "Balance", "OpenOrders",
               "ClosedOrders", "QueryOrders", "TradesHistory", "TradeVolume",
               "TradeBalance", "OpenPositions", "QueryTrades", "Ledgers"):
        assert not _endpoint_is_forbidden(ok), f"{ok} was wrongly blocked"


def test_every_denied_verb_is_covered_under_normalization():
    from data.kraken_feed import (FORBIDDEN_PRIVATE_ENDPOINTS,
                                  _endpoint_is_forbidden)
    for verb in FORBIDDEN_PRIVATE_ENDPOINTS:
        assert _endpoint_is_forbidden(verb.lower())
        assert _endpoint_is_forbidden(verb.upper())


def test_the_LIVE_CALL_SITE_blocks_before_any_network_io(monkeypatch):
    """PINS THE GUARD THAT ACTUALLY RUNS, not just the helper beside it.

    Mutation caught this gap (2026-09-05): reverting `_private_post` to the old
    `endpoint in FORBIDDEN_PRIVATE_ENDPOINTS` left every helper test GREEN
    while the live path was wide open again. That is finding #11's exact shape
    - "the batteries pin the dead guard; the guard that actually runs has zero
    tests" - reproduced by me, in the commit that fixes it.

    Asserts the enforcement point returns None and performs NO network I/O."""
    import data.kraken_feed as kf

    feed = kf.KrakenFeed.__new__(kf.KrakenFeed)
    feed.api_key, feed.api_secret = "k", "c2VjcmV0"        # non-empty only

    def _boom(*a, **k):                       # any HTTP attempt is a failure
        raise AssertionError("NETWORK I/O ATTEMPTED for a denied endpoint")
    for attr in ("requests", "_session"):
        if hasattr(kf, attr):
            monkeypatch.setattr(kf, attr, type("X", (), {
                "post": staticmethod(_boom), "get": staticmethod(_boom)})())
    monkeypatch.setattr(feed, "_throttle", lambda *a, **k: None, raising=False)

    for spelling in ("withdraw", "WITHDRAW", "Withdraw ", "Withdraw",
                     "wallettransfer", "Balance/../Withdraw"):
        assert feed._private_post(spelling) is None, (
            f"{spelling!r} was not blocked AT THE CALL SITE - invariant #4's "
            f"only enforcement point let it through")


# ----------------------------------------------------------------- S1
class _Bot:
    def __init__(self, dry_run):
        self.dry_run = dry_run


def _seed(tmp_path, *, dry_run=True, version=None):
    from core.persistence import SNAPSHOT_VERSION
    p = tmp_path / "state.json"
    p.write_text(json.dumps({
        "version": SNAPSHOT_VERSION if version is None else version,
        "dry_run": dry_run, "portfolio": {"starting_capital": 811.11}}),
        encoding="utf-8")
    (tmp_path / "state.json.bak").write_text(p.read_text(encoding="utf-8"),
                                             encoding="utf-8")
    return p


def _rejected(tmp_path):
    return sorted(tmp_path.glob("state.json*.rejected_*"))


def test_a_paper_live_mismatch_QUARANTINES_before_starting_fresh(tmp_path):
    """THE ONE THAT FIRES ON THE ARMED-LIVE RESTART.

    dry_run flips false at step 3 of invariant 1's four-step road to live. The
    snapshot on disk was taken in paper, so restore() refuses it and returns
    False - and the runner's periodic snapshot() then overwrote BOTH
    generations inside ~60s at the shipped snapshot_interval_sec=30. Measured
    before this fix: `811.11 recoverable anywhere on disk: False`."""
    from core.persistence import StateStore
    _seed(tmp_path, dry_run=True)
    store = StateStore(str(tmp_path / "state.json"))
    assert store.restore(_Bot(dry_run=False)) is False, "fixture: must reject"
    kept = _rejected(tmp_path)
    assert kept, ("a rejected snapshot was left to be overwritten by the next "
                  "cadence - on the armed-live boot, which is the one whose "
                  "prior state is least reproducible")
    blob = "".join(p.read_text(encoding="utf-8") for p in kept)
    assert "811.11" in blob, "the quarantine copy does not contain the state"


def test_a_version_mismatch_also_quarantines(tmp_path):
    from core.persistence import StateStore
    _seed(tmp_path, version="v-not-a-real-version")
    store = StateStore(str(tmp_path / "state.json"))
    assert store.restore(_Bot(dry_run=True)) is False
    assert _rejected(tmp_path)


def test_quarantine_COPIES_and_does_not_change_restore_semantics(tmp_path):
    """The original must still be in place: restore() starting fresh is the
    documented behaviour and this fix must not alter it."""
    from core.persistence import StateStore
    p = _seed(tmp_path, dry_run=True)
    StateStore(str(tmp_path / "state.json")).restore(_Bot(dry_run=False))
    assert p.exists(), "quarantine MOVED the snapshot instead of copying it"


def test_a_SUCCESSFUL_restore_quarantines_nothing(tmp_path):
    """ANTI-RUBBER-STAMP: quarantining on the happy path would fill the disk
    with copies of a state that was never rejected."""
    from core.persistence import StateStore
    _seed(tmp_path, dry_run=True)
    store = StateStore(str(tmp_path / "state.json"))
    try:
        store.restore(_Bot(dry_run=True))
    except Exception:                      # noqa: BLE001 - partial fixture
        pass
    assert not _rejected(tmp_path), "quarantined a snapshot it did not reject"


def test_quarantined_state_may_never_leave_the_box():
    """state.json NEVER travels. The quarantine names are unique per timestamp,
    so the exact-name NEVER set cannot see them."""
    from scripts.session_export import travels
    assert not travels("state.json")
    assert not travels(f"state.json.rejected_{int(time.time())}_version")
    assert not travels("state.json.bak.rejected_1788664596_paper_live_mismatch")
    assert travels("fills.csv"), "the export must still carry its real payload"


# ----------------------------------------------------------------- S4
def test_a_repo_module_error_is_NOT_classified_tool_unavailable():
    """THE FAIL-OPEN THAT ADMITTED DEPLOYS. smoke_test traceback.print_exc()s
    any exception from 60 mocked engine cycles, so a needle can appear anywhere
    in the blob. A missing REPO module is the breakage the gate exists for."""
    from scripts.auto_update import _classify_missing_tool
    for repo_mod in ("strategies.smc", "core.runtime", "ml.history",
                     "risk.protocols", "execution.venue_adapters", "main"):
        blob = (f"Traceback (most recent call last):\n"
                f"  File \"main.py\", line 1, in <module>\n"
                f"ModuleNotFoundError: No module named '{repo_mod}'")
        assert _classify_missing_tool(blob) is False, (
            f"a missing REPO module ({repo_mod}) was classified TOOL "
            f"UNAVAILABLE - the hard gate is skipped and the deploy admitted")


def test_a_genuinely_absent_external_tool_still_classifies():
    """ANTI-RUBBER-STAMP: the whole point of the class is that a missing tool
    is not a finding. Narrowing it must not delete it."""
    from scripts.auto_update import _classify_missing_tool
    for ext in ("ruff", "bandit", "pyright"):
        assert _classify_missing_tool(
            f"ModuleNotFoundError: No module named '{ext}'") is True
    assert _classify_missing_tool(
        "'bandit' is not recognized as an internal or external command") is True


def test_a_needle_buried_MID_BLOB_does_not_classify():
    """Only the FINAL line is evidence about why the gate exited."""
    from scripts.auto_update import _classify_missing_tool
    blob = ("some test printed: ModuleNotFoundError: No module named 'foo'\n"
            "...600 more lines...\n"
            "FAILED tests/test_x.py::test_y - assert 1 == 2")
    assert _classify_missing_tool(blob) is False, (
        "a needle 600 lines from the exit was read as the exit reason")


def test_empty_output_is_not_a_missing_tool():
    from scripts.auto_update import _classify_missing_tool
    assert _classify_missing_tool("") is False
    assert _classify_missing_tool("   \n \n") is False


def test_the_LIVE_GATE_RUNNER_does_not_launder_a_repo_import_error(monkeypatch):
    """PINS THE CALL SITE, for the same reason as the deny-list above: mutation
    showed that reverting `_run_gate`'s classification left every
    `_classify_missing_tool` test green while the deploy-admitting fail-open
    was fully restored."""
    import scripts.auto_update as au

    class _P:
        returncode = 1
        stdout = ("Traceback (most recent call last):\n"
                  "ModuleNotFoundError: No module named 'strategies.smc'")
        stderr = ""

    monkeypatch.setattr(au.subprocess, "run", lambda *a, **k: _P())
    rc, tail, could_not_run = au._run_gate(Path("."), "py", ["x.py"], {}, 60)
    assert rc == 1
    assert could_not_run is False, (
        "a repo ModuleNotFoundError came back as could_not_run=True - "
        "_dod_gates `continue`s on that, skipping a HARD gate and ADMITTING "
        "the deploy")


def test_the_live_gate_runner_still_reports_a_genuinely_absent_tool(monkeypatch):
    """ANTI-RUBBER-STAMP at the call site: a missing tool must still be
    could_not_run, which is NEVER a rejection."""
    import scripts.auto_update as au

    class _P:
        returncode = 1
        stdout = "ModuleNotFoundError: No module named 'bandit'"
        stderr = ""

    monkeypatch.setattr(au.subprocess, "run", lambda *a, **k: _P())
    _, _, could_not_run = au._run_gate(Path("."), "py", ["x.py"], {}, 60)
    assert could_not_run is True


# ----------------------------------------------------------------- S7
def test_lock_staleness_outlives_the_REAL_in_lock_ceiling():
    """THE TWO-UPDATER PIN. The shipped derivation counted the pytest wall and
    the replay gate and omitted all seven DoD gates: real ceiling
    4800 + 1200 + 5*900 + 2*1800 = 14100 against a 7800s window. Measured
    boundary before the fix: 7799s -> BUSY, 7800s -> TWO UPDATERS, and the
    reclaim path then destroyed 8 of 8 worktree files while a battery was live.

    Pins the RELATIONSHIP, never either number."""
    import scripts.auto_update as au
    assert au.LOCK_STALE_SEC > au._in_lock_ceiling_sec(), (
        f"LOCK_STALE_SEC={au.LOCK_STALE_SEC} does not outlive the in-lock "
        f"ceiling {au._in_lock_ceiling_sec()}s - a healthy updater's lock "
        f"reads as abandoned and a second one starts concurrently")


def test_the_ceiling_counts_every_gate_that_runs_inside_the_lock():
    """The previous ceiling was wrong because it was hand-written. This asserts
    it is DERIVED: add a gate, the ceiling must grow."""
    import scripts.auto_update as au
    expected = (au.BATTERY_TIMEOUT_MAX + au._REPLAY_GATE_WALL_SEC
                + len(au._HARD_GATES) * au._HARD_GATE_WALL_SEC
                + len(au._ADVISORY_GATES) * au._ADVISORY_GATE_WALL_SEC)
    assert au._in_lock_ceiling_sec() == expected
    assert au._in_lock_ceiling_sec() >= 14100, (
        "the ceiling fell below the 2026-09-05 measured value; if a gate was "
        "removed that is fine - re-derive and update this floor consciously")


# ----------------------------------------------------------------- S6
def _labeler(tmp_path):
    """A real CandidateLabeler exercising the ACTUAL restore().

    The first draft of these pins asserted a regex against a dict it had
    populated itself, and the second SKIPPED because the constructor takes
    arguments. Both would have passed with the fix reverted. A skipped pin is
    not a pin."""
    from ml.history import CandidateLabeler, HistoryStore
    store = HistoryStore(path=str(tmp_path / "signal_history.csv"))
    return CandidateLabeler(store, {})


def _snap(ids):
    """A snapshot restore() will actually accept: current feature-schema
    version and full-width feature vectors, or it drops every candidate on the
    floor before the re-mint loop is ever reached."""
    from ml.features import FEATURE_NAMES
    from ml.history import FEATURE_SCHEMA_VERSION
    return {"schema_version": FEATURE_SCHEMA_VERSION, "seq": 0, "bars": {},
            "cands": [{"id": i, "asset": "BTC/USD", "direction": "long",
                       "features": [0.0] * len(FEATURE_NAMES)} for i in ids]}


def test_a_salted_candidate_id_SURVIVES_restore(tmp_path):
    """THE CORPUS JOIN-KEY PIN, exercised through the real restore().

    restore() re-minted every id unconditionally, while core/persistence.py
    restores the POSITION's candidate_id unchanged - so the two halves
    disagreed after any restart. Measured on the real training path
    (_scan_live_dedup_keys): 79 of 187 cited ids orphaned (42.2%), and a
    restored id drifted AGAIN on every subsequent restart."""
    lab = _labeler(tmp_path)
    lab.restore(_snap(["cand-15f66e8b-1", "cand-deadbeef-42"]))
    got = [c.get("id") for c in lab._cands]
    assert len(got) == 2, f"fixture rejected by restore(): {got}"
    assert "cand-15f66e8b-1" in got and "cand-deadbeef-42" in got, (
        f"salted ids were re-minted across restore() -> {got}. The corpus "
        f"join key is severed: the position keeps the OLD candidate_id while "
        f"the labeler writes the new one as position_id.")


def test_restoring_TWICE_still_preserves_the_id(tmp_path):
    """The measured defect drifted again on every restart, so one round trip
    is not enough to pin it."""
    lab = _labeler(tmp_path)
    lab.restore(_snap(["cand-15f66e8b-1"]))
    assert lab._cands, "fixture rejected by restore()"
    lab.restore(_snap([lab._cands[0]["id"]]))
    assert lab._cands[0]["id"] == "cand-15f66e8b-1"


def test_a_BARE_preSALT_id_IS_reminted_by_restore(tmp_path):
    """ANTI-RUBBER-STAMP through the real path: keeping EVERY id would
    reintroduce the 2026-07-14 collision (seq reset -> reused bare id)."""
    lab = _labeler(tmp_path)
    lab.restore(_snap(["cand-7"]))
    assert lab._cands, "fixture rejected by restore()"
    assert lab._cands[0]["id"] != "cand-7", (
        "a bare pre-salt id survived restore() - it can collide with an "
        "existing position_id in signal_history.csv after a rollback")


def test_bare_preSALT_ids_are_STILL_reminted():
    """ANTI-RUBBER-STAMP, and the reason the fix is narrow. A bare
    `cand-{seq}` id CAN be reused after a filesystem rollback resets the
    counter (lived 2026-07-14). Those must still be re-minted - keeping every
    id would reintroduce that collision."""
    from ml.history import _SALTED_CAND_ID
    for bare in ("cand-1", "cand-42", "cand-0",
                 "cand-XYZ-1", "cand-15f66e8-1", "cand-15f66e8bb-1",
                 "", "position-15f66e8b-1", "cand-15f66e8b-1-extra"):
        assert not _SALTED_CAND_ID.match(bare), (
            f"{bare!r} matched the salted shape - it would be kept across "
            f"restore() and can collide in signal_history.csv")


def test_the_salted_shape_matches_what_register_actually_mints():
    """The regex must track the minting format or the fix silently reverts to
    re-minting everything."""
    import os
    from ml.history import _SALTED_CAND_ID
    salt = os.urandom(4).hex()
    for seq in (1, 7, 1234, 999999):
        assert _SALTED_CAND_ID.match(f"cand-{salt}-{seq}")
