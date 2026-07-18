"""TH-017 spoof/layering flicker detector (strategies/thales.py).

Cartea–Jaimungal–Wang: spoofing operates through top-of-book imbalance;
Korea Exchange evidence: imbalance-followers are the victims. Snapshot
footprint under test: a level much larger than median top depth that
VANISHES while the mid never crossed it (pulled, not consumed).

Contract:
  - repeated large-bid flicker pumps the bid EWMA; steady books and
    normal-size churn do not;
  - a large level that vanishes WITH the mid crossing it (consumed) is
    innocent;
  - high bid-flicker shades LONG entries down (TH-017 note) and leaves
    shorts untouched when the ask side is clean;
  - the shade is a SAFETY shade: never graded by V2 reliability (no
    fired entry), and a hostile ledger cannot mute it;
  - TH-016 lapse resets flicker state (gap-straddling vanishes are
    fiction);
  - config_guard rejects incoherent spoof knobs.
"""
from core.config_guard import validate
from strategies.thales import ThalesEngine

CFG = {
    "enabled": True,
    "influence": "advise",
    "max_conf_shade": 1.15,
    "reliability": {"enabled": True, "min_fired": 20},
    "spoof": {"top_levels": 5, "big_ratio": 3.0, "drop_frac": 0.8,
              "decay": 0.85, "score_thr": 0.35, "gain": 0.4},
}


def _eng(**over):
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in CFG.items()}
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    return ThalesEngine(cfg)


def _book(big_bid=None, big_ask=None):
    """Five modest levels a side (size 1.0) + optional huge outlier."""
    bids = [[100.30 - 0.01 * i, 1.0] for i in range(5)]
    asks = [[100.44 + 0.01 * i, 1.0] for i in range(5)]
    if big_bid is not None:
        bids[2] = [bids[2][0], big_bid]
    if big_ask is not None:
        asks[2] = [asks[2][0], big_ask]
    return {"bids": bids, "asks": asks}


def _flicker(eng, asset="BTC", n=6, side="bid"):
    """Alternate huge-level-present / huge-level-pulled snapshots with a
    stable mark (level never crossed): the classic layering cadence."""
    t = 1000.0
    for k in range(n):
        kw = {"big_bid": 12.0} if side == "bid" else {"big_ask": 12.0}
        eng.observe_fast(asset, _book(**kw), 100.37, t)
        t += 5.0
        eng.observe_fast(asset, _book(), 100.37, t)   # pulled, mid unmoved
        t += 5.0
    return t


def test_flicker_pumps_side_ewma_and_steady_book_does_not():
    eng = _eng()
    _flicker(eng, "BTC", side="bid")
    assert eng._st("BTC").spoof_ewma["bids"] > 0.35
    assert eng._st("BTC").spoof_ewma["asks"] < 0.05
    calm = _eng()
    t = 1000.0
    for _ in range(12):                      # persistent big bid: RESTING,
        calm.observe_fast("ETH", _book(big_bid=12.0), 100.37, t)  # not spoof
        t += 5.0
    assert calm._st("ETH").spoof_ewma["bids"] < 0.05


def test_consumed_level_is_innocent():
    eng = _eng()
    t = 1000.0
    for _ in range(6):
        eng.observe_fast("BTC", _book(big_bid=12.0), 100.37, t)
        t += 5.0
        # level at 100.28 vanishes but the mark CROSSED DOWN through it:
        # sells plausibly ate it - not a pull
        eng.observe_fast("BTC", _book(), 100.27, t)
        t += 5.0
    assert eng._st("BTC").spoof_ewma["bids"] < 0.05


def test_bid_flicker_shades_long_not_short():
    eng = _eng()
    t = _flicker(eng, "BTC", side="bid")
    lo = eng.shade_confidence("BTC", "long", 1.0, 0.5, "range", t)
    sh = eng.shade_confidence("BTC", "short", 1.0, 0.5, "range", t)
    assert lo.mult < 1.0
    assert any("TH-017" in n for n in lo.notes)
    assert sh.mult == 1.0 and not any("TH-017" in n for n in sh.notes)


def test_spoof_shade_is_safety_not_graded():
    eng = _eng()
    eng._rel["spoof"] = {"fired": 40, "vindicated": 0}   # hostile ledger
    t = _flicker(eng, "BTC", side="bid")
    out = eng.shade_confidence("BTC", "long", 1.0, 0.5, "range", t)
    assert out.mult < 1.0                    # still shades: ledger ignored
    assert out.fired == []                   # and is never up for grading


def test_lapse_resets_spoof_state():
    eng = _eng()
    t = _flicker(eng, "BTC", side="bid")
    assert eng._st("BTC").spoof_ewma["bids"] > 0.35
    eng.observe_fast("BTC", _book(), 100.37, t + 7200.0)   # 2h hole
    st = eng._st("BTC")
    assert st.spoof_ewma == {"bids": 0.0, "asks": 0.0}
    assert st.spoof_prev["bids"] != {}       # re-seeded post-gap only


def test_guard_rejects_incoherent_spoof_knobs():
    def fatals(cfg):
        return [m for s, m in validate(cfg) if s == "FATAL"]
    assert any("big_ratio" in m for m in fatals(
        {"thales": {"enabled": True, "spoof": {"big_ratio": 1.1}}}))
    assert any("drop_frac" in m for m in fatals(
        {"thales": {"enabled": True, "spoof": {"drop_frac": 1.5}}}))
    assert any("decay" in m for m in fatals(
        {"thales": {"enabled": True, "spoof": {"decay": 1.0}}}))
    assert any("spoof.gain" in m for m in fatals(
        {"thales": {"enabled": True, "spoof": {"gain": -0.1}}}))
    assert not any("spoof" in m for m in fatals(
        {"thales": {"enabled": True, "spoof": {}}}))     # defaults coherent
