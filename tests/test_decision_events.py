# tests/test_decision_events.py
"""DE-010 pins: capture shape, absorb tagging, hourly batch, EN-000 recon."""
import json
from types import SimpleNamespace
from pathlib import Path

from core.audit import configure_audit
from main import LiquidityBot, load_config
from scripts.smoke_test import MockBinanceUS, MockKraken, MockOKX

_ROOT = Path(__file__).resolve().parents[1]


def _bot(tmp_path):
    cfg = load_config(str(_ROOT / "config.json"))
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["context"]["enabled"] = False
    cfg["long_book"]["enabled"] = False
    configure_audit(tmp_path / "audit.jsonl")
    return LiquidityBot(cfg, okx=MockOKX({"ETH": 2000.0, "BTC": 60000.0}),
                        binanceus=MockBinanceUS({"ETH": 2000.0, "BTC": 60000.0}),
                        kraken=MockKraken({"ETH": 2000.0, "BTC": 60000.0}),
                        resume=False)


def test_de_event_mid_from_book():
    v = {"order_book": {"bids": [[1999.0, 1.0]], "asks": [[2001.0, 1.0]]}}
    ev = LiquidityBot._de_event("ETH", v, 1_700_000_000.0)
    assert ev["decision_mid"] == "2000" and ev["mid_available"] is True
    # Lane C: born carrying the key; deterministic policy ⇒ propensity 1.0
    assert ev["propensity"] == 1.0
    ev2 = LiquidityBot._de_event("ETH", {"order_book": {"bids": [], "asks": []}},
                                 1_700_000_000.0)
    assert ev2["decision_mid"] == "" and ev2["mid_available"] is False
    assert "propensity" in ev2


def test_arrivals_buffered_and_batched_hourly(tmp_path):
    bot = _bot(tmp_path)
    bot.gates.evaluate_asset = lambda asset, v: SimpleNamespace(
        direction=None, all_confirmed=False, confidence=0.5,
        gates_passed={"rsi": True}, urgency=0.0,
        evidence_concentration=0.0, components={})
    t = 1_700_000_000.0
    bot.slow_cycle(t)
    n_arrivals = bot.entry_absorb_status()["arrivals"]
    assert len(bot._de_events) == n_arrivals
    assert all(e["absorb"] == "EN-030" for e in bot._de_events)
    assert all("propensity" in e for e in bot._de_events)
    bot._flush_decision_events(t + 3601.0)   # past the hourly gate
    recs = [json.loads(line) for line in
            (tmp_path / "audit.jsonl").read_text().splitlines()]
    de = [r for r in recs if r["code"] == "DE-010"]
    assert len(de) == 1
    assert len(de[0]["data"]["events"]) == n_arrivals   # EN-000 reconciliation
    assert bot._de_events == []


def test_passed_gate_stack_absorb_tag(tmp_path, monkeypatch):
    # chdir: a confirmed signal can reach order placement even in dry_run;
    # keep any ledger/state-file writes out of the repo tree (same harness
    # discipline as tests/test_context_integration.py).
    monkeypatch.chdir(tmp_path)
    bot = _bot(tmp_path)
    # shipped config has signal_gates.learned_weights.enabled=true: the
    # cold-start naive fraction of an ALL-PASS gates_passed dict is 1.0 and
    # would overwrite confidence before the capture site. The pin targets
    # the capture-site coercion, not the shading pipeline, so stub the
    # shaper off (same double discipline as evaluate_asset below); thales
    # shadow-mode + the disabled concentration shade leave 0.61 untouched.
    bot.gate_stats.enabled = False
    bot.gates.evaluate_asset = lambda asset, v: SimpleNamespace(
        direction="long", all_confirmed=True, confidence=0.61,
        gates_passed={"rsi": True, "mom": True}, urgency=0.0,
        evidence_concentration=0.0, components={})
    bot.slow_cycle(1_700_000_000.0)
    assert bot._de_events, "confirmed signals must buffer a DE-010 event"
    for e in bot._de_events:
        assert e["absorb"] == "passed_gate_stack"
        assert e["direction"] == "long"
        assert e["confidence"] == 0.61
        assert "propensity" in e


def test_en020_open_entry_absorb_tag(tmp_path):
    bot = _bot(tmp_path)
    bot.orders.has_open = lambda *a, **k: True   # force the EN-020 branch
    bot.slow_cycle(1_700_000_000.0)
    assert bot._de_events, "open-entry arrivals must buffer a DE-010 event"
    assert all(e["absorb"] == "EN-020" for e in bot._de_events)
