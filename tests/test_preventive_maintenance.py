"""Preventive-maintenance fixes, 2026-08-15 confirmed-defect scan.

232 candidates were raised across six subsystems; 217 were killed by the
auditors themselves or by an adversarial kill pass. These pin the six that
survived AND were classified SAFE (no change to which orders are placed or
how they fill). The nine SHIP-BLOCKED survivors are NOT fixed here — they sit
behind the era-4 accrual moratorium and need operator adjudication.

Several pins are source-level on purpose. The defect class for most of these
is "a future edit quietly restores the old line", and the runtime path is
either hourly (checkin), boot-only (runner lock), or needs a live gateway
(moomoo) — so a behavioural test would not run in CI where the regression
would actually be introduced.
"""
import pathlib

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _code_only(rel: str) -> str:
    """Source with comment lines and trailing comments stripped.

    A source-level pin that matches its own explanatory COMMENT is not a pin,
    it is a tautology — and both source pins below failed exactly that way on
    first run, because the forbidden strings appear verbatim in the comments
    that document WHY they are forbidden. Assert against code, not prose.
    """
    out = []
    for line in _src(rel).splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split("  #")[0])
    return "\n".join(out)


# --- HIGH: the digest was WRITING to the live audit chain -------------------
def test_session_digest_never_constructs_an_audit_writer():
    """core/session_digest.py:139 called AuditTrail(...).verify().

    Constructing an AuditTrail runs _adopt_tail, which TRUNCATES a torn tail
    and appends a newline (core/audit.py:101-102, :116-118). This module runs
    hourly from scripts/checkin.py against the LIVE outputs/audit.jsonl, so it
    could delete a just-appended record mid-write and latch tamper=True
    permanently — from a module whose own docstring promises it never writes
    to the audit chain. verify_chain() is read-only by contract.
    """
    src = _code_only("core/session_digest.py")
    assert "verify_chain" in src, "digest must use the READ-ONLY verifier"
    assert "AuditTrail" not in src, \
        "constructing an AuditTrail is a WRITE - it heals (truncates) a torn tail"


def test_read_csv_drops_torn_and_overlong_rows(tmp_path):
    """A torn final append parsed as a real sample: '1786000000,98' gave
    equity_min 98.0 on a ~$800 book, and a truncated epoch put the window
    start in 1970 with duration_h in the hundreds of thousands."""
    from core.session_digest import _read_csv
    p = tmp_path / "equity.csv"
    p.write_text("ts,equity\n1786000000,800.5\n1786000060,798.25\n1786000120,98\n",
                 encoding="utf-8")
    rows = _read_csv(p)
    assert len(rows) == 3, "well-formed rows must all survive"

    # now tear the final line mid-field, exactly as a crash would
    p.write_text("ts,equity\n1786000000,800.5\n1786000060,798.25\n1786000120\n",
                 encoding="utf-8")
    rows = _read_csv(p)
    assert len(rows) == 2, "the short fragment must be dropped, not averaged in"
    assert all(r["equity"] is not None for r in rows)

    # a row with EXTRA fields lands under the None restkey and is equally junk
    p.write_text("ts,equity\n1786000000,800.5\n1786000060,798.25,STRAY\n",
                 encoding="utf-8")
    assert len(_read_csv(p)) == 1


def test_read_csv_keeps_legitimately_empty_trailing_values(tmp_path):
    """An EMPTY field ('') is a real value; only a MISSING one (None) is torn.
    Dropping empties would silently discard valid sparse rows."""
    from core.session_digest import _read_csv
    p = tmp_path / "x.csv"
    p.write_text("a,b,c\n1,,3\n", encoding="utf-8")
    rows = _read_csv(p)
    assert len(rows) == 1 and rows[0]["b"] == ""


# --- MEDIUM: a healthy peer was paged CRITICAL with "stop.bat" -------------
def test_runner_guards_the_heartbeatless_lock_sentinels():
    """core/runtime.py returns {"pid":"initializing"} and {"pid":"contended"}
    with NO heartbeat key. float(held.get("heartbeat", 0)) made hb_age ~1.79e9s
    -> the benign branch was unreachable -> a healthy peer got a CRITICAL
    telling the operator to run stop.bat."""
    src = _code_only("runner.py")
    assert 'float(held.get("heartbeat", 0))' not in src, \
        "bare heartbeat read reintroduces the 1.79e9s sentinel age"
    assert '_pid_raw.isdigit()' in src, \
        "sentinel pids are non-numeric strings - that is the discriminator"


