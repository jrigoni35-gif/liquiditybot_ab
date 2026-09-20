# Desk Instruments — Plan 1: Census + Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure the era-9 ungradeable-decision hole exactly (Lane 0 census), then close it going forward (DE-010 capture) and make the fills ledger's `book` column honest (A2).

**Architecture:** Report-plane census script reads the hash-chained audit trail + fills.csv and decomposes the era-9 arrival population with exact arithmetic; engine-side, an hourly-batched DE-010 audit record captures every sweep arrival beside the existing EN-000 vector; three 5m entry `meta` dicts gain `"book": "5m"`. Spec: `docs/superpowers/specs/2026-09-19-desk-instruments-design.md`; architecture: `docs/quant/2026-09-19_institutional_integration.md`.

**Tech Stack:** repo venv `.venv/Scripts/python.exe`, stdlib + pandas (tests), `core.audit` (`get_audit`, `configure_audit`, record shape `{"code","data","h","msg","prev","seq","src","ts"}`), `core.codes.Code`, `core.fill_ledger.EXEC_ERA`.

## Global Constraints

- Era-9 moratorium in force: measurement/logging only. Nothing here feeds decisioning. No gate, sizing, exit, fill-sim, fee, lifecycle, universe, hedger, probe, or heat change.
- Invariant 6: new audit emissions use a registered `Code` member, never a bare string.
- Guarded telemetry: new audit code paths never raise into the entry loop (mirror `_absorb`'s try/except discipline).
- Refusal labels in report scripts follow the `gate_efficacy_report.py` precedent (named constants printed in output); only audit-emitting code touches `core/codes.py`.
- Definition of done per code-touching task, full matrix: `python -m pytest tests/ -q` · `python scripts/smoke_test.py` · `python scripts/assurance_check.py` · `python scripts/overfit_check.py` (OF-3 pbo 0.69 / OF-5 DSR 0.006 are the documented guarded reds — do NOT touch) · `ruff check core data execution ml risk regime strategies sentiment api main.py runner.py tests scripts/quant_trials.py scripts/overfit_check.py` · `pyright core data execution ml risk regime strategies sentiment api main.py runner.py` (zero-error ratchet; tests/scripts outside the gate) · `bandit -c pyproject.toml -r . -x ./.venv,./tests,./outputs` · `python -m compileall -q . -x '(\.venv|\.claude)'`.
- Commit one lane at a time; commit messages `SAFE`-tagged where the lane is measurement-plane.
- `rtk` is NOT installed on this box — never prefix commands.

## Spec amendments made at plan time (both verified in-tree, both SAFE)

1. **DE-010 is hourly-batched, not per-arrival.** `core/codes.py:673-679` registers why per-event emission is barred (~11,520 records/day against a trail at ~1,450/day). DE-010 mirrors EN-000: one audit record per hour carrying the per-arrival event vector. Loss window: up to 1 h of buffered events on process stop — named, accepted. Reconciliation pin: DE-010 event count == EN-000 `arrivals` delta over the same window.
2. **A2 is a three-site meta stamp, not a writer change.** `core/fill_ledger.py:253` already writes `book` from `order.meta`; the hole is that the three 5m entry `meta` dicts (main.py:1541 algo-child, :5113 main entry, :6032 grid rung) never set it, so 1,359 of 1,373 fills carry empty book (measured 2026-09-19 eve; only 14 `long`). `fill_row`'s default stays `""` — the None/""/value three-way semantics at fill_ledger.py:247-252 are preserved. Note the name collision: `submit(book=...)` (main.py:1539, :5111, :6030) is the order-BOOK snapshot; `meta["book"]` is the desk label. Do not conflate.

## File Structure

- Create `scripts/gradeability_census.py` — Lane 0 census (report-plane).
- Create `tests/test_gradeability_census.py` — synthetic-chain pins.
- Modify `core/codes.py` (EN block ends :689) — register `DE-010`.
- Modify `main.py` — buffer init (~:1223), `_de_event` + `_flush_decision_events` beside `_emit_absorb_summary` (:1910), capture in the `slow_cycle` loop (:4609–4688), flush call beside :4596; three meta stamps (:1541, :5113, :6032).
- Create `tests/test_decision_events.py` — DE-010 pins.
- Create `tests/test_book_stamp.py` — A2 pins.
- Create `docs/quant/<run-date>_gradeability_census.md` — dated census record (Task 1 step).

---

### Task 1: `scripts/gradeability_census.py` — the hole, measured exactly

**Files:**
- Create: `scripts/gradeability_census.py`
- Test: `tests/test_gradeability_census.py`
- Produces: `docs/quant/<run-date>_gradeability_census.md`

**Interfaces:**
- Consumes: `outputs/audit.jsonl` (record keys `code,data,h,msg,prev,seq,src,ts` — verified), `outputs/fills.csv` (columns verified: `ts,order_id,position_id,purpose,symbol,side,ordertype,post_only,attempt,fill_size,fill_price,arrival_ref,slip_bps,fees_delta_usd,remaining,reason,exec_era,book`), `core.fill_ledger.EXEC_ERA == "12-10d4d0c2"`.
- Produces: stdout census table + `--doc` markdown record. Later lanes (B) read the doc, not the script internals.

**Census semantics (exact arithmetic, no overclaim):** pre-DE-010 arrivals have no per-arrival records by construction (EN-000 is counts-only). The census therefore reports: N arrivals by absorb key (exact, from EN-000 deltas); `g` = gradeable priced entry decisions (era fills with `arrival_ref`); `L` = lost-forever = EN-020 + EN-030 counts; `D` = deep-pipeline = N − EN-020 − EN-030 − g (reached/passed the gate stack without a priced entry; retro-gradeable only via CV-record ts+asset through a Kraken-OHLC proxy, which Lane B owns); `r` = CV-* audit records carrying an asset name (printed beside D, NEVER equated). Pins: `EN-020 + EN-030 ≤ N`, `g ≤ N − EN-020 − EN-030`, `L + g + D == N` (definitional), else refuse `CENSUS_INCONSISTENT`. Chain damage → refuse `CHAIN_TORN`. No EN-000 in window → refuse `NO_EN000_IN_WINDOW`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_gradeability_census.py
import json
from pathlib import Path

from core.audit import configure_audit, get_audit
from core.codes import Code
from scripts.gradeability_census import census, REFUSAL_CHAIN_TORN


def _chain(tmp_path, n_sweeps=3):
    """Real records, real chain, via the engine's own writer."""
    configure_audit(tmp_path / "audit.jsonl")
    a = get_audit()
    a.log("startup", Code.CG_CONFIG_START if hasattr(Code, "CG_CONFIG_START")
          else list(Code)[0], "session start: config fingerprint",
          {"config_sha256": "x", "dry_run": True}, counted=False)
    # two hourly EN-000 ticks, cumulative: 4 arrivals/hr, 3 absorbed EN-030
    vec1 = {"arrivals": 4, "EN-030": 3}
    vec2 = {"arrivals": 8, "EN-030": 6}
    a.log("entry_sweep", Code.EN_SWEEP_SUMMARY, "v1", vec1, counted=False)
    a.log("entry_sweep", Code.EN_SWEEP_SUMMARY, "v2", vec2, counted=False)
    return tmp_path / "audit.jsonl"


def test_census_reconstructs_arrival_deltas(tmp_path):
    path = _chain(tmp_path)
    out = census(audit_path=path, fills_path=None,
                 since=0.0, doc_path=None)
    assert out["arrivals"] == 8
    assert out["by_key"]["EN-030"] == 6
    assert out["lost_forever"] == 6        # EN-020(0) + EN-030(6)
    assert out["refused"] is None


def test_census_refuses_torn_chain(tmp_path):
    path = _chain(tmp_path)
    lines = path.read_text().splitlines()
    rec = json.loads(lines[-1])
    rec["data"]["arrivals"] = 999          # tamper: breaks its own h
    lines[-1] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n")
    out = census(audit_path=path, fills_path=None,
                 since=0.0, doc_path=None)
    assert out["refused"] == REFUSAL_CHAIN_TORN
```

Note for the implementer: if `Code` has no `CG_CONFIG_START` member, use `list(Code)[0]` as written — the startup record's code does not matter to the census; the FIRST record's `src == "startup"` is what the boot-window logic reads. Verify the actual CG-000 member name in `core/codes.py` before finalizing and use it.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_gradeability_census.py -q -p no:cacheprovider`
Expected: FAIL — `ModuleNotFoundError: scripts.gradeability_census`

- [ ] **Step 3: Implement the census**

```python
"""scripts/gradeability_census.py - the era-9 decision-population census.

WHY THIS EXISTS. 82.6% of era-9's decision population is ungradeable
(measured 2026-09-19): EN-000 carries counts only, so pre-DE-010 arrivals
have no per-arrival record BY CONSTRUCTION. This census sizes the hole
exactly - by absorb key, with hard reconciliation - and derives the field
list DE-010 must carry so the hole never regrows. Report-plane: reads
outputs/, writes only its dated doc. Refuses rather than approximates.

    python scripts/gradeability_census.py
    python scripts/gradeability_census.py --since 2026-09-08 \
        --doc docs/quant/2026-09-20_gradeability_census.md
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.fill_ledger import EXEC_ERA          # "12-10d4d0c2" (era-9)

REFUSAL_CHAIN_TORN = "CHAIN_TORN"
REFUSAL_NO_EN000 = "NO_EN000_IN_WINDOW"
REFUSAL_INCONSISTENT = "CENSUS_INCONSISTENT"
REFUSAL_NO_FILLS = "NO_FILLS"

# cut-#12 runner restart (era-9 accrual begins), docs/HANDOFF.md.
CUT12_FLOOR = datetime(2026, 9, 8, tzinfo=timezone.utc).timestamp()

GRADER_NEEDS = ("asset", "ts", "decision_mid", "mid_available",
                "gates", "absorb", "direction", "confidence")


def _h(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def read_chain(path):
    """Parse + structurally verify. Refusal on any tear, never a partial."""
    records, prev_h, prev_seq = [], "0000000000000000", 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue                     # torn-tail fragment guard
        rec = json.loads(line)
        if (rec.get("seq") != prev_seq + 1 or rec.get("prev") != prev_h
                or not rec.get("h")):
            return None                  # CHAIN_TORN
        records.append(rec)
        prev_h, prev_seq = rec["h"], rec["seq"]
    return records


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def en000_deltas(records, since: float) -> dict:
    """Restart-aware positive deltas of the cumulative EN-000 vector."""
    ticks = [r for r in records
             if r.get("src") == "entry_sweep"
             and r.get("code") == "EN-000" and r.get("ts", 0) >= since]
    if not ticks:
        return {}
    out, prev = {}, None
    for t in sorted(ticks, key=lambda r: r["ts"]):
        data = t.get("data") or {}
        for k, v in data.items():
            if not isinstance(v, (int, float)):
                continue
            delta = v if prev is None or k not in prev or v < prev[k] \
                else v - prev[k]
            out[k] = out.get(k, 0) + delta
        prev = data
    return out


def gradeable_entries(fills_path, since: float) -> int:
    """Era-stamped entry fills carrying a decision price (arrival_ref)."""
    if not fills_path or not Path(fills_path).exists():
        return 0
    seen = set()
    with open(fills_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row.get("exec_era") == EXEC_ERA
                    and row.get("purpose") == "entry"
                    and (row.get("arrival_ref") or "")):
                seen.add(row.get("position_id") or row["order_id"])
    return len(seen)


def cv_records(records, since: float) -> int:
    return sum(1 for r in records
               if str(r.get("code", "")).startswith("CV-")
               and r.get("ts", 0) >= since and (r.get("data") or {}).get("asset"))


def census(*, audit_path, fills_path, since, doc_path) -> dict:
    records = read_chain(audit_path)
    if records is None:
        return {"refused": REFUSAL_CHAIN_TORN}
    keys = en000_deltas(records, since)
    if not keys:
        return {"refused": REFUSAL_NO_EN000}
    n = int(keys.get("arrivals", 0))
    en020, en030 = int(keys.get("EN-020", 0)), int(keys.get("EN-030", 0))
    g = gradeable_entries(fills_path, since)
    if en020 + en030 > n or g > n - en020 - en030:
        return {"refused": REFUSAL_INCONSISTENT}
    lost = en020 + en030
    deep = n - en020 - en030 - g
    out = {
        "refused": None, "since": _iso(since), "arrivals": n,
        "by_key": {k: int(v) for k, v in keys.items()},
        "gradeable": g, "lost_forever": lost, "deep_pipeline": deep,
        "cv_records_with_asset": cv_records(records, since),
        "de010_coverage": sum(len((r.get("data") or {}).get("events") or [])
                              for r in records if r.get("code") == "DE-010"),
        "de010_fields_derived": list(GRADER_NEEDS),
    }
    if doc_path:
        _write_doc(out, doc_path)
    return out


def _write_doc(out: dict, doc_path) -> None:
    p = Path(doc_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(f"| {k} | {v} |" for k, v in out["by_key"].items())
    p.write_text(f"""# Gradeability census (run {_iso(__import__('time').time())}, SAFE-plane)

Window since {out['since']} (era-9 = {EXEC_ERA}).

| absorb key | count |
|---|---|
{rows}

- arrivals N = {out['arrivals']}
- gradeable (priced entries) g = {out['gradeable']}
- lost forever L (EN-020+EN-030, no per-arrival record exists) = {out['lost_forever']}
- deep pipeline D (gate stack reached, no priced entry) = {out['deep_pipeline']}
- CV records carrying an asset (retro path via Kraken-OHLC proxy, Lane B) = {out['cv_records_with_asset']}
- DE-010 coverage (post-capture events) = {out['de010_coverage']}
- DE-010 derived fields: {', '.join(out['de010_fields_derived'])}

Reconciliation pins held: EN-020+EN-030 <= N, g <= N-EN-020-EN-030,
L+g+D == N. Unreconciled census = refused census.
""", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", default="outputs/audit.jsonl")
    ap.add_argument("--fills", default="outputs/fills.csv")
    ap.add_argument("--since", default=None,
                    help="epoch or YYYY-MM-DD (default: cut-#12 floor)")
    ap.add_argument("--doc", default=None)
    ns = ap.parse_args()
    since = (float(ns.since) if ns.since and ns.since[0].isdigit()
             and len(ns.since) > 10 else
             datetime.fromisoformat(ns.since).replace(
                 tzinfo=timezone.utc).timestamp()) if ns.since else CUT12_FLOOR
    out = census(audit_path=ns.audit, fills_path=ns.fills,
                 since=since, doc_path=ns.doc)
    if out["refused"]:
        print(f"CENSUS REFUSED: {out['refused']}")
        return 2
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

(Implementer: keep exactly this shape; if the real trail reveals an EN-000 `data` payload nesting difference, adapt `en000_deltas` to the OBSERVED shape and say so in the commit message — the vector is written by `dict(self._entry_absorb)` at main.py:1942, keys `"arrivals"`/`"EN-010"`/`"EN-020"`/`"EN-030"`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_gradeability_census.py -q -p no:cacheprovider`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the real census + write the dated record**

Run: `.venv/Scripts/python.exe scripts/gradeability_census.py --doc docs/quant/2026-09-20_gradeability_census.md`
(Use the actual run date for the filename.) Expected: JSON with reconciliation holding; if it prints `CENSUS REFUSED: CENSUS_INCONSISTENT`, STOP — that is a finding, not a bug to patch over; bring it to the operator.

- [ ] **Step 6: Commit**

```bash
git add scripts/gradeability_census.py tests/test_gradeability_census.py docs/quant/*_gradeability_census.md
git commit -m "feat(measure): era-9 gradeability census with reconciliation refusals (SAFE)"
```

---

### Task 2: DE-010 decision-event capture (engine, additive logging)

**Files:**
- Modify: `core/codes.py` (after the EN block, :689)
- Modify: `main.py` (:1223 buffer init; new methods beside :1910; capture in loop :4609–4688; flush call beside :4596)
- Test: `tests/test_decision_events.py`

**Interfaces:**
- Consumes: the sweep's in-scope `asset`, `v` (view dict with `order_book: {"bids","asks"}`), `now`, `signal` — nothing new computed.
- Produces: audit records `{"code":"DE-010","src":"entry_sweep","data":{"events":[{asset,ts,decision_mid,mid_available,direction,confidence,gates,absorb}, ...]}}`. Lane B/C consume `data.events`.

- [ ] **Step 1: Register the code**

Append to the EN block in `core/codes.py` (after `EN_SIGNAL_UNCONFIRMED`, :689):

```python
    # ---- decision-event capture (DE) — the gradeability hole's closer -----
    # THE HOLE THIS CLOSES. EN-000 is counts-only by design (above), so
    # pre-DE-010 arrivals left no per-arrival record: 82.6% of era-9's
    # decision population is ungradeable (census, docs/quant/..._gradeability_census.md).
    # Same volume discipline as EN-000: events BUFFER and emit as ONE hourly
    # record carrying the per-arrival vector. Loss window on process stop:
    # up to one hour of buffered events - named, accepted.
    DE_DECISION_EVENTS = "DE-010"    # hourly batch of per-arrival decision events
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_decision_events.py
"""DE-010 pins: capture shape, absorb tagging, hourly batch, EN-000 recon."""
import json
from types import SimpleNamespace
from pathlib import Path

from core.audit import configure_audit
from core.codes import Code
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
    ev2 = LiquidityBot._de_event("ETH", {"order_book": {"bids": [], "asks": []}},
                                 1_700_000_000.0)
    assert ev2["decision_mid"] == "" and ev2["mid_available"] is False


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
    bot._flush_decision_events(t + 3601.0)   # past the hourly gate
    recs = [json.loads(l) for l in
            (tmp_path / "audit.jsonl").read_text().splitlines()]
    de = [r for r in recs if r["code"] == "DE-010"]
    assert len(de) == 1
    assert len(de[0]["data"]["events"]) == n_arrivals   # EN-000 reconciliation
    assert bot._de_events == []
```

Note: `SignalResult` is not required — the suite's sanctioned double pattern (SimpleNamespace) is used deliberately; the loop only attribute-reads the signal. If `slow_cycle`'s pre-loop guards block the cycle in this harness (watchdog etc.), mirror the stubbing in `tests/test_context_integration.py::test_context_polled_from_slow_cycle_poll_cluster`.

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_decision_events.py -q -p no:cacheprovider`
Expected: FAIL — `AttributeError: ... _de_event` (and `Code.DE_DECISION_EVENTS` missing if Step 1 not yet run)

- [ ] **Step 4: Implement in main.py**

(a) Buffer init, beside main.py:1223 (`self._entry_absorb_emitted = 0.0`):

```python
        self._de_events = []            # DE-010 per-arrival buffer
        self._de_emitted = 0.0          # monotonic of the last DE-010 tick
```

(b) New methods immediately after `_emit_absorb_summary` (ends main.py:1944):

```python
    @staticmethod
    def _de_event(asset: str, v: dict, now: float) -> dict:
        """One per-arrival decision-event seed (DE-010 payload element).
        decision_mid = best bid/ask midpoint of the combined view book;
        empty side -> "" + mid_available False, never a fabricated 0."""
        book = (v or {}).get("order_book") or {}
        bids, asks = book.get("bids") or [], book.get("asks") or []
        mid = (bids[0][0] + asks[0][0]) / 2.0 if bids and asks else 0.0
        return {"asset": asset, "ts": now,
                "decision_mid": f"{mid:.10g}" if mid > 0 else "",
                "mid_available": bool(mid > 0),
                "direction": "", "confidence": "", "gates": {},
                "absorb": ""}

    def _de_append(self, ev: dict) -> None:
        """Guarded exactly like _absorb: telemetry never breaks the loop."""
        try:
            self._de_events.append(ev)
        except Exception:              # pragma: no cover - defensive only
            log.exception("DE-010 buffer append failed")

    def _flush_decision_events(self, now: float) -> None:
        """One DE-010 audit record per hour carrying the arrival vector.
        Same rate-limit discipline as EN-000 (core/codes.py:673-679).
        Buffer is kept on emit failure and retried next hour; on process
        stop up to one hour of buffered events is lost - named, accepted."""
        if not self._de_events:
            return
        if now - self._de_emitted < 3600.0:
            return
        try:
            get_audit().log("entry_sweep", Code.DE_DECISION_EVENTS,
                            "per-arrival decision events (hourly batch)",
                            {"events": list(self._de_events)})
            self._de_events = []
            self._de_emitted = now
        except Exception:              # pragma: no cover - defensive only
            log.exception("DE-010 emit failed")
```

(c) Flush call beside main.py:4596 (`self._emit_absorb_summary(now)`):

```python
        self._flush_decision_events(now)
```

(d) Capture in the loop. At main.py:4616–4619 (arrival + EN-020 branch):

```python
            self._absorb("arrivals")
            _de = self._de_event(asset, v, now)
            if self.orders.has_open(asset, "entry", book="5m"):
                self._absorb(Code.EN_OPEN_ENTRY)
                _de["absorb"] = Code.EN_OPEN_ENTRY.value
                self._de_append(_de)
                continue
```

At main.py:4686–4688 (EN-030 branch):

```python
            if not signal.all_confirmed or not signal.direction:
                self._absorb(Code.EN_SIGNAL_UNCONFIRMED)
                _de["absorb"] = Code.EN_SIGNAL_UNCONFIRMED.value
                _de["gates"] = {k: bool(x) for k, x in
                                (signal.gates_passed or {}).items()}
                self._de_append(_de)
                continue
```

Immediately after that block (the fall-through, gate stack passed):

```python
            _de["absorb"] = "passed_gate_stack"
            _de["direction"] = str(signal.direction or "")
            _de["confidence"] = round(float(signal.confidence), 3)
            _de["gates"] = {k: bool(x) for k, x in
                            (signal.gates_passed or {}).items()}
            self._de_append(_de)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_decision_events.py -q -p no:cacheprovider`
Expected: PASS (2 tests)

- [ ] **Step 6: Full DoD matrix**

Run every command from Global Constraints (all eight). Expected: pytest/smoke/assurance green; overfit 3/2 with ONLY the two documented guarded reds; ruff/pyright/bandit/compileall clean.

- [ ] **Step 7: Commit**

```bash
git add core/codes.py main.py tests/test_decision_events.py
git commit -m "feat(measure): DE-010 hourly per-arrival decision-event capture (SAFE)"
```

---

### Task 3: `book` stamp on 5m entries (A2, the honest version)

**Files:**
- Modify: `main.py` (:1541, :5113, :6032 meta dicts)
- Test: `tests/test_book_stamp.py`

**Interfaces:**
- Consumes: nothing new — the desk label is constant per site.
- Produces: `fills.csv.book` populated `"5m"` on new 5m fills (long book already stamps `"long"` via main.py:5842). Lane B's attribution reads this column.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_book_stamp.py
"""A2 pins: every 5m entry meta carries book='5m'; fill_row keeps its
three-way semantics (None pre-column / '' absent / value stamped)."""
from pathlib import Path
from types import SimpleNamespace

from core.fill_ledger import fill_row

_ROOT = Path(__file__).resolve().parents[1]
_MAIN_SRC = (_ROOT / "main.py").read_text(encoding="utf-8")


def _fill_book(meta):
    order = SimpleNamespace(purpose="entry", symbol="ETH/USD", side="buy",
                            ordertype="limit", post_only=True,
                            meta=meta, remaining=0.0)
    event = SimpleNamespace(fill_size=1.0, fill_price=2000.0)
    return fill_row(order, event, 0.0, 1_700_000_000.0)["book"]


def test_each_5m_entry_meta_dict_stamps_book():
    # the three 5m entry submit() sites (algo-child / main / grid rung):
    # each meta literal must carry "book": "5m" after this task
    assert _MAIN_SRC.count('"book": "5m"') >= 3


def test_fill_row_semantics_unchanged():
    assert _fill_book({"book": "5m"}) == "5m"
    assert _fill_book({"book": "long"}) == "long"
    assert _fill_book({}) == ""          # writer-knew-but-absent, preserved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_book_stamp.py -q -p no:cacheprovider`
Expected: FAIL on the count assertion (0 < 3)

- [ ] **Step 3: Stamp the three sites**

main.py:1541 (algo-child meta, first key): add `"book": "5m",` as the first entry of the meta literal.
main.py:5113 (main entry meta): add `"book": "5m",` as the first entry.
main.py:6032 (grid-rung meta): add `"book": "5m",` as the first entry.

Each with a one-line comment: `# desk label for fills.csv attribution (A2)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_book_stamp.py -q -p no:cacheprovider`
Expected: PASS (2 tests)

- [ ] **Step 5: Full DoD matrix** (all eight commands, same expectations as Task 2 Step 6)

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_book_stamp.py
git commit -m "fix(measure): stamp book='5m' at the three 5m entry meta sites (SAFE half of long-book row)"
```

---

### Task 4: Close-out — findings contributed properly

**Files:**
- Modify: `docs/HANDOFF.md` (one-line router rows per its contract)

- [ ] **Step 1: HANDOFF rows**

Add one line each to the appropriate sections (RECENTLY SETTLED / LIVE STATE per the file's contract): the census record path + headline decomposition; DE-010 live (hole stops regrowing from the first post-capture boot; coverage readable via the census's `de010_coverage` line); book stamp landed (attribution unblocked for new fills).

- [ ] **Step 2: Docs gate**

Run: `.venv/Scripts/python.exe -m pytest tests/test_docs_era_currency.py -q -p no:cacheprovider` — Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add docs/HANDOFF.md
git commit -m "docs(state): census record + DE-010 + book stamp router rows (SAFE)"
```

---

## Self-review notes (plan author, 2026-09-19)

- Spec coverage: Lane 0 → Task 1; A1 → Task 2; A2 → Task 3; "findings contributed" → Tasks 1 Step 5 + 4. Lanes B–E are Plan 2+ (B and C consume DE-010's schema; D/E independent). The spec's closing census re-run maps to the census's built-in `de010_coverage` line.
- The census's refusal-on-inconsistency is deliberate: an unreconciled census is a finding for the operator, never something to patch over (Task 1 Step 5 says so in place).
- Type consistency: `_de_event` payload keys match `GRADER_NEEDS` in the census; `DE-010` string matches `Code.DE_DECISION_EVENTS.value`; test imports verified against `tests/test_context_integration.py:60-66`.
