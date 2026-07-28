"""tests/test_event_sampler.py — State-Change Sampler (ml/event_sampler.py).

Symmetric CUSUM on log returns (h = k·sigma_bar) OR-fused with the bot's own
macro/liquidity regime-label flips, gating ONLY candidate registration. Pins:
trigger arithmetic (units: sigma_bar_pct is a PERCENT, r is a fraction), vol
scaling, label-flip triggers on flat prices, per-asset isolation, disabled
pass-through, bad-price hygiene, the main.py wiring contract, and the
config_guard cusum_k bounds.
"""
import math
from pathlib import Path

from core.config_guard import validate
from ml.event_sampler import StateChangeSampler

_MAIN = (Path(__file__).resolve().parents[1] / "main.py") \
    .read_text(encoding="utf-8")


def _scs(k=3.0, enabled=True):
    return StateChangeSampler({"cusum_enabled": enabled, "cusum_k": k})


def _drift(s, asset="ETH", n=10, r=0.001, p0=100.0, sig_pct=0.1):
    """Feed n bars of constant log-return r; return list of observe() results
    (bootstrap excluded)."""
    assert s.observe(asset, p0, sigma_bar_pct=sig_pct)   # bootstrap event
    out, px = [], p0
    for _ in range(n):
        px *= math.exp(r)
        out.append(s.observe(asset, px, sigma_bar_pct=sig_pct))
    return out


def test_drift_triggers_exactly_past_k_sigma():
    # sigma_bar_pct=0.1 -> sigma=0.001 (percent->fraction), h=3*0.001=0.003.
    # r=0.0011/bar: S+ = 0.0011, 0.0022, 0.0033 > h -> event on bar 3, reset,
    # same 3-bar cadence repeats. r=0.0009/bar: S+ crosses only on bar 4
    # (0.0027 < h < 0.0036). Off-boundary drifts so no float-eps ambiguity.
    assert _drift(_scs(3.0), n=6, r=0.0011) == \
        [False, False, True, False, False, True]
    assert _drift(_scs(3.0), n=4, r=0.0009) == \
        [False, False, False, True]


def test_zero_drift_noise_below_h_never_triggers():
    s = _scs(3.0)
    assert s.observe("ETH", 100.0, sigma_bar_pct=0.1)
    px, res = 100.0, []
    for i in range(50):                       # +/-0.05% alternating: S+ <= 0.0005
        px = 100.0 * math.exp(0.0005 if i % 2 == 0 else 0.0)
        res.append(s.observe("ETH", px, sigma_bar_pct=0.1))
    assert not any(res)


def test_vol_scaling_larger_sigma_fewer_events():
    # same 21-bar r=0.0011 path: h=0.003 -> event every 3 bars (7 total);
    # h=0.03 -> total drift 0.0231 never reaches it (0 events)
    lo = sum(_drift(_scs(3.0), n=21, r=0.0011, sig_pct=0.1))
    hi = sum(_drift(_scs(3.0), n=21, r=0.0011, sig_pct=1.0))
    assert lo == 7 and hi == 0
    assert hi < lo


def test_regime_label_flip_triggers_on_flat_prices():
    s = _scs(3.0)
    assert s.observe("ETH", 100.0, sigma_bar_pct=0.1, regime_label="range")
    assert not s.observe("ETH", 100.0, sigma_bar_pct=0.1, regime_label="range")
    # flip with ZERO net drift = new market state -> event
    assert s.observe("ETH", 100.0, sigma_bar_pct=0.1, regime_label="trend")
    assert not s.observe("ETH", 100.0, sigma_bar_pct=0.1, regime_label="trend")


def test_liq_label_flip_triggers_and_resets_cusum():
    s = _scs(3.0)
    assert s.observe("ETH", 100.0, sigma_bar_pct=0.1, liq_label="liquid")
    # accumulate 2 bars of drift (S+=0.002, below h=0.003) then flip the label:
    # the flip is the event AND must reset the sums (state changed)
    px = 100.0 * math.exp(0.001)
    assert not s.observe("ETH", px, sigma_bar_pct=0.1, liq_label="liquid")
    px *= math.exp(0.001)
    assert not s.observe("ETH", px, sigma_bar_pct=0.1, liq_label="liquid")
    px *= math.exp(0.001)
    assert s.observe("ETH", px, sigma_bar_pct=0.1, liq_label="thin")
    # post-reset: 0.002 more drift must NOT trigger (old S+ was wiped)
    px *= math.exp(0.001)
    assert not s.observe("ETH", px, sigma_bar_pct=0.1, liq_label="thin")
    px *= math.exp(0.001)
    assert not s.observe("ETH", px, sigma_bar_pct=0.1, liq_label="thin")


def test_none_to_label_transition_is_not_an_event():
    # detector warming up: bootstrap with no labels, first label seen later
    # is ADOPTED, never fired on (last-seen was None)
    s = _scs(3.0)
    assert s.observe("ETH", 100.0, sigma_bar_pct=0.1)          # bootstrap
    assert not s.observe("ETH", 100.0, sigma_bar_pct=0.1,
                         regime_label="range", liq_label="liquid")
    assert s.observe("ETH", 100.0, sigma_bar_pct=0.1,
                     regime_label="trend", liq_label="liquid")  # real flip


def test_per_asset_independence():
    s = _scs(3.0)
    assert s.observe("ETH", 100.0, sigma_bar_pct=0.1)
    assert s.observe("BTC", 50000.0, sigma_bar_pct=0.1)         # own bootstrap
    # drive ETH through an event; BTC's sums must stay untouched
    px = 100.0
    for _ in range(4):
        px *= math.exp(0.001)
        s.observe("ETH", px, sigma_bar_pct=0.1)
    assert not s.observe("BTC", 50000.0, sigma_bar_pct=0.1)     # still calm
    st = s._st["BTC"]
    assert st["sp"] == 0.0 and st["sn"] == 0.0


