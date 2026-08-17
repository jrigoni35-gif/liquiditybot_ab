"""FW-081 labeler bars-cache staleness alert (staleness audit 2026-08-16).

DOT sat 157h stale and SOL 36h with ZERO log lines: legitimate skimmer
rotation froze their CandidateLabeler._bars caches, and nothing anywhere
alerted on labeler-cache age. That instance was benign - but the same
silence would have hidden a genuinely dead fetch path on an ACTIVE asset,
because FW-080 (_bar_age_check) only runs when a fresh-enough _kr_candles
entry EXISTS: _augment_view_with_kraken `continue`s past absent/aged
entries, which is exactly the signature of a fetch path that died outright.

_label_bars_age_check is the consumer-side complement: ACTIVE (symbol_map)
assets only, latched once per stale episode, re-armed on fresh bars,
never raises. Same module-level duck-typed-bot convention as
_bar_age_check (see tests/test_latency_truth.py for why).
"""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace

import main as main_mod
from core.codes import Code

THRESH = 7200.0        # 240 cycles x 30s, the shipped default
WARMUP = main_mod._LABEL_BARS_WARMUP_SEC


def _bot(bars: dict, assets=("ADA",)) -> SimpleNamespace:
    return SimpleNamespace(
        symbol_map={a: f"{a}/USD" for a in assets},
        candidates=SimpleNamespace(_bars=bars),
        _label_bars_stale_sec=THRESH)


def _bars_at(ts: float) -> dict:
    return {"t": [ts], "c": [1.0], "h": [1.0], "l": [1.0]}


def test_registered_code():
    assert Code.FW_LABEL_BARS_STALE.value == "FW-081"


def test_stale_cache_warns_once_per_episode(caplog):
    now = 1_786_000_000.0
    b = _bot({"ADA": _bars_at(now - 10 * 3600.0)})
    with caplog.at_level(logging.WARNING, logger="liquiditybot.main"):
        main_mod._label_bars_age_check(b, now)             # seeds t0: grace
        main_mod._label_bars_age_check(b, now + WARMUP + 1.0)
        main_mod._label_bars_age_check(b, now + WARMUP + 30.0)
    hits = [r for r in caplog.records if "FW-081" in r.getMessage()]
    assert len(hits) == 1, "latched: one warning per stale episode"
    assert "ADA" in hits[0].getMessage()


def test_boot_warmup_grace_suppresses_restored_stale_cache(caplog):
    """A restart restores the cache hours-stale while the Kraken candle
    warmup refills at most 3 assets per slow cycle - no alert inside the
    warmup window (the DOT-repromotion false-positive)."""
    now = 1_786_000_000.0
    b = _bot({"ADA": _bars_at(now - 157 * 3600.0)})
    with caplog.at_level(logging.WARNING, logger="liquiditybot.main"):
        main_mod._label_bars_age_check(b, now)
        main_mod._label_bars_age_check(b, now + WARMUP - 1.0)
    assert not [r for r in caplog.records if "FW-081" in r.getMessage()]


def test_fresh_bars_release_latch_then_new_episode_fires(caplog):
    now = 1_786_000_000.0
    cache = {"ADA": _bars_at(now - 10 * 3600.0)}
    b = _bot(cache)
    with caplog.at_level(logging.WARNING, logger="liquiditybot.main"):
        main_mod._label_bars_age_check(b, now)             # grace
        main_mod._label_bars_age_check(b, now + WARMUP + 1.0)   # episode 1
        t2 = now + WARMUP + 60.0
        cache["ADA"] = _bars_at(t2 - 300.0)                # fresh 5m bar
        main_mod._label_bars_age_check(b, t2)              # releases latch
        t3 = t2 + THRESH + 301.0                           # goes stale again
        main_mod._label_bars_age_check(b, t3)              # episode 2
    hits = [r for r in caplog.records if "FW-081" in r.getMessage()]
    assert len(hits) == 2
    assert "ADA" in b._label_bars_latched      # episode 2 still latched


