"""CUT #11 — the COMMIT configuration (era-8). Pins.

The operator's objective: every trade must be able to end clearly positive or
negative. Three zero-makers that are not the model were removed - the hedger,
the alt-coin universe, and $18 probe tickets - and NOTHING else changed. These
pins hold that shape for the length of the era-8 run.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cfg():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------ the change
def test_universe_is_the_four_majors_only():
    """Alts are the measured loss channel (15/22 alt exits are stop-losses)."""
    pairs = _cfg()["exchanges"]["kraken"]["trading_pairs"]
    assert set(pairs) == {"PAXG/USD", "ETH/USD", "BTC/USD", "LINK/USD"}, pairs


def test_skimmer_is_off_so_the_universe_cannot_rewiden_at_boot():
    """runner.py merges outputs/skimmer_active.json into trading_pairs on
    every dry-run boot when the skimmer is enabled - the universe cut would
    silently undo itself."""
    assert _cfg()["skimmer"]["enabled"] is False


def test_hedger_is_off():
    """A hedge leg opens against the bet and cancels its outcome; 40% of all
    fees at taker rates. A hedged bet cannot end clearly positive or negative."""
    assert _cfg()["hedging"]["enabled"] is False


def test_probe_ticket_floor_is_sixty_dollars():
    """size_scale is clamped to [0.01, 1.0] (main.py) and was already 1.0;
    the probe sat on max(min_ticket_usd, min_order x 1.2) = $18. The floor
    is the only lever that makes an outcome dollars rather than cents."""
    assert _cfg()["position_sizer"]["min_ticket_usd"] == 60


def test_the_universe_change_took_effect_in_the_engine(monkeypatch):
    """The config says four pairs; the engine must SEE four - not the seven
    plus skimmer promotions the runner used to merge back in."""
    from runner import merge_skimmer_universe
    cfg = _cfg()
    merged = merge_skimmer_universe(cfg, str(ROOT / "outputs" / "skimmer_active.json"))
    assert merged == [], f"skimmer still widened the universe by {merged}"
    assert len(cfg["exchanges"]["kraken"]["trading_pairs"]) == 4


# --------------------------------------------------------- the untouched
def test_the_things_that_must_NOT_move_during_era_8_did_not():
    """Every one of these restarts the count if it moves. Values are the
    cut-#10 world as shipped, EXCEPT fees, which cut #12 (2026-09-08) moved
    to the account's real Tier 5 - held there by tests/test_cut12_fees.py."""
    c = _cfg()
    # Fees moved at cut #12 (2026-09-08, FEE-4: the account's real Tier 5,
    # 15/30) - era-8 closed there. The fee pin lives in tests/test_cut12_fees.py;
    # here only the shape that cut #11 owns is held.
    from core.venue_fees import is_a_published_row
    assert is_a_published_row(c["pretrade"]["maker_fee_bps"], c["pretrade"]["taker_fee_bps"])
    assert c["ml"]["label_pt_cost_mult"] == 4.0 and c["ml"]["label_pt_vol_mult"] == 8
    assert c["ml"]["label_sl_vol_mult"] == 6 and c["ml"]["label_max_bars"] == 432
    assert c["ml"]["exploration"]["admission"]["budget"]["tokens_per_day"] == 5.0
    assert c["ml"]["exploration"]["size_scale"] == 1.0
    assert c["profit_taking"]["time_stop"]["enabled"] is True
    assert c["profit_taking"]["give_back"]["enabled"] is True
    assert c["system"]["dry_run"] is True, "invariant 1: dry_run stays true"


# -------------------------------------------------------------- the stage
def test_stage_refuses_to_disable_the_hedger_over_an_open_hedge(tmp_path):
    """execution/hedging.py:171 returns NO actions when disabled - including
    unwinds - and a hedge leg is exempt from profit tiers. Disabling with a
    hedge open would strand it. The stage must refuse."""
    from scripts.cut11_stage import open_hedges
    st = tmp_path / "state.json"
    st.write_text(json.dumps({"portfolio": {"positions": {
        "a": {"symbol": "BTC/USD", "is_hedge": False},
        "b": {"symbol": "ETH/USD", "is_hedge": True}}}}), encoding="utf-8")
    assert open_hedges(st) == ["ETH/USD"]
    st.write_text(json.dumps({"portfolio": {"positions": {
        "a": {"symbol": "BTC/USD", "is_hedge": False}}}}), encoding="utf-8")
    assert open_hedges(st) == []


def test_stage_treats_missing_state_as_nothing_to_strand(tmp_path):
    from scripts.cut11_stage import open_hedges
    assert open_hedges(tmp_path / "absent.json") == []


# --------------------------------------------------------------- the stamp
def test_exec_era_was_minted_for_cut_11():
    from core.fill_ledger import EXEC_ERA
    m = re.match(r"^(\d+)-([0-9a-f]{8})$", EXEC_ERA)
    assert m, f"EXEC_ERA {EXEC_ERA!r} is not <cut>-<8hex>"
    assert int(m.group(1)) >= 11, (
        f"EXEC_ERA {EXEC_ERA!r} predates cut #11 - fills would be stamped as era-7")
