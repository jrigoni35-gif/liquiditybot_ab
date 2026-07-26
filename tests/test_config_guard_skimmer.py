"""config_guard skimmer capacity envelope — incl. the merged-promotion
double-count regression (observed CRITICAL 2026-07-25: 6 core + 6 merged
promotions + max_extra 6 read as 18 > 12). Promoted pairs already consumed
the promotion budget; the guard must subtract the runner's
`skimmer._merged_promoted` marker before comparing against the 12-pair
REST-fallback envelope."""
import json

from core.config_guard import validate
from runner import merge_skimmer_universe


def _fatals(cfg):
    return [m for s, m in validate(cfg) if s == "FATAL"]


def _envelope_fatals(cfg):
    return [m for m in _fatals(cfg) if "REST-fallback" in m]


def _cfg(pairs, max_extra=6, promoted=None):
    cfg = {"system": {"dry_run": True},
           "exchanges": {"kraken": {"trading_pairs": list(pairs)}},
           "skimmer": {"enabled": True, "max_extra": max_extra}}
    if promoted is not None:
        cfg["skimmer"]["_merged_promoted"] = list(promoted)
    return cfg


_P = ["ETH/USD", "BTC/USD", "SOL/USD", "XRP/USD", "ADA/USD", "DOGE/USD",
      "DOT/USD", "AVAX/USD", "LINK/USD", "LTC/USD", "UNI/USD", "ATOM/USD",
      "NEAR/USD", "ALGO/USD"]


def test_base_beyond_envelope_still_fatal():
    assert _envelope_fatals(_cfg(_P[:8], max_extra=6))


def test_base_within_envelope_ok():
    assert not _envelope_fatals(_cfg(_P[:6], max_extra=6))


def test_merged_promotions_do_not_double_count():
    # the exact observed scenario: 6 base + 6 merged promotions, budget 6
    assert not _envelope_fatals(
        _cfg(_P[:12], max_extra=6, promoted=_P[6:12]))


def test_oversized_base_with_promotions_still_fatal():
    # effective base 8 + budget 6 = 14 > 12 even after subtracting merges
    assert _envelope_fatals(
        _cfg(_P[:14], max_extra=6, promoted=_P[8:14]))


def test_merge_then_validate_sequence(tmp_path):
    # end-to-end pin of the boot ordering that produced the CRITICAL
    active = tmp_path / "skimmer_active.json"
    active.write_text(json.dumps(
        {"version": 1, "updated": 0, "extra_pairs": _P[6:12], "scores": {}}),
        encoding="utf-8")
    cfg = _cfg(_P[:6], max_extra=6)
    extra = merge_skimmer_universe(cfg, active_path=str(active))
    assert extra == _P[6:12]
    assert cfg["skimmer"]["_merged_promoted"] == _P[6:12]
    assert cfg["exchanges"]["kraken"]["trading_pairs"] == _P[:12]
    assert not _envelope_fatals(cfg)