def test_missing_cache_entry_counts_as_stale_since_boot(caplog):
    """An active asset the labeler has NEVER seen a bar for (feed dead from
    boot - the FW-080 blind spot) must alert once its silence exceeds the
    threshold measured from the first check."""
    now = 1_786_000_000.0
    b = _bot({}, assets=("SUI",))
    with caplog.at_level(logging.WARNING, logger="liquiditybot.main"):
        main_mod._label_bars_age_check(b, now)             # seeds t0
        main_mod._label_bars_age_check(b, now + WARMUP + 1.0)   # under thresh
        main_mod._label_bars_age_check(b, now + THRESH + 1.0)   # over thresh
    hits = [r for r in caplog.records if "FW-081" in r.getMessage()]
    assert len(hits) == 1
    assert "SUI" in hits[0].getMessage()


def test_inactive_assets_never_checked(caplog):
    """Rotation-frozen caches are EXPECTED (DOT 157h, 2026-08-16): only
    symbol_map membership makes staleness a defect."""
    now = 1_786_000_000.0
    b = _bot({"DOT": _bars_at(now - 157 * 3600.0),
              "ADA": _bars_at(now - 60.0)}, assets=("ADA",))
    with caplog.at_level(logging.WARNING, logger="liquiditybot.main"):
        main_mod._label_bars_age_check(b, now)
        main_mod._label_bars_age_check(b, now + THRESH + 1.0)
    assert not [r for r in caplog.records if "DOT" in r.getMessage()]


def test_never_raises_on_stub_bots_and_garbage_caches():
    """Telemetry must never raise: __new__ doubles lack every attribute,
    and cache rows can be malformed mid-restore."""
    now = 1_786_000_000.0
    main_mod._label_bars_age_check(SimpleNamespace(), now)      # no attrs
    b = _bot({"ADA": {"t": []}})                                # empty t
    main_mod._label_bars_age_check(b, now)
    main_mod._label_bars_age_check(b, now + WARMUP + 1.0)
    b2 = _bot({"ADA": {"t": "garbage"}})                        # wrong type
    main_mod._label_bars_age_check(b2, now)
    main_mod._label_bars_age_check(b2, now + WARMUP + 1.0)
    b3 = _bot(None)                                             # no dict
    main_mod._label_bars_age_check(b3, now + WARMUP + 1.0)


def test_wired_into_slow_cycle():
    """The check must run where update_candles runs (parsed AST, not a
    text scan - same proof shape as FW-080's wiring test)."""
    tree = ast.parse(Path(main_mod.__file__).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "slow_cycle")
    calls = {c.func.id for c in ast.walk(fn)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "_label_bars_age_check" in calls


def test_config_guard_fatals_incoherent_threshold():
    """Guard law: the derived threshold must clear the 1200s FW-080 floor
    and non-positive is nonsense, not a disable switch."""
    from core.config_guard import validate
    base = {"ml": {"label_bars_stale_cycles": 240},
            "system": {"polling_interval_sec": 5, "slow_cycle_every_n": 6}}
    assert not [f for f in validate(base)
                if "label_bars_stale_cycles" in f[1]]
    bad = {"ml": {"label_bars_stale_cycles": 8},        # 8 x 30s = 240s
           "system": {"polling_interval_sec": 5, "slow_cycle_every_n": 6}}
    fatals = [f for f in validate(bad)
              if f[0] == "FATAL" and "label_bars_stale_cycles" in f[1]]
    assert fatals, "240s threshold must FATAL (under the 1200s floor)"
    zero = {"ml": {"label_bars_stale_cycles": 0},
            "system": {"polling_interval_sec": 5, "slow_cycle_every_n": 6}}
    fatals = [f for f in validate(zero)
              if f[0] == "FATAL" and "label_bars_stale_cycles" in f[1]]
    assert fatals, "0 must FATAL - no silent off switch"
