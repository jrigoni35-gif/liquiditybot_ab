"""tests/test_lessons_digest.py — scripts/lessons_digest.py (TA-A1 + FinMem
retention tiers, docs/research/2026-07-24_compounder_context_evidence.md
pass-2 §2.5). Offline/deterministic/stdlib-only reporting script: NO engine
imports, no LLM, no network, missing inputs degrade to "no data" sections,
never raises. These tests exercise the pure `build_digest()` function
against small hand-built fixture directories (never the repo's real
outputs/), plus a source-pin that the script stays stdlib-only.
"""
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import lessons_digest as ld  # noqa: E402

_ROOT = Path(__file__).resolve().parents[1]

_NEWEST = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc).timestamp()
_DAY = 86400.0
_OLD = _NEWEST - 200 * _DAY   # well outside any 91-day trailing quarter

_POSTMORTEM_HEADER = ["ts", "position_id", "asset", "direction", "p_win",
                      "expected_pct", "realized_pct", "shortfall_pct",
                      "cause", "cost_overrun_bps", "mfe_pct", "mae_pct",
                      "recovered_after_stop", "regime_entry", "regime_exit"]


def _pm_row(ts, pid, asset, direction, cause, realized_pct, regime="range",
            **extra):
    row = {"ts": ts, "position_id": pid, "asset": asset,
           "direction": direction, "p_win": 0.62, "expected_pct": 0.2,
           "realized_pct": realized_pct, "shortfall_pct": 1.0,
           "cause": cause, "cost_overrun_bps": 30.0, "mfe_pct": 0.0,
           "mae_pct": -1.0, "recovered_after_stop": 0,
           "regime_entry": regime, "regime_exit": regime}
    row.update(extra)
    return row


