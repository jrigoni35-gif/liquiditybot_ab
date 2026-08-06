"""Replace-hysteresis must survive a restart.

Round-2 finding (2026-08-05). _persist wrote each promoted pair's score into
skimmer_active.json, but _restore read back only `extra_pairs` — so
`self._scores` started EMPTY on every boot while `_promoted` was full. The
replace comparison then read every incumbent's score as its 0.0 default:

    worst = min(promoted, key=lambda p: scores.get(p, {}).get("score", 0.0))
    if score >= scores.get(worst, {}).get("score", 0.0) + replace_margin:

so a marginal 0.55 candidate satisfied `0.55 >= 0.0 + 0.10` and evicted a
0.90 incumbent. Deploys restart the runner on a 15-minute cadence and
evaluation is round-robin, so incumbents were routinely still unscored when
a candidate was judged — precisely the churn replace_margin exists to
prevent.
"""
import json

from core.skimmer import AssetSkimmer


CORE = ["ETH/USD", "BTC/USD"]


def _cfg(**over):
    cfg = {"enabled": True,
           "candidates": ["SOL/USD", "XRP/USD", "ADA/USD"],
           "max_extra": 1,
           "promote_score": 0.55,
           "demote_score": 0.35,
           "replace_margin": 0.10}
    cfg.update(over)
    return cfg


def _active_file(tmp_path, promoted, scores):
    p = tmp_path / "skimmer_active.json"
    p.write_text(json.dumps({"version": 1, "updated": 0,
                             "extra_pairs": promoted,
                             "scores": scores}), encoding="utf-8")
    return p


def test_incumbent_scores_are_restored(tmp_path):
    path = _active_file(tmp_path, ["SOL/USD"], {"SOL/USD": {"score": 0.90}})
    sk = AssetSkimmer(_cfg(), core_pairs=CORE, feed=None,
                      active_path=str(path))
    assert sk._promoted == ["SOL/USD"]
    assert sk._scores.get("SOL/USD", {}).get("score") == 0.90, \
        "a persisted incumbent score must be adopted at boot"


def test_marginal_candidate_cannot_evict_a_strong_incumbent(tmp_path):
    """THE bug: with the pool full, the eviction comparison must see the
    incumbent's real 0.90, so a 0.55 candidate is refused."""
    path = _active_file(tmp_path, ["SOL/USD"], {"SOL/USD": {"score": 0.90}})
    sk = AssetSkimmer(_cfg(), core_pairs=CORE, feed=None,
                      active_path=str(path))
    worst = min(sk._promoted,
                key=lambda p: sk._scores.get(p, {}).get("score", 0.0))
    incumbent = sk._scores.get(worst, {}).get("score", 0.0)
    assert not (0.55 >= incumbent + sk.replace_margin), \
        "a 0.55 candidate must not clear a restored 0.90 incumbent"


def test_a_genuinely_better_candidate_still_replaces(tmp_path):
    """The hysteresis must not become a lockout: a clearly better
    candidate still wins."""
    path = _active_file(tmp_path, ["SOL/USD"], {"SOL/USD": {"score": 0.60}})
    sk = AssetSkimmer(_cfg(), core_pairs=CORE, feed=None,
                      active_path=str(path))
    incumbent = sk._scores.get("SOL/USD", {}).get("score", 0.0)
    assert 0.85 >= incumbent + sk.replace_margin


def test_malformed_scores_fall_back_without_raising(tmp_path):
    for bad in ({"SOL/USD": {"score": "abc"}}, {"SOL/USD": "nope"},
                {"SOL/USD": {"score": float("nan")}},
                {"SOL/USD": {"score": 7.0}}, "not-a-dict"):
        path = _active_file(tmp_path, ["SOL/USD"], bad)
        sk = AssetSkimmer(_cfg(), core_pairs=CORE, feed=None,
                          active_path=str(path))
        assert sk._promoted == ["SOL/USD"]          # promotion still adopted
        assert "SOL/USD" not in sk._scores          # score refused, no crash


def test_scores_for_non_incumbents_are_ignored(tmp_path):
    """Only pairs actually promoted carry a restored score; a stale entry
    for a demoted pair must not resurrect."""
    path = _active_file(tmp_path, ["SOL/USD"],
                        {"SOL/USD": {"score": 0.80},
                         "XRP/USD": {"score": 0.95}})
    sk = AssetSkimmer(_cfg(), core_pairs=CORE, feed=None,
                      active_path=str(path))
    assert "XRP/USD" not in sk._scores


def test_missing_file_is_a_clean_cold_start(tmp_path):
    sk = AssetSkimmer(_cfg(), core_pairs=CORE, feed=None,
                      active_path=str(tmp_path / "absent.json"))
    assert sk._promoted == [] and sk._scores == {}
