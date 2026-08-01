"""config_guard coverage for the informed_flow (rev-3 fusion) engine and the
capital_management/position_sizer max-position-pct duplication.

Both gaps were found in a flow/parity audit: strategies.engine defaults to
"informed_flow" (config.json's shipped default), but config_guard previously
validated only the five_gate rollback's signal_gates.* section - the active
decision path had zero coherence checks. Separately, config_guard validated
capital_management.max_position_size_pct_of_capital, but that value is read
by risk/capital_manager.py's calculate_position_size, which is dead code -
never called from main.py. The value that actually caps a live entry is
position_sizer.max_position_size_pct_of_capital, read by
risk/position_sizer.py's PositionSizer (the real Kelly sizer). Nothing
enforced the two keys staying in sync.

AUDIT H10 UPDATE: the parity check was still defeatable, because it resolved
the sizer copy with the capital_management copy as its DEFAULT - so an ABSENT
sizer key could never differ from the value it was compared against. That is
not theoretical: the operator's 10 -> 25 raise (6e57ebd7) was deleted from
the position_sizer block by an unrelated commit (ae4b5314), the live entry cap
silently reverted to PositionSizer's 10.0 code default, and this check
reported clean throughout. The guard now resolves with a None sentinel;
test_max_position_pct_missing_sizer_copy_defaults_to_cap_mgmt below encoded
the OLD blindness as intended behaviour and has been rewritten accordingly
(see its own comment). Both keys ship at 25 in config.json.
"""
from core.config_guard import validate


def _cfg(**informed_flow_overrides):
    cfg = {"system": {"dry_run": True},
           "informed_flow": dict(informed_flow_overrides)}
    return cfg


def _warns(cfg):
    return [m for sev, m in validate(cfg) if sev == "WARN"]


def _fatals(cfg):
    return [m for sev, m in validate(cfg) if sev == "FATAL"]


def test_default_informed_flow_section_is_coherent():
    # config.json's shipped defaults (mirrored here) must not trip any of
    # the new checks
    cfg = _cfg(min_agree=3, evidence_threshold=1.15, flow_min=0.25,
               material_threshold=0.10, persistence_evals=3, fast_period=9,
               slow_period=21, absorption_move_sigmas=1.0,
               absorption_ad_min=0.15,
               weights={"flow": 1.0, "delta": 0.6, "accum": 0.9,
                        "burst": 0.8, "trend": 0.7})
    fatals = _fatals(cfg)
    assert not any("informed_flow" in m for m in fatals)


def test_min_agree_out_of_component_range_is_fatal():
    assert any("min_agree=6" in m and "must be in [1, 5]" in m
               for m in _fatals(_cfg(min_agree=6)))
    assert any("min_agree=0" in m for m in _fatals(_cfg(min_agree=0)))


def test_slow_period_not_above_fast_is_fatal():
    assert any("slow_period (9) must exceed fast_period (9)" in m
               for m in _fatals(_cfg(fast_period=9, slow_period=9)))


def test_negative_weight_warns_not_fatal():
    warns = _warns(_cfg(weights={"flow": -1.0}))
    assert any("negative entries" in m and "flow" in m for m in warns)
    assert not any("negative entries" in m
                  for m in _fatals(_cfg(weights={"flow": -1.0})))


def test_evidence_threshold_must_be_positive():
    assert any("evidence_threshold must be positive" in m
               for m in _fatals(_cfg(evidence_threshold=0.0)))


def test_flow_min_out_of_unit_range_is_fatal():
    assert any("flow_min=1.5" in m for m in _fatals(_cfg(flow_min=1.5)))


def test_material_threshold_out_of_unit_range_is_fatal():
    assert any("material_threshold=-0.1" in m
               for m in _fatals(_cfg(material_threshold=-0.1)))


def _cap_cfg(cap_mgmt_pct, sizer_pct):
    return {"system": {"dry_run": True},
            "capital_management": {
                "max_position_size_pct_of_capital": cap_mgmt_pct},
            "position_sizer": {
                "max_position_size_pct_of_capital": sizer_pct}}


def test_max_position_pct_mismatch_is_fatal():
    fatals = _fatals(_cap_cfg(10, 15))
    assert any("max_position_size_pct_of_capital mismatch" in m
               and "capital_management (10.0)" in m
               and "position_sizer (15.0)" in m for m in fatals)


def test_max_position_pct_match_is_not_flagged():
    fatals = _fatals(_cap_cfg(10, 10))
    assert not any("max_position_size_pct_of_capital mismatch" in m
                  for m in fatals)


def test_max_position_pct_missing_sizer_copy_is_fatal():
    # REWRITTEN for audit finding H10. This test previously asserted the
    # opposite ("_f defaults to the cap_mgmt value itself, so this must NOT
    # false-positive") and was named ..._defaults_to_cap_mgmt: it encoded the
    # OLD BUGGY behaviour - the blindness that let the sizer copy be deleted
    # from config.json for weeks while the parity FATAL reported clean and
    # live entries ran at PositionSizer's 10.0 code default instead of the
    # configured 25. A missing key is the exact failure this check exists to
    # catch, so "absent reads as parity" was never a property worth pinning.
    # The no-false-positive concern it was really guarding (a bare config
    # that sets neither key) is now covered by
    # test_max_position_pct_both_copies_absent_is_clean below.
    cfg = {"system": {"dry_run": True},
           "capital_management": {"max_position_size_pct_of_capital": 10}}
    assert any("position_sizer.max_position_size_pct_of_capital is MISSING"
               in m for m in _fatals(cfg))


def test_max_position_pct_both_copies_absent_is_clean():
    # neither key set = no operator decision to half-revert, and the two code
    # defaults (PositionSizer 10.0 / CapitalManager 10) agree - the sentinel
    # must not fire on partial/bare configs
    cfg = {"system": {"dry_run": True},
           "capital_management": {"max_concurrent_positions": 5}}
    assert not any("max_position_size_pct_of_capital" in m
                   for m in _fatals(cfg))
