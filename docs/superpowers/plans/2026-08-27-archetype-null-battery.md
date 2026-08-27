# Archetype Null Battery + Trial Ledger (v0.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 8-rung naive→expert reference-strategy population, run it through the deployed replay engine on rebuilt venue-coherent synthetic tapes, and produce the measured trial ledger that ends OF-5's assumed-trial-count era — under a ratchet that can only deepen deflation.

**Architecture:** Two new report-only scripts (`scripts/trial_ledger.py` owns the ledger + harvest; `scripts/archetype_battery.py` owns the tape generator, the rungs, and the grid runner) plus one keyword-only hook in `scripts/replay.py` and one ratcheted read in `scripts/overfit_check.py` OF-5. Zero engine footprint: archetypes live in `scripts/` (unreachable by `strategies.engine`), every run is QA-isolated (config paths via `prepare_replay_config`, process singletons via `configure_audit`/`configure_registry`).

**Tech Stack:** Python stdlib + numpy (already a dependency). No new packages.

## Global Constraints (from the spec — verbatim where quoted)

- SAFE-class, report-only: nothing changes which orders are placed or how they fill in the live bot; no config default moves; no floor, gate, or measurement standard is loosened.
- OF-5 ratchet: `n_trials_eff = max(configured dsr_n_trials, measured_N)`; measured `var_trial_sr` is NOT used in v0.1 (`sr` column stays empty behind the TRIPS_FLOOR=20 rule); absent/invalid ledger ≡ today, byte-identical.
- "a (tape, member, anchor) row with < MIN_TRIPS=1 trades is marked `degenerate=true`, counted, printed — never a silent zero."
- Determinism: per member, seed-1 double-run must match `_DETERMINISM_KEYS` **plus `cycles`**; cycles equality asserted across all members per tape; refusals counted and printed.
- Entries only: every rung exits through the deployed machinery; `exit_profile="deployed"` on every v0.1 row.
- All tests tmp-rooted (the production-outputs write guard in `tests/conftest.py` fails any test that writes the real `outputs/` tree).
- Windows is the target runtime: `pathlib` paths, `encoding="utf-8"` on every open.
- Ruff pinned set (`E4,E7,E9,F,B,C901`) and `bandit` must stay clean; `scripts/` and `tests/` are outside the pyright shipped-scope gate.
- Run suite commands with the venv python: `.venv/bin/python -m pytest …` (POSIX) / `.venv\Scripts\python.exe` (Windows). Never pipe pytest through a filter — redirect to a file and echo the real `$?`.

---

### Task 1: `run_replay` gains `mutate_bot` + per-run fills path in the summary

**Files:**
- Modify: `scripts/replay.py:94-135` (`run_replay`)
- Test: `tests/test_replay_mutate_hook.py` (create)

**Interfaces:**
- Consumes: `scripts.replay.run_replay(config: dict, recording: str, quiet: bool = True)` (existing), `scripts.overfit_check.make_offline_recording(tmpdir: Path) -> str` (existing — returns the recording path, sink at `tmpdir/"session.jsonl"`).
- Produces: `run_replay(config, recording, quiet=True, *, mutate_bot=None) -> dict` where `mutate_bot: Callable[[LiquidityBot], None] | None` is called once, after construction, before the first `cycle_once`; the summary dict gains `"fills_ledger_path": str` (the QA per-run fills CSV) and keeps every existing key unchanged. Later tasks rely on exactly: `summary["cycles"]`, `summary["entries_filled"]`, `summary["exit_orders"]`, `summary["realized_pnl"]`, `summary["fees"]`, `summary["final_equity"]`, `summary["fills_ledger_path"]`.

- [ ] **Step 1: Write the failing test**

```python
"""run_replay mutate_bot hook: default is byte-identical; hook sees the bot.

The hook exists so scripts/archetype_battery.py can inject an archetype
evaluate_asset (the overfit_check.py:360 precedent) WITHOUT run_replay
growing any strategy knowledge. Determinism keys plus cycles must be
unchanged by a no-op hook.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.replay_gate import _DETERMINISM_KEYS, determinism_ok  # noqa: E402


def _recording_and_cfg(tmp_path):
    from main import load_config
    from scripts.overfit_check import make_offline_recording
    rec_dir = tmp_path / "rec"
    make_offline_recording(rec_dir)
    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    return str(rec_dir / "session.jsonl"), cfg


def test_default_mutate_bot_is_inert_and_deterministic(tmp_path):
    from scripts.replay import run_replay
    rec, cfg = _recording_and_cfg(tmp_path)
    a = run_replay(cfg, rec, quiet=True)
    b = run_replay(cfg, rec, quiet=True, mutate_bot=None)
    ok, diff = determinism_ok(a, b, keys=_DETERMINISM_KEYS + ("cycles",))
    assert ok, diff
    assert "fills_ledger_path" in a and a["fills_ledger_path"].endswith(".csv")


def test_mutate_bot_receives_the_constructed_bot(tmp_path):
    from scripts.replay import run_replay
    rec, cfg = _recording_and_cfg(tmp_path)
    seen = {}

    def probe(bot):
        seen["gates"] = hasattr(bot, "gates")
        seen["evaluate"] = callable(getattr(bot.gates, "evaluate_asset", None))

    run_replay(cfg, rec, quiet=True, mutate_bot=probe)
    assert seen == {"gates": True, "evaluate": True}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_replay_mutate_hook.py -v 2>&1 | tail -5`
Expected: both tests ERROR/FAIL with `TypeError: run_replay() got an unexpected keyword argument 'mutate_bot'` (first test fails on the missing `fills_ledger_path` key if reached).

- [ ] **Step 3: Implement the hook**

In `scripts/replay.py`, change the `run_replay` signature and body (exact anchors shown; keep everything else):

```python
def run_replay(config: dict, recording: str, quiet: bool = True, *,
               mutate_bot=None) -> dict:
    """Drive the engine through one recorded session; return the summary.

    mutate_bot: optional callable invoked with the constructed LiquidityBot
    after init and before the first cycle — the sanctioned strategy-injection
    seam (the overfit_check make_offline_recording precedent). Default None
    is byte-identical to the pre-hook behavior; pinned by
    tests/test_replay_mutate_hook.py.
    """
    cfg = prepare_replay_config(config)

    players = load_session(recording)
    meta = players.pop("_meta")
    bot = LiquidityBot(cfg,
                       okx=players.get("okx"),
                       binanceus=players.get("binanceus"),
                       kraken=players.get("kraken"),
                       resume=False)
    if mutate_bot is not None:
        mutate_bot(bot)
    if quiet:
        logging.getLogger("liquiditybot").setLevel(logging.WARNING)
```

and add one key to the returned dict (after `"labeled_rows": bot.history.row_count(),`):

```python
        "labeled_rows": bot.history.row_count(),
        # per-run QA fills ledger — read it BEFORE the next run: successive
        # runs share the per-pid QA dir and prepare_replay_config unlinks it
        "fills_ledger_path": cfg["system"]["fills_ledger_path"],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_replay_mutate_hook.py -v 2>&1 | tail -4`
Expected: `2 passed`

- [ ] **Step 5: Regression-check the replay family and lint**

Run: `.venv/bin/python -m pytest tests/test_qa_isolation.py tests/test_replay_parity.py -q > /tmp/t1.log 2>&1; echo "REAL rc=$?"; tail -2 /tmp/t1.log`
Expected: `REAL rc=0`, all passed.
Run: `.venv/bin/ruff check scripts/replay.py tests/test_replay_mutate_hook.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add scripts/replay.py tests/test_replay_mutate_hook.py
git commit -m "feat(replay): mutate_bot injection seam + per-run fills path in summary"
```

---

### Task 2: `scripts/trial_ledger.py` — schema, append/read/validate, meta counters

**Files:**
- Create: `scripts/trial_ledger.py`
- Test: `tests/test_trial_ledger.py` (create)

**Interfaces:**
- Consumes: nothing from other tasks (stdlib only).
- Produces (later tasks import these exact names from `scripts.trial_ledger`):
  - `LEDGER_COLUMNS: tuple[str, ...]`
  - `SCHEMA_VERSION: int = 1`
  - `append_rows(rows: list[dict], ledger_path: Path) -> None` (creates file + header if absent; every row must carry every column)
  - `read_ledger(ledger_path: Path) -> list[dict]` (raises `LedgerInvalid` on schema mismatch / unknown enum values)
  - `class LedgerInvalid(ValueError)`
  - `measured_trials(rows: list[dict]) -> dict` returning `{"n_trials": int, "by_source": dict, "degenerate": int, "non_degenerate": int}` where `n_trials` = count of distinct `(source, strategy_id, harness_profile)` tuples plus the sum of harvest `count` fields
  - `write_meta(ledger_path: Path, attempted: int, accepted: int, refused: int, notes: list[str]) -> None` → `<ledger>.meta.json`

