"""tests/test_conviction.py — Phase A Conviction Formula (Compounder):
the pure admission rule's unit contract. Four conjunctive terms, fixed
evaluation order, first failure names the registered CV-* code, no
fitted weights anywhere."""
from core.codes import Code
from risk.conviction import ConvictionFormula


def _f(**over):
    cfg = {"enabled": True, "mode": "report", "agreement_floor": 0.75,
           "ev_cost_mult": 2.0, "share_window": 8, "share_min_n": 4,
           "share_lo": 0.25, "share_hi": 0.75}
    cfg.update(over)
    return ConvictionFormula(cfg)


# a clean all-terms-pass input set reused across tests
PASS = dict(agreement=1.0, est_edge_bps=100.0, est_cost_bps=20.0,
            regime_known=True)


def test_cv_codes_registered_and_stable():
    assert Code.CV_ADMIT.value == "CV-000"
    assert Code.CV_AGREEMENT_LOW.value == "CV-010"
    assert Code.CV_EV_MULTIPLE_LOW.value == "CV-020"
    assert Code.CV_REGIME_UNKNOWN.value == "CV-030"
    assert Code.CV_CONTEXT_MISALIGNED.value == "CV-040"
    assert Code.CV_CADENCE_HIGH.value == "CV-050"
    assert Code.CV_CADENCE_LOW.value == "CV-051"


def test_all_terms_pass_admits_cv000():
    d = _f().evaluate(**PASS)
    assert d.admitted and d.code == Code.CV_ADMIT


def test_agreement_below_floor_denies():
    d = _f().evaluate(**{**PASS, "agreement": 0.74})
    assert not d.admitted and d.code == Code.CV_AGREEMENT_LOW


def test_agreement_at_floor_admits():
    assert _f().evaluate(**{**PASS, "agreement": 0.75}).admitted


def test_ev_below_multiple_denies():
    # cost 20 x mult 2.0 -> 40bps edge required; 39.9 fails
    d = _f().evaluate(**{**PASS, "est_edge_bps": 39.9})
    assert not d.admitted and d.code == Code.CV_EV_MULTIPLE_LOW


def test_ev_at_multiple_admits():
    assert _f().evaluate(**{**PASS, "est_edge_bps": 40.0}).admitted


def test_regime_unknown_denies():
    d = _f().evaluate(**{**PASS, "regime_known": False})
    assert not d.admitted and d.code == Code.CV_REGIME_UNKNOWN


def test_context_none_is_not_applicable_and_passes():
    # 5m book: no context engine yet — None means the term does not apply
    assert _f().evaluate(**PASS, context_aligned=None).admitted


def test_context_misaligned_denies_cv040():
    # long-book term (Phase C wires the call site); the formula itself
    # must already honor it so Phase C is a parameter, not a code change
    d = _f().evaluate(**PASS, context_aligned=False)
    assert not d.admitted and d.code == Code.CV_CONTEXT_MISALIGNED


def test_term_order_first_failure_names_the_code():
    d = _f().evaluate(agreement=0.0, est_edge_bps=0.0, est_cost_bps=20.0,
                      regime_known=False, context_aligned=False)
    assert d.code == Code.CV_AGREEMENT_LOW


def test_evaluate_is_pure_and_deterministic():
    f = _f()
    assert f.evaluate(**PASS) == f.evaluate(**PASS)


def test_decision_terms_carry_the_evidence():
    t = _f().evaluate(**PASS).terms
    assert t["agreement"] == 1.0 and t["agreement_floor"] == 0.75
    assert t["est_edge_bps"] == 100.0 and t["est_cost_bps"] == 20.0
    assert t["ev_cost_mult"] == 2.0 and t["regime_known"] is True


def test_enforce_only_when_enabled_and_mode_enforce():
    assert not _f().enforce                          # report mode
    assert not _f(mode="enforce", enabled=False).enforce
    assert _f(mode="enforce").enforce


# ---- Task 2: cadence governor ---------------------------------------

def test_governor_counts_and_status():
    f = _f()
    for _ in range(3):
        f.note(f.evaluate(**PASS), "range")
    f.note(f.evaluate(**{**PASS, "agreement": 0.0}), "trend_up")
    st = f.status()
    assert st["evaluated"] == 4 and st["admitted"] == 3
    assert st["denials"] == {"CV-010": 1}
    assert st["share"] == 0.75 and st["n"] == 4
    assert st["by_regime"]["range"] == {"share": 1.0, "n": 3}
    assert st["by_regime"]["trend_up"] == {"share": 0.0, "n": 1}


def test_cadence_alarm_suppressed_below_min_n():
    f = _f()                                  # share_min_n 4
    for _ in range(3):
        f.note(f.evaluate(**PASS), "range")
    assert f.cadence_alarms() == []


def test_cadence_alarm_high_fires_on_transition_only():
    f = _f()                                  # share_hi 0.75, window 8
    for _ in range(8):
        f.note(f.evaluate(**PASS), "range")
    alarms = f.cadence_alarms()
    assert any(c == Code.CV_CADENCE_HIGH for c, _ in alarms)
    assert f.cadence_alarms() == []           # steady state: no re-alarm
    assert f.status()["alarm"] == "high"


def test_cadence_alarm_low():
    f = _f()
    deny = {**PASS, "agreement": 0.0}
    for _ in range(8):
        f.note(f.evaluate(**deny), "range")
    assert any(c == Code.CV_CADENCE_LOW for c, _ in f.cadence_alarms())


def test_share_within_band_no_alarm():
    f = _f()                                  # band [0.25, 0.75]
    for i in range(8):
        d = f.evaluate(**(PASS if i % 2 else
                          {**PASS, "agreement": 0.0}))
        f.note(d, "range")
    assert f.cadence_alarms() == []
    assert f.status()["alarm"] == "ok"


def test_status_is_json_serializable():
    import json
    f = _f()
    f.note(f.evaluate(**PASS), "range")
    json.dumps(f.status())                    # raises on non-serializable
