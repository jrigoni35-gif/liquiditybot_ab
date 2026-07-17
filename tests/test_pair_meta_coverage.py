"""tests/test_pair_meta_coverage.py — every pair the bot can trade (core
trading_pairs AND every skimmer candidate) has an offline pair-meta fallback
row with real Kraken values. Two failure modes this kills:

  * OFFLINE boot (AssetPairs unreachable): the generic default of 2 price
    decimals silently grids sub-dollar prices (documented bug class: 'the
    generic default would reject MINA');
  * ALTNAME mismatch EVEN ONLINE: AssetPairs keys its response by altname
    (BTCUSD -> XBTUSD, DOGEUSD -> XDGUSD), so those pairs resolve from the
    fallback table on every boot — it is the designed mechanism, not a
    fallback of last resort.
"""
import json
from pathlib import Path

from data.kraken_feed import PAIR_META_FALLBACK

_CFG = json.loads((Path(__file__).resolve().parents[1] / "config.json")
                  .read_text(encoding="utf-8"))


def _all_tradable_pairs():
    core = _CFG["exchanges"]["kraken"].get("trading_pairs", [])
    cands = (_CFG.get("skimmer") or {}).get("candidates", [])
    return [p.replace("/", "") for p in list(core) + list(cands)]


def test_every_tradable_pair_has_fallback_meta():
    missing = [p for p in _all_tradable_pairs()
               if p not in PAIR_META_FALLBACK]
    assert not missing, \
        f"pairs would run on the generic 2-decimal default: {missing} — " \
        f"add AssetPairs-verified rows to PAIR_META_FALLBACK"


def test_fallback_rows_are_sane():
    for pair, m in PAIR_META_FALLBACK.items():
        assert 0 <= m["price_decimals"] <= 10, pair
        assert 0 <= m["lot_decimals"] <= 10, pair
        assert m["ordermin"] >= 0, pair


def test_doge_altname_rows_agree():
    # Kraken serves DOGE under altname XDGUSD; both spellings must resolve
    # to the SAME values or the online/offline paths would price differently
    assert PAIR_META_FALLBACK["DOGEUSD"] == PAIR_META_FALLBACK["XDGUSD"]
    # 7 price decimals is the load-bearing fact: 2 would grid $0.10 prices
    assert PAIR_META_FALLBACK["DOGEUSD"]["price_decimals"] == 7


def test_btc_altname_rows_agree():
    assert PAIR_META_FALLBACK["BTCUSD"] == PAIR_META_FALLBACK["XBTUSD"]


def test_get_pair_meta_offline_uses_table(monkeypatch):
    from data.kraken_feed import KrakenFeed
    f = KrakenFeed({"trading_pairs": []})
    monkeypatch.setattr(f, "_public_get", lambda *a, **k: None)  # offline
    meta = f.get_pair_meta(["DOGEUSD", "ADAUSD", "ETHUSD"])
    assert meta["DOGEUSD"]["price_decimals"] == 7
    assert meta["ADAUSD"]["price_decimals"] == 6
    assert meta["ETHUSD"]["ordermin"] == 0.002
