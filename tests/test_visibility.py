"""
Regressions for the invisible-failure sweep: fail-safe degradation is
correct ONLY when it is visible. Two gaps found and closed:

1. webdata `available` was a sticky latch (`got_any or previous`): one
   ancient success kept the flag true forever while both fetches failed
   every poll and values froze at last-good. Now freshness-based.
2. SMC compute degraded 7 features to in-contract NEUTRAL on any
   exception with only a DEBUG log - a dead SMC block was structurally
   invisible. Now counted (surfaced in status) and WARNING-logged.
"""
from data.webdata_feed import WebDataFeed
from strategies.smc import SMCEngine


def test_webdata_available_is_freshness_not_latch():
    calls = {"n": 0}

    def fetch(url, timeout=10.0):
        calls["n"] += 1
        if calls["n"] <= 2:                     # first poll succeeds
            if "fng" in url:
                return '{"data": [{"value": "41"}]}'
            return ('{"data": {"market_cap_percentage": {"btc": 52.0},'
                    '"total_market_cap": {"usd": 2.1e12}}}')
        raise OSError("feed dead")              # every later poll fails

    feed = WebDataFeed({"enabled": True, "poll_minutes": 10}, fetch=fetch)
    t0 = 1_700_000_000.0
    snap = feed.maybe_poll(t0)
    assert snap.available                       # fresh success

    poll = feed.poll_sec
    snap = feed.maybe_poll(t0 + poll + 1)       # 1st failed poll
    assert snap.available                       # within freshness window
    snap = feed.maybe_poll(t0 + 5 * poll)       # far beyond 3 polls
    assert not snap.available, \
        "a feed dead for 3+ polls must read unavailable, not latch true"


def test_smc_faults_are_counted_and_neutral(monkeypatch):
    eng = SMCEngine({"enabled": True})
    monkeypatch.setattr("strategies.smc.mtf_align",
                        lambda *a, **k: 1 / 0)   # geometry bug stand-in
    bars = [{"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0,
             "volume": 5.0, "time": i * 300} for i in range(60)]
    out = eng.compute("BTC", bars, "long", 0.0)
    assert eng.compute_faults >= 1, "degradation must increment the counter"
    assert out.get("mtf_align") == 0.0          # still fail-safe NEUTRAL
    assert "compute_faults" in eng.status()
