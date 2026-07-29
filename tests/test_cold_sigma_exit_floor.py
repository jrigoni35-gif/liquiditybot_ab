"""Cold-sigma exit-floor regression (LINK 3ea2a851, 2026-07-28 20:19Z).

38 seconds after a restart the give-back ratchet armed on a 0.18% peak and
instantly exited a restored (underwater) short as "tier trail". Root cause:
the fast cycle evaluates restored positions BEFORE the slow cycle's first
vol.update, so `self.vol.state(asset)` returned the VolState dataclass
DEFAULT sigma_bar_pct=0.05 — a placeholder, not a measurement — which slips
past _give_back_candidate's `sig > 0` guard and collapses the vol-scaled arm
to 2.0 x 0.05 = 0.10%. Warm sigma (>= 0.09%) puts the arm above 0.18%, which
is why the same position never armed in 5.6 pre-restart hours.

Fix under test: VolState grows `measured` (False until update() computes the
fast estimate from real candles); main.py's exit-floor call sites pass
sigma via _exit_sigma(), which returns None until measured — selecting the
tier engine's DESIGNED static fallbacks (arm_gain_pct / legacy triggers /
trail_pct) instead of arithmetic on a fabricated number. Exits are never
blocked (invariant 5): only the ARMING input changes, the fire path and
every escape are untouched.
"""
from datetime import datetime, timezone
from pathlib import Path

from core.state import Position
from regime.vol_regime import VolRegimeEngine
from risk.profit_tiers import ProfitTierEngine

_MAIN = (Path(__file__).resolve().parents[1] / "main.py") \
    .read_text(encoding="utf-8")


# ---- VolState.measured contract ---------------------------------------------

def _candles(n, px=100.0):
    return [{"open": px, "high": px * 1.001, "low": px * 0.999,
             "close": px} for _ in range(n)]


def test_state_unknown_asset_is_unmeasured():
    eng = VolRegimeEngine({})
    st = eng.state("LINK")
    assert st.measured is False
    assert st.sigma_bar_pct == 0.05          # the placeholder default


def test_update_with_enough_candles_marks_measured():
    eng = VolRegimeEngine({})
    st = eng.update("LINK", _candles(30), [])
    assert st.measured is True
    assert st.sigma_bar_pct > 0.0
    # and the flag survives the state() read path
    assert eng.state("LINK").measured is True


def test_update_below_warmup_floor_stays_unmeasured():
    # < 20 candles: the fast estimate never computes -> still a placeholder
    eng = VolRegimeEngine({})
    st = eng.update("LINK", _candles(10), [])
    assert st.measured is False
    st = eng.update("LINK", [], [])
    assert st.measured is False


def test_measured_is_per_asset():
    eng = VolRegimeEngine({})
    eng.update("ETH", _candles(30), [])
    assert eng.state("ETH").measured is True
    assert eng.state("BTC").measured is False


def test_percentile_fallback_uses_parkinson_when_unmeasured():
    # daily history warm (>=40) but 5m estimate cold: the percentile must
    # come from the last-5-daily-bars Parkinson fallback, NOT from the
    # truthy sigma_daily_pct=2.0 placeholder (which put `current` at 0.02
    # regardless of the actual market). Daily bars with ~0.35% range give
    # a Parkinson daily vol ~0.0021 — far below the 0.02 placeholder, so
    # the two paths give opposite percentile extremes.
    daily = [{"open": 100.0, "high": 100.35, "low": 100.0, "close": 100.2}
             for _ in range(50)]
    eng = VolRegimeEngine({})
    st = eng.update("X", _candles(5), daily)          # 5m cold, daily warm
    assert st.measured is False
    # fallback: current == mean of the same distribution -> mid percentile,
    # never the ~100th the 2.0% placeholder produced against 0.21% history
    assert st.percentile < 90.0
    # and a measured update still uses the fast estimate (unchanged path)
    st2 = VolRegimeEngine({}).update("Y", _candles(30), daily)
    assert st2.measured is True


# ---- engine-level regression: the exact LINK geometry -----------------------

def _deployed_engine():
    # the deployed give_back block (config.json 2026-07-28)
    return ProfitTierEngine({
        "vol_scaled": False, "est_fee_bps": 40, "be_buffer_bps": 6,
        "give_back": {"enabled": True, "arm_gain_pct": 0.6,
                      "arm_vol_mult": 2.0, "giveback_frac": 0.4,
                      "tighten_gain_pct": 4.0, "tight_frac": 0.25}})


def _link_short():
    p = Position(position_id="3ea2a851", symbol="LINK/USD",
                 direction="short", entry_price=8.29442, size=1.455036,
                 original_size=1.455036,
                 opened_at=datetime.now(timezone.utc))
    p.high_water = 8.29442 * (1 - 0.0018)     # MFE 0.18% (short: lowest low)
    return p


def test_fabricated_default_sigma_reproduces_the_incident():
    # documents the arithmetic that made the wiring bug live: the VolState
    # placeholder 0.05 collapses the arm to 0.10% and a 0.18% peak arms
    eng = _deployed_engine()
    gb = eng._give_back_candidate(_link_short(), sigma_bar_pct=0.05)
    assert gb is not None
    assert 8.38 >= gb                          # underwater short: instant exit


def test_cold_none_sigma_uses_static_arm_and_does_not_arm():
    # the fixed wiring passes None until measured -> static arm 0.6% > 0.18%
    eng = _deployed_engine()
    assert eng._give_back_candidate(_link_short(),
                                    sigma_bar_pct=None) is None
    # the full floor check agrees: no stop is installed, nothing fires
    assert eng._exit_floor_hit(_link_short(), 8.38,
                               sigma_bar_pct=None) is False