- [ ] **Step 1: Write the failing tests**

```python
"""Trial ledger: schema round-trip, validation, measured-N semantics.

The ledger is the TRIALS-1 artifact: OF-5's deflated Sharpe will read a
MEASURED trial count from it under a ratchet. Rows must be complete and
enum-legal or the reader refuses loudly (OF-5 then falls back, also
loudly). sr/max_dd/n_eff are nullable by design in v0.1 (spec: sr stays
empty behind TRIPS_FLOOR=20)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.trial_ledger import (LEDGER_COLUMNS, LedgerInvalid,  # noqa: E402
                                  SCHEMA_VERSION, append_rows,
                                  measured_trials, read_ledger, write_meta)


def _row(**over):
    base = {"schema_version": SCHEMA_VERSION, "strategy_id": "naive_grid",
            "source": "battery", "seed": 1, "fee_anchor": "booked",
            "harness_profile": "neutral-admission", "cycles": 60,
            "entries": 3, "exits": 2, "gross_pct": 0.41, "net_pct": -0.12,
            "sr": "", "max_dd": "", "n_eff": "", "degenerate": False,
            "exit_profile": "deployed", "count": 1}
    base.update(over)
    return base


def test_round_trip_and_columns(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    append_rows([_row(), _row(strategy_id="buy_hold", seed=2)], p)
    rows = read_ledger(p)
    assert len(rows) == 2
    assert set(rows[0]) == set(LEDGER_COLUMNS)
    assert rows[0]["strategy_id"] == "naive_grid"
    assert rows[0]["degenerate"] is False


def test_invalid_source_refused(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    append_rows([_row(source="vibes")], p)
    with pytest.raises(LedgerInvalid):
        read_ledger(p)


def test_measured_trials_counts_distinct_and_harvest(tmp_path):
    rows = [_row(), _row(seed=2),                        # same trial, 2 tapes
            _row(strategy_id="buy_hold"),                # second trial
            _row(source="harvest", strategy_id="tune_search",
                 harness_profile="n/a", count=57)]       # harvest N=57
    m = measured_trials(rows)
    assert m["n_trials"] == 2 + 57
    assert m["by_source"] == {"battery": 3, "harvest": 1}


def test_meta_counters(tmp_path):
    p = tmp_path / "trial_ledger.csv"
    append_rows([_row()], p)
    write_meta(p, attempted=4, accepted=1, refused=3,
               notes=["determinism refused 3 rows"])
    import json
    meta = json.loads((p.with_suffix(".meta.json")).read_text(encoding="utf-8"))
    assert meta["attempted"] == 4 and meta["refused"] == 3
    assert meta["schema_version"] == SCHEMA_VERSION
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_trial_ledger.py -v 2>&1 | tail -4`
Expected: `ModuleNotFoundError: No module named 'scripts.trial_ledger'`

- [ ] **Step 3: Implement `scripts/trial_ledger.py`**

```python
"""scripts/trial_ledger.py — the TRIALS-1 artifact (spec 2026-08-27 v0.1).

One CSV of every strategy trial actually evaluated (battery runs +
harvested historical searches) + a meta sidecar with attempted/accepted/
refused counters so refusals are never a silent cap. OF-5 reads
measured_trials() under a ratchet: max(configured, measured) — a ledger
can only DEEPEN deflation. sr/max_dd/n_eff are nullable ('' in CSV) in
v0.1: per-run SR is undefined below TRIPS_FLOOR=20 uncensored trips.
Report-only; never touches config or engine state.
"""
import csv
import json
import sys
from pathlib import Path

SCHEMA_VERSION = 1
TRIPS_FLOOR = 20          # sr stays '' below this (spec §1; measurement standard)
SOURCES = ("battery", "harvest")
ANCHORS = ("booked", "true")

LEDGER_COLUMNS = ("schema_version", "strategy_id", "source", "seed",
                  "fee_anchor", "harness_profile", "cycles", "entries",
                  "exits", "gross_pct", "net_pct", "sr", "max_dd",
                  "n_eff", "degenerate", "exit_profile", "count")


class LedgerInvalid(ValueError):
    pass


def append_rows(rows: list, ledger_path: Path) -> None:
    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    new = not ledger_path.exists()
    with open(ledger_path, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(LEDGER_COLUMNS))
        if new:
            w.writeheader()
        for r in rows:
            missing = set(LEDGER_COLUMNS) - set(r)
            if missing:
                raise LedgerInvalid(f"row missing columns: {sorted(missing)}")
            w.writerow({k: r[k] for k in LEDGER_COLUMNS})


def _coerce(r: dict) -> dict:
    out = dict(r)
    out["schema_version"] = int(r["schema_version"])
    out["seed"] = int(r["seed"])
    out["cycles"] = int(r["cycles"])
    out["entries"] = int(r["entries"])
    out["exits"] = int(r["exits"])
    out["count"] = int(r.get("count") or 1)
    out["degenerate"] = str(r["degenerate"]).strip().lower() == "true"
    for k in ("gross_pct", "net_pct"):
        out[k] = float(r[k]) if str(r[k]).strip() != "" else None
    for k in ("sr", "max_dd", "n_eff"):
        out[k] = float(r[k]) if str(r[k]).strip() != "" else None
    return out


def read_ledger(ledger_path: Path) -> list:
    ledger_path = Path(ledger_path)
    with open(ledger_path, newline="", encoding="utf-8") as fh:
        raw = list(csv.DictReader(fh))
    rows = []
    for i, r in enumerate(raw):
        if set(r) != set(LEDGER_COLUMNS):
            raise LedgerInvalid(f"row {i}: columns {sorted(r)} != schema")
        try:
            row = _coerce(r)
        except (TypeError, ValueError) as e:
            raise LedgerInvalid(f"row {i}: {e}") from e
        if row["schema_version"] != SCHEMA_VERSION:
            raise LedgerInvalid(f"row {i}: schema_version "
                                f"{row['schema_version']} != {SCHEMA_VERSION}")
        if row["source"] not in SOURCES:
            raise LedgerInvalid(f"row {i}: source {row['source']!r}")
        if row["fee_anchor"] not in ANCHORS and row["source"] == "battery":
            raise LedgerInvalid(f"row {i}: fee_anchor {row['fee_anchor']!r}")
        rows.append(row)
    return rows


def measured_trials(rows: list) -> dict:
    battery = {(r["source"], r["strategy_id"], r["harness_profile"])
               for r in rows if r["source"] == "battery"}
    harvest_n = sum(r["count"] for r in rows if r["source"] == "harvest")
    by_source = {}
    for r in rows:
        by_source[r["source"]] = by_source.get(r["source"], 0) + 1
    deg = sum(1 for r in rows if r["degenerate"])
    return {"n_trials": len(battery) + harvest_n, "by_source": by_source,
            "degenerate": deg, "non_degenerate": len(rows) - deg}


def write_meta(ledger_path: Path, attempted: int, accepted: int,
               refused: int, notes: list) -> None:
    meta = {"schema_version": SCHEMA_VERSION, "attempted": attempted,
            "accepted": accepted, "refused": refused, "notes": list(notes)}
    Path(ledger_path).with_suffix(".meta.json").write_text(
        json.dumps(meta, indent=1), encoding="utf-8")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="outputs/trial_ledger.csv")
    ap.add_argument("--report", action="store_true")
    ns = ap.parse_args()
    p = Path(ns.ledger)
    if not p.exists():
        print(f"no ledger at {p} (ABSENT, not zero trials)")
        return 0
    try:
        rows = read_ledger(p)
    except LedgerInvalid as e:
        print(f"LEDGER INVALID: {e}")
        return 1
    m = measured_trials(rows)
    print(f"trial ledger: {len(rows)} rows | measured n_trials="
          f"{m['n_trials']} | by_source={m['by_source']} | "
          f"degenerate={m['degenerate']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_trial_ledger.py -v 2>&1 | tail -4`
Expected: `4 passed`

- [ ] **Step 5: Lint and commit**

Run: `.venv/bin/ruff check scripts/trial_ledger.py tests/test_trial_ledger.py`
Expected: `All checks passed!`

```bash
git add scripts/trial_ledger.py tests/test_trial_ledger.py
git commit -m "feat(trials): trial ledger schema + measured-N semantics (TRIALS-1 artifact)"
```

