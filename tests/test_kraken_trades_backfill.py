"""scripts/kraken_trades_backfill.py — the tape walker's exit conditions,
its int-only cursor, and its idempotent store. No network: a FakeFeed
serves a synthetic tape through the same _public_get(endpoint, params)
surface the real KrakenFeed exposes."""
from __future__ import annotations

import json

import pytest

# scripts/kraken_trades_backfill.py imports pandas at MODULE scope, so an
# unguarded import here breaks collection of the whole suite - not just this
# file - wherever pandas is absent (see tests/test_feed_freeze_gate.py).
pytest.importorskip("pandas")

import scripts.kraken_trades_backfill as kb  # noqa: E402

PAGE = kb.PAGE
NS = 1_000_000_000


def make_tape(n: int, t0: float = 1_783_900_800.0, dt_s: float = 0.7) -> list[list]:
    """n trades, ids 1..n, monotone times; sides/otypes alternate."""
    return [[f"{100 + i * 0.01:.5f}", "0.10000000", t0 + i * dt_s,
             "b" if i % 2 else "s", "l" if i % 3 else "m", "", i + 1]
            for i in range(n)]


class FakeFeed:
    """Serves the venue's paging contract: trades with time >= since
    (nanoseconds), up to `count`, `last` = ns time of the final row."""

    def __init__(self, tape, *, truncate_cursor=False, fail_first=0):
        self.tape = tape
        self.calls: list[dict] = []
        self.truncate_cursor = truncate_cursor
        self.fail_first = fail_first
        self.api_key = self.api_secret = ""

    def _public_get(self, endpoint, params=None):
        assert endpoint == "Trades"
        self.calls.append(dict(params))
        if self.fail_first > 0:
            self.fail_first -= 1
            return None
        since = int(params["since"])
        rows = [r for r in self.tape if int(r[2] * NS) >= since][: int(params["count"])]
        if not rows:
            return {"XXBTZUSD": [], "last": str(since)}
        last = int(rows[-1][2] * NS) + 1     # strictly past the last row
        if self.truncate_cursor:
            last = int(float(since))        # the float-bug shape: never advances
        return {"XXBTZUSD": rows, "last": str(last)}


def test_parse_page_keeps_int_cursor_and_side_flags():
    tape = make_tape(3)
    rows, last_ns = kb.parse_page({"XXBTZUSD": tape, "last": "1783900802400000123"}, "XBTUSD")
    assert last_ns == 1783900802400000123 and isinstance(last_ns, int)
    assert [r["trade_id"] for r in rows] == [1, 2, 3]
    assert rows[0]["side"] == "s" and rows[1]["side"] == "b"
    assert rows[0]["otype"] == "m" and rows[1]["otype"] == "l"


def test_walk_to_end_of_tape_and_resume_is_idempotent(tmp_path):
    tape = make_tape(2 * PAGE + 137)
    store = kb.TickStore(tmp_path)
    feed = FakeFeed(tape)
    res = kb.backfill_pair(feed, store, "XBTUSD", 0, sleep=lambda s: None)
    assert res["stop"] == "end_of_tape"
    assert res["fetched"] == len(tape) and res["added"] == len(tape)
    assert res["calls"] == 3
    # the cursor written is the venue's int, verbatim
    cur = json.loads(store.cursor_path("XBTUSD").read_text())
    assert isinstance(cur["last_ns"], int) and cur["last_ns"] == int(feed.calls[-1]["since"]) or cur["last_ns"] > 0
    assert cur["last_id"] == len(tape)
    # second run: resumes from cursor, adds nothing, store unchanged
    feed2 = FakeFeed(tape)
    res2 = kb.backfill_pair(feed2, store, "XBTUSD", 0, sleep=lambda s: None)
    assert int(feed2.calls[0]["since"]) == cur["last_ns"]
    assert res2["added"] == 0
    df = store.load("XBTUSD")
    assert len(df) == len(tape) and df["trade_id"].is_unique
    assert list(df["trade_id"].iloc[:3]) == [1, 2, 3]


