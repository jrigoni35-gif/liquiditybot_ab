"""tests/test_skimmer.py — asset skimmer: scan wide, trade narrow.

Contracts under test:
  * scoring is pure, bounded [0,1], and hard-zero below the depth floor;
  * evaluate() costs <= 2 feed calls and touches AT MOST one candidate;
  * promotion/demotion hysteresis (promote_score / demote_evals /
    replace_margin) — no churn;
  * promotions persist atomically and the BOOT reader validates hard
    (malformed file, non-USD pairs, core overlap, cap) — never raises;
  * the skimmer itself never touches the live universe (restart-applied).
"""
import json

import pytest

from core.skimmer import (AssetSkimmer, avg_bar_range_pct, book_metrics,
                          score_candidate)

_TH = {"spread_bps_max": 25.0, "min_depth_usd": 5000.0,
       "activity_range_pct": 0.30}


# ---------------------------------------------------------------- scoring
def test_score_bounds_and_depth_floor():
    # generous book: tight spread, deep, active -> near 1
    hi = score_candidate(1.0, 40_000.0, 0.5, **_TH)
    assert 0.9 <= hi <= 1.0
    # below the depth floor: hard zero regardless of spread/activity
    assert score_candidate(0.5, 4_999.0, 2.0, **_TH) == 0.0
    # wide spread kills the spread component
    wide = score_candidate(30.0, 40_000.0, 0.5, **_TH)
    assert wide == pytest.approx(hi - 0.40, abs=0.02)
    # garbage never raises, never leaves [0,1]
    assert 0.0 <= score_candidate(float("nan"), None, "x", **_TH) <= 1.0


def test_book_metrics():
    book = {"bids": [[100.0, 10.0], [99.5, 5.0]],
            "asks": [[100.2, 8.0], [100.5, 4.0]]}
    spread_bps, depth = book_metrics(book)
    assert spread_bps == pytest.approx(0.2 / 100.1 * 1e4, rel=1e-3)
    assert depth == pytest.approx(100 * 10 + 99.5 * 5 + 100.2 * 8 + 100.5 * 4)
    assert book_metrics({}) == (None, 0.0)
    assert book_metrics({"bids": [[0, 1]], "asks": [[1, 1]]}) == (None, 0.0)
    # crossed book (bid >= ask) is unusable, not a negative spread
    assert book_metrics({"bids": [[101, 1]], "asks": [[100, 1]]}) == (None, 0.0)


def test_avg_bar_range():
    candles = [{"high": 101.0, "low": 100.0, "close": 100.5}] * 10
    assert avg_bar_range_pct(candles) == pytest.approx(1.0 / 100.5 * 100,
                                                       rel=1e-3)
    assert avg_bar_range_pct([]) == 0.0
    assert avg_bar_range_pct([{"high": "x"}, None]) == 0.0


# ---------------------------------------------------------------- fixture
class _Feed:
    """Scripted feed: pair -> (book, candles); counts calls."""
    def __init__(self, worlds):
        self.worlds, self.calls = worlds, 0

    def kraken_pair(self, symbol):
        return symbol.replace("/", "")

    def get_order_book(self, pair, depth=10):
        self.calls += 1
        return self.worlds.get(pair, ({}, []))[0]

    def get_candles(self, pair, interval=5):
        self.calls += 1
        return self.worlds.get(pair, ({}, []))[1]


def _good_world():
    book = {"bids": [[100.0, 300.0]], "asks": [[100.02, 300.0]]}
    candles = [{"high": 100.6, "low": 100.0, "close": 100.3}] * 48
    return (book, candles)


def _dead_world():
    book = {"bids": [[100.0, 1.0]], "asks": [[101.0, 1.0]]}   # thin + wide
    return (book, [])


def _skimmer(tmp_path, feed, candidates, **over):
    cfg = {"enabled": True, "candidates": candidates, "max_extra": 2,
           "eval_every_min": 60, "spread_bps_max": 25.0,
           "min_depth_usd": 5000.0, "activity_range_pct": 0.30,
           "promote_score": 0.55, "demote_score": 0.35, "demote_evals": 2,
           "replace_margin": 0.10}
    cfg.update(over)
    return AssetSkimmer(cfg, feed, core_pairs=["ETH/USD", "BTC/USD"],
                        active_path=str(tmp_path / "active.json"))


# ------------------------------------------------------------ budget + rr
def test_evaluate_costs_at_most_two_calls_one_candidate(tmp_path):
    feed = _Feed({"SOLUSD": _good_world(), "ADAUSD": _good_world()})
    sk = _skimmer(tmp_path, feed, ["SOL/USD", "ADA/USD"])
    assert sk.evaluate(now=1000.0) == "promoted"
    assert feed.calls == 2                       # book + candles, ONE candidate
    assert sk.evaluate(now=1001.0) == "promoted"  # round-robin: the other one
    assert feed.calls == 4
    # both evaluated within the hour -> idle, zero calls
    assert sk.evaluate(now=1002.0) == "idle"
    assert feed.calls == 4


