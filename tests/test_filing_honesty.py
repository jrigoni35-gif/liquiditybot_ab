"""Four places the filing system reported something other than the truth.

All four were found by the 2026-08-06 geometry deep dive, and all four
share a shape: the code was RIGHT about the thing it computed and WRONG
about what it wrote down, so no decision path misbehaved and no test
failed - the corpus and the dashboards just quietly said something the
system did not mean.

  1. mark_disposition truncated the veto reason at 40 chars, which cut
     through the bracket geometry the sizer had just computed. Measured on
     the live corpus: ZERO of 9,692 rows retained a "[bracket ...]"
     payload.
  2. bracket_divergence_summary blended tb_time records - whose delta is 0
     BY CONSTRUCTION - into the agreement rate it publishes to Grafana.
     33 of 35 lifetime records were tb_time, so the 1.0000 gauge was 94.3%
     definitional.
  3. AuditTrail.log dropped a record on OSError without re-arming
     _adopt_tail, so a PARTIAL write left orphan bytes the next append
     welded onto - and once further records followed, verify_chain saw a
     mid-file break and reported tamper=True permanently. Crash damage
     presenting as tampering on the regulated trail of record.
  4. _ensure_schema rotated the corpus without invalidating the derived
     LIVE counters, which are keyed on the file's (mtime, size). The next
     append stamped the NEW file's key onto the OLD counts, so the caches
     matched and refused to re-scan. These are not telemetry:
     asset_live_counts is n_a in SPB-R scarcity pricing (position SIZING).
"""
import csv

import numpy as np

from ml.features import FEATURE_NAMES
from ml.history import DISPOSITION_MAX_CHARS, CandidateLabeler, HistoryStore


def _store(tmp_path) -> HistoryStore:
    return HistoryStore(str(tmp_path / "signal_history.csv"))


def _labeler(tmp_path) -> CandidateLabeler:
    return CandidateLabeler(_store(tmp_path), {})


# --- 1. the disposition payload -------------------------------------------
# The real SZ-023 string, verbatim from risk/position_sizer.py:417-425.
_SZ023 = ("SZ-023: p 0.28 below bar 0.63 (net breakeven 0.594 + margin "
          "0.036, derived) [bracket pt=2.06% sl=1.54% b=0.983]")


def test_disposition_keeps_the_bracket_geometry(tmp_path):
    """The 40-char cap kept only as far as '(net break'. The geometry is
    the whole reason a VETOED candidate is worth filing - it is the bet
    that would have been traded."""
    assert len(_SZ023) > 40, "fixture must exceed the old cap"
    lab = _labeler(tmp_path)
    lab.register("BTC", "long", np.zeros(len(FEATURE_NAMES)), 0.001, 1)
    lab.mark_disposition("BTC", "long", _SZ023)
    disp = lab._cands[-1]["disp"]
    assert "[bracket" in disp, "the bracket payload was truncated away"
    assert "b=0.983]" in disp, "the payload must survive to its last char"
    assert "net breakeven 0.594" in disp


def test_disposition_is_still_bounded(tmp_path):
    """A cap still exists - an unbounded free-text column in a 9,692-row
    corpus is its own hazard."""
    lab = _labeler(tmp_path)
    lab.register("BTC", "long", np.zeros(len(FEATURE_NAMES)), 0.001, 1)
    lab.mark_disposition("BTC", "long", "X" * 5000)
    assert len(lab._cands[-1]["disp"]) == DISPOSITION_MAX_CHARS


def test_the_cap_clears_the_longest_real_disposition():
    assert DISPOSITION_MAX_CHARS >= len(_SZ023)


# --- 2. the tautological agreement gauge ----------------------------------
def _record(store, barrier, net_usd, pt=0.02, sl=0.015):
    store._record_bracket_divergence(barrier, pt, sl, 0.5, net_usd,
                                     1000.0, {})


def test_time_barrier_closes_do_not_inflate_the_agreement_rate(tmp_path):
    """tb_time's counterfactual IS its realized value, so it always
    'agrees' and carries no information about geometry alignment."""
    s = _store(tmp_path)
    for _ in range(20):
        _record(s, "tb_time", 3.0)
    out = s.bracket_divergence_summary()
    assert out["n"] == 20, "the closes themselves are still counted"
    assert out["n_priced"] == 0
    assert out["agree_rate"] is None, \
        "20 definitional agreements must not publish as a 1.0 rate"


