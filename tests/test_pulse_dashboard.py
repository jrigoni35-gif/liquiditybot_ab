"""tests/test_pulse_dashboard.py — the Pulse stays RETIRED as a board.

Operator decision 2026-07-23 ("integrate it with my 4 boards, not a new
one"): the board family stays at FOUR, and the standalone
`liquiditybot-pulse` uid that shipped once is deleted on every import run.

The Pulse hero COMPOSITION that used to live on the Command board (the
Business Text hero, the native equity strip, the truth rows) was deleted
wholesale when every visualization panel was stripped from all four
boards, so its content pins are gone from this file — git history holds
them for whoever rebuilds the boards.

What survives here is the part that is not a panel at all: the board
registry's shape, the retired-uid cleanup, and the shared nav built by
`gen._links()`. Those hold on an empty board and must keep holding, or a
fifth board silently re-appears and the retired uid comes back from the
dead on the next import.
"""
from pathlib import Path

import scripts.build_trading_dashboard as gen
import scripts.grafana_import as gi

ROOT = Path(__file__).resolve().parents[1]


# ---- placement: the family stays at four boards -----------------------------
def test_no_standalone_pulse_board_anywhere():
    assert "liquiditybot_pulse.json" not in gen.DASHBOARDS, \
        "the family stays at FOUR boards — Pulse is a Command composition"
    assert "liquiditybot_pulse.json" not in gi.DASHBOARDS
    assert not (ROOT / "docs" / "grafana" / "liquiditybot_pulse.json").exists()
    assert len(gi.DASHBOARDS) == 4


def test_standalone_pulse_uid_is_retired_on_import():
    # the uid shipped once (2026-07-23) — the import run must delete it
    assert "liquiditybot-pulse" in gi.RETIRED_UIDS


def test_pulse_absent_from_shared_nav():
    for d in gen.DASHBOARDS.values():
        nav = {ln["url"] for ln in d["links"]}
        assert "/d/liquiditybot-pulse" not in nav, \
            f'{d["uid"]}: nav still links the retired standalone board'
        assert len(nav) == 4, f'{d["uid"]}: nav must list exactly the 4 boards'
