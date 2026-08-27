"""OF-5 trial-count ratchet: measured N can only DEEPEN deflation.

Spec [SEV-2]: n_trials_eff = max(configured, measured). No ledger or an
invalid ledger ≡ today's behavior, and the source line always names the
world OF-5 ran in — a green is only as big as its corpus."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.overfit_check import resolve_dsr_trials  # noqa: E402
from scripts.trial_ledger import append_rows  # noqa: E402


def _battery_row(strategy_id, profile="neutral-admission"):
    return {"schema_version": 1, "strategy_id": strategy_id,
            "source": "battery", "seed": 1, "fee_anchor": "booked",
            "harness_profile": profile, "cycles": 60, "entries": 2,
            "exits": 1, "gross_pct": 0.1, "net_pct": 0.0, "sr": "",
            "max_dd": "", "n_eff": "", "degenerate": False,
            "exit_profile": "deployed", "count": 1}


def test_no_ledger_is_configured_verbatim(tmp_path):
    n, line = resolve_dsr_trials(7, tmp_path / "absent.csv")
    assert n == 7
    assert "no ledger" in line and "assumed" in line


def test_measured_below_configured_cannot_relax(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    append_rows([_battery_row("a"), _battery_row("b")], p)   # measured N=2
    n, line = resolve_dsr_trials(7, p)
    assert n == 7
    assert "measured N=2" in line and "ratchet holds configured 7" in line


def test_measured_above_configured_deepens(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    rows = [_battery_row(f"s{i}") for i in range(9)]
    rows.append({**_battery_row("harvested"), "source": "harvest",
                 "fee_anchor": "n/a", "harness_profile": "n/a", "count": 57})
    append_rows(rows, p)
    n, line = resolve_dsr_trials(7, p)
    assert n == 9 + 57
    assert "measured N=66" in line


def test_invalid_ledger_falls_back_loudly(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    p.write_text("garbage,header\n1,2\n", encoding="utf-8")
    n, line = resolve_dsr_trials(7, p)
    assert n == 7
    assert "INVALID" in line


def test_unreadable_ledger_falls_back_loudly(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    p.write_bytes(b"\xff\xfe\x00garbage")
    n, line = resolve_dsr_trials(7, p)
    assert n == 7
    assert "INVALID" in line or "unreadable" in line


def test_directory_ledger_falls_back_loudly(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    p.mkdir()
    n, line = resolve_dsr_trials(7, p)
    assert n == 7
    assert "INVALID" in line or "unreadable" in line