def test_warm_sigma_matches_prerestart_behavior():
    # any plausible warm sigma (>= 0.09%) keeps the arm above the 0.18% peak
    eng = _deployed_engine()
    for sig in (0.09, 0.15, 0.25):
        assert eng._give_back_candidate(_link_short(),
                                        sigma_bar_pct=sig) is None


def test_warm_vol_arming_is_unchanged_by_the_fix():
    # the vol-scaled arm still works exactly as shipped for measured sigma:
    # sigma 0.3 -> arm 0.6%; a 0.7% peak arms
    eng = _deployed_engine()
    p = _link_short()
    p.high_water = 8.29442 * (1 - 0.007)       # peak 0.7%
    assert eng._give_back_candidate(p, sigma_bar_pct=0.3) is not None


# ---- the SAME placeholder fed the vol-scaled tier triggers ------------------

def test_cold_none_sigma_restores_legacy_tier_trigger():
    # vol-scaled trigger clamps to [0.5x, 3x] legacy: the placeholder 0.05
    # bottomed tier 1 out at HALF its configured trigger (2.0 x 0.05 =
    # 0.10 -> clamp 1.0) at the first post-boot cycles; None restores the
    # exact legacy trigger (the engine's designed no-vol-feed mode)
    eng = ProfitTierEngine({
        "vol_scaled": True,
        "tier_1": {"trigger_pct_gain": 2.0, "trigger_vol_mult": 2.0,
                   "close_pct_of_position": 25}})
    tier = eng.tiers[0]
    assert eng._tier_trigger_pct(tier, 0.05) == 1.0     # the placeholder bug
    assert eng._tier_trigger_pct(tier, None) == 2.0     # cold -> legacy
    assert eng._tier_trigger_pct(tier, 0.5) == 1.0      # warm floor unchanged
    assert eng._tier_trigger_pct(tier, 2.0) == 4.0      # warm scaling unchanged


def test_placeholder_never_tightened_the_trail():
    # the chandelier distance is max(legacy, k*sig*sqrt(bars)): the tiny
    # placeholder term always lost to the legacy floor, so trail geometry
    # was never at risk - pinned so a refactor can't remove the floor
    eng = _deployed_engine()
    p = _link_short()
    assert eng._trail_distance_frac(p, 0.05) == \
        eng._trail_distance_frac(p, None)


# ---- main.py wiring contract (source pin) -----------------------------------

def test_main_defines_measured_sigma_gate():
    assert "def _measured_sigma(self, asset" in _MAIN
    # the helper's contract: unmeasured vol reads as None, never a number
    # (getattr tolerance: only the real VolState carries the flag; a
    # duck-typed test stub without it means its number)
    assert 'if getattr(st, "measured", True) else None' in _MAIN


def test_main_exit_floor_sites_use_the_gate():
    # all three exit-floor consumers (long-book evaluate, 5m evaluate, the
    # floor un-occlusion _exit_floor_hit) take the gated sigma
    assert _MAIN.count("sigma_bar_pct=self._measured_sigma(asset)") >= 3
    # and the raw state read no longer feeds the tier-evaluate calls
    assert "evaluate(\n                    pos, px,\n" \
           "                    sigma_bar_pct=self.vol.state(asset)" \
           not in _MAIN


def test_main_scs_hint_is_measured_gated():
    # the state-change sampler's sigma HINT is gated too: the placeholder
    # bypassed the sampler's own designed EWMA fallback with a fabricated
    # h = k * 0.0005 for sparse (<warmup) assets
    assert "self.scs.observe(asset, closes[asset],\n" \
           "                                    sigma_bar_pct=self." \
           "_measured_sigma(asset)," in _MAIN


# ---- vol-warmup floor is a named constant + guard-pinned --------------------

def test_fast_warmup_bars_constant_is_the_measurement_floor():
    from regime.vol_regime import FAST_WARMUP_BARS
    assert FAST_WARMUP_BARS == 20
    eng = VolRegimeEngine({})
    assert eng.update("X", _candles(FAST_WARMUP_BARS), []).measured is True
    eng2 = VolRegimeEngine({})
    assert eng2.update("X", _candles(FAST_WARMUP_BARS - 1), []) \
        .measured is False


def _guard_cfg(slow, ad):
    return {"system": {"dry_run": True},
            "informed_flow": {"slow_period": slow, "ad_lookback_bars": ad}}


def _guard_fatals(cfg):
    from core.config_guard import validate
    return [m for s, m in validate(cfg) if s == "FATAL"]


def test_guard_sufficiency_must_cover_vol_warmup():
    # entry-side warm-by-construction rests on informed_flow's V3
    # sufficiency floor max(slow+2, ad+1, 14) being >= the vol estimator's
    # 20-bar warmup: a config below it would evaluate signals (and price
    # bracket geometry) off the unmeasured placeholder. Deployed 21/24
    # (floor 25) passes; a 12/13 config (floor 14) is FATAL; exactly-20
    # combos are legal.
    assert not any("sufficiency" in m for m in _guard_fatals(
        _guard_cfg(21, 24)))
    assert any("sufficiency" in m for m in _guard_fatals(
        _guard_cfg(12, 13)))
    assert not any("sufficiency" in m for m in _guard_fatals(
        _guard_cfg(18, 19)))                     # max(20, 20, 14) == 20
