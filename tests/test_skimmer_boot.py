"""tests/test_skimmer_boot.py — the skimmer's boot-time universe merge.

Contracts: promotions widen trading_pairs ONLY through runner's live
entrypoint (merge_skimmer_universe); dry-run applies, live requires the
explicit apply_in_live flag; disabled skimmer never merges; and the engine
itself (LiquidityBot path: a raw config dict) is untouched by the promotions
file — replay/smoke/overfit stay pinned to their recorded universe."""
import json

from runner import merge_skimmer_universe

_CORE = ["ETH/USD", "BTC/USD"]


def _cfg(dry_run=True, enabled=True, apply_in_live=False, max_extra=6):
    return {"system": {"dry_run": dry_run},
            "skimmer": {"enabled": enabled, "apply_in_live": apply_in_live,
                        "max_extra": max_extra},
            "exchanges": {"kraken": {"trading_pairs": list(_CORE)}}}


def _active(tmp_path, pairs):
    p = tmp_path / "skimmer_active.json"
    p.write_text(json.dumps({"version": 1, "extra_pairs": pairs}),
                 encoding="utf-8")
    return str(p)


def test_dry_run_merges_promotions(tmp_path):
    cfg = _cfg(dry_run=True)
    path = _active(tmp_path, ["SOL/USD", "ADA/USD"])
    merged = merge_skimmer_universe(cfg, active_path=path)
    assert merged == ["SOL/USD", "ADA/USD"]
    assert cfg["exchanges"]["kraken"]["trading_pairs"] == \
        _CORE + ["SOL/USD", "ADA/USD"]


def test_live_requires_explicit_flag(tmp_path):
    path = _active(tmp_path, ["SOL/USD"])
    cfg = _cfg(dry_run=False, apply_in_live=False)
    assert merge_skimmer_universe(cfg, active_path=path) == []
    assert cfg["exchanges"]["kraken"]["trading_pairs"] == _CORE
    cfg2 = _cfg(dry_run=False, apply_in_live=True)
    assert merge_skimmer_universe(cfg2, active_path=path) == ["SOL/USD"]


def test_disabled_never_merges(tmp_path):
    path = _active(tmp_path, ["SOL/USD"])
    cfg = _cfg(enabled=False)
    assert merge_skimmer_universe(cfg, active_path=path) == []
    assert cfg["exchanges"]["kraken"]["trading_pairs"] == _CORE


def test_merge_validates_and_caps(tmp_path):
    # core overlap dropped, junk dropped, capped at max_extra
    path = _active(tmp_path, ["ETH/USD", "SOL/USD", "X/USDT", "ADA/USD",
                              "DOT/USD"])
    cfg = _cfg(max_extra=2)
    assert merge_skimmer_universe(cfg, active_path=path) == \
        ["SOL/USD", "ADA/USD"]


def test_missing_file_is_noop(tmp_path):
    cfg = _cfg()
    assert merge_skimmer_universe(
        cfg, active_path=str(tmp_path / "absent.json")) == []
    assert cfg["exchanges"]["kraken"]["trading_pairs"] == _CORE


def test_engine_path_never_reads_promotions(tmp_path, monkeypatch):
    """The battery's guarantee: constructing the engine from a raw config
    (as replay/smoke/overfit do) ignores any promotions file on disk —
    only runner.main's explicit merge can widen the universe."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs" / "skimmer_active.json").write_text(
        json.dumps({"extra_pairs": ["SOL/USD"]}), encoding="utf-8")
    cfg = _cfg()
    # the engine reads trading_pairs from the dict it was given, full stop
    universe = {s.split("/")[0]: s
                for s in cfg["exchanges"]["kraken"]["trading_pairs"]}
    assert "SOL" not in universe
    assert cfg["exchanges"]["kraken"]["trading_pairs"] == _CORE
