"""Tests for monitor/flow_transfers.py — decode, pairing, hub ranking (offline)."""

from __future__ import annotations

import base64
import json

import pytest

from monitor import flow_transfers as ft


def cdc(fields: dict) -> str:
    """Build a JSON-CDC event payload the way the access node encodes it."""
    fs = []
    for name, (typ, val) in fields.items():
        if typ == "Optional":
            inner = None if val is None else {"type": "Address", "value": val}
            fs.append({"name": name, "value": {"type": "Optional", "value": inner}})
        else:
            fs.append({"name": name, "value": {"type": typ, "value": val}})
    doc = {
        "value": {"id": "A.f233dcee88fe0abe.FungibleToken.Deposited", "fields": fs},
        "type": "Event",
    }
    return base64.b64encode(json.dumps(doc).encode()).decode()


def test_decode_payload_unwraps_optionals_and_keeps_strings():
    p = cdc(
        {
            "type": ("String", ft.FLOW_VAULT),
            "amount": ("UFix64", "4449.74728000"),
            "to": ("Optional", "0xf919ee77447b7497"),
            "balanceAfter": ("UFix64", "1.0"),
        }
    )
    d = ft.decode_payload(p)
    assert d["type"] == ft.FLOW_VAULT
    assert d["amount"] == "4449.74728000"
    assert d["to"] == "0xf919ee77447b7497"
    assert ft.decode_payload(cdc({"to": ("Optional", None)}))["to"] is None


def rows_for(tx, ts, frm, to, amt, fb=0.0, tb=0.0):
    return [
        {
            "height": 1,
            "ts": ts,
            "tx": tx,
            "kind": "Withdrawn",
            "amt": amt,
            "addr": frm,
            "bal": fb,
        },
        {
            "height": 1,
            "ts": ts,
            "tx": tx,
            "kind": "Deposited",
            "amt": amt,
            "addr": to,
            "bal": tb,
        },
    ]


def test_pair_transfers_matches_equal_amounts_within_tx():
    rows = rows_for(
        "t1", "2026-09-07T12:00:00Z", "0xaaa", "0xbbb", 1_700_000, 5e6, 2.7e7
    )
    rows += rows_for("t2", "2026-09-07T13:00:00Z", "0xccc", "0xbbb", 40_000)
    # a fee-only withdrawal with no matching deposit must not pair
    rows.append(
        {
            "height": 2,
            "ts": "2026-09-07T14:00:00Z",
            "tx": "t3",
            "kind": "Withdrawn",
            "amt": 9_999,
            "addr": "0xddd",
            "bal": 1,
        }
    )
    xf = ft.pair_transfers(rows)
    assert [(x["from"], x["to"], x["amt"]) for x in xf] == [
        ("0xaaa", "0xbbb", 1_700_000),
        ("0xccc", "0xbbb", 40_000),
    ]
    assert xf[0]["to_bal"] == 2.7e7


def test_hub_stats_ranks_by_counterparties_then_balance():
    rows = []
    for i, src in enumerate(("0x1", "0x2", "0x3")):
        rows += rows_for(
            f"t{i}", f"2026-09-07T0{i}:00:00Z", src, "0xhub", 10_000 + i, 0, 45e6
        )
    rows += rows_for("t9", "2026-09-07T09:00:00Z", "0xhub", "0x9", 5_000, 45e6, 5_000)
    hubs = ft.hub_stats(ft.pair_transfers(rows))
    top = hubs[0]
    assert top["addr"] == "0xhub"
    assert top["counterparties"] == 4
    assert top["nin"] == 3 and top["nout"] == 1
    assert top["net"] == pytest.approx(30_003 - 5_000)
    assert top["balance"] == 45e6


def test_daily_flows_nets_in_minus_out_per_day():
    rows = rows_for("a", "2026-09-06T10:00:00Z", "0xx", "0xhub", 100)
    rows += rows_for("b", "2026-09-06T11:00:00Z", "0xhub", "0xy", 30)
    rows += rows_for("c", "2026-09-07T11:00:00Z", "0xz", "0xhub", 7)
    d = ft.daily_flows(ft.pair_transfers(rows), ["0xhub"])
    assert d["2026-09-06"]["0xhub"] == pytest.approx(70)
    assert d["2026-09-06"]["total"] == pytest.approx(130)
    assert d["2026-09-07"]["0xhub"] == pytest.approx(7)


def test_report_offline_shape():
    rows = rows_for("a", "2026-09-06T10:00:00Z", "0xx", "0xhub", 100)
    rep = ft.report(rows, 24, 50)
    assert rep["transfers"] == 1 and rep["total_flow"] == 100
    assert rep["hubs"][0]["addr"] in {"0xhub", "0xx"}
    json.dumps(rep)


def test_get_refuses_non_flow_host(monkeypatch):
    monkeypatch.setattr(ft, "REST", "https://evil.example/v1")
    with pytest.raises(ValueError):
        ft._get("blocks?height=sealed")
