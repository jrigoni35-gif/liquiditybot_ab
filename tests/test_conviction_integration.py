"""tests/test_conviction_integration.py — engine-seam contract for the
Phase A conviction formula (_conviction_disposition): report mode is
byte-identical (never skips), enforce mode returns the denial code,
probes are exempt, the T4 regime floor feeds term 3. Runs off a minimal
LiquidityBot.__new__() stub (the established entry-path test pattern —
see _record_probe_admission's docstring)."""
import types

from core.codes import Code
from main import LiquidityBot
from risk.conviction import ConvictionFormula


class _Hist:
    def __init__(self, live):
        self._live = live

    def regime_live_count(self, regime_label):
        return self._live


def _bot(mode="report", live=100, floor=60, enabled=True):
    bot = LiquidityBot.__new__(LiquidityBot)
    bot.conviction = ConvictionFormula(
        {"enabled": enabled, "mode": mode, "agreement_floor": 0.75,
         "ev_cost_mult": 2.0, "share_window": 8, "share_min_n": 4,
         "share_lo": 0.25, "share_hi": 0.75})
    bot._regime_floor_live = floor
    bot.history = _Hist(live)
    return bot


def _signal(gates=None):
    s = types.SimpleNamespace()
    s.gates_passed = {"g1": True, "g2": True, "g3": True,
                      "g4": True} if gates is None else gates
    return s


def _decision(edge=100.0, cost=20.0):
    return types.SimpleNamespace(est_edge_bps=edge, est_cost_bps=cost)


def test_report_mode_never_skips_even_on_denial():
    bot = _bot(mode="report")
    deny = bot._conviction_disposition(
        "BTC", _signal({"g1": False, "g2": False, "g3": False,
                        "g4": True}), _decision(), "range", False)
    assert deny is None                    # denied but report: proceed
    assert bot.conviction.status()["denials"] == {"CV-010": 1}


def test_enforce_mode_returns_denial_code():
    bot = _bot(mode="enforce")
    deny = bot._conviction_disposition(
        "BTC", _signal(), _decision(edge=10.0, cost=20.0), "range", False)
    assert deny == Code.CV_EV_MULTIPLE_LOW


def test_enforce_mode_admits_clean_entry():
    assert _bot(mode="enforce")._conviction_disposition(
        "BTC", _signal(), _decision(), "range", False) is None


def test_probe_exempt_and_unnoted():
    bot = _bot(mode="enforce")
    assert bot._conviction_disposition(
        "BTC", _signal({"g1": False}), _decision(edge=0.0), "range",
        True) is None
    assert bot.conviction.status()["evaluated"] == 0


def test_disabled_formula_is_inert():
    bot = _bot(enabled=False)
    assert bot._conviction_disposition(
        "BTC", _signal(), _decision(), "range", False) is None
    assert bot.conviction.status()["evaluated"] == 0


def test_under_covered_regime_denies_in_enforce():
    bot = _bot(mode="enforce", live=10, floor=60)
    assert bot._conviction_disposition(
        "BTC", _signal(), _decision(), "range", False) == \
        Code.CV_REGIME_UNKNOWN


def test_unmapped_regime_label_denies_in_enforce():
    # a label outside REGIME_LABELS has no evidence bucket: unknown
    bot = _bot(mode="enforce")
    assert bot._conviction_disposition(
        "BTC", _signal(), _decision(), "never_a_regime", False) == \
        Code.CV_REGIME_UNKNOWN


def test_regime_floor_zero_disables_term():
    bot = _bot(mode="enforce", live=0, floor=0)
    assert bot._conviction_disposition(
        "BTC", _signal(), _decision(), "range", False) is None


def test_empty_gates_dict_reads_as_zero_agreement():
    bot = _bot(mode="enforce")
    assert bot._conviction_disposition(
        "BTC", _signal({}), _decision(), "range", False) == \
        Code.CV_AGREEMENT_LOW


def test_missing_stub_attrs_self_heal():
    bot = LiquidityBot.__new__(LiquidityBot)   # no conviction attr at all
    assert bot._conviction_disposition(
        "BTC", _signal(), _decision(), "range", False) is None


def test_status_shape():
    bot = _bot()
    bot._conviction_disposition("BTC", _signal(), _decision(), "range",
                                False)
    st = bot.conviction.status()
    assert {"enabled", "mode", "evaluated", "admitted", "denials",
            "share", "n", "by_regime", "alarm"} <= set(st)