def test_core_pairs_never_candidates(tmp_path):
    sk = _skimmer(tmp_path, _Feed({}), ["ETH/USD", "SOL/USD"])
    assert sk.candidates == ["SOL/USD"]


def test_disabled_is_noop(tmp_path):
    feed = _Feed({"SOLUSD": _good_world()})
    sk = _skimmer(tmp_path, feed, ["SOL/USD"], enabled=False)
    assert sk.evaluate(now=1000.0) == "disabled"
    assert feed.calls == 0


# ------------------------------------------------------- hysteresis rules
def test_promote_persist_and_boot_roundtrip(tmp_path):
    feed = _Feed({"SOLUSD": _good_world()})
    sk = _skimmer(tmp_path, feed, ["SOL/USD"])
    sk.evaluate(now=1000.0)
    assert sk.snapshot()["promoted"] == ["SOL/USD"]
    data = json.loads((tmp_path / "active.json").read_text())
    assert data["extra_pairs"] == ["SOL/USD"]
    # boot reader adopts it; a fresh instance restores it
    assert AssetSkimmer.load_active(tmp_path / "active.json",
                                    ["ETH/USD", "BTC/USD"], 6) == ["SOL/USD"]
    sk2 = _skimmer(tmp_path, feed, ["SOL/USD"])
    assert sk2.snapshot()["promoted"] == ["SOL/USD"]


def test_demotion_needs_consecutive_strikes(tmp_path):
    feed = _Feed({"SOLUSD": _good_world()})
    sk = _skimmer(tmp_path, feed, ["SOL/USD"])
    sk.evaluate(now=0.0)                              # promoted
    feed.worlds["SOLUSD"] = _dead_world()
    assert sk.evaluate(now=4000.0) == "strike"        # 1st weak eval: held
    assert sk.snapshot()["promoted"] == ["SOL/USD"]
    assert sk.evaluate(now=8000.0) == "demoted"       # 2nd consecutive: out
    assert sk.snapshot()["promoted"] == []
    # a recovery between strikes resets the count
    sk.evaluate(now=12000.0)                          # re-... still dead: scored
    feed.worlds["SOLUSD"] = _good_world()
    sk.evaluate(now=16000.0)                          # promoted again
    feed.worlds["SOLUSD"] = _dead_world()
    assert sk.evaluate(now=20000.0) == "strike"
    feed.worlds["SOLUSD"] = _good_world()
    assert sk.evaluate(now=24000.0) == "held"         # recovery clears strikes
    feed.worlds["SOLUSD"] = _dead_world()
    assert sk.evaluate(now=28000.0) == "strike"       # count restarted at 1


def test_replacement_requires_margin(tmp_path):
    # cap 1: incumbent holds unless the challenger CLEARLY beats it
    ok = _good_world()
    feed = _Feed({"SOLUSD": ok, "ADAUSD": ok})
    sk = _skimmer(tmp_path, feed, ["SOL/USD", "ADA/USD"], max_extra=1)
    assert sk.evaluate(now=0.0) == "promoted"           # SOL in
    assert sk.evaluate(now=1.0) == "eligible_full"      # ADA equal: no churn
    assert sk.snapshot()["promoted"] == ["SOL/USD"]


def test_boot_reader_validates_hard(tmp_path):
    p = tmp_path / "active.json"
    # malformed json
    p.write_text("{not json", encoding="utf-8")
    assert AssetSkimmer.load_active(p, ["ETH/USD"], 6) == []
    # wrong quote, core overlap, dupes, junk types, over cap
    p.write_text(json.dumps({"extra_pairs": [
        "SOL/USDT", "ETH/USD", "SOL/USD", "SOL/USD", 42, "X" * 30 + "/USD",
        "ADA/USD", "DOT/USD"]}), encoding="utf-8")
    out = AssetSkimmer.load_active(p, ["ETH/USD"], 2)
    assert out == ["SOL/USD", "ADA/USD"]               # validated + capped
    # missing file
    assert AssetSkimmer.load_active(tmp_path / "nope.json", [], 6) == []


def test_feed_error_is_contained(tmp_path):
    class Boom:
        def kraken_pair(self, s):
            raise RuntimeError("down")
    sk = _skimmer(tmp_path, Boom(), ["SOL/USD"])
    assert sk.evaluate(now=1000.0) == "feed_error"     # no raise, no promote
    assert sk.snapshot()["promoted"] == []