def test_disabled_always_true():
    s = _scs(enabled=False)
    assert all(s.observe("ETH", p, sigma_bar_pct=0.1)
               for p in [100.0, 100.0, 100.0, 100.01])
    assert s._st == {}                        # disabled keeps no state


def test_bad_prices_return_false_and_do_not_corrupt_state():
    s = _scs(3.0)
    # bad FIRST observation: no bootstrap, no state
    assert not s.observe("ETH", float("nan"), sigma_bar_pct=0.1)
    assert "ETH" not in s._st
    assert s.observe("ETH", 100.0, sigma_bar_pct=0.1)           # now bootstrap
    for bad in (float("nan"), float("inf"), 0.0, -5.0):
        assert not s.observe("ETH", bad, sigma_bar_pct=0.1)
    # baseline still 100: a +0.4% bar computes r off 100 and fires (S+ > h)
    assert s.observe("ETH", 100.0 * math.exp(0.004), sigma_bar_pct=0.1)


def test_sigma_fallback_without_sigma_bar_pct_stays_finite():
    # no sigma supplied -> internal EWMA of r^2; must stay deterministic and
    # never blow up on a calm path (bootstrap aside, flat = no events)
    s = _scs(3.0)
    assert s.observe("ETH", 100.0)
    assert not any(s.observe("ETH", 100.0) for _ in range(10))


# ---- main.py wiring contract (source pin) -----------------------------------

def test_main_observes_in_slow_cycle_loop_and_latches():
    # observe advances EVERY bar in the slow-cycle per-asset loop and the
    # result is latched into _scs_pending
    assert "self.scs.observe(asset, closes[asset]" in _MAIN
    assert "self._scs_pending[asset] = True" in _MAIN


def test_main_register_gated_by_latch_and_consumed():
    gate = 'if v.get("candles") and self._scs_pending.get(asset):'
    assert gate in _MAIN
    reg = _MAIN.index("self.candidates.register(asset, signal.direction")
    assert _MAIN.index(gate) < reg
    consume = _MAIN.index("self._scs_pending[asset] = False")
    # window covers the register call + its inline comments only (gate-truth
    # T3's gate_components arg grew the block past the original 700)
    assert reg < consume < reg + 900          # consumed right after register
    # and nothing else registers in between - the proximity claim, made
    # structural instead of purely char-counted
    assert "self.candidates.register(" not in _MAIN[reg + 1:consume]


def test_main_carries_the_unbiasedness_invariant_comment():
    # the sampler gates ONLY candidate registration; unbiasedness holds
    # because event times are independent of gate verdicts
    assert "event times are independent of gate verdicts" in _MAIN


# ---- config_guard bounds -----------------------------------------------------

def _sev(cfg, sev):
    return [m for s, m in validate(cfg) if s == sev]


def _cfg(k, enabled=True):
    return {"system": {"dry_run": True},
            "ml": {"sampling": {"cusum_enabled": enabled, "cusum_k": k}}}


def test_guard_cusum_k_bounds():
    assert any("cusum_k" in m for m in _sev(_cfg(0.5), "FATAL"))   # clock-ish
    assert any("cusum_k" in m for m in _sev(_cfg(7.0), "FATAL"))   # starves
    assert not any("cusum_k" in m for m in _sev(_cfg(3.0), "FATAL"))  # deployed
    assert not any("cusum_k" in m for m in _sev(_cfg(1.0), "FATAL"))  # edges ok
    assert not any("cusum_k" in m for m in _sev(_cfg(6.0), "FATAL"))
    assert not any("cusum_k" in m
                   for m in _sev(_cfg(0.5, enabled=False), "FATAL"))  # off


# --- reviewer fixes (same-day adversarial review) ----------------------------
def test_register_reports_append_vs_dedup(tmp_path):
    """The SCS latch may only be consumed by a REAL append: a same-candle
    dedup no-op returns False so the state-change lesson stays pending and
    registers at the next bar."""
    import numpy as np

    from ml.features import FEATURE_NAMES
    from ml.history import CandidateLabeler, HistoryStore
    hs = HistoryStore(str(tmp_path / "h.csv"))
    cb = CandidateLabeler(hs, {})
    f = np.zeros(len(FEATURE_NAMES))
    assert cb.register("ETH", "long", f, 0.003, 1000) is True
    assert cb.register("ETH", "long", f, 0.003, 1000) is False   # same candle
    assert cb.register("ETH", "long", f, 0.003, 1300) is True    # next bar


def test_guard_k_zero_is_fatal():
    # k=0 silently kills the price channel (h=0 never triggers) - the same
    # corpus starvation the k>6 bound exists to block; no carve-out
    from core.config_guard import validate
    cfg = {"system": {"dry_run": True},
           "ml": {"sampling": {"cusum_enabled": True, "cusum_k": 0.0}}}
    assert any("cusum_k" in m for sev, m in validate(cfg) if sev == "FATAL")


def test_ewma_alpha_lifted_to_config():
    from ml.event_sampler import StateChangeSampler
    s = StateChangeSampler({"cusum_enabled": True, "cusum_k": 3.0,
                            "ewma_alpha": 0.10})
    assert s._ewma_alpha == 0.10
    # identical default when absent; clamped against degenerate values
    assert StateChangeSampler({})._ewma_alpha == 0.06
    assert StateChangeSampler({"ewma_alpha": 5.0})._ewma_alpha == 0.5