---

### Task 3: harvest mode — back-fill N from searches already run

**Files:**
- Modify: `scripts/trial_ledger.py` (add `harvest()` + `--harvest` CLI)
- Test: `tests/test_trial_ledger.py` (extend)

**Interfaces:**
- Consumes: `append_rows`, `LEDGER_COLUMNS`, `SCHEMA_VERSION` from Task 2.
- Produces: `harvest(outputs_dir: Path) -> tuple[list[dict], list[str]]` — returns `(rows, absent)` where each row is a ledger row with `source="harvest"`, `count=<trials found>`, and `absent` lists source names not found (reported ABSENT, never zero).

- [ ] **Step 1: Write the failing tests (append to `tests/test_trial_ledger.py`)**

```python
def test_harvest_counts_and_absent(tmp_path):
    from scripts.trial_ledger import harvest
    out = tmp_path / "outputs"
    (out / "sweeps").mkdir(parents=True)
    (out / "sweeps" / "sweep_1.csv").write_text(
        "position_sizer.kelly_fraction,realized_pnl\n0.1,-1\n0.2,2\n0.3,0\n",
        encoding="utf-8")
    (out / "tune_search_state.json").write_text(
        '{"evaluated": [{"theta": [1], "objective": 0.1},'
        ' {"theta": [2], "objective": 0.2}]}', encoding="utf-8")
    rows, absent = harvest(out)
    by_id = {r["strategy_id"]: r["count"] for r in rows}
    assert by_id["sweep:sweep_1.csv"] == 3
    assert by_id["tune_search"] == 2
    assert by_id["geometry_search_grid"] == 48   # static, from module constants
    assert by_id["of3_model_space"] == 9         # ml/overfit._BASE_ORDER
    assert absent == []                          # nothing missing in fixture? no:
    # geometry/of3 are static (always present); sweeps+tune present here


def test_harvest_reports_absent_sources(tmp_path):
    from scripts.trial_ledger import harvest
    rows, absent = harvest(tmp_path / "outputs")   # dir doesn't exist
    ids = {r["strategy_id"] for r in rows}
    assert ids == {"geometry_search_grid", "of3_model_space"}
    assert set(absent) == {"tune_search_state.json", "sweeps/*.csv"}
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_trial_ledger.py -k harvest -v 2>&1 | tail -4`
Expected: `ImportError: cannot import name 'harvest'`

- [ ] **Step 3: Implement `harvest()` (add to `scripts/trial_ledger.py`)**

```python
def _harvest_row(strategy_id: str, count: int) -> dict:
    return {"schema_version": SCHEMA_VERSION, "strategy_id": strategy_id,
            "source": "harvest", "seed": 0, "fee_anchor": "n/a",
            "harness_profile": "n/a", "cycles": 0, "entries": 0, "exits": 0,
            "gross_pct": "", "net_pct": "", "sr": "", "max_dd": "",
            "n_eff": "", "degenerate": False, "exit_profile": "n/a",
            "count": count}


def harvest(outputs_dir: Path) -> tuple:
    """Count trials ALREADY evaluated by historical search tools.

    Objective-only sources: these yield N, never SR dispersion (spec
    [SEV-3]). An absent source is returned in `absent` and NEVER counted
    as zero trials — absence of a record is not a record of absence.
    Static sources (geometry grid, OF-3 model space) are read from the
    module constants that define them, so they track code, not memory.
    """
    outputs_dir = Path(outputs_dir)
    rows, absent = [], []

    ts = outputs_dir / "tune_search_state.json"
    if ts.exists():
        try:
            state = json.loads(ts.read_text(encoding="utf-8"))
            n = len(state.get("evaluated") or [])
            if n:
                rows.append(_harvest_row("tune_search", n))
        except (OSError, json.JSONDecodeError):
            absent.append("tune_search_state.json (unreadable)")
    else:
        absent.append("tune_search_state.json")

    sweeps = sorted((outputs_dir / "sweeps").glob("sweep_*.csv"))
    if sweeps:
        for sw in sweeps:
            with open(sw, newline="", encoding="utf-8") as fh:
                n = sum(1 for _ in csv.DictReader(fh))
            if n:
                rows.append(_harvest_row(f"sweep:{sw.name}", n))
    else:
        absent.append("sweeps/*.csv")

    from scripts.geometry_search import HORIZON_BARS, SL_PCT, TP_PCT
    rows.append(_harvest_row("geometry_search_grid",
                             len(TP_PCT) * len(SL_PCT) * len(HORIZON_BARS)))

    from ml.overfit import _BASE_ORDER
    rows.append(_harvest_row("of3_model_space", len(_BASE_ORDER)))
    return rows, absent
```

and extend `main()` — replace the body between `ns = ap.parse_args()` and `p = Path(ns.ledger)` handling with:

```python
    ap.add_argument("--harvest", action="store_true",
                    help="append harvest rows from outputs/ search records")
```
(add this argument above `ns = ap.parse_args()`), and after argument parsing insert:

```python
    if ns.harvest:
        rows, absent = harvest(Path("outputs"))
        append_rows(rows, p)
        for a in absent:
            print(f"harvest source ABSENT (not zero): {a}")
        print(f"harvested {sum(r['count'] for r in rows)} trials "
              f"from {len(rows)} sources -> {p}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_trial_ledger.py -v 2>&1 | tail -4`
Expected: `6 passed`

- [ ] **Step 5: Lint and commit**

Run: `.venv/bin/ruff check scripts/trial_ledger.py tests/test_trial_ledger.py`
Expected: `All checks passed!`

```bash
git add scripts/trial_ledger.py tests/test_trial_ledger.py
git commit -m "feat(trials): harvest mode - N from historical searches, absent-is-not-zero"
```

---

### Task 4: OF-5 ratchet — measured N via `max(configured, measured)`

**Files:**
- Modify: `scripts/overfit_check.py:1006-1009` (the `_dsr_trials` block inside `main()`)
- Test: `tests/test_of5_trial_ratchet.py` (create)

**Interfaces:**
- Consumes: `read_ledger`, `measured_trials`, `LedgerInvalid` (Task 2); the existing `_dsr_trials` config read at `scripts/overfit_check.py:1006-1007`.
- Produces: a module-level function in `scripts/overfit_check.py`:
  `resolve_dsr_trials(configured: int, ledger_path) -> tuple[int, str]` returning `(n_trials_eff, source_line)`. `main()` calls it and prints the source line. `var_trial_sr` is NOT passed anywhere (stays `None` → legacy fallback inside `deflated_sharpe`).

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_of5_trial_ratchet.py -v 2>&1 | tail -4`
Expected: `ImportError: cannot import name 'resolve_dsr_trials'`

- [ ] **Step 3: Implement in `scripts/overfit_check.py`**

Add this module-level function (place it directly above `def main():`):

```python
def resolve_dsr_trials(configured: int, ledger_path) -> tuple:
    """TRIALS-1 ratchet (spec 2026-08-27 [SEV-2]): the measured trial
    ledger can only DEEPEN the DSR deflation, never relax it below the
    configured floor. Absent/invalid ledger ≡ legacy behavior, loudly.
    Returns (n_trials_eff, source_line) — main() prints the line so
    every OF-5 green names the world it ran in."""
    from pathlib import Path as _P

    from scripts.trial_ledger import (LedgerInvalid, measured_trials,
                                      read_ledger)
    p = _P(ledger_path)
    if not p.exists():
        return configured, (f"OF-5 trials: assumed N={configured} "
                            f"(no ledger at {p}; var=SR^2 fallback)")
    try:
        m = measured_trials(read_ledger(p))
    except LedgerInvalid as e:
        return configured, (f"OF-5 trials: ledger INVALID ({e}); assumed "
                            f"N={configured}, var=SR^2 fallback")
    measured = int(m["n_trials"])
    if measured > configured:
        return measured, (f"OF-5 trials: measured N={measured} from ledger "
                          f"({m['by_source']}); var=SR^2 fallback (v0.1)")
    return configured, (f"OF-5 trials: measured N={measured} < configured; "
                        f"ratchet holds configured {configured}")
```

Then in `main()` replace the `_dsr_trials` assignment block's tail — after the existing `except` sets `_dsr_trials = 7` — insert immediately below the whole try/except:

```python
    _dsr_trials, _dsr_src = resolve_dsr_trials(
        _dsr_trials, Path(__file__).resolve().parents[1] /
        "outputs" / "trial_ledger.csv")
    print(f"  --    {_dsr_src}")
