"""CUT #12 — FEE-4, the row the account actually holds (era-9). Pins.

The operator's 2026-09-08 Kraken-app reading: Tier 5, 30-day spot volume
$69,652.65, assets on platform $822.24 -> maker 15 / taker 30 bps. Cut #10's
E1 had booked 20/35 (Tier 4) on a legacy ladder. These pins hold the shape
for the length of the era-9 run.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _cfg():
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------ the change
def test_fees_are_the_account_s_tier_5_row():
    c = _cfg()
    assert (c["pretrade"]["maker_fee_bps"], c["pretrade"]["taker_fee_bps"]) == (15.0, 30.0)
    assert (c["order_manager"]["maker_fee_bps"], c["order_manager"]["taker_fee_bps"]) == (15.0, 30.0)
    assert c["profit_taking"]["est_fee_bps"] == 30
    assert c["ml"]["label_round_trip_cost_pct"] == pytest.approx(0.45)
    assert c["pretrade"]["allow_sub_floor_fees"] is True, "15/30 sits below the Tier-1 tripwire on purpose"


def test_the_booked_row_is_what_the_venue_binds_at_the_operators_reading():
    """Not a literal: the row must be what core.venue_fees resolves from the
    reading that justified the cut, and must be a published tier."""
    from core.venue_fees import binding_row, is_a_published_row
    from scripts.cut12_stage import READING
    c = _cfg()
    booked = (c["pretrade"]["maker_fee_bps"], c["pretrade"]["taker_fee_bps"])
    assert is_a_published_row(*booked)
    assert binding_row(READING["volume_30d_usd"], aop_usd=READING["aop_usd"]) == booked


def test_the_reading_reproduces_the_apps_next_tier_distances():
    """The app said '30,348.35 more spot volume or 199,178.76 more AoP to the
    next tier'. The table must reproduce both to the cent - that is the
    third route on the ladder and the AoP column."""
    from core.venue_fees import KRAKEN_SPOT_AOP_USD, KRAKEN_SPOT_SCHEDULE
    from scripts.cut12_stage import READING
    vols = [r[0] for r in KRAKEN_SPOT_SCHEDULE]
    i = max(k for k, v in enumerate(vols) if READING["volume_30d_usd"] >= v)
    assert (vols[i + 1] + 1) - READING["volume_30d_usd"] == pytest.approx(30_348.35, abs=0.01)
    assert (KRAKEN_SPOT_AOP_USD[i + 1] + 1) - READING["aop_usd"] == pytest.approx(199_178.76, abs=0.01)


# --------------------------------------------------------- the untouched
def test_the_things_that_must_NOT_move_during_era_9_did_not():
    c = _cfg()
    assert set(c["exchanges"]["kraken"]["trading_pairs"]) == {"PAXG/USD", "ETH/USD", "BTC/USD", "LINK/USD"}
    assert c["skimmer"]["enabled"] is False and c["hedging"]["enabled"] is False
    assert c["position_sizer"]["min_ticket_usd"] == 60
    assert c["ml"]["label_pt_cost_mult"] == 4.0 and c["ml"]["label_pt_vol_mult"] == 8
    assert c["ml"]["label_sl_vol_mult"] == 6 and c["ml"]["label_max_bars"] == 432
    assert c["ml"]["exploration"]["admission"]["budget"]["tokens_per_day"] == 5.0
    assert c["profit_taking"]["time_stop"]["enabled"] is True
    assert c["profit_taking"]["give_back"]["enabled"] is True
    assert c["risk_protocols"]["heat"]["max_portfolio_heat_frac"] == 0.35, "operator: wait it out"
    assert c["system"]["dry_run"] is True, "invariant 1: dry_run stays true"


# -------------------------------------------------------------- the stage
def test_stage_refuses_when_the_world_moved():
    from scripts.cut12_stage import EDITS, drifted
    world = _cfg()
    # after --apply every key sits at TO, so FROM no longer matches: the
    # stage must refuse a second application rather than re-cut.
    assert drifted(world), "the stage would re-apply on an already-cut config"
    pre = json.loads(json.dumps(world))
    for key, frm, _to in EDITS:
        cur = pre
        parts = key.split(".")
        for p in parts[:-1]:
            cur = cur[p]
        cur[parts[-1]] = frm
    assert drifted(pre) == []


def test_stage_to_row_is_tier_5_and_the_cascade_is_consistent():
    from scripts.cut12_stage import EDITS
    to = {k: t for k, _f, t in EDITS}
    assert (to["pretrade.maker_fee_bps"], to["pretrade.taker_fee_bps"]) == (15.0, 30.0)
    assert to["order_manager.maker_fee_bps"] == to["pretrade.maker_fee_bps"]
    assert to["order_manager.taker_fee_bps"] == to["pretrade.taker_fee_bps"]
    assert to["profit_taking.est_fee_bps"] == to["pretrade.taker_fee_bps"]
    assert to["ml.label_round_trip_cost_pct"] == pytest.approx(
        (to["pretrade.maker_fee_bps"] + to["pretrade.taker_fee_bps"]) / 100.0)


def _tmp_config(tmp_path, mutate=None):
    """A copy of the SHIPPED config to drive main() against; `mutate` edits it."""
    cfg = _cfg()
    if mutate:
        mutate(cfg)
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    return p


def _run_main(monkeypatch, cfg_path, *argv):
    import sys
    import scripts.cut12_stage as st
    monkeypatch.setattr(st, "CONFIG", cfg_path)
    monkeypatch.setattr(sys, "argv", ["cut12_stage.py", *argv])
    return st.main()


def _set(cfg, dotted, value):
    cur = cfg
    parts = dotted.split(".")
    for p in parts[:-1]:
        cur = cur[p]
    cur[parts[-1]] = value


def _pre_cut(cfg):
    from scripts.cut12_stage import EDITS
    for key, frm, _to in EDITS:
        _set(cfg, key, frm)


def test_main_refuses_a_second_apply_and_writes_nothing(tmp_path, monkeypatch, capsys):
    """The stage is single-shot: against the already-cut live config every
    FROM has drifted, so --apply must refuse (rc 2), leave the file
    byte-identical, and create no backup."""
    p = _tmp_config(tmp_path)
    before = p.read_text(encoding="utf-8")
    assert _run_main(monkeypatch, p, "--apply") == 2
    assert p.read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob("config.json.pre-cut12-*"))
    assert "DRIFTED" in capsys.readouterr().out


def test_main_applies_once_on_the_pre_cut_world(tmp_path, monkeypatch, capsys):
    from scripts.cut12_stage import EDITS
    p = _tmp_config(tmp_path, _pre_cut)
    assert _run_main(monkeypatch, p, "--apply") == 0
    after = json.loads(p.read_text(encoding="utf-8"))
    for key, _frm, to in EDITS:
        cur = after
        for part in key.split("."):
            cur = cur[part]
        assert cur == to, key
    assert len(list(tmp_path.glob("config.json.pre-cut12-*"))) == 1, "one backup"
    assert "0.6642 -> 0.6381" in capsys.readouterr().out


def test_main_refuses_when_the_reading_binds_a_different_row(tmp_path, monkeypatch, capsys):
    import scripts.cut12_stage as st
    p = _tmp_config(tmp_path, _pre_cut)
    monkeypatch.setitem(st.READING, "volume_30d_usd", 30_000.0)   # Tier 4 -> 20/35
    assert _run_main(monkeypatch, p, "--apply") == 2
    assert "not what the schedule binds" in capsys.readouterr().out
    assert not list(tmp_path.glob("config.json.pre-cut12-*"))


def test_main_refuses_an_incoherent_cascade(tmp_path, monkeypatch, capsys):
    """Fees moved, label cost not: the half-applied-stage hazard."""
    import scripts.cut12_stage as st
    p = _tmp_config(tmp_path, _pre_cut)
    edits = [(k, f, (0.55 if k == "ml.label_round_trip_cost_pct" else t)) for k, f, t in st.EDITS]
    monkeypatch.setattr(st, "EDITS", edits)
    assert _run_main(monkeypatch, p, "--apply") == 2
    assert "incoherent" in capsys.readouterr().out
    assert not list(tmp_path.glob("config.json.pre-cut12-*"))


# --------------------------------------------------------------- the stamp
def test_exec_era_was_minted_for_cut_12():
    """The literal is held by tests/test_fill_ledger_provenance.py; this pin
    holds the ORDER (>= 12) and, since the record commit is known, the sha
    itself - so a stamp naming any other commit reads red here too."""
    from core.fill_ledger import EXEC_ERA
    m = re.match(r"^(\d+)-([0-9a-f]{8})$", EXEC_ERA)
    assert m, f"EXEC_ERA {EXEC_ERA!r} is not <cut>-<8hex>"
    assert int(m.group(1)) >= 12, (
        f"EXEC_ERA {EXEC_ERA!r} predates cut #12 - fills would be stamped as era-8")
    assert EXEC_ERA == "12-10d4d0c2", "the cut #12 record commit, committed alone and first"