def test_new_trades_after_resume_are_appended_once(tmp_path):
    tape = make_tape(PAGE + 10)
    store = kb.TickStore(tmp_path)
    kb.backfill_pair(FakeFeed(tape[:PAGE]), store, "XBTUSD", 0, sleep=lambda s: None)
    res = kb.backfill_pair(FakeFeed(tape), store, "XBTUSD", 0, sleep=lambda s: None)
    assert res["added"] == 10
    assert len(store.load("XBTUSD")) == PAGE + 10


def test_stall_guard_stops_when_cursor_does_not_advance(tmp_path):
    tape = make_tape(3 * PAGE)
    store = kb.TickStore(tmp_path)
    feed = FakeFeed(tape, truncate_cursor=True)
    res = kb.backfill_pair(feed, store, "XBTUSD", 0, max_calls=50, sleep=lambda s: None)
    assert res["stop"] == "stalled"
    assert res["calls"] == 1            # not 50: the loop did not spin
    assert len(store.load("XBTUSD")) == PAGE


def test_call_budget_and_until_are_exit_conditions(tmp_path):
    tape = make_tape(5 * PAGE)
    store = kb.TickStore(tmp_path)
    res = kb.backfill_pair(FakeFeed(tape), store, "XBTUSD", 0, max_calls=2, sleep=lambda s: None)
    assert res["stop"] == "budget" and res["calls"] == 2 and res["fetched"] == 2 * PAGE
    until = int(tape[3 * PAGE][2] * NS)
    res = kb.backfill_pair(FakeFeed(tape), store, "ETHUSD", 0, until_ns=until, sleep=lambda s: None)
    assert res["stop"] == "until" and res["calls"] <= 4


def test_transient_failures_back_off_then_give_up(tmp_path):
    tape = make_tape(10)
    store = kb.TickStore(tmp_path)
    slept: list[float] = []
    res = kb.backfill_pair(FakeFeed(tape, fail_first=2), store, "XBTUSD", 0, sleep=slept.append)
    assert res["stop"] == "end_of_tape" and res["added"] == 10
    assert slept == [2.0, 4.0]
    res = kb.backfill_pair(FakeFeed(tape, fail_first=99), store, "ETHUSD", 0, sleep=slept.append)
    assert res["stop"] == "failures" and res["calls"] == kb._MAX_FAILURES


def test_month_partition_and_window_load(tmp_path):
    # straddle 2026-07 / 2026-08 (2026-08-01T00:00:00Z = 1785542400)
    t0 = 1785542400.0 - 5 * 0.7
    tape = make_tape(10, t0=t0)
    store = kb.TickStore(tmp_path)
    kb.backfill_pair(FakeFeed(tape), store, "XBTUSD", 0, sleep=lambda s: None)
    files = sorted(p.name for p in store.pair_dir("XBTUSD").glob("*.parquet"))
    assert files == ["2026-07.parquet", "2026-08.parquet"]
    assert len(store.load("XBTUSD", start_s=1785542400.0)) == 5
    cov = store.coverage("XBTUSD")
    assert cov["rows"] == 10 and cov["id_min"] == 1 and cov["id_max"] == 10


def test_to_ns_and_pair_mapping():
    assert kb.to_ns("2026-07-13") == 1783900800 * NS
    assert kb.to_ns(1783900800) == 1783900800 * NS
    assert kb.to_ns("1783900800.5") == 1783900800 * NS + 500_000_000
    assert kb.kraken_pair("BTC") == "XBTUSD" and kb.kraken_pair("doge") == "XDGUSD"
    assert kb.kraken_pair("ADA") == "ADAUSD"


def test_build_feed_is_credential_free(monkeypatch):
    monkeypatch.setenv("KRAKEN_API_KEY", "planted-key")
    monkeypatch.setenv("KRAKEN_API_SECRET", "cGxhbnRlZA==")
    from scripts.candle_backfill import build_feed
    feed = build_feed("kraken", {"exchanges": {"kraken": {"rate_limit_per_sec": 3}}})
    assert feed.api_key == "" and feed.api_secret == ""
    assert not feed.has_private_credentials()


@pytest.mark.parametrize("bad", [{"last": "abc"}, {}])
def test_parse_page_tolerates_malformed(bad):
    rows, last = kb.parse_page(bad, "XBTUSD")
    assert rows == [] and last is None