def _write_postmortems(path: Path, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_POSTMORTEM_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _write_ledger(path: Path, header: list, rows: list) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------------------
# missing inputs -> "no data", never raises
# ---------------------------------------------------------------------------
def test_empty_outputs_dir_produces_no_data_and_does_not_raise(tmp_path):
    text = ld.build_digest(tmp_path)
    assert isinstance(text, str) and text
    assert "no data" in text.lower()
    assert "Traceback" not in text


def test_missing_postmortem_csv_only_reports_no_data_for_postmortems(
        tmp_path):
    _write_ledger(tmp_path / "weekly_ledger.csv",
                 ["week", "weekly_realized", "reserve_refill", "cash",
                  "savings", "reserve", "realized_total", "goal", "hit",
                  "category", "attainment_pct", "shortfall_usd",
                  "miss_reason"],
                 [["2026-W29", "12.5", "0.0", "5012.5", "10.0", "5.0",
                   "12.5", "25.0", "False", "shortfall", "50.0", "12.5",
                   "under target"]])
    text = ld.build_digest(tmp_path)
    assert "no data" in text.lower()          # postmortem section
    assert "shortfall" in text.lower()        # goal section still populated


def test_malformed_postmortem_row_is_skipped_not_raised(tmp_path):
    good = _pm_row(_NEWEST, "aaaaaaaa-1", "BTC", "long", "cost_overrun", -2.0)
    bad = dict(good, ts="not-a-timestamp", position_id="bad-row")
    _write_postmortems(tmp_path / "postmortem_summary.csv", [good, bad])
    text = ld.build_digest(tmp_path)
    assert "Traceback" not in text
    assert "bad-row" not in text
    assert "aaaaaaaa" in text


# ---------------------------------------------------------------------------
# tier 1: last-N verbatim, newest first, capped
# ---------------------------------------------------------------------------
def test_tier1_lists_newest_first_capped_at_default_n(tmp_path):
    rows = [_pm_row(_NEWEST - i * _DAY, f"{i:08d}-x", "BTC", "long",
                    "cost_overrun", -1.0) for i in range(12)]
    _write_postmortems(tmp_path / "postmortem_summary.csv", rows)
    text = ld.build_digest(tmp_path)
    btc_section = text.split("### BTC", 1)[1].split("### ", 1)[0]
    # exactly LAST_N_VERBATIM ids present, the newest ones (i=0..9), oldest
    # two (i=10,11) excluded from the verbatim tier. Rendering truncates
    # position_id to its first 8 chars (short-id convention), which for
    # this fixture's "%08d-x" ids is exactly the zero-padded number.
    for i in range(ld.LAST_N_VERBATIM):
        assert f"{i:08d}" in btc_section
    for i in range(ld.LAST_N_VERBATIM, 12):
        assert f"{i:08d}-x" not in btc_section
    # newest-first ordering
    pos0 = btc_section.index("00000000")
    pos1 = btc_section.index("00000001")
    assert pos0 < pos1


# ---------------------------------------------------------------------------
# tier 2 + tier 3: aggregates
# ---------------------------------------------------------------------------
def test_tier2_trailing_quarter_and_tier3_all_time_aggregates(tmp_path):
    rows = [
        _pm_row(_NEWEST, "r1", "BTC", "long", "cost_overrun", -2.0),
        _pm_row(_NEWEST - 1 * _DAY, "r2", "BTC", "long", "cost_overrun", 1.0),
        _pm_row(_NEWEST - 2 * _DAY, "r3", "BTC", "short", "alpha_wrong", -1.5),
        _pm_row(_OLD, "r4", "BTC", "long", "cost_overrun", -3.0),
    ]
    _write_postmortems(tmp_path / "postmortem_summary.csv", rows)
    text = ld.build_digest(tmp_path)
    btc_section = text.split("### BTC", 1)[1].split("### ", 1)[0]

    # tier 2 (trailing quarter: r1, r2, r3 only - r4 is 200d old)
    assert "cost_overrun" in btc_section.split("Tier 2")[1].split("Tier 3")[0]
    assert "1/3" in btc_section or "33.3%" in btc_section
    assert "-2.50" in btc_section       # net of r1+r2+r3 = -2.0+1.0-1.5

    # tier 3 (all-time: all 4 rows)
    tier3 = btc_section.split("Tier 3", 1)[1]
    assert "n=4" in tier3
    assert "-5.50" in tier3             # net of all four


def test_hit_rate_counts_positive_realized_pct_only(tmp_path):
    rows = [
        _pm_row(_NEWEST, "r1", "ETH", "long", "alpha_wrong", 2.0),
        _pm_row(_NEWEST - 1 * _DAY, "r2", "ETH", "long", "alpha_wrong", -1.0),
    ]
    _write_postmortems(tmp_path / "postmortem_summary.csv", rows)
    text = ld.build_digest(tmp_path)
    eth_section = text.split("### ETH", 1)[1].split("### ", 1)[0]
    tier2 = eth_section.split("Tier 2")[1].split("Tier 3")[0]
    assert "1/2" in tier2 or "50.0%" in tier2


def test_dominant_cause_tie_break_is_deterministic_alphabetical(tmp_path):
    rows = [
        _pm_row(_NEWEST, "r1", "BTC", "long", "zzz_cause", -1.0),
        _pm_row(_NEWEST - 1 * _DAY, "r2", "BTC", "long", "aaa_cause", -1.0),
    ]
    _write_postmortems(tmp_path / "postmortem_summary.csv", rows)
    text1 = ld.build_digest(tmp_path)
    text2 = ld.build_digest(tmp_path)
    assert text1 == text2               # deterministic given a tie
    btc_section = text1.split("### BTC", 1)[1].split("### ", 1)[0]
    tier2 = btc_section.split("Tier 2")[1].split("Tier 3")[0]
    assert "aaa_cause" in tier2          # alphabetically-first tie winner


# ---------------------------------------------------------------------------
# grouping: per asset AND per regime, independently
# ---------------------------------------------------------------------------
def test_grouped_by_both_asset_and_regime_sections_present(tmp_path):
    rows = [
        _pm_row(_NEWEST, "r1", "BTC", "long", "cost_overrun", -1.0,
               regime="range"),
        _pm_row(_NEWEST - 1 * _DAY, "r2", "ETH", "long", "alpha_wrong", -1.0,
               regime="bull_quiet"),
    ]
    _write_postmortems(tmp_path / "postmortem_summary.csv", rows)
    text = ld.build_digest(tmp_path)
    assert "## By asset" in text
    assert "### BTC" in text and "### ETH" in text
    assert "## By regime" in text
    assert "### range" in text and "### bull_quiet" in text


# ---------------------------------------------------------------------------
# goal ledger + governor sections
# ---------------------------------------------------------------------------
def test_goal_section_reports_latest_week_and_month_row(tmp_path):
    _write_ledger(tmp_path / "weekly_ledger.csv",
                 ["week", "weekly_realized", "reserve_refill", "cash",
                  "savings", "reserve", "realized_total", "goal", "hit",
                  "category", "attainment_pct", "shortfall_usd",
                  "miss_reason"],
                 [["2026-W28", "5.0", "0.0", "5005.0", "1.0", "0.5", "5.0",
                   "25.0", "False", "shortfall", "20.0", "20.0",
                   "under target"],
                  ["2026-W29", "30.0", "0.0", "5035.0", "3.0", "1.5", "35.0",
                   "25.0", "True", "hit", "120.0", "0.0", ""]])
    _write_ledger(tmp_path / "monthly_ledger.csv",
                 ["month", "monthly_realized", "cash", "savings", "reserve",
                  "realized_total", "goal", "hit", "category",
                  "attainment_pct", "shortfall_usd", "miss_reason"],
                 [["2026-06", "-5.0", "4995.0", "1.0", "0.5", "-5.0",
                   "110.0", "False", "loss", "0.0", "115.0",
                   "realized loss"]])
    text = ld.build_digest(tmp_path)
    goal_section = text.split("## Goal attainment", 1)[1].split("## ", 1)[0]
    assert "2026-W29" in goal_section and "hit" in goal_section
    assert "2026-W28" not in goal_section       # latest row only, not all
    assert "2026-06" in goal_section and "loss" in goal_section


def test_goal_section_no_data_when_ledgers_missing(tmp_path):
    text = ld.build_digest(tmp_path)
    goal_section = text.split("## Goal attainment", 1)[1].split("## ", 1)[0]
    assert "no data" in goal_section.lower()


def test_governor_section_reads_session_digest_when_present(tmp_path):
    (tmp_path / "session_digest.json").write_text(json.dumps({
        "generated_at": _NEWEST,
        "model": {"monitor_level": 2, "use_model": True, "brier": 0.19,
                  "history_rows": 500, "cold": False},
    }), encoding="utf-8")
    text = ld.build_digest(tmp_path)
    gov = text.split("## Governor", 1)[1].split("## ", 1)[0]
    assert "level 2" in gov.lower() or "monitor_level: 2" in gov.lower() \
        or "2" in gov


def test_governor_section_no_data_when_session_digest_missing(tmp_path):
    text = ld.build_digest(tmp_path)
    gov = text.split("## Governor", 1)[1].split("## ", 1)[0]
    assert "no data" in gov.lower()


# ---------------------------------------------------------------------------
# determinism: same inputs -> byte-identical output, no wall-clock leakage
# ---------------------------------------------------------------------------
def test_byte_identical_across_reruns(tmp_path):
    rows = [_pm_row(_NEWEST - i * _DAY, f"id{i}", "BTC", "long",
                    "cost_overrun", -1.0) for i in range(5)]
    _write_postmortems(tmp_path / "postmortem_summary.csv", rows)
    a = ld.build_digest(tmp_path)
    b = ld.build_digest(tmp_path)
    assert a == b


def test_no_timestamp_beyond_newest_input_row(tmp_path, monkeypatch):
    """The digest must never stamp real wall-clock time anywhere in its
    output - only the newest INPUT row's own timestamp."""
    rows = [_pm_row(_NEWEST, "id0", "BTC", "long", "cost_overrun", -1.0)]
    _write_postmortems(tmp_path / "postmortem_summary.csv", rows)
    before = ld.build_digest(tmp_path)
    # advancing the wall clock must not change a single byte of the output
    import time as _time
    real_time = _time.time
    monkeypatch.setattr(_time, "time", lambda: real_time() + 999999)
    after = ld.build_digest(tmp_path)
    assert before == after


# ---------------------------------------------------------------------------
# no engine imports; stdlib-only; never raises on any input shape
# ---------------------------------------------------------------------------
def test_source_pin_stdlib_only_no_engine_imports():
    """AST-based (not substring) so prose in the module docstring/comments
    ('nothing from main.py, ...') can't false-positive this pin."""
    import ast
    src = (_ROOT / "scripts" / "lessons_digest.py").read_text(
        encoding="utf-8")
    tree = ast.parse(src)
    banned_roots = {"main", "runner", "core", "ml", "execution", "risk",
                    "data", "sentiment", "api", "requests", "urllib",
                    "socket", "http"}
    stdlib_allowed = {"argparse", "csv", "json", "collections", "datetime",
                      "pathlib", "typing", "sys", "ast", "__future__"}
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_roots.add(node.module.split(".")[0])
    assert not (imported_roots & banned_roots), (
        f"forbidden imports: {imported_roots & banned_roots}")
    assert imported_roots <= stdlib_allowed, (
        f"non-stdlib import(s): {imported_roots - stdlib_allowed}")


def test_cli_writes_lessons_digest_md(tmp_path):
    rows = [_pm_row(_NEWEST, "id0", "BTC", "long", "cost_overrun", -1.0)]
    _write_postmortems(tmp_path / "postmortem_summary.csv", rows)
    rc = ld.main(["--outputs-dir", str(tmp_path)])
    assert rc == 0
    out = tmp_path / "lessons_digest.md"
    assert out.exists()
    assert "id0" in out.read_text(encoding="utf-8")


def test_script_runnable_as_subprocess_against_a_fixture_dir(tmp_path):
    rows = [_pm_row(_NEWEST, "id0", "BTC", "long", "cost_overrun", -1.0)]
    _write_postmortems(tmp_path / "postmortem_summary.csv", rows)
    result = subprocess.run(
        [sys.executable, str(_ROOT / "scripts" / "lessons_digest.py"),
         "--outputs-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "lessons_digest.md").exists()
