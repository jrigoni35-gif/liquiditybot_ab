"""tests/test_kraken_fee_schedule.py — FEE-3 remedy: KrakenFeed's
TradeVolume read keeps the FULL tier context (minfee / maxfee / nextfee /
nextvolume / tiervolume per pair, plus the account-level 30-day volume and
its currency) instead of discarding everything but `fee`.

Those fields are what distinguish an ACCOUNT RATE from a SCHEDULE TOP
(an untraded pair reports the bottom tier's fee == maxfee), so without
them the docket's {40/80 vs 22/38} identified set cannot be resolved.

Planted fixture = Kraken's documented TradeVolume shape. Every value is
asserted EXACTLY (percent string -> bps is x100; volume strings -> float).
The mutation pin (`test_context_fields_removed_yield_none_old_keys_unchanged`)
strips the new fields and requires None back with the headline keys
byte-identical - never a fabricated 0.0, never a KeyError.

Measurement plane only: nothing here changes a fee VALUE used for pricing
or booking; get_trade_fee_tiers' legacy keys are asserted unchanged.
"""
import copy

import pytest

from data.kraken_feed import (
    _MAX_CURRENCY_LEN,
    KrakenFeed,
    _volume_str_to_float,
)

# Kraken's documented TradeVolume response shape (XBT/USD, one pair). The
# numbers are FIXTURE values, not a venue reading - see docs/HANDOFF.md
# FEE-3: this bot has never held a credential.
_PLANTED = {
    "currency": "ZUSD",
    "volume": "17482.00",
    "fees": {                       # taker schedule
        "XXBTZUSD": {"fee": "0.3800", "minfee": "0.1000", "maxfee": "0.4000",
                     "nextfee": "0.3500", "nextvolume": "50000.00",
                     "tiervolume": "10000.00"},
    },
    "fees_maker": {                 # maker schedule
        "XXBTZUSD": {"fee": "0.2200", "minfee": "0.0000", "maxfee": "0.2500",
                     "nextfee": "0.2000", "nextvolume": "50000.00",
                     "tiervolume": "10000.00"},
    },
}

_CONTEXT_FIELDS = ("minfee", "maxfee", "nextfee", "nextvolume", "tiervolume")
_NEW_KEYS = tuple(f"{side}_{suffix}" for side in ("maker", "taker")
                  for suffix in ("min_bps", "max_bps", "next_bps",
                                 "next_volume", "tier_volume"))


def _feed(response, calls=None):
    f = KrakenFeed({"rate_limit_per_sec": 3, "trading_pairs": []})
    f._internal_to_alt = {"XXBTZUSD": "XBTUSD"}      # as AssetPairs sets it
    calls = calls if calls is not None else []

    def _post(endpoint, data=None):
        calls.append((endpoint, dict(data or {})))
        return copy.deepcopy(response)

    f._private_post = _post          # type: ignore[method-assign]
    return f, calls


# --------------------------------------------------------------------------
# full fixture: every field lands, exactly
# --------------------------------------------------------------------------
def test_full_fixture_parses_every_field_exactly():
    f, calls = _feed(_PLANTED)
    sched = f.get_trade_fee_schedule(["XBTUSD"])

    assert calls == [("TradeVolume", {"pair": "XBTUSD"})]
    assert sched is not None
    assert set(sched) == {"pairs", "volume_30d", "volume_currency"}
    assert sched["volume_30d"] == 17482.0
    assert sched["volume_currency"] == "ZUSD"

    row = sched["pairs"]["XBTUSD"]
    assert row == {
        "maker_bps": 22.0, "taker_bps": 38.0,          # legacy keys
        "maker_min_bps": 0.0, "maker_max_bps": 25.0, "maker_next_bps": 20.0,
        "maker_next_volume": 50000.0, "maker_tier_volume": 10000.0,
        "taker_min_bps": 10.0, "taker_max_bps": 40.0, "taker_next_bps": 35.0,
        "taker_next_volume": 50000.0, "taker_tier_volume": 10000.0,
    }
    # types: every numeric is a real float (never the venue's string)
    for k, v in row.items():
        assert isinstance(v, float), k


def test_get_trade_fee_tiers_keeps_legacy_keys_and_shape():
    """The pre-remedy accessor: same {pair: {...}} shape, same legacy key
    values, the new keys purely additive - and NO pseudo-pair key (every
    consumer iterates this map as pairs)."""
    f, _ = _feed(_PLANTED)
    tiers = f.get_trade_fee_tiers(["XBTUSD"])
    assert tiers is not None
    assert set(tiers) == {"XBTUSD"}, "no reserved/account pseudo-key"
    assert tiers["XBTUSD"]["maker_bps"] == 22.0
    assert tiers["XBTUSD"]["taker_bps"] == 38.0
    for k in _NEW_KEYS:
        assert k in tiers["XBTUSD"]


# --------------------------------------------------------------------------
# MUTATION PIN: fields removed -> None, headline keys unchanged
# --------------------------------------------------------------------------
def test_context_fields_removed_yield_none_old_keys_unchanged():
    stripped = copy.deepcopy(_PLANTED)
    for side in ("fees", "fees_maker"):
        for field in _CONTEXT_FIELDS:
            del stripped[side]["XXBTZUSD"][field]
    del stripped["volume"]
    del stripped["currency"]

    f, _ = _feed(stripped)
    sched = f.get_trade_fee_schedule(["XBTUSD"])
    assert sched is not None
    assert sched["volume_30d"] is None
    assert sched["volume_currency"] is None
    row = sched["pairs"]["XBTUSD"]
    assert row["maker_bps"] == 22.0
    assert row["taker_bps"] == 38.0
    for k in _NEW_KEYS:
        assert k in row, f"{k} must be PRESENT (None), not missing"
        assert row[k] is None, f"{k} must be None when the venue omits it"