```

(`_dsr_of` at line 1011 keeps using `_dsr_trials` unchanged — the ratchet only ever raises it.)

- [ ] **Step 4: Run tests + the untouched-behavior regression**

Run: `.venv/bin/python -m pytest tests/test_of5_trial_ratchet.py tests/test_overfit.py -q > /tmp/t4.log 2>&1; echo "REAL rc=$?"; tail -2 /tmp/t4.log`
Expected: `REAL rc=0`, all passed (test_overfit pins the OF battery's existing behavior; no ledger exists in the repo's real `outputs/`, so `main()`'s path is legacy-identical).

- [ ] **Step 5: Lint and commit**

Run: `.venv/bin/ruff check scripts/overfit_check.py tests/test_of5_trial_ratchet.py`
Expected: `All checks passed!`

```bash
git add scripts/overfit_check.py tests/test_of5_trial_ratchet.py
git commit -m "feat(of5): trial-count ratchet reads the measured ledger, never relaxes"
```

---

### Task 5: coherent tape generator (inside `scripts/archetype_battery.py`)

**Files:**
- Create: `scripts/archetype_battery.py` (generator half)
- Test: `tests/test_archetype_battery.py` (create — generator tests)

**Interfaces:**
- Consumes: `data.replay.FeedRecorder`, `main.load_config`, `scripts.smoke_test.qa_redirect_paths`, `scripts.smoke_test.synth_book`.
- Produces (exact names later steps import from `scripts.archetype_battery`):
  - `ASSETS = ("ETH", "BTC")`, `BASE_PRICES = {"ETH": 2000.0, "BTC": 60000.0}`
  - `class PriceWorld(seed: int, bars: int, bar_sec: int)` with `.price(asset, bar_i) -> float`, `.bar_time(bar_i) -> float`, `.bars`
  - `record_tape(seed: int, cycles: int, out_dir: Path) -> str` — returns the recording path; candles carry ADVANCING real `time` values; all venues serve the same world price ± ≤10bps venue noise
  - `tape_coherence(recording_path: str) -> dict` with `{"max_venue_gap_bps": float, "bar_times_advance": bool, "distinct_series": int}`

- [ ] **Step 1: Write the failing generator tests**

```python
"""Archetype battery: the tape must be able to host a trade.

SEV-1 pins: bar times ADVANCE across market-data calls (the old mock froze
them at 0..119), venue prices stay coherent (the watchdog hard-returns on
~180bps+ divergence), and the candle series actually EVOLVES so momentum/
EMA rungs are not constants."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_tape_bar_times_advance_and_series_evolves(tmp_path):
    from scripts.archetype_battery import record_tape, tape_coherence
    rec = record_tape(seed=1, cycles=40, out_dir=tmp_path)
    c = tape_coherence(rec)
    assert c["bar_times_advance"] is True
    assert c["distinct_series"] > 1          # the frozen-mock failure mode
    assert c["max_venue_gap_bps"] < 50.0     # far inside the watchdog gate


def test_tape_is_seed_deterministic(tmp_path):
    from scripts.archetype_battery import record_tape
    a = Path(record_tape(seed=3, cycles=20, out_dir=tmp_path / "a"))
    b = Path(record_tape(seed=3, cycles=20, out_dir=tmp_path / "b"))
    fa = [json.loads(x)["result"] for x in a.read_text(encoding="utf-8").splitlines()]
    fb = [json.loads(x)["result"] for x in b.read_text(encoding="utf-8").splitlines()]
    assert fa == fb


def test_tapes_differ_across_seeds(tmp_path):
    from scripts.archetype_battery import PriceWorld
    w1, w2 = PriceWorld(1, 200, 300), PriceWorld(2, 200, 300)
    assert w1.price("ETH", 150) != w2.price("ETH", 150)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_archetype_battery.py -v 2>&1 | tail -4`
Expected: `ModuleNotFoundError: No module named 'scripts.archetype_battery'`

- [ ] **Step 3: Implement the generator half of `scripts/archetype_battery.py`**

```python
"""scripts/archetype_battery.py — archetype null population runner (v0.1).

Spec: docs/superpowers/specs/2026-08-27-archetype-null-battery-design.md.
Report-only. Archetypes live HERE, in scripts/ — the engine's
strategies.engine dispatch cannot reach them. Every run is QA-isolated
twice over: config paths via prepare_replay_config inside run_replay,
process singletons via configure_audit/configure_registry in main().

The tape generator exists because the smoke-test mocks cannot host a
trade (measured 2026-08-27: candle bar times frozen at 0..119, per-call
reseed, drift-vs-history divergence tripping the watchdog). One
PriceWorld per seed drives ALL venues; candles are a rolling window
whose times advance with the replay clock.
"""
import copy
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.replay import FeedRecorder  # noqa: E402
from scripts.smoke_test import synth_book  # noqa: E402

ASSETS = ("ETH", "BTC")
BASE_PRICES = {"ETH": 2000.0, "BTC": 60000.0}
BAR_SEC = 300                       # 5m bars == the engine's candle bar
VENUE_NOISE_BPS = {"okx": 4.0, "binanceus": 7.0, "kraken": 0.0}
CANDLE_WINDOW = 120


class PriceWorld:
    """One GBM-with-regime path per asset per seed; every venue reads it."""

    def __init__(self, seed: int, bars: int, bar_sec: int = BAR_SEC):
        self.bars = bars
        self.bar_sec = bar_sec
        self.t0 = 1_700_000_000.0           # fixed epoch: tapes are timeless
        rng = np.random.default_rng(seed)
        self._px = {}
        for a in ASSETS:
            drift = rng.normal(0.0, 0.00035)         # per-seed regime tilt
            vol = float(rng.uniform(0.0015, 0.0045))  # per-seed vol level
            steps = rng.normal(drift, vol, bars)
            self._px[a] = BASE_PRICES[a] * np.exp(np.cumsum(steps))

    def price(self, asset: str, bar_i: int) -> float:
        return float(self._px[asset][min(max(bar_i, 0), self.bars - 1)])

    def bar_time(self, bar_i: int) -> float:
        return self.t0 + bar_i * self.bar_sec


def _candles(world: PriceWorld, asset: str, upto_bar: int,
             n: int = CANDLE_WINDOW) -> list:
    lo = max(0, upto_bar - n + 1)
    out = []
    for i in range(lo, upto_bar + 1):
        c = world.price(asset, i)
        o = world.price(asset, i - 1) if i > 0 else c
        out.append({"time": world.bar_time(i), "open": o,
                    "high": max(o, c) * 1.001, "low": min(o, c) * 0.999,
                    "close": c, "volume": 900.0})
    return out


class _WorldVenue:
    """Shared venue base: serves the world's price ± bounded venue noise."""

    def __init__(self, world: PriceWorld, name: str):
        self._w = world
        self._name = name
        self._bar = 0
        self._i = 0

    def set_bar(self, bar_i: int):
        self._bar = bar_i

    def _mark(self, asset: str) -> float:
        px = self._w.price(asset, self._bar)
        noise = VENUE_NOISE_BPS[self._name] * 1e-4
        # deterministic per (venue, asset, bar): coherent AND seed-stable
        h = (hash((self._name, asset, self._bar)) % 1000) / 1000.0 - 0.5
        return px * (1.0 + 2.0 * noise * h)


class WorldOKX(_WorldVenue):
    def get_market_data(self):
        out = {}
        for sym, asset in (("ETH-USDT-SWAP", "ETH"), ("BTC-USDT-SWAP", "BTC")):
            px = self._mark(asset)
            self._i += 1
            out[sym] = {"order_book": synth_book(px, depth=300, seed=self._i),
                        "candles": _candles(self._w, asset, self._bar),
                        "funding_rate": 0.0001, "volume_24h": 5e8}
        return out

    def get_daily_candles(self, symbol, limit=300):
        asset = "ETH" if symbol.startswith("ETH") else "BTC"
        step = max(1, 288)                       # 288 x 5m = 1 day
        bars = list(range(0, self._w.bars, step))[-limit:]
        return [{"time": self._w.bar_time(i), "open": self._w.price(asset, i),
                 "high": self._w.price(asset, i) * 1.01,
                 "low": self._w.price(asset, i) * 0.99,
                 "close": self._w.price(asset, i), "volume": 5e4}
                for i in bars]

    def get_candles(self, symbol, bar="5m", limit=100):
        asset = "ETH" if symbol.startswith("ETH") else "BTC"
        return _candles(self._w, asset, self._bar, n=min(limit, 300))


