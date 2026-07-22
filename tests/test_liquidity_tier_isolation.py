"""v9 liquidity-tier isolation — the low/mid/high-cap gate separation.

Why this exists: the four low-volume pairs (SUI/ARB/MINA/FLOW) never filled
because (a) they carry no external cross-venue imbalance, so the alpha's flow
gate read a defaulted 1.0 and never confirmed, and (b) even if they had, every
categorical liquidity floor was calibrated to ETH/BTC and vetoed them. This
pins both halves of the fix:

  * the Kraken-book imbalance the regime engine already computes is now stored
    on the state (surfaced to the view so the alpha can evaluate the asset);
  * an asset is classified into a cap-tier from its OWN trailing-median depth,
    and ONLY the categorical floors (depth / spread) scale by tier — CORE
    reproduces the legacy flat floors exactly (majors unchanged), MID/MICRO
    lower them so a low-volume asset REACHES the honest EV gate, which stays
    flat for every tier.
"""
from core.codes import Code
from core.config_guard import validate
from execution.pretrade import PreTradeContext, PreTradeGate
from regime.liquidity_regime import LiquidityRegimeEngine, _imbalance

TIERS = {
    "enabled": True,
    "order": ["core", "mid", "micro"],
    "core":  {"min_depth_usd": 150000, "max_spread_bps": 12},
    "mid":   {"min_depth_usd": 40000,  "max_spread_bps": 25},
    "micro": {"min_depth_usd": 12000,  "max_spread_bps": 45},
}


def _engine(tiers=True):
    cfg = {"min_depth_usd": 150000, "max_spread_bps": 12}
    if tiers:
        cfg["tiers"] = TIERS
    return LiquidityRegimeEngine(cfg)


def _book(mid=2000.0, size=5.0, half_spread=0.05, n=12):
    """A symmetric ladder. depth_top10 ~= 20 * mid * size; spread_bps ~=
    2*half_spread/mid*1e4. Tune size for the tier, half_spread for the label."""
    bids = [[mid - half_spread - 0.1 * i, size] for i in range(n)]
    asks = [[mid + half_spread + 0.1 * i, size] for i in range(n)]
    return {"bids": bids, "asks": asks}


# ---- tier assignment (derived from median depth, not a symbol map) ---------

def test_tier_assignment_tracks_median_depth():
    eng = _engine()
    eng.update("CORE", _book(size=5.0), _book(size=5.0), now=0.0)     # ~200k
    eng.update("MID", _book(size=1.5), _book(size=1.5), now=0.0)      # ~60k
    eng.update("MICRO", _book(size=0.5), _book(size=0.5), now=0.0)    # ~20k
    eng.update("DUST", _book(size=0.1), _book(size=0.1), now=0.0)     # ~4k
    assert eng.state("CORE").tier == "core"
    assert eng.state("MID").tier == "mid"
    assert eng.state("MICRO").tier == "micro"
    assert eng.state("DUST").tier == "micro"        # sub-floor -> thinnest tier


# ---- the isolation itself: a mid asset the flat floor kills is admitted -----

def test_mid_asset_liquid_under_tier_but_thin_under_flat():
    # depth ~60k, spread ~15bps: flat floor (150k / 12bps) => thin; the mid
    # tier (40k / 25bps) => liquid. This is the whole point of the change.
    book = _book(size=1.5, half_spread=1.5)          # ~60k depth, ~15bps
    on = _engine(tiers=True)
    on.update("MID", book, book, now=0.0)
    assert on.state("MID").label == "liquid"
    assert on.state("MID").size_mult == 1.0

    off = _engine(tiers=False)
    off.update("MID", book, book, now=0.0)
    assert off.state("MID").label == "thin"          # ETH/BTC-calibrated veto
    assert off.state("MID").tier == "core"           # disabled => all core


def test_micro_asset_admitted_by_its_tier():
    book = _book(size=0.5, half_spread=3.0)           # ~20k depth, ~30bps
    eng = _engine(tiers=True)
    eng.update("MICRO", book, book, now=0.0)
    assert eng.state("MICRO").tier == "micro"
    assert eng.state("MICRO").label == "liquid"       # 30bps <= micro cap 45


def test_tier_floor_still_bites_when_genuinely_too_wide():
    # mid-depth asset but a 30bps spread exceeds even the mid cap (25) -> thin.
    # Isolation widens the bar per scale; it does not remove it.
    book = _book(size=1.5, half_spread=3.0)           # ~60k depth, ~30bps
    eng = _engine(tiers=True)
    eng.update("MID", book, book, now=0.0)
    assert eng.state("MID").tier == "mid"
    assert eng.state("MID").label == "thin"