@pytest.mark.parametrize("bad", ["abc", "-1", "inf", "nan", "", None, {}, []])
def test_garbage_context_fields_yield_none_never_fabricated(bad):
    """A garbled context field must read as unknown; the pair itself is
    still reported (the headline fee parsed) - the context is additive."""
    doctored = copy.deepcopy(_PLANTED)
    for side in ("fees", "fees_maker"):
        for field in _CONTEXT_FIELDS:
            doctored[side]["XXBTZUSD"][field] = bad
    doctored["volume"] = bad
    doctored["currency"] = bad

    f, _ = _feed(doctored)
    sched = f.get_trade_fee_schedule(["XBTUSD"])
    assert sched is not None
    assert sched["volume_30d"] is None
    # currency is an opaque venue string: any non-empty str is kept
    # verbatim, everything else (empty, None, non-str) reads as None
    expected_cur = bad if isinstance(bad, str) and bad else None
    assert sched["volume_currency"] == expected_cur
    row = sched["pairs"]["XBTUSD"]
    assert row["maker_bps"] == 22.0 and row["taker_bps"] == 38.0
    for k in _NEW_KEYS:
        assert row[k] is None


def test_top_tier_null_next_fields_read_as_none():
    """Kraken reports nextfee/nextvolume as null at the highest tier."""
    top = copy.deepcopy(_PLANTED)
    for side in ("fees", "fees_maker"):
        top[side]["XXBTZUSD"]["nextfee"] = None
        top[side]["XXBTZUSD"]["nextvolume"] = None
    f, _ = _feed(top)
    row = f.get_trade_fee_schedule(["XBTUSD"])["pairs"]["XBTUSD"]
    assert row["maker_next_bps"] is None and row["taker_next_bps"] is None
    assert row["maker_next_volume"] is None
    assert row["taker_next_volume"] is None
    assert row["taker_tier_volume"] == 10000.0     # untouched neighbour


def test_headline_fee_unparseable_still_drops_the_pair():
    """Pre-remedy contract preserved: no headline fee -> pair ABSENT, and
    with no pair parsed the whole read is None (skip the reconciliation)."""
    doctored = copy.deepcopy(_PLANTED)
    doctored["fees"]["XXBTZUSD"]["fee"] = "garbage"
    f, _ = _feed(doctored)
    assert f.get_trade_fee_schedule(["XBTUSD"]) is None
    assert f.get_trade_fee_tiers(["XBTUSD"]) is None


def test_not_tradevolume_shaped_is_none():
    f, _ = _feed({"volume": "17482.00", "currency": "ZUSD"})   # no fees maps
    assert f.get_trade_fee_schedule(["XBTUSD"]) is None
    f2, _ = _feed(None)                                          # transport fail
    assert f2.get_trade_fee_schedule(["XBTUSD"]) is None
    f3, calls = _feed(_PLANTED)
    assert f3.get_trade_fee_schedule([]) is None
    assert calls == [], "empty pair list never hits the venue"


@pytest.mark.parametrize("raw,expected", [
    ("17482.00", 17482.0), ("0", 0.0), (5, 5.0), ("-1", None), ("inf", None),
    ("nan", None), ("x", None), (None, None), ({}, None),
])
def test_volume_str_to_float_contract(raw, expected):
    assert _volume_str_to_float(raw) == expected


def test_currency_string_is_bounded_never_truncated():
    """volume_currency is a venue-controlled string written verbatim into
    audit.jsonl / status.json: a plausible asset code is kept, an
    over-long one reads as None (not truncated - never a fabricated code)."""
    ok = copy.deepcopy(_PLANTED)
    ok["currency"] = "Z" * _MAX_CURRENCY_LEN
    f, _ = _feed(ok)
    assert f.get_trade_fee_schedule(["XBTUSD"])["volume_currency"] == ok["currency"]
    too_long = copy.deepcopy(_PLANTED)
    too_long["currency"] = "Z" * (_MAX_CURRENCY_LEN + 1)
    f2, _ = _feed(too_long)
    assert f2.get_trade_fee_schedule(["XBTUSD"])["volume_currency"] is None


def test_tier_context_key_list_agrees_across_producer_and_consumers():
    """The same ten keys are named in three modules (feed produces them,
    OrderManager copies them onto OM-080, cost_truth_report reads them
    back). A drift would silently read as None everywhere downstream, so
    pin all three to the feed's actual output."""
    from execution.order_manager import _FEE_TIER_CONTEXT_KEYS
    from scripts.cost_truth_report import _TIER_CONTEXT_KEYS

    f, _ = _feed(_PLANTED)
    produced = set(f.get_trade_fee_tiers(["XBTUSD"])["XBTUSD"]) \
        - {"maker_bps", "taker_bps"}
    assert produced == set(_NEW_KEYS)
    assert set(_FEE_TIER_CONTEXT_KEYS) == produced
    assert set(_TIER_CONTEXT_KEYS) == produced
    assert len(_FEE_TIER_CONTEXT_KEYS) == len(_TIER_CONTEXT_KEYS) == 10
