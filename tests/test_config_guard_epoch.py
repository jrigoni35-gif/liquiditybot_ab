"""config_guard: ml.epoch block (T3.6a candidate_cutoff_ts marker, T3.6
production loader-seam flag exclude_old_candidates).

candidate_cutoff_ts must be a real number in the corpus's plausible
timestamp range [1752000000, 1900000000] whenever the ml.epoch block is
present at all (shared by both consumers: the report-only --epoch-ab
experiment arm and the T3.6 production loader seam). exclude_old_
candidates additionally must be a boolean, and - the T3.6 FATAL - true
while candidate_cutoff_ts is missing/invalid is refused: the production
filter must never activate without a real cutoff.
"""
from core.config_guard import validate


def _cfg(exclude_old_candidates=False, candidate_cutoff_ts=1784830855):
    epoch: dict = {}
    if exclude_old_candidates is not None:
        epoch["exclude_old_candidates"] = exclude_old_candidates
    if candidate_cutoff_ts is not None:
        epoch["candidate_cutoff_ts"] = candidate_cutoff_ts
    return {"system": {"dry_run": True}, "ml": {"epoch": epoch}}


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def test_shipped_default_no_fatal():
    assert not any("epoch" in m for m in _fatals(_cfg()))


def test_default_absent_epoch_block_no_fatal():
    assert not any("epoch" in m
                  for m in _fatals({"system": {"dry_run": True}}))


def test_exclude_old_candidates_true_with_valid_cutoff_no_fatal():
    assert not any("epoch" in m for m in _fatals(
        _cfg(exclude_old_candidates=True, candidate_cutoff_ts=1784830855)))


def test_exclude_old_candidates_true_missing_cutoff_is_fatal():
    fatals = _fatals(_cfg(exclude_old_candidates=True,
                          candidate_cutoff_ts=None))
    assert any("candidate_cutoff_ts" in m for m in fatals)


def test_exclude_old_candidates_true_invalid_cutoff_is_fatal():
    fatals = _fatals(_cfg(exclude_old_candidates=True,
                          candidate_cutoff_ts="not-a-number"))
    assert any("candidate_cutoff_ts" in m for m in fatals)


def test_exclude_old_candidates_non_bool_is_fatal():
    fatals = _fatals(_cfg(exclude_old_candidates="true"))
    assert any("exclude_old_candidates" in m for m in fatals)


def test_cutoff_out_of_range_is_fatal_regardless_of_flag():
    fatals = _fatals(_cfg(exclude_old_candidates=False,
                          candidate_cutoff_ts=1))
    assert any("candidate_cutoff_ts" in m for m in fatals)
