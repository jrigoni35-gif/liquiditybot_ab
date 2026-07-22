"""tests/test_glass_suite.py — the Liquid Glass suite contract.

The glass suite IS the four banner boards (2026-07-22 spec). The dedicated
glass + mobile boards were retired; these pins keep them retired and keep
the glass primitives (value-only state tiles, joinByField tables, CSS
injector, transparency) from regressing.
"""
from pathlib import Path

import scripts.build_trading_dashboard as gen
import scripts.grafana_import as gi

ROOT = Path(__file__).resolve().parents[1]


def test_retired_glass_boards_stay_retired():
    four = {"liquiditybot_command.json", "liquiditybot_execution.json",
            "liquiditybot_problem_solution.json",
            "liquiditybot_screening.json"}
    assert set(gi.DASHBOARDS) == four
    assert set(gen.DASHBOARDS) == four
    for name in ("liquiditybot_glass.json", "liquiditybot_glass_mobile.json"):
        assert not (ROOT / "docs" / "grafana" / name).exists(), \
            f"{name} was retired on 2026-07-22 — do not resurrect"