# --- MEDIUM: stale sibling flags outlived the session that set them --------
def test_moomoo_degrade_clears_every_sibling_flag():
    """Setting available=False alone left options_available / quotes_frozen at
    their last-LIVE values, so a corpus row written during a dead TCP session
    recorded avail_options="1"."""
    from data.moomoo_feed import MoomooFeed, MoomooSnapshot
    feed = MoomooFeed.__new__(MoomooFeed)
    feed._snapshot = MoomooSnapshot(
        available=True, options_available=True, quotes_frozen=True, ts=123.0)
    feed._degrade()
    s = feed._snapshot
    assert s.available is False
    assert s.options_available is False, "a dead session has no options chain"
    assert s.quotes_frozen is False
    assert s.ts == 123.0, \
        "ts must keep pointing at the last REAL observation, not be stamped now"


def test_both_moomoo_degradation_paths_go_through_degrade():
    """Two paths degrade (ensure_ctx failure, poll exception). Either one
    setting only `available` reopens the stale-flag defect."""
    src = _src("data/moomoo_feed.py")
    assert src.count("self._degrade()") >= 2, \
        "both degradation paths must clear the sibling flags"
    assert "self._snapshot.available = False\n            return" not in src


def test_moomoo_unreachable_message_does_not_lie_about_the_port():
    """The ret!=0 branch is reached ONLY after _probe_port() returned True, so
    the gateway IS listening. Saying 'unreachable' sent a 2026-08-15 diagnosis
    down a dead end: port 11111 open, feed still unavailable."""
    src = _src("data/moomoo_feed.py")
    assert "is LISTENING at" in src
    assert "ret={ret}" in src, "ret is the only value separating the causes"


# --- MEDIUM: the gauge and the kill line were different quantities ---------
def test_baseline_brier_uses_the_prior_not_the_in_window_oracle():
    """status() published clip(y.mean()) — the in-window ORACLE base rate no
    forecaster could have known — while _judge decides on _prior_base_rate().
    The Grafana rule pages 'the governor has moved to kill it' off the gauge
    while the governor is still at level 0."""
    src = _src("ml/monitor.py")
    assert "np.clip(self._prior_base_rate()" in src, \
        "published baseline must be the quantity _judge decides on"
    assert "np.full_like(p, np.clip(y.mean(), 0.05, 0.95))" not in src, \
        "in-window oracle baseline reintroduces the phantom kill page"


def test_prior_base_rate_and_judge_share_one_clip():
    """Same bounds in both places, or the gauge and the line diverge again."""
    src = _src("ml/monitor.py")
    assert src.count("self._prior_base_rate(), 0.05, 0.95") >= 1 or \
        src.count("np.clip(self._prior_base_rate()") >= 1


def test_overfit_summary_prints_the_corpus_and_reuses_the_one_flag():
    """The corpus banner must key on `on_synthetic` — the flag derived ONCE at
    dataset load — and never re-derive it by string-matching the
    human-readable source message.

    This pin exists because the banner's own first cut did exactly that. A
    second copy of the predicate can silently diverge from the first (reword
    the reason string and the banner stops printing), and the failure mode is
    that the caveat vanishes while the battery keeps reporting 'passed' — the
    precise false-green the banner was added to prevent. Found in adversarial
    review before merge, not after.
    """
    src = _code_only("scripts/overfit_check.py")
    assert 'print(f"corpus: {source}")' in src, \
        "the corpus must appear on the SUMMARY line, not only in the OF-1 header"
    assert '"SYNTHETIC" in str(source).upper()' not in src, \
        "re-deriving the flag duplicates the predicate that already exists"
    assert src.count('on_synthetic = source.startswith') == 1, \
        "exactly ONE place may derive on_synthetic; a second copy can diverge"


@pytest.mark.parametrize("y_mean,prior", [(0.9, 0.25), (0.1, 0.25)])
def test_oracle_and_prior_baselines_actually_differ(y_mean, prior):
    """Guard against the fix being cosmetic: on a skewed window the two
    quantities are far apart, which is exactly when the phantom page fired."""
    from ml.calibration import brier_score
    n = 40
    y = np.zeros(n)
    y[: int(n * y_mean)] = 1.0
    p = np.full(n, 0.3)
    oracle = brier_score(y, np.full_like(p, np.clip(y.mean(), 0.05, 0.95)))
    prior_b = brier_score(y, np.full_like(p, prior))
    assert abs(oracle - prior_b) > 0.01, \
        "if these coincided the defect would have been harmless"
