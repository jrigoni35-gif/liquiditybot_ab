"""main.LiquidityBot._retrain_gate — the cold-start training trigger.

Regression for a learning STALL: the first champion never trained because
the cold-start attempt was gated on a flag file (gitignored, wiped by a
container rollback) while the durable retrain cooldown refused to rewrite it
- so after every restart the flag was absent and no train fired for a full
cooldown, leaving the bot on the cold-start prior forever at 240+ rows.

The gate now drives cold start DIRECTLY off "no champion + enough rows",
independent of the flag, and lets the first cold attempt bypass the
min-NEW-rows throttle exactly once (a cold container's _rows_at_last_train
== full restored count would otherwise zero the delta and block it).
"""
from types import SimpleNamespace

import main as main_mod


def _bot(*, trained, level=0, flag=False, rows_at_last_train=0,
         retrain_attempted=False, min_rows=60, min_new_rows=25):
    calls = []
    monitor = SimpleNamespace(
        retrain_min_rows=min_rows, retrain_min_new_rows=min_new_rows,
        level=level, flag_path=SimpleNamespace(exists=lambda: flag),
        request_retrain=lambda msg: calls.append(msg))
    bot = SimpleNamespace(
        meta=SimpleNamespace(trained=trained), monitor=monitor,
        _rows_at_last_train=rows_at_last_train,
        _retrain_attempted=retrain_attempted)
    return bot, calls


def _gate(bot, rows):
    return main_mod.LiquidityBot._retrain_gate(bot, rows)


def test_cold_start_trains_despite_absent_flag_and_active_cooldown():
    # THE regression: post-restart the flag is gone and the cooldown refuses
    # to rewrite it, yet with no champion + enough rows we MUST attempt.
    bot, calls = _bot(trained=False, level=0, flag=False,
                      rows_at_last_train=250)          # cold container: == rows
    assert _gate(bot, rows=250) is True
    assert bot._retrain_attempted is True
    assert calls and "cold start" in calls[0]


def test_cold_start_first_attempt_bypasses_new_rows_then_throttles():
    bot, _ = _bot(trained=False, rows_at_last_train=250)
    assert _gate(bot, 250) is True                      # first attempt: bypass
    # second attempt (already attempted, no new rows) is throttled off
    assert _gate(bot, 250) is False
    # ... until enough NEW rows accrue
    assert _gate(bot, 250 + 25) is True


def test_cold_start_blocked_below_min_rows():
    bot, calls = _bot(trained=False, rows_at_last_train=0)
    assert _gate(bot, rows=59) is False                 # < retrain_min_rows(60)
    assert not calls                                    # no cold request logged


def test_trained_champion_needs_degradation_or_flag():
    # a healthy trained champion (level 0, no flag) must NOT retrain
    bot, _ = _bot(trained=True, level=0, flag=False, rows_at_last_train=100)
    assert _gate(bot, rows=200) is False


def test_trained_champion_retrains_on_level2_with_new_rows():
    bot, _ = _bot(trained=True, level=2, rows_at_last_train=100)
    assert _gate(bot, rows=100 + 25) is True            # degradation + new rows
    # but not without enough new rows
    bot2, _ = _bot(trained=True, level=2, rows_at_last_train=100)
    assert _gate(bot2, rows=100 + 10) is False


def test_trained_champion_flag_triggers_retrain():
    bot, _ = _bot(trained=True, level=0, flag=True, rows_at_last_train=100)
    assert _gate(bot, rows=100 + 40) is True