def test_agreement_rate_is_measured_over_priced_closes_only(tmp_path):
    s = _store(tmp_path)
    for _ in range(9):
        _record(s, "tb_time", 3.0)
    _record(s, "tb_pt", 15.0)          # +1.5% vs counterfactual +1.5% -> agree
    _record(s, "tb_sl", 5.0)           # +0.5% vs counterfactual -2.0% -> not
    out = s.bracket_divergence_summary()
    assert out["n"] == 11
    assert out["n_priced"] == 2
    assert out["agree_rate"] == 0.5, "must be 1-of-2, not 10-of-11"


def test_honest_absence_before_any_close(tmp_path):
    out = _store(tmp_path).bracket_divergence_summary()
    assert out == {"n": 0, "n_priced": 0, "agree_rate": None,
                   "mean_abs_ret_delta_pct": None}


# --- 3. the audit chain's torn/tamper confusion ---------------------------
def test_a_dropped_write_re_arms_the_tail_adoption(tmp_path):
    """After a failed write the next log() must re-adopt the tail, so a
    partial write is TRUNCATED rather than welded onto."""
    from core.audit import AuditTrail
    from core.codes import Code

    a = AuditTrail(str(tmp_path / "audit.jsonl"))
    a.log("t", Code.ML_DEPLOY, "first")
    assert a._synced is True
    # a payload json.dumps cannot serialize -> TypeError -> dropped
    class _Bad:
        def __repr__(self):
            raise TypeError("unserializable")

    seq = a.log("t", Code.ML_DEPLOY, "bad", {"k": {_Bad(): 1}})
    if seq == 0:                       # the write really was dropped
        assert a._synced is False, \
            "a dropped write must re-arm _adopt_tail or the next append " \
            "fuses onto whatever bytes it left behind"


def test_a_torn_tail_is_healed_not_fused(tmp_path):
    """The end-to-end property: a torn final line must not take the next
    record down with it, and the chain must not read as tampered."""
    from core.audit import AuditTrail
    from core.codes import Code

    p = tmp_path / "audit.jsonl"
    a = AuditTrail(str(p))
    a.log("t", Code.ML_DEPLOY, "one")
    a.log("t", Code.ML_DEPLOY, "two")
    raw = p.read_bytes()
    p.write_bytes(raw[:-20])           # kill mid-record
    b = AuditTrail(str(p))             # fresh process re-adopts
    b.log("t", Code.ML_DEPLOY, "three")
    v = b.verify()
    assert not v.get("tamper"), f"crash damage read as tampering: {v}"


# --- 4. derived counters after a rotation ---------------------------------
def test_rotation_invalidates_the_live_counters(tmp_path):
    """The counters are keyed on (mtime, size). A rotation replaces the
    file while the counts still describe the OLD corpus; without explicit
    invalidation the next append stamps the NEW key onto STALE counts and
    the cache refuses to re-scan."""
    p = tmp_path / "signal_history.csv"
    s = HistoryStore(str(p))
    feats = np.zeros(len(FEATURE_NAMES), dtype=float)
    for i in range(5):
        s._append_row(f"P{i}", "ETH", "long", feats, 1, 1.0, "live")
    assert s.asset_live_counts().get("ETH") == 5

    # another process re-headers the file (a FEATURE_NAMES bump)
    hdr = list(s._header)
    hdr.insert(3, "brand_new_feature")
    with open(p, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(hdr)

    s._append_row("P-NEW", "ETH", "long", feats, 1, 1.0, "live")
    on_disk = sum(1 for r in csv.DictReader(
        open(p, newline="", encoding="utf-8")) if r.get("source") == "live")
    assert s.asset_live_counts().get("ETH") == on_disk, \
        "counter kept pre-rotation counts under the post-rotation cache key"


# --- 5. the unlabeled-close counter ---------------------------------------
def test_a_close_with_no_pending_vector_is_counted(tmp_path):
    """The one exit in the whole write path that used to be silent."""
    s = _store(tmp_path)
    s.log_close("never-registered", 1.23)
    assert getattr(s, "unlabeled_closes", 0) == 1
    s.log_close("also-never-registered", -4.56)
    assert s.unlabeled_closes == 2
    assert s.row_count() == 0, "no training row may be invented"