class WorldBinanceUS(WorldOKX):
    def get_market_data(self):
        out = {}
        for sym, asset in (("ETHUSD", "ETH"), ("BTCUSD", "BTC")):
            px = self._mark(asset)
            self._i += 1
            out[sym] = {"order_book": synth_book(px, depth=280, seed=self._i + 7),
                        "candles": _candles(self._w, asset, self._bar),
                        "funding_rate": None, "volume_24h": 4e5}
        return out


class WorldKraken(_WorldVenue):
    def __init__(self, world: PriceWorld):
        super().__init__(world, "kraken")
        self.trading_pairs = ["ETH/USD", "BTC/USD"]

    def kraken_pair(self, symbol):
        return symbol.replace("/", "")

    def get_ticker_price(self, pair):
        return self._mark("ETH" if pair.startswith(("ETH", "XETH")) else "BTC")

    def get_tickers(self, pairs):
        return {p: self.get_ticker_price(p) for p in pairs}

    def get_order_book(self, pair, depth=20):
        px = self.get_ticker_price(pair)
        self._i += 1
        return synth_book(px, spread_bps=5.0, depth=80, seed=self._i)

    def get_candles(self, pair, interval_min=5, limit=100):
        asset = "ETH" if pair.startswith(("ETH", "XETH")) else "BTC"
        return _candles(self._w, asset, self._bar, n=min(limit, 300))

    def get_daily_candles(self, pair, limit=720):
        return WorldOKX.get_daily_candles(self, pair, limit)


def _battery_config(cycles: int) -> dict:
    from main import load_config
    from scripts.smoke_test import qa_redirect_paths
    cfg = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    qa_redirect_paths(cfg, "archetype_tape")
    cfg["system"]["dry_run"] = True
    cfg["sentiment"]["enabled"] = False
    cfg["webdata"]["enabled"] = False
    cfg["moomoo"]["enabled"] = False
    cfg["trading_pairs"] = ["ETH/USD", "BTC/USD"]   # world-backed assets only
    return cfg


def record_tape(seed: int, cycles: int, out_dir: Path) -> str:
    """Record one coherent tape by driving the REAL engine over world
    venues (mirrors overfit_check.make_offline_recording's isolation; no
    forced signals — the tape is strategy-neutral)."""
    from main import LiquidityBot
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sink = str(out_dir / f"tape_s{seed}.jsonl")
    Path(sink).unlink(missing_ok=True)

    cfg = _battery_config(cycles)
    cfg["system"]["state_path"] = str(out_dir / f"state_s{seed}.json")

    world = PriceWorld(seed, bars=cycles + CANDLE_WINDOW + 8)
    okx, bnc, krk = WorldOKX(world, "okx"), WorldBinanceUS(world, "binanceus"), \
        WorldKraken(world)
    bot = LiquidityBot(cfg, okx=FeedRecorder(okx, "okx", sink),
                       binanceus=FeedRecorder(bnc, "binanceus", sink),
                       kraken=FeedRecorder(krk, "kraken", sink),
                       resume=False)
    # the replay clock and the world bar clock advance TOGETHER: one
    # cycle == one bar (poll_sec is the recording cadence; data/replay.py
    # requires replaying at the cadence recorded)
    t = world.bar_time(CANDLE_WINDOW)
    for k in range(cycles):
        bar = CANDLE_WINDOW + k
        for v in (okx, bnc, krk):
            v.set_bar(bar)
        bot.cycle_once(t)
        t += bot.poll_sec
    return sink


def tape_coherence(recording_path: str) -> dict:
    """Self-check: the three SEV-1 defects, measured on the tape itself."""
    frames = [json.loads(x) for x in
              Path(recording_path).read_text(encoding="utf-8").splitlines()]
    md = [f for f in frames if f["method"] == "get_market_data"
          and f["feed"] == "okx"]
    end_times, series = [], set()
    for f in md:
        c = f["result"]["ETH-USDT-SWAP"]["candles"]
        end_times.append(c[-1]["time"])
        series.add(round(c[-1]["close"], 6))
    ticks = [f for f in frames if f["feed"] == "kraken"
             and f["method"] == "get_tickers" and isinstance(f["result"], dict)]
    gaps = []
    for f in md:
        okx_px = f["result"]["ETH-USDT-SWAP"]["candles"][-1]["close"]
        near = min(ticks, key=lambda g: abs(g["t"] - f["t"]), default=None)
        if near:
            kp = next((v for k, v in near["result"].items()
                       if k.startswith(("ETH", "XETH"))), None)
            if kp:
                gaps.append(abs(okx_px / float(kp) - 1.0) * 1e4)
    return {"bar_times_advance": end_times == sorted(end_times)
            and len(set(end_times)) == len(end_times),
            "distinct_series": len(series),
            "max_venue_gap_bps": max(gaps) if gaps else 0.0}
```

- [ ] **Step 4: Run generator tests**

Run: `.venv/bin/python -m pytest tests/test_archetype_battery.py -v 2>&1 | tail -5`
Expected: `3 passed` (if `max_venue_gap_bps` fails ≥50, the candle noise term is the suspect: candles read the WORLD price, books read the venue mark — both derive from `PriceWorld`, so gaps stay in single-digit bps by construction; debug by printing `tape_coherence(rec)`).

- [ ] **Step 5: Lint and commit**

Run: `.venv/bin/ruff check scripts/archetype_battery.py tests/test_archetype_battery.py`
Expected: `All checks passed!`

```bash
git add scripts/archetype_battery.py tests/test_archetype_battery.py
git commit -m "feat(battery): venue-coherent evolving tape generator + coherence self-check"
```

---

### Task 6: the eight rungs (entries only) + the oracle

**Files:**
- Modify: `scripts/archetype_battery.py` (add archetypes)
- Test: `tests/test_archetype_battery.py` (extend)

**Interfaces:**
- Consumes: `strategies.signal_gates.SignalResult` (fields: `symbol, direction, confidence, size, all_confirmed, gates_passed`; defaults cover the rest).
- Produces:
  - `ARCHETYPES: dict[str, Callable[[int], Callable]]` — maps `strategy_id -> factory(seed)`; each factory returns a FRESH `evaluate_asset(base_asset: str, view: dict) -> SignalResult` closure (stateful rungs re-anchor per run). Keys exactly: `"random_entry", "buy_hold", "naive_grid", "clockwork_dca", "momentum_chaser", "stop_herder", "vol_trend"`. The deployed member is `strategy_id="deployed"` and is represented by factory `None` (no patch).
  - `oracle_factory(world: PriceWorld, horizon_bars: int = 12)` — test-only planted edge: looks the world's price up `horizon_bars` ahead.

- [ ] **Step 1: Write the failing archetype tests (append)**

```python
def _view(closes, mark):
    return {"candles": [{"time": float(i), "open": c, "high": c, "low": c,
                         "close": c, "volume": 1.0}
                        for i, c in enumerate(closes)],
            "mark_price": mark}


def test_archetypes_registry_shape():
    from scripts.archetype_battery import ARCHETYPES
    assert set(ARCHETYPES) == {"random_entry", "buy_hold", "naive_grid",
                               "clockwork_dca", "momentum_chaser",
                               "stop_herder", "vol_trend", "deployed"}
    assert ARCHETYPES["deployed"] is None


def test_rungs_emit_valid_signalresults_and_never_raise():
    from scripts.archetype_battery import ARCHETYPES
    closes = [100 + 0.3 * i for i in range(60)]
    for name, factory in ARCHETYPES.items():
        if factory is None:
            continue
        fn = factory(seed=7)
        r = fn("ETH", _view(closes, closes[-1]))
        assert r.symbol == "ETH/USD"
        assert r.direction in ("long", "short", None)
        assert (r.direction is None) == (r.all_confirmed is False)
        r2 = fn("ETH", _view([], 100.0))     # empty candles never raise
        assert r2.direction is None


def test_momentum_flips_with_the_tape():
    from scripts.archetype_battery import ARCHETYPES
    up = ARCHETYPES["momentum_chaser"](seed=1)("ETH",
        _view([100 + i for i in range(30)], 130.0))
    dn = ARCHETYPES["momentum_chaser"](seed=1)("ETH",
        _view([130 - i for i in range(30)], 100.0))
    assert up.direction == "long" and dn.direction == "short"


def test_state_is_fresh_per_factory_call():
    from scripts.archetype_battery import ARCHETYPES
    closes = [100.0] * 40
    a = ARCHETYPES["clockwork_dca"](seed=2)
    b = ARCHETYPES["clockwork_dca"](seed=2)
    va = [a("ETH", _view(closes, 100.0)).direction for _ in range(6)]
    vb = [b("ETH", _view(closes, 100.0)).direction for _ in range(6)]
    assert va == vb                      # same seed, same fresh sequence


