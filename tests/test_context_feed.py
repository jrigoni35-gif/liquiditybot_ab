"""tests/test_context_feed.py — Compounder Phase B context engine:
`ContextFeed` (data/context_engine.py). Mirrors `data/webdata_feed.py`'s
shape (injectable fetch, cadence early-return, per-source availability
with the 3x-grace window) generalized to five independent network
sources feeding two dial groups, plus two local (no-network) components:
the halving clock (always known) and the shipped event calendar (known
iff the file parses).

NO network in these tests — every ContextFeed is constructed with an
injected `fetch` stub; `_default_fetch`/`requests` is never exercised.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.codes import Code
from data.context_engine import ContextFeed, cme_expiry_utc

_LOGGER_NAME = "liquiditybot.data.context_engine"


# ---- fixture builders (synthetic, no network) ------------------------------

def _fred_csv(value: float) -> str:
    return f"DATE,X\n2026-01-01,{value}\n"


def _cot_row(long_: float, short_: float) -> str:
    fields = (['"BITCOIN - CHICAGO MERCANTILE EXCHANGE"'] +
              [str(i) for i in range(1, 14)] +
              [str(long_), str(short_)] + ["x"] * 71)
    return ",".join(fields) + "\n"


def _stablecoins_json(total: float) -> str:
    return json.dumps({"peggedAssets": [{"circulating":
                                          {"peggedUSD": total}}]})


_URLS = {"fred_dff": "https://x.test/dff", "fred_t10y2y": "https://x.test/t10y2y",
        "fred_vix": "https://x.test/vix", "cot_finfut": "https://x.test/cot",
        "stablecoins": "https://x.test/stable"}


def _cfg(**overrides) -> dict:
    base = {
        "enabled": True,
        "poll_hours": 1.0,
        "next_halving_date": "2028-04-17",
        "phase_bucket_days": {"accumulation": 180, "expansion": 540,
                              "euphoria": 900, "contraction": 1460},
        "stress": {"dff_center": 0.0, "dff_scale": 0.5,
                  "t10y2y_center": 0.0, "t10y2y_scale": 0.5,
                  "vix_center": 20.0, "vix_scale": 10.0, "clip": 2.0},
        "flow": {"cot_scale": 5000.0, "stable_scale_pct": 2.0, "clip": 2.0},
        "event_window": {"fomc_pre_h": 24.0, "fomc_post_h": 6.0,
                        "expiry_pre_h": 8.0, "expiry_post_h": 2.0},
        "urls": dict(_URLS),
    }
    base.update(overrides)
    return base


def _ts(iso: str, hour: int = 0, minute: int = 0) -> float:
    y, m, d = (int(x) for x in iso.split("-"))
    return datetime(y, m, d, hour, minute, tzinfo=timezone.utc).timestamp()


# a reference instant confirmed far from every 2026 FOMC date (nearest is
# 2026-07-29, 5 days = 120h away, outside the 24h pre-window) and far from
# the July 2026 CME expiry (2026-07-31, ~7 days away, outside the 8h
# pre-window) — "steady, uneventful" for tests that don't care about the
# event-window mechanics.
_QUIET_NOW = _ts("2026-07-24", hour=12)


def _responses(dff=0.25, t10y2y=-0.3, vix=25.0, cot_long=4015.0,
               cot_short=11506.0, stable_total=1.0e11) -> dict:
    return {
        _URLS["fred_dff"]: _fred_csv(dff),
        _URLS["fred_t10y2y"]: _fred_csv(t10y2y),
        _URLS["fred_vix"]: _fred_csv(vix),
        _URLS["cot_finfut"]: _cot_row(cot_long, cot_short),
        _URLS["stablecoins"]: _stablecoins_json(stable_total),
    }


class _FetchStub:
    """Injected fetch: url -> canned text (or None = simulated dark),
    counts calls, and can be monkey-patched mid-test by mutating
    `.responses`."""

    def __init__(self, responses: dict | None = None):
        self.responses = dict(responses or {})
        self.calls: list[str] = []

    def __call__(self, url: str) -> str | None:
        self.calls.append(url)
        return self.responses.get(url)


def _calendar_file(tmp_path: Path, fomc: list[str] | None = None) -> Path:
    p = tmp_path / "calendar.json"
    p.write_text(json.dumps({"fomc": fomc if fomc is not None
                             else ["2026-01-28"]}), encoding="utf-8")
    return p


def _make_feed(tmp_path: Path, responses: dict | None = None,
              fomc: list[str] | None = None, **cfg_overrides) -> tuple:
    fetch = _FetchStub(_responses() if responses is None else responses)
    feed = ContextFeed(_cfg(**cfg_overrides), fetch=fetch,
                       history_path=str(tmp_path / "context_history.jsonl"),
                       calendar_path=_calendar_file(tmp_path, fomc))
    return feed, fetch


# ---- cadence / early-return ------------------------------------------------

def test_cadence_early_return_no_refetch(tmp_path):
    feed, fetch = _make_feed(tmp_path)
    s1 = feed.maybe_poll(_QUIET_NOW)
    n_calls_after_first = len(fetch.calls)
    assert n_calls_after_first == 5           # one call per network source
    s2 = feed.maybe_poll(_QUIET_NOW + 1800)   # 30min later, poll_hours=1
    assert s2 is s1
    assert len(fetch.calls) == n_calls_after_first     # no new fetches


def test_cadence_repolls_after_interval(tmp_path):
    feed, fetch = _make_feed(tmp_path)
    feed.maybe_poll(_QUIET_NOW)
    n1 = len(fetch.calls)
    feed.maybe_poll(_QUIET_NOW + 3600.0)
    assert len(fetch.calls) == n1 + 5


def test_disabled_feed_never_polls(tmp_path):
    feed, fetch = _make_feed(tmp_path, enabled=False)
    s = feed.maybe_poll(_QUIET_NOW)
    assert fetch.calls == []
    assert s.stress is None
    assert s.stress_known is False


# ---- per-source dark -> component unknown, CX-010 on transition only ------

def test_dark_source_degrades_only_its_component(tmp_path):
    responses = _responses()
    del responses[_URLS["fred_vix"]]          # vix always dark
    feed, fetch = _make_feed(tmp_path, responses=responses)
    poll_sec = 3600.0
    # push well past the 3x grace window so vix reads definitively dark
    state = None
    for i in range(5):
        state = feed.maybe_poll(_QUIET_NOW + i * poll_sec)
    assert state.stress is None
    assert state.stress_known is False
    # unrelated components unaffected by the vix outage
    assert state.flow_known is True
    assert state.cot_z is not None
    assert state.calendar_known is True
    assert state.halving_phase != ""


def test_halving_always_known_even_when_every_network_source_dark(tmp_path):
    feed, fetch = _make_feed(tmp_path, responses={})   # every source dark
    s = feed.maybe_poll(_QUIET_NOW)
    assert s.days_since >= 0
    assert s.days_to_next != 0 or s.days_since != 0
    assert s.halving_phase != ""
    assert feed.status()["sources"]["halving"] is True


def test_calendar_known_true_with_valid_file(tmp_path):
    feed, _ = _make_feed(tmp_path)
    s = feed.maybe_poll(_QUIET_NOW)
    assert s.calendar_known is True


def test_calendar_unknown_missing_file(tmp_path):
    fetch = _FetchStub(_responses())
    feed = ContextFeed(_cfg(), fetch=fetch,
                       history_path=str(tmp_path / "h.jsonl"),
                       calendar_path=tmp_path / "does_not_exist.json")
    s = feed.maybe_poll(_QUIET_NOW)
    assert s.calendar_known is False


def test_calendar_unknown_invalid_file(tmp_path):
    p = tmp_path / "bad_calendar.json"
    p.write_text("{not valid json", encoding="utf-8")
    fetch = _FetchStub(_responses())
    feed = ContextFeed(_cfg(), fetch=fetch,
                       history_path=str(tmp_path / "h.jsonl"),
                       calendar_path=p)
    s = feed.maybe_poll(_QUIET_NOW)
    assert s.calendar_known is False


def test_cx_source_dark_logged_once_on_transition(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
    responses = _responses()
    feed, fetch = _make_feed(tmp_path, responses=responses)
    poll_sec = 3600.0
    feed.maybe_poll(_QUIET_NOW)                       # vix known (ok)
    del fetch.responses[_URLS["fred_vix"]]            # vix goes dark now
    caplog.clear()
    # advance past the 3x grace window (> 3*3600 = 10800s) in one jump so
    # the dark->transition fires exactly once, on this poll
    feed.maybe_poll(_QUIET_NOW + 4 * poll_sec)
    dark_msgs = [r.message for r in caplog.records if Code.CX_SOURCE_DARK.value in r.message]
    assert len(dark_msgs) == 1
    assert "vix" in dark_msgs[0]
    caplog.clear()
    # still dark on the NEXT poll too -> steady state, no repeat log
    feed.maybe_poll(_QUIET_NOW + 5 * poll_sec)
    assert [r for r in caplog.records if Code.CX_SOURCE_DARK.value in r.message] == []


def test_grace_window_keeps_known_within_3x(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
    responses = _responses()
    feed, fetch = _make_feed(tmp_path, responses=responses)
    poll_sec = 3600.0
    feed.maybe_poll(_QUIET_NOW)                        # vix known
    del fetch.responses[_URLS["fred_vix"]]             # vix now fails
    caplog.clear()
    # two misses, still within 3x poll_sec (10800s) grace
    feed.maybe_poll(_QUIET_NOW + 1 * poll_sec)
    feed.maybe_poll(_QUIET_NOW + 2 * poll_sec)
    assert feed.status()["sources"]["vix"] is True
    assert [r for r in caplog.records if Code.CX_SOURCE_DARK.value in r.message] == []


def test_grace_window_expires_past_3x(tmp_path):
    responses = _responses()
    feed, fetch = _make_feed(tmp_path, responses=responses)
    poll_sec = 3600.0
    feed.maybe_poll(_QUIET_NOW)
    del fetch.responses[_URLS["fred_vix"]]
    # 4th poll at t=4*poll_sec: 4*3600 - 0 = 14400 >= 3*3600=10800 -> dark
    feed.maybe_poll(_QUIET_NOW + 4 * poll_sec)
    assert feed.status()["sources"]["vix"] is False


# ---- CX_STATE_CHANGE: phase / event-window transitions, steady silence ----

def test_event_window_flip_logs_state_change(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
    # use a FOMC date AFTER _QUIET_NOW so the second poll's `now` also
    # advances forward (a poll `now` behind the cadence anchor is itself
    # a no-op early-return, not a real second poll)
    feed, fetch = _make_feed(tmp_path, fomc=["2026-07-29"])
    feed.maybe_poll(_QUIET_NOW)                        # far from any event
    fomc_ts = _ts("2026-07-29", hour=18)               # fixed FOMC ref hour
    caplog.clear()
    s = feed.maybe_poll(fomc_ts - 3600.0)              # 1h before decision
    assert s.in_event_window is True
    assert "fomc:2026-07-29" in s.next_event
    change_msgs = [r.message for r in caplog.records if Code.CX_STATE_CHANGE.value in r.message]
    assert len(change_msgs) >= 1


def test_cme_expiry_window(tmp_path):
    feed, fetch = _make_feed(tmp_path)
    expiry_ts = cme_expiry_utc(2026, 7)
    s = feed.maybe_poll(expiry_ts + 3600.0)            # 1h after expiry
    assert s.in_event_window is True
    assert "cme_expiry:2026-07-31" in s.next_event


def test_steady_state_is_silent(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
    feed, fetch = _make_feed(tmp_path)
    feed.maybe_poll(_QUIET_NOW)
    caplog.clear()
    poll_sec = 3600.0
    feed.maybe_poll(_QUIET_NOW + poll_sec)             # identical everything
    assert [r for r in caplog.records
            if r.name == _LOGGER_NAME and "CX-" in r.message] == []


def test_first_poll_logs_cx_poll_ok_once(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
    feed, fetch = _make_feed(tmp_path)
    feed.maybe_poll(_QUIET_NOW)
    ok_msgs = [r.message for r in caplog.records if Code.CX_POLL_OK.value in r.message]
    assert len(ok_msgs) == 1
    caplog.clear()
    feed.maybe_poll(_QUIET_NOW + 3600.0)
    assert [r for r in caplog.records if Code.CX_POLL_OK.value in r.message] == []


# ---- PIT append + warm start -----------------------------------------------

def test_pit_appends_one_line_per_poll(tmp_path):
    hpath = tmp_path / "hist.jsonl"
    fetch = _FetchStub(_responses())
    feed = ContextFeed(_cfg(), fetch=fetch, history_path=str(hpath),
                       calendar_path=_calendar_file(tmp_path))
    for i in range(3):
        feed.maybe_poll(_QUIET_NOW + i * 3600.0)
    lines = hpath.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    for ln in lines:
        row = json.loads(ln)
        assert set(row.keys()) == {"ts", "state", "raw"}
        assert set(row["raw"].keys()) == {"dff", "t10y2y", "vix",
                                          "cot_net", "stable_total"}
        assert isinstance(row["state"], dict)


def test_warm_start_seeds_prev_values_from_last_pit_line(tmp_path):
    hpath = tmp_path / "hist.jsonl"
    seed = {"ts": _QUIET_NOW - 3600.0,
           "state": {}, "raw": {"dff": 0.2, "t10y2y": -0.1, "vix": 18.0,
                                "cot_net": 10000.0, "stable_total": 1.0e11}}
    hpath.write_text(json.dumps(seed) + "\n", encoding="utf-8")
    fetch = _FetchStub(_responses(cot_long=4015.0, cot_short=1000.0,
                                  stable_total=1.05e11))
    feed = ContextFeed(_cfg(), fetch=fetch, history_path=str(hpath),
                       calendar_path=_calendar_file(tmp_path))
    s = feed.maybe_poll(_QUIET_NOW)          # FIRST poll after "restart"
    # without warm-start this would be None (no prev on a genuine first poll)
    assert s.cot_z is not None
    assert s.stable_wk_pct is not None
    assert s.stable_wk_pct == pytest.approx(5.0)


def test_warm_start_corrupt_last_line_no_seed_no_raise(tmp_path):
    hpath = tmp_path / "hist.jsonl"
    hpath.write_text("not valid json at all {\n", encoding="utf-8")
    fetch = _FetchStub(_responses())
    feed = ContextFeed(_cfg(), fetch=fetch, history_path=str(hpath),
                       calendar_path=_calendar_file(tmp_path))   # no raise
    s = feed.maybe_poll(_QUIET_NOW)
    assert s.cot_z is None                   # behaves like a genuine 1st poll
    assert s.stable_wk_pct is None


def test_warm_start_missing_file_no_seed_no_raise(tmp_path):
    fetch = _FetchStub(_responses())
    feed = ContextFeed(_cfg(), fetch=fetch,
                       history_path=str(tmp_path / "does_not_exist.jsonl"),
                       calendar_path=_calendar_file(tmp_path))
    s = feed.maybe_poll(_QUIET_NOW)
    assert s.cot_z is None
    assert s.stable_wk_pct is None


def test_pit_write_failure_swallowed_and_logged(tmp_path, caplog):
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)
    blocker = tmp_path / "blocked"
    blocker.write_text("i am a file, not a directory", encoding="utf-8")
    bad_history = blocker / "history.jsonl"       # parent exists as a FILE
    fetch = _FetchStub(_responses())
    feed = ContextFeed(_cfg(), fetch=fetch, history_path=str(bad_history),
                       calendar_path=_calendar_file(tmp_path))
    s = feed.maybe_poll(_QUIET_NOW)                # must not raise
    assert s is not None
    assert any("context" in r.message.lower() for r in caplog.records)


# ---- status(): shape + JSON-safe -------------------------------------------

def test_status_shape_and_json_safe(tmp_path):
    feed, fetch = _make_feed(tmp_path)
    feed.maybe_poll(_QUIET_NOW)
    status = feed.status()
    dumped = json.dumps(status)          # must not raise
    assert isinstance(dumped, str)
    for key in ("enabled", "halving_phase", "days_since", "days_to_next",
               "stress", "stress_known", "cot_z", "stable_wk_pct",
               "flow_known", "in_event_window", "next_event",
               "calendar_known", "sources", "last_poll_age_sec"):
        assert key in status
    assert isinstance(status["sources"], dict)
    for src in ("dff", "t10y2y", "vix", "cot", "stablecoins", "calendar",
               "halving"):
        assert src in status["sources"]
    assert isinstance(status["last_poll_age_sec"], (int, float))


def test_status_before_any_poll_is_json_safe(tmp_path):
    fetch = _FetchStub(_responses())
    feed = ContextFeed(_cfg(), fetch=fetch,
                       history_path=str(tmp_path / "h.jsonl"),
                       calendar_path=_calendar_file(tmp_path))
    status = feed.status()
    json.dumps(status)
    assert status["last_poll_age_sec"] is None


# ---- exact math sanity (stress/flow dials wired through correctly) --------

def test_stress_computed_when_all_three_sources_known(tmp_path):
    feed, fetch = _make_feed(tmp_path, responses=_responses(
        dff=0.25, t10y2y=-0.3, vix=25.0))
    s = feed.maybe_poll(_QUIET_NOW)
    assert s.stress_known is True
    assert s.stress == pytest.approx((0.5 + 0.6 + 0.5) / 3.0)


def test_flow_none_on_genuine_first_poll_no_history(tmp_path):
    feed, fetch = _make_feed(tmp_path)
    s = feed.maybe_poll(_QUIET_NOW)
    assert s.cot_z is None                   # no prev yet (genuine first poll)
    assert s.flow_known is False


def test_flow_known_on_second_poll_with_fresh_prev(tmp_path):
    feed, fetch = _make_feed(tmp_path)
    feed.maybe_poll(_QUIET_NOW)
    s2 = feed.maybe_poll(_QUIET_NOW + 3600.0)
    assert s2.cot_z is not None
    assert s2.flow_known is True


# ---- config-key translation: pins __init__'s dff_scale/cot_scale ----------
# ---- -> dff_delta_scale/cot_delta_scale rewrite ---------------------------

def test_config_key_translation_reaches_stress_and_flow_dials(tmp_path):
    """`stress_dial`/`flow_dials` read `dff_delta_scale`/`cot_delta_scale`
    (their real parameter names); the shipped config block spells them
    `dff_scale`/`cot_scale`. `ContextFeed.__init__` translates one onto
    the other. Both fallback defaults on the dial side are 0.5 and
    5000.0 respectively - if this test used those same numbers as its
    "override", a DELETED translation would silently fall back to an
    identical value and the test would pass either way. So this test
    overrides both to HALF the dial functions' fallback default and
    checks the resulting stress/cot_z against that overridden anchor,
    not the untranslated fallback. If the translation block in
    `__init__` is ever deleted, both assertions below fail (verified by
    hand: commenting out the two `if "dff_scale"/"cot_scale"` blocks and
    re-running this test flips stress to ~0.5333 and cot_z to 0.5,
    failing both `pytest.approx` checks - see task-B3-report.md)."""
    overridden_stress = {
        # HALF of stress_dial's internal dff_delta_scale fallback (0.5);
        # spelled the way config.json ships it, not the dial's own name.
        "dff_center": 0.0, "dff_scale": 0.25,
        # left at the dial's own defaults - these two are NOT translated
        # (the config spelling already matches the dial's parameter
        # name), so they are not part of what this test is pinning.
        "t10y2y_center": 0.0, "t10y2y_scale": 0.5,
        "vix_center": 20.0, "vix_scale": 10.0,
        "clip": 2.0,
    }
    overridden_flow = {
        # HALF of flow_dials' internal cot_delta_scale fallback (5000.0);
        # spelled the way config.json ships it, not the dial's own name.
        "cot_scale": 2500.0, "clip": 2.0,
    }

    fetch = _FetchStub(_responses(dff=0.25, t10y2y=-0.3, vix=25.0,
                                  cot_long=1000.0, cot_short=1000.0,
                                  stable_total=1.0e11))
    feed = ContextFeed(_cfg(stress=overridden_stress, flow=overridden_flow),
                       fetch=fetch,
                       history_path=str(tmp_path / "context_history.jsonl"),
                       calendar_path=_calendar_file(tmp_path))
    feed.maybe_poll(_QUIET_NOW)   # first poll: net = 1000-1000 = 0, seeds prev

    # second poll: cot net becomes 3500-1000 = 2500 -> delta vs prev(0) = 2500
    fetch.responses[_URLS["cot_finfut"]] = _cot_row(3500.0, 1000.0)
    s2 = feed.maybe_poll(_QUIET_NOW + 3600.0)

    # stress: dff_term uses the OVERRIDDEN dff_delta_scale=0.25 (translated
    # from config's dff_scale), NOT the dial's own fallback of 0.5:
    #   dff_term   = (dff - dff_delta_center) / dff_delta_scale
    #              = (0.25 - 0.0) / 0.25                       = 1.0
    #   curve_term = (-t10y2y - t10y2y_center) / t10y2y_scale
    #              = (-(-0.3) - 0.0) / 0.5                     = 0.6
    #   vix_term   = (vix - vix_center) / vix_scale
    #              = (25.0 - 20.0) / 10.0                      = 0.5
    #   stress     = (dff_term + curve_term + vix_term) / 3.0
    #              = (1.0 + 0.6 + 0.5) / 3.0                   = 0.7
    # If the translation were deleted, dff_delta_scale would fall back to
    # the dial's default 0.5: dff_term = 0.25/0.5 = 0.5, giving
    # stress = (0.5 + 0.6 + 0.5) / 3.0 = 0.53333... instead.
    assert s2.stress == pytest.approx(0.7)

    # cot_z: uses the OVERRIDDEN cot_delta_scale=2500.0 (translated from
    # config's cot_scale), NOT the dial's own fallback of 5000.0:
    #   net_prev = 1000.0 - 1000.0                             = 0.0
    #   net_now  = 3500.0 - 1000.0                              = 2500.0
    #   delta    = net_now - net_prev = 2500.0 - 0.0             = 2500.0
    #   cot_z    = delta / cot_delta_scale = 2500.0 / 2500.0     = 1.0
    # If the translation were deleted, cot_delta_scale would fall back to
    # the dial's default 5000.0: cot_z = 2500.0 / 5000.0 = 0.5 instead.
    assert s2.cot_z == pytest.approx(1.0)


# ---- real PIT round-trip: writer's schema feeds the reader's warm-start ---

def test_real_pit_round_trip_warm_start_from_actual_writer(tmp_path):
    """Feed A performs a REAL poll and its REAL `_append_pit` writer emits
    the PIT line (never a hand-constructed JSON fixture). Feed B is a
    fresh `ContextFeed` on the SAME history path, so its REAL
    `_warm_start` reader is what seeds `_prev_cot_net`/
    `_prev_stable_total` for feed B's own first poll. The assertions
    below are computed as feed-B-vs-feed-A deltas, which can only match
    if the value the writer put under `raw["cot_net"]`/
    `raw["stable_total"]` is the SAME key the reader pulls out of
    `raw.get("cot_net")`/`raw.get("stable_total")` - if either key drifts
    between writer and reader this test fails."""
    hpath = tmp_path / "context_history.jsonl"
    calendar_path = _calendar_file(tmp_path)

    # feed A: one real poll, writes one real PIT line via _append_pit
    cot_long_a, cot_short_a, stable_a = 4015.0, 11506.0, 1.0e11
    fetch_a = _FetchStub(_responses(cot_long=cot_long_a, cot_short=cot_short_a,
                                    stable_total=stable_a))
    feed_a = ContextFeed(_cfg(), fetch=fetch_a, history_path=str(hpath),
                        calendar_path=calendar_path)
    feed_a.maybe_poll(_QUIET_NOW)

    lines = hpath.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1              # the real writer actually ran

    # feed B: a FRESH ContextFeed on the SAME path -> its real _warm_start
    # reads feed A's real PIT line (never a value we construct by hand)
    cot_long_b, cot_short_b, stable_b = 5000.0, 9000.0, 1.03e11
    fetch_b = _FetchStub(_responses(cot_long=cot_long_b, cot_short=cot_short_b,
                                    stable_total=stable_b))
    feed_b = ContextFeed(_cfg(), fetch=fetch_b, history_path=str(hpath),
                        calendar_path=calendar_path)
    s_b = feed_b.maybe_poll(_QUIET_NOW + 3600.0)   # feed B's FIRST poll

    # cot_z: feed B's delta against feed A's net, through the default
    # (untranslated-override) cot_delta_scale=5000.0, clip=2.0:
    #   net_a = 4015.0 - 11506.0                              = -7491.0
    #   net_b = 5000.0 - 9000.0                                = -4000.0
    #   delta = net_b - net_a = -4000.0 - (-7491.0)             = 3491.0
    #   cot_z = delta / 5000.0 = 3491.0 / 5000.0                = 0.6982
    net_a = cot_long_a - cot_short_a
    net_b = cot_long_b - cot_short_b
    expected_cot_z = (net_b - net_a) / 5000.0
    assert s_b.cot_z == pytest.approx(expected_cot_z)

    # stable_wk_pct: feed B's delta against feed A's stable total:
    #   stable_a = 1.0e11, stable_b = 1.03e11
    #   pct = 100 * (stable_b - stable_a) / stable_a
    #       = 100 * (1.03e11 - 1.0e11) / 1.0e11               = 3.0
    expected_stable_pct = 100.0 * (stable_b - stable_a) / stable_a
    assert s_b.stable_wk_pct == pytest.approx(expected_stable_pct)
