"""Batch 3 of verified findings, 2026-09-07 (SAFE). Each CONFIRMED by execution
in the 47-finding verification pass (`docs/quant/2026-09-07_verified_findings_
register_47.md`), each pin mutation-checked.

  h7   main.py               ARM LIVE gate had NO pytest pin (neutering it
                             reddened 0 of 2,027 tests). Pinned at the gate.
  h5   core/fill_ledger.py   width guard one-directional -> ragged rows; the
                             live 17-col ledger silently lost `book` on every
                             fill with no counter.
  h44  scripts/auto_update.py deploy-gate bandit scanned 82 files; the DoD law
                             scans 195. Planted B602 x7: gate saw 2, law 14.
  h41  scripts/auto_update.py a red HARD gate whose last line said "cannot
                             find" was `continue`d -> deploy ADMITTED.
  h31  scripts/pc_supervisor.py self-handoff inherited its own log handle and
                             overwrote the exit-forensics line (2/2).
  h18  scripts/cost_attribution.py ratio literal 65.0 printed x1.182; labels
                             three struck schedules deep.
  h19  9 scripts             naive local timestamps in report provenance
                             (read 00:13Z, stamped 19:13).
"""
from __future__ import annotations

import ast
import csv
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


# -------------------------------------------------------------------- h7
def _bot():
    from main import LiquidityBot
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    cfg["system"]["dry_run"] = True
    for k in ("sentiment", "webdata", "moomoo"):
        cfg[k]["enabled"] = False
    cfg["system"]["record_feeds"] = False
    return LiquidityBot(cfg, kraken=SimpleNamespace(kraken_pair=lambda s: "XETHZUSD"),
                        resume=False)


def test_arm_live_gate_blocks_new_risk_when_disarmed_in_live_mode():
    """INVARIANT #1's runtime gate, pinned under pytest for the first time.
    Neutering `_live_order_allowed` to `return True` reddened NOTHING in the
    suite (measured: 0 of 2,027); the only real pin lived in smoke_test.
    The INSTANCE flag is flipped, never the config (invariant 1)."""
    bot = _bot()
    bot.dry_run = False
    bot.live_armed = False
    assert bot._live_order_allowed("entry") is False, "disarmed live entry ALLOWED"
    assert bot._live_order_allowed("hedge") is False, "disarmed live hedge ALLOWED"


def test_exits_are_ALWAYS_allowed_even_disarmed():
    """Invariant #5: kill switches block new risk, never escapes."""
    bot = _bot()
    bot.dry_run = False
    bot.live_armed = False
    assert bot._live_order_allowed("exit") is True


def test_arming_opens_the_gate_and_dry_run_is_unaffected():
    bot = _bot()
    bot.dry_run = False
    bot.live_armed = True
    assert bot._live_order_allowed("entry") is True
    bot.dry_run = True
    bot.live_armed = False
    assert bot._live_order_allowed("entry") is True, "dry-run must be unaffected"


# -------------------------------------------------------------------- h5
def _row(**kw):
    r = {"ts": 1.0, "order_id": "o1", "position_id": "p", "purpose": "entry",
         "symbol": "BTC/USD", "side": "buy", "ordertype": "limit",
         "post_only": True, "attempt": 1, "fill_size": 1.0, "fill_price": 100.0,
         "arrival_ref": 100.0, "slip_bps": 0.0, "fees_delta_usd": 0.02,
         "remaining": 0.0, "reason": "", "exec_era": "t", "book": "5m"}
    r.update(kw)
    return r