def test_core_asset_unchanged_by_enabling_tiers():
    # a deep, tight book classifies liquid identically with tiers on or off,
    # and stays in the core tier (== default) so no LT-010 churn for majors.
    book = _book(size=5.0, half_spread=0.05)          # ~200k, ~0.5bps
    on, off = _engine(True), _engine(False)
    on.update("ETH", book, book, now=0.0)
    off.update("ETH", book, book, now=0.0)
    assert on.state("ETH").label == off.state("ETH").label == "liquid"
    assert on.state("ETH").tier == "core"


# ---- the data unlock: the flow scalar is surfaced on the state -------------

def test_imbalance_ratio_stored_on_state():
    book = _book(size=1.5)
    eng = _engine()
    eng.update("MID", book, book, now=0.0)
    # exec book == kraken book here; engine decay default is 15bps
    assert eng.state("MID").imbalance_ratio == _imbalance(book, decay_bps=15.0)
    assert eng.state("MID").imbalance_ratio > 0.0     # never the defaulted 1.0-only


# ---- LT-010 fires on a tier CHANGE only (no per-cycle spam) -----------------

def test_lt010_emitted_on_tier_change_only(caplog):
    eng = _engine(tiers=True)
    book = _book(size=1.5, half_spread=1.5)           # -> mid tier
    with caplog.at_level("INFO", logger="liquiditybot.regime.liquidity"):
        eng.update("MID", book, book, now=0.0)        # core(default) -> mid
    assert sum(Code.LT_TIER_ASSIGNED.value in r.message for r in caplog.records) == 1
    caplog.clear()
    with caplog.at_level("INFO", logger="liquiditybot.regime.liquidity"):
        eng.update("MID", book, book, now=30.0)       # still mid -> silent
    assert not any(Code.LT_TIER_ASSIGNED.value in r.message for r in caplog.records)


def test_tier_hysteresis_holds_across_a_boundary():
    # an asset settled in 'mid' whose median then drifts just BELOW the 40k
    # floor must HOLD mid within the 15% dead-band — no flicker of tier /
    # size_mult / spread ceiling. A FRESH engine seeing the same book lands
    # micro, proving the difference is the sticky band, not the depth.
    eng = _engine(tiers=True)
    mid = _book(size=1.5, half_spread=1.5)          # ~60k -> mid
    for t in range(3):
        eng.update("X", mid, mid, now=float(t))
    assert eng.state("X").tier == "mid"
    near = _book(size=0.975, half_spread=1.5)       # ~39k, just under 40k
    for t in range(3, 14):
        eng.update("X", near, near, now=float(t))
    assert eng.state("X").tier == "mid"             # held (39k > 40k*0.85=34k)

    fresh = _engine(tiers=True)
    fresh.update("Y", near, near, now=0.0)
    assert fresh.state("Y").tier == "micro"         # same book, no prior -> micro


def test_outage_zeros_do_not_drop_a_major_tier():
    # a book outage (empty book -> depth 0) must NOT pollute the median and drag
    # a major into a looser tier that persists into the volatile recovery window.
    eng = _engine(tiers=True)
    core = _book(size=5.0, half_spread=0.05)        # ~200k -> core
    for t in range(5):
        eng.update("ETH", core, core, now=float(t))
    assert eng.state("ETH").tier == "core"
    empty = {"bids": [], "asks": []}
    for t in range(5, 25):                          # long outage
        eng.update("ETH", empty, empty, now=float(t))
    assert eng.state("ETH").tier == "core"          # median off REAL samples only
    assert eng.state("ETH").label != "liquid"       # still flagged unexecutable


def test_disabled_tiers_never_emit_lt010(caplog):
    eng = _engine(tiers=False)
    book = _book(size=0.5, half_spread=3.0)
    with caplog.at_level("INFO", logger="liquiditybot.regime.liquidity"):
        eng.update("MICRO", book, book, now=0.0)
    assert not any(Code.LT_TIER_ASSIGNED.value in r.message for r in caplog.records)


# ---- pretrade: the tier scales ONLY the spread ceiling, never the EV test ---

def _gate():
    return PreTradeGate({
        "maker_fee_bps": 25, "taker_fee_bps": 40, "max_spread_bps": 15,
        "tier_max_spread_bps": {"core": 15, "mid": 30, "micro": 55},
        "min_edge_cost_ratio": 1.3, "min_order_usd": 15,
    })