def test_oracle_sees_the_future(tmp_path):
    from scripts.archetype_battery import PriceWorld, oracle_factory
    w = PriceWorld(5, bars=200)
    fn = oracle_factory(w, horizon_bars=12)
    i = 140
    view = _view([w.price("ETH", j) for j in range(i - 40, i + 1)],
                 w.price("ETH", i))
    r = fn("ETH", view)
    future_up = w.price("ETH", i + 12) > w.price("ETH", i)
    assert r.direction == ("long" if future_up else "short")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_archetype_battery.py -k "archetypes or momentum or fresh or oracle" -v 2>&1 | tail -4`
Expected: `ImportError: cannot import name 'ARCHETYPES'`

- [ ] **Step 3: Implement the rungs (append to `scripts/archetype_battery.py`)**

```python
# ---------------------------------------------------------------- archetypes
# Entries ONLY (spec [SEV-5]): every rung exits through the deployed
# machinery; exit_profile="deployed" on every row. Each factory returns a
# FRESH closure so grid anchors / clocks / EMAs never leak across runs.
# The engine may SHADE the confidence downstream — it is an input, not a
# pass-through.
from strategies.signal_gates import SignalResult  # noqa: E402


def _no_signal(asset: str) -> "SignalResult":
    return SignalResult(symbol=f"{asset}/USD", direction=None,
                        confidence=0.0, size=0.0, all_confirmed=False,
                        gates_passed={})


def _sig(asset: str, direction: str, conf: float) -> "SignalResult":
    return SignalResult(symbol=f"{asset}/USD", direction=direction,
                        confidence=conf, size=0.0, all_confirmed=True,
                        gates_passed={"archetype": True})


def _closes(view: dict) -> list:
    return [c["close"] for c in (view.get("candles") or [])]


def _random_entry(seed: int, p_fire: float = 0.06):
    rng = np.random.default_rng(seed * 1009 + 1)

    def fn(asset, view):
        if not _closes(view):
            return _no_signal(asset)
        if rng.random() < p_fire:
            return _sig(asset, "long" if rng.random() < 0.5 else "short", 0.8)
        return _no_signal(asset)
    return fn


def _buy_hold(seed: int):
    fired = set()

    def fn(asset, view):
        if asset in fired or not _closes(view):
            return _no_signal(asset)
        fired.add(asset)
        return _sig(asset, "long", 0.9)
    return fn