def _widths(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [len(r) for r in csv.reader(f)]


def test_a_file_with_an_unknown_column_never_gets_a_ragged_row(tmp_path):
    """The old guard adopted the header only when it was a subset of COLS;
    any unknown column fell through to an 18-col write. Measured before the
    fix: widths [18,18,18,17] -> RAGGED True."""
    import core.fill_ledger as FL
    path = tmp_path / "fills.csv"
    hdr = list(FL.COLS) + ["zzz_future_col"]
    path.write_text(",".join(hdr) + "\n", encoding="utf-8")
    FL._seen_keys.pop(str(path), None)
    FL.append_fill(path, _row(order_id="a"))
    FL.append_fill(path, _row(order_id="b"))
    w = _widths(path)
    assert len(set(w)) == 1, f"ragged widths {w}"
    assert w[0] == len(hdr)


def test_a_narrow_ledger_drops_fields_VISIBLY(tmp_path, caplog):
    """The live ledger is 17 columns; `book` has been lost on every fill
    since 39f36e49 with no counter and no log line."""
    import logging

    import core.fill_ledger as FL
    path = tmp_path / "fills.csv"
    narrow = [c for c in FL.COLS if c != "book"]
    path.write_text(",".join(narrow) + "\n", encoding="utf-8")
    FL._seen_keys.pop(str(path), None)
    FL._width_warned.discard(str(path))
    before = FL.fields_dropped
    with caplog.at_level(logging.WARNING):
        FL.append_fill(path, _row(order_id="a"))
        FL.append_fill(path, _row(order_id="b"))
    assert FL.fields_dropped == before + 2, "dropped fields are not counted"
    assert any("book" in r.getMessage() and "NOT persisted" in r.getMessage()
               for r in caplog.records), "the loss is still silent"
    assert set(_widths(path)) == {len(narrow)}, "row width must match the file"


def test_a_full_width_ledger_drops_nothing(tmp_path):
    """ANTI-RUBBER-STAMP: the counter must be silent when nothing is lost."""
    import core.fill_ledger as FL
    path = tmp_path / "fills.csv"
    FL._seen_keys.pop(str(path), None)
    before = FL.fields_dropped
    FL.append_fill(path, _row(order_id="a"))          # creates at full width
    FL.append_fill(path, _row(order_id="b"))
    assert FL.fields_dropped == before
    assert set(_widths(path)) == {len(FL.COLS)}


# ------------------------------------------------------------------- h44
def test_deploy_gate_bandit_scans_what_the_law_scans():
    """auto_update's bandit gate listed six packages (82 files, 26k LOC);
    CLAUDE.md's DoD is `-r . -x ./.venv,./tests` (195 files, 67k). Seven
    planted B602s: the gate saw 2, the law 14 - main.py, runner.py, regime/,
    sentiment/, strategies/, scripts/ were all outside the deploy gate."""
    import scripts.auto_update as au
    argv = dict(au._HARD_GATES)["bandit"]
    assert "-r" in argv and argv[argv.index("-r") + 1] == ".", (
        f"deploy bandit argv does not scan the tree root: {argv}")
    assert "./tests" in " ".join(argv), "the law excludes ./tests; mirror it"


# ------------------------------------------------------------------- h41
def _canned(rc, tail, missing):
    return lambda *a, **k: (rc, tail, missing)


def test_a_red_HARD_gate_with_a_cannot_find_needle_is_REFUSED(monkeypatch):
    """Measured with the real _run_gate: rc=1 + last line 'cannot find' ->
    missing=True -> `continue` -> deploy admitted. A library
    FileNotFoundError is the realistic path."""
    import scripts.auto_update as au
    monkeypatch.setattr(au, "_run_gate", _canned(
        1, "FileNotFoundError: [WinError 2] The system cannot find the file", True))
    monkeypatch.setattr(au, "log", lambda *a, **k: None)
    assert au._dod_gates(Path("."), "py") is False, (
        "a red HARD gate was waved through on a 'cannot find' needle")


def test_a_genuinely_absent_tool_is_still_advisory(monkeypatch):
    """ANTI-RUBBER-STAMP: `python -m bandit` with bandit not installed must
    stay advisory (the interpreter's own 'No module named'), as must a shell
    command-not-found (rc 127 / 9009)."""
    import scripts.auto_update as au
    assert au._hard_gate_tool_absent(["-m", "bandit", "-q"], 1,
                                     "ModuleNotFoundError: No module named 'bandit'")
    assert au._hard_gate_tool_absent(["-m", "ruff", "check"], 9009, "'ruff' is not recognized")
    assert au._hard_gate_tool_absent(["-m", "ruff", "check"], 127, "ruff: command not found")
    assert not au._hard_gate_tool_absent(["scripts/smoke_test.py"], 1, "cannot find"), (
        "a script gate runs under this interpreter; its tool cannot be absent")
    assert not au._hard_gate_tool_absent(["-m", "bandit"], 1,
                                         "assert x == 'cannot find it'"), (
        "a needle in an assertion message is not a missing tool")


# ------------------------------------------------------------------- h31
def test_supervisor_self_handoff_keeps_its_own_log():
    """The successor must not inherit the parent's log handle."""
    tree = ast.parse((ROOT / "scripts/pc_supervisor.py").read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_spawn":
            src = ast.unparse(node)
            if "_SELF" in src:
                hits.append((src, {k.arg: ast.unparse(k.value) for k in node.keywords}))
    assert hits, "no self-handoff _spawn found"
    for src, kw in hits:
        assert kw.get("own_log") == "False", (
            f"self-handoff spawns with an inherited log handle: {src}")


# ------------------------------------------------------------------- h18
def test_cost_attribution_ratio_and_labels_are_derived():
    import scripts.cost_attribution as ca
    src = (ROOT / "scripts/cost_attribution.py").read_text(encoding="utf-8")
    assert "65.0 / (KRAKEN_T1_MAKER_BPS" not in src, "the struck 65.0 literal is back"
    for struck in ('"configured (25/40)"', '"Kraken T1 maker/taker (40/80)"',
                   '"Kraken T5 maker/maker (15/15)"'):
        assert struck not in src, f"struck label literal present: {struck}"
    bm, bt = ca._booked_fees()
    assert (bm + bt) / (ca.KRAKEN_T1_MAKER_BPS + ca.KRAKEN_T1_TAKER_BPS) == pytest.approx(1.0), (
        "tool schedule has drifted from the booked schedule")


# ------------------------------------------------------------------- h19
def test_report_provenance_timestamps_are_utc_aware():
    """read 00:13Z, stamped 19:13 - a -5h skew that reads as a different day
    after 19:00 local. One site is DELIBERATELY naive (it computes the local
    offset) and is exempt by name."""
    naive = re.compile(r"datetime\.now\(\)|datetime\.fromtimestamp\([^,)]*\)")
    exempt = {"scripts/disposition_integrity_report.py"}
    bad = []
    for rel in ("scripts/kyle_lambda.py", "scripts/ledger_continuity.py",
                "scripts/markout_report.py", "scripts/outputs_gc.py",
                "scripts/cut10_stage.py", "scripts/fee_correction_stage.py",
                "scripts/boundary5_stage.py"):
        if rel in exempt:
            continue
        for i, line in enumerate((ROOT / rel).read_text(encoding="utf-8").splitlines(), 1):
            if naive.search(line) and "timezone.utc" not in line:
                bad.append(f"{rel}:{i}")
    assert not bad, f"naive local timestamps in report provenance: {bad}"