def _ctx(spread, tier):
    return PreTradeContext(
        kraken_book={"bids": [[100.0, 100.0]], "asks": [[100.2, 100.0]]},
        sigma_daily_pct=2.0, adv_usd=1e6, liq_label="liquid",
        spread_bps=spread, staleness_ms=0.0, tier=tier)


def _reasons(dec):
    return " ".join(str(r) for r in dec.reasons)


def test_core_tier_vetoes_wide_spread_like_the_flat_cap():
    d = _gate().evaluate("buy", 1.0, 100.0, exp_alpha_bps=500.0,
                         fv_edge_bps=0.0, ctx=_ctx(25.0, "core"))
    assert not d.approved
    assert Code.PT_SPREAD_WIDE.value in _reasons(d)


def test_mid_tier_admits_the_same_spread_past_the_ceiling():
    d = _gate().evaluate("buy", 1.0, 100.0, exp_alpha_bps=500.0,
                         fv_edge_bps=0.0, ctx=_ctx(25.0, "mid"))
    # the spread ceiling no longer vetoes; whatever happens downstream, it is
    # NOT the categorical spread gate that stopped it.
    assert Code.PT_SPREAD_WIDE.value not in _reasons(d)


def test_ev_gate_stays_honest_at_micro_tier():
    # micro admits a 40bps spread (<= 55 cap), but a tiny edge must STILL fail
    # the flat edge/cost ratio — isolation never loosens the net-profit test.
    d = _gate().evaluate("buy", 1.0, 100.0, exp_alpha_bps=1.0,
                         fv_edge_bps=0.0, ctx=_ctx(40.0, "micro"))
    assert not d.approved
    assert Code.PT_SPREAD_WIDE.value not in _reasons(d)   # spread passed
    assert Code.PT_EDGE_RATIO.value in _reasons(d)        # EV honestly vetoed


# ---- config_guard coherence -------------------------------------------------

def _cfg(core=(150000, 12), mid=(40000, 25), micro=(12000, 45),
         base=(150000, 12), pt_base=15, pt=(15, 30, 55)):
    return {
        "system": {"dry_run": True},
        "liquidity_regime": {
            "min_depth_usd": base[0], "max_spread_bps": base[1],
            "tiers": {"enabled": True, "order": ["core", "mid", "micro"],
                      "core":  {"min_depth_usd": core[0], "max_spread_bps": core[1]},
                      "mid":   {"min_depth_usd": mid[0],  "max_spread_bps": mid[1]},
                      "micro": {"min_depth_usd": micro[0], "max_spread_bps": micro[1]}}},
        "pretrade": {"max_spread_bps": pt_base,
                     "tier_max_spread_bps": {"core": pt[0], "mid": pt[1], "micro": pt[2]}},
    }


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def test_coherent_tiers_have_no_tier_fatal():
    fatals = _fatals(_cfg())
    assert not any("tiers" in m or "tier_max_spread" in m for m in fatals)


def test_core_drift_from_legacy_is_fatal():
    fatals = _fatals(_cfg(core=(120000, 12)))     # core depth != legacy 150k
    assert any("must equal the legacy flat floors" in m for m in fatals)


def test_thinner_tier_with_tighter_spread_is_fatal():
    fatals = _fatals(_cfg(micro=(12000, 10)))     # micro spread 10 < mid 25
    assert any("TIGHTER spread ceiling" in m for m in fatals)


def test_pretrade_core_cap_must_match_flat_cap():
    fatals = _fatals(_cfg(pt=(20, 30, 55)))       # pt core 20 != max_spread 15
    assert any("must equal pretrade.max_spread_bps" in m for m in fatals)


def test_disabled_tiers_skip_the_guard():
    cfg = _cfg(core=(120000, 12))                 # would be fatal if enabled
    cfg["liquidity_regime"]["tiers"]["enabled"] = False
    assert not any("must equal the legacy flat floors" in m for m in _fatals(cfg))


def test_pretrade_inverted_tier_cap_is_fatal():
    # the live-order spread veto scaling harder for a thinner tier is FATAL now
    fatals = _fatals(_cfg(pt=(15, 60, 30)))       # micro cap 30 < mid cap 60
    assert any("TIGHTER spread ceiling" in m for m in fatals)


def test_pretrade_missing_tier_cap_warns():
    cfg = _cfg()
    del cfg["pretrade"]["tier_max_spread_bps"]["micro"]   # declared tier, no cap
    warns = [m for sev, m in validate(cfg) if sev == "WARN"]
    assert any("no entry for tier 'micro'" in m for m in warns)