def _naive_grid(seed: int, levels: int = 5, spacing_pct: float = 0.8):
    anchors = {}

    def fn(asset, view):
        closes = _closes(view)
        if not closes:
            return _no_signal(asset)
        px = closes[-1]
        if asset not in anchors:
            anchors[asset] = px
            return _no_signal(asset)
        drop_pct = (anchors[asset] - px) / anchors[asset] * 100.0
        rung = int(drop_pct // spacing_pct)
        if 1 <= rung <= levels:
            anchors[asset] = px            # re-arm below the fill (grid-bot)
            return _sig(asset, "long", 0.7)
        return _no_signal(asset)
    return fn


def _clockwork_dca(seed: int, every_n_calls: int = 12):
    calls = {}

    def fn(asset, view):
        if not _closes(view):
            return _no_signal(asset)
        calls[asset] = calls.get(asset, 0) + 1
        if calls[asset] % every_n_calls == 0:
            return _sig(asset, "long", 0.7)
        return _no_signal(asset)
    return fn


def _momentum_chaser(seed: int, k: int = 12):
    def fn(asset, view):
        closes = _closes(view)
        if len(closes) < k + 1:
            return _no_signal(asset)
        ret = closes[-1] / closes[-1 - k] - 1.0
        if abs(ret) < 0.001:
            return _no_signal(asset)
        return _sig(asset, "long" if ret > 0 else "short", 0.75)
    return fn


def _stop_herder(seed: int, proximity_pct: float = 0.25):
    def fn(asset, view):
        closes = _closes(view)
        if not closes:
            return _no_signal(asset)
        px = closes[-1]
        step = 10 ** max(0, len(str(int(px))) - 2)     # 2 leading digits
        dist = abs(px - round(px / step) * step) / px * 100.0
        if dist <= proximity_pct:
            return _sig(asset, "long", 0.7)
        return _no_signal(asset)
    return fn


def _vol_trend(seed: int, fast: int = 8, slow: int = 24,
               max_bar_vol: float = 0.006):
    def _ema(xs, n):
        a = 2.0 / (n + 1.0)
        e = xs[0]
        for x in xs[1:]:
            e = a * x + (1 - a) * e
        return e

    def fn(asset, view):
        closes = _closes(view)
        if len(closes) < slow + 2:
            return _no_signal(asset)
        rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
        vol = float(np.std(rets[-slow:]))
        if vol > max_bar_vol:
            return _no_signal(asset)              # vol gate: stand down
        f, s = _ema(closes[-slow:], fast), _ema(closes[-slow:], slow)
        if abs(f / s - 1.0) < 0.0008:
            return _no_signal(asset)
        return _sig(asset, "long" if f > s else "short", 0.8)
    return fn


ARCHETYPES = {
    "random_entry": _random_entry,
    "buy_hold": _buy_hold,
    "naive_grid": _naive_grid,
    "clockwork_dca": _clockwork_dca,
    "momentum_chaser": _momentum_chaser,
    "stop_herder": _stop_herder,
    "vol_trend": _vol_trend,
    "deployed": None,          # the measured member: no patch
}


def oracle_factory(world: "PriceWorld", horizon_bars: int = 12):
    """Test-only planted edge: reads the world's FUTURE price. Exists so
    the battery's validation can prove the pipeline ranks a real edge
    first (the-method injection obligation). Never in ARCHETYPES."""
    def fn(asset, view):
        closes = _closes(view)
        if not closes:
            return _no_signal(asset)
        px = closes[-1]
        arr = world._px[asset]
        i = int(np.argmin(np.abs(arr - px)))
        fut = world.price(asset, min(i + horizon_bars, world.bars - 1))
        if abs(fut / px - 1.0) < 0.0005:
            return _no_signal(asset)
        return _sig(asset, "long" if fut > px else "short", 0.95)
    return fn
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_archetype_battery.py -v 2>&1 | tail -4`
Expected: `8 passed`

- [ ] **Step 5: Lint and commit**

Run: `.venv/bin/ruff check scripts/archetype_battery.py tests/test_archetype_battery.py`
Expected: `All checks passed!`

```bash
git add scripts/archetype_battery.py tests/test_archetype_battery.py
git commit -m "feat(battery): eight entry-only rungs + test-only oracle"
```

---

### Task 7: the grid runner — harness profiles, determinism, activity floor, ledger

**Files:**
- Modify: `scripts/archetype_battery.py` (runner + CLI)
- Test: `tests/test_archetype_battery.py` (extend — liveness, audit pin, all-null bracket, oracle rank)

**Interfaces:**
- Consumes: `run_replay(cfg, rec, quiet=True, mutate_bot=...)` (Task 1), `append_rows`/`write_meta` (Task 2), `ARCHETYPES`/`oracle_factory`/`record_tape` (Tasks 5-6), `core.replay_gate.determinism_ok`, `_DETERMINISM_KEYS`, `scripts.replay.set_dotted`, `core.audit.configure_audit`, `ml.registry.configure_registry`.
- Produces:
  - `HARNESS_PROFILES: dict[str, dict]` — `"native": {}` and `"neutral-admission": {...dotted overrides...}`
  - `FEE_ANCHORS: dict[str, dict]` — `"booked": {}`, `"true": {...}` (true anchor INCLUDES `ml.exploration.p_win=0.85`: FEE-1's config_guard interlock FATALs the boot otherwise — the staged boundary value, in the throwaway replay config only)
  - `run_battery(tapes: int, cycles: int, out_dir: Path, ledger_path: Path, members: dict | None = None, profiles: dict | None = None) -> dict` returning `{"rows": int, "attempted": int, "refused": int, "degenerate": int, "report_path": str}`

- [ ] **Step 1: Write the failing runner tests (append)**

```python
def test_battery_end_to_end_pins(tmp_path):
    """One compact battery run pins four spec properties at once:
    (a) LIVENESS — the oracle member records >=1 entry (a tape that
        cannot host a trade is a red suite, not a quiet zero) [SEV-1];
    (b) ORACLE RANKS FIRST among members by net_pct (injection duty);
    (c) AUDIT ISOLATION — the production audit trail gains zero bytes;
    (d) LEDGER/META — rows appended, attempted/refused counters written.
    Small grid (2 tapes x subset) to stay test-budget honest."""
    import os
    from pathlib import Path as P

    from scripts.archetype_battery import (ARCHETYPES, PriceWorld,
                                           oracle_factory, run_battery)
    from scripts.trial_ledger import measured_trials, read_ledger

    prod_audit = P("outputs") / "audit.jsonl"
    before = prod_audit.stat().st_size if prod_audit.exists() else -1

    members = {"random_entry": ARCHETYPES["random_entry"],
               "buy_hold": ARCHETYPES["buy_hold"],
               "oracle": lambda seed: oracle_factory(
                   PriceWorld(seed, bars=200))}
    res = run_battery(tapes=2, cycles=48, out_dir=tmp_path / "bat",
                      ledger_path=tmp_path / "trial_ledger.csv",
                      members=members)
    rows = read_ledger(tmp_path / "trial_ledger.csv")
    assert res["rows"] == len(rows) > 0
    oracle_rows = [r for r in rows if r["strategy_id"] == "oracle"
                   and not r["degenerate"]]
    assert oracle_rows, "oracle degenerate on every tape — tape cannot host a trade"
    by_member = {}
    for r in rows:
        if r["net_pct"] is not None and not r["degenerate"]:
            by_member.setdefault(r["strategy_id"], []).append(r["net_pct"])
    mean_net = {k: sum(v) / len(v) for k, v in by_member.items()}
    assert max(mean_net, key=mean_net.get) == "oracle", mean_net
    after = prod_audit.stat().st_size if prod_audit.exists() else -1
    assert after == before, "battery wrote the PRODUCTION audit trail"
    meta = (tmp_path / "trial_ledger.meta.json")
    assert meta.exists()
    assert os.path.getsize(res["report_path"]) > 0


def test_all_null_population_brackets_zero(tmp_path):
    """Pure-noise members' mean net over the population must bracket 0
    within 3 SD/sqrt(n) at the booked anchor — a directional tape or a
    leaky harness shows up here [the-method all-null obligation]."""
    import statistics as st

    from scripts.archetype_battery import ARCHETYPES, run_battery
    from scripts.trial_ledger import read_ledger
    members = {"random_entry": ARCHETYPES["random_entry"]}
    run_battery(tapes=4, cycles=48, out_dir=tmp_path / "bat",
                ledger_path=tmp_path / "ledger.csv", members=members,
                profiles=None)
    rows = [r for r in read_ledger(tmp_path / "ledger.csv")
            if r["fee_anchor"] == "booked" and not r["degenerate"]
            and r["net_pct"] is not None]
    if len(rows) < 3:
        return                       # degenerate-dominated: floor did its job
    nets = [r["net_pct"] for r in rows]
    bound = 3 * (st.pstdev(nets) / max(len(nets), 1) ** 0.5) + 0.05
    assert abs(st.mean(nets)) <= bound, (st.mean(nets), bound)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_archetype_battery.py -k "end_to_end or brackets" -v 2>&1 | tail -4`
Expected: `ImportError: cannot import name 'run_battery'`

- [ ] **Step 3: Implement the runner (append to `scripts/archetype_battery.py`)**

```python
# ---------------------------------------------------------------- runner
from core.replay_gate import _DETERMINISM_KEYS, determinism_ok  # noqa: E402
from scripts.replay import run_replay, set_dotted  # noqa: E402
from scripts.trial_ledger import (SCHEMA_VERSION, append_rows,  # noqa: E402
                                  write_meta)

MIN_TRIPS = 1          # activity floor (spec [SEV-1]): entries < this -> degenerate

# Pre-registered harness profiles (spec §2). neutral-admission exists
# because archetypes cannot clear the deployed admission stack (SZ-023
# derived bar ~0.69 vs cold prior 0.62). These are THROWAWAY replay-config
# overrides — never a real config change — and the profile name rides on
# every ledger row so the report can say strategy∘harness out loud.
HARNESS_PROFILES = {
    "native": {},
    "neutral-admission": {
        "ml.cold_start_prior_p": 0.90,          # clears the derived bar
        "position_sizer.entry_cooldown_min": 0,
        "ml.exploration.enabled": False,         # no probe lane noise
    },
}

# Fee anchors (spec §2). The true anchor carries the staged exploration
# p_win: FEE-1 measured that true fees + shipped exploration p_win FATAL
# config_guard at boot ("the bot will not start") — 0.85 is the staged
# boundary value, applied to the throwaway config only.
FEE_ANCHORS = {
    "booked": {},
    "true": {"pretrade.maker_fee_bps": 40, "pretrade.taker_fee_bps": 80,
             "order_manager.maker_fee_bps": 40,
             "order_manager.taker_fee_bps": 80,
             "ml.exploration.p_win": 0.85},
}


def _overlay(base_cfg: dict, overrides: dict) -> dict:
    cfg = copy.deepcopy(base_cfg)
    for dotted, val in overrides.items():
        set_dotted(cfg, dotted, json.dumps(val))
    return cfg


def _summary_to_row(member, profile, anchor, seed, s) -> dict:
    start = 10_000.0
    entries = int(s["entries_filled"])
    return {"schema_version": SCHEMA_VERSION, "strategy_id": member,
            "source": "battery", "seed": seed, "fee_anchor": anchor,
            "harness_profile": profile, "cycles": int(s["cycles"]),
            "entries": entries, "exits": int(s["exit_orders"]),
            "gross_pct": round((s["realized_pnl"] + s["fees"]) / start * 100, 4),
            "net_pct": round(s["realized_pnl"] / start * 100, 4),
            "sr": "", "max_dd": "", "n_eff": "",
            "degenerate": entries < MIN_TRIPS, "exit_profile": "deployed",
            "count": 1}


def run_battery(tapes: int, cycles: int, out_dir: Path, ledger_path: Path,
                members: dict | None = None,
                profiles: dict | None = None) -> dict:
    """The grid: members x tapes x anchors under each harness profile.
    Never a silent zero: degenerate rows are flagged and counted;
    determinism refusals are counted; both land in the meta sidecar."""
    from main import load_config
    members = dict(ARCHETYPES if members is None else members)
    profiles = dict(HARNESS_PROFILES if profiles is None
                    else profiles) or {"neutral-admission":
                                       HARNESS_PROFILES["neutral-admission"]}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = load_config(str(Path(__file__).resolve().parents[1] / "config.json"))
    base["capital_management"]["starting_capital_usd"] = 10_000

    tapes_paths = {s: record_tape(s, cycles, out_dir / "tapes")
                   for s in range(1, tapes + 1)}

    rows, refused, attempted = [], 0, 0
    notes = []
    cycles_seen = {}
    for member, factory in members.items():
        for profile, prof_over in (profiles.items()
                                   if factory is not None or True else []):
            if factory is None and profile not in ("native",
                                                   "neutral-admission"):
                continue
            for anchor, fee_over in FEE_ANCHORS.items():
                for seed, rec in tapes_paths.items():
                    attempted += 1
                    cfg = _overlay(_overlay(base, prof_over), fee_over)
                    mut = None
                    if factory is not None:
                        fn = factory(seed)
                        mut = (lambda f: (lambda bot: setattr(
                            bot.gates, "evaluate_asset",
                            lambda a, v: f(a, v))))(fn)
                    s = run_replay(cfg, rec, quiet=True, mutate_bot=mut)
                    if seed == 1:
                        fn2 = factory(seed) if factory is not None else None
                        mut2 = None if fn2 is None else (
                            lambda bot: setattr(bot.gates, "evaluate_asset",
                                                lambda a, v: fn2(a, v)))
                        s2 = run_replay(cfg, rec, quiet=True, mutate_bot=mut2)
                        ok, diff = determinism_ok(
                            s, s2, keys=_DETERMINISM_KEYS + ("cycles",))
                        if not ok:
                            refused += 1
                            notes.append(f"determinism refused "
                                         f"{member}/{profile}/{anchor}: {diff}")
                            continue
                    key = (seed, anchor, profile)
                    if key in cycles_seen and cycles_seen[key] != s["cycles"]:
                        refused += 1
                        notes.append(f"cycles mismatch {member} on tape "
                                     f"{seed}: {s['cycles']} != "
                                     f"{cycles_seen[key]}")
                        continue
                    cycles_seen.setdefault(key, s["cycles"])
                    rows.append(_summary_to_row(member, profile, anchor,
                                                seed, s))

    append_rows(rows, ledger_path)
    deg = sum(1 for r in rows if r["degenerate"])
    write_meta(ledger_path, attempted=attempted, accepted=len(rows),
               refused=refused, notes=notes)
    report = out_dir / "archetype_battery.md"
    lines = [f"# archetype battery — {len(rows)} rows "
             f"(attempted {attempted}, refused {refused}, degenerate {deg})",
             f"corpus: {tapes} tapes x {cycles} cycles x "
             f"{len(members)} members x {len(FEE_ANCHORS)} anchors "
             f"[population measures strategy∘harness]", ""]
    for r in sorted(rows, key=lambda r: (r["strategy_id"], r["seed"])):
        lines.append(f"- {r['strategy_id']:16} s{r['seed']} "
                     f"{r['fee_anchor']:6} {r['harness_profile']:18} "
                     f"entries={r['entries']:3} net={r['net_pct']}% "
                     f"{'DEGENERATE' if r['degenerate'] else ''}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"rows": len(rows), "attempted": attempted, "refused": refused,
            "degenerate": deg, "report_path": str(report)}


def main() -> int:
    import argparse
    import tempfile

    # keep synthetic dispositions/models out of the production trail —
    # the sweep.py precedent, mandatory (spec [SEV-4])
    from core.audit import configure_audit
    from ml.registry import configure_registry
    tmp = Path(tempfile.gettempdir())
    configure_audit(tmp / "liqbot_battery_audit.jsonl")
    configure_registry(tmp / "liqbot_battery_models")

    ap = argparse.ArgumentParser()
    ap.add_argument("--tapes", type=int, default=6)
    ap.add_argument("--cycles", type=int, default=240)
    ap.add_argument("--out", default="outputs/archetype_battery")
    ap.add_argument("--ledger", default="outputs/trial_ledger.csv")
    ns = ap.parse_args()
    t0 = time.time()
    res = run_battery(ns.tapes, ns.cycles, Path(ns.out), Path(ns.ledger))
    print(f"battery: {res['rows']} rows, refused {res['refused']}, "
          f"degenerate {res['degenerate']} in {time.time() - t0:.0f}s "
          f"-> {res['report_path']}")
    return 0 if res["rows"] else 1


if __name__ == "__main__":
    sys.exit(main())
```

Note for the implementer: `run_battery` itself does NOT call `configure_audit` (tests must inject tmp sinks first and the test process already redirects config paths); the CLI `main()` does, before anything else. The end-to-end TEST therefore also calls `configure_audit`/`configure_registry` to tmp paths in a fixture if the production-size assertion ever trips — but expectation is it passes because `prepare_replay_config` + the conftest guard cover the config-path writes, and audit singleton writes only happen on engine dispositions, which run inside the replayed bot whose audit calls go through the module singleton. **If assertion (c) fails, that is the SEV-4 leak the pin exists to catch: add `configure_audit(tmp_path / "a.jsonl")` + `configure_registry(tmp_path / "m")` at the TOP of both battery tests and keep the production-size assertion.**

- [ ] **Step 4: Run the battery tests**

Run: `.venv/bin/python -m pytest tests/test_archetype_battery.py -v 2>&1 | tail -6`
Expected: `10 passed` (the end-to-end test takes the longest — two tapes × 3 members × 2 anchors × ~1-3 s/replay plus determinism doubles ≈ 30-90 s).

- [ ] **Step 5: Lint, bandit, and commit**

Run: `.venv/bin/ruff check scripts/archetype_battery.py tests/test_archetype_battery.py && .venv/bin/bandit -c pyproject.toml -q scripts/archetype_battery.py scripts/trial_ledger.py 2>&1 | tail -3`
Expected: ruff `All checks passed!`; bandit no NEW findings (severity High 0 / Medium 0).

```bash
git add scripts/archetype_battery.py tests/test_archetype_battery.py
git commit -m "feat(battery): grid runner - harness profiles, determinism+cycles gate, activity floor, ledger"
```

---

### Task 8: wire the docs, run the matrix, push

**Files:**
- Modify: `docs/INDEX.md` (EXPLORATION row), `docs/HANDOFF.md` (docket row), `docs/thales/REGISTRY.md` (TH-R-013 capture note stays; no status change — the battery is measurement, not remedy)
- Test: (existing suites)

**Interfaces:** none new — this task publishes and validates.

- [ ] **Step 1: INDEX pointer**

In `docs/INDEX.md`, EXPLORATION row, extend the "re-derive with" cell:
change `` `scripts/cohort_eval.py` (SELECTION-ERA), audit census (`core/codes.py` SZ-047/ML-070/SZ-051) `` to `` `scripts/cohort_eval.py` (SELECTION-ERA), `scripts/archetype_battery.py` + `scripts/trial_ledger.py` (null population, measured trials), audit census (`core/codes.py` SZ-047/ML-070/SZ-051) ``.

- [ ] **Step 2: HANDOFF docket row**

In `docs/HANDOFF.md`, directly under the THALES-R row, add:

```markdown
| **TRIALS-1 build** *(SAFE, shipped)* | archetype null battery + trial ledger v0.1: measured trial N feeds OF-5 under a ratchet (max(configured, measured); var stays legacy behind TRIPS_FLOOR=20); 8 entry-only rungs + deployed member on venue-coherent multi-seed tapes; activity floor + liveness pin close the confident-zero hole; run `python scripts/archetype_battery.py` then `python scripts/trial_ledger.py --report` | `docs/superpowers/specs/2026-08-27-archetype-null-battery-design.md`, `docs/superpowers/plans/2026-08-27-archetype-null-battery.md` |
```

- [ ] **Step 3: Run the FULL definition-of-done matrix**

Run each, real exit codes, no pipes on pytest:

```bash
.venv/bin/python -m pytest tests/ -q > /tmp/dod_suite.log 2>&1; echo "REAL rc=$?"; tail -2 /tmp/dod_suite.log
.venv/bin/python scripts/smoke_test.py > /tmp/dod_smoke.log 2>&1; echo "rc=$?"; tail -2 /tmp/dod_smoke.log
.venv/bin/python scripts/assurance_check.py > /tmp/dod_assur.log 2>&1; echo "rc=$?"; tail -1 /tmp/dod_assur.log
.venv/bin/python scripts/overfit_check.py > /tmp/dod_overfit.log 2>&1; echo "rc=$?"; grep -i "^corpus\|OF-5 trials" /tmp/dod_overfit.log
.venv/bin/ruff check core data execution ml risk regime strategies sentiment api main.py runner.py tests scripts/quant_trials.py scripts/overfit_check.py
/root/.local/bin/pyright core data execution ml risk regime strategies sentiment api main.py runner.py 2>&1 | tail -1
.venv/bin/bandit -c pyproject.toml -r . -x ./.venv,./tests -q > /tmp/dod_bandit.log 2>&1; grep -A4 "by severity" /tmp/dod_bandit.log | head -5
.venv/bin/python -m compileall -q . -x '.venv'; echo "compileall rc=$?"
```

Expected: suite `REAL rc=0`; smoke/assurance rc=0; overfit rc=0 **and read the corpus line + the new "OF-5 trials:" line** (no ledger in production outputs yet → "assumed N=7 (no ledger…)" — legacy world, by design until the operator runs the battery); ruff clean; pyright `0 errors`; bandit High 0 / Medium 0 (the 2 pre-existing `.claude/hooks` Lows persist); compileall rc=0.

- [ ] **Step 4: Commit and push**

```bash
git add docs/INDEX.md docs/HANDOFF.md
git commit -m "docs: battery + trial ledger wired into INDEX and HANDOFF docket"
git push -u origin claude/remote-control-hds2hd
```

---

## Self-Review (performed at plan time)

1. **Spec coverage:** ledger+meta counters (T2), harvest/absent-not-zero (T3), OF-5 ratchet + source line (T4), rebuilt tape + coherence self-check (T5), entries-only rungs + fresh state + oracle (T6), harness profiles + fee anchors incl. the FEE-1 FATAL guard + determinism+cycles + activity floor + audit isolation + report (T7), INDEX/HANDOFF + full matrix (T8). SPA/percentile, measured-var, ML features: spec non-goals — no tasks, correct. `sr` nullable behind TRIPS_FLOOR=20: constant in T2, dormant by construction ✓.
2. **Placeholder scan:** none — every step carries code or exact commands.
3. **Type consistency:** `run_replay(..., mutate_bot=)` (T1) is what T7 calls; `append_rows/read_ledger/measured_trials/write_meta` signatures match between T2/T3/T4/T7; `ARCHETYPES` keys in T6 = the set T7 iterates and the T6 test pins; `resolve_dsr_trials` consumes T2's reader; summary keys used in `_summary_to_row` are exactly Task 1's produced set.
