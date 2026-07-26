# Learnaccel Phase 2 — Free Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the report-only learning instruments from spec §3 (calib-gap
surfacing, sim-to-live detectors, learning-curve report, Fellegi–Sunter
linkage estimator) plus the skimmer promotion double-count guard fix —
zero authority paths, every stat grep-provably report-only.

**Architecture:** Every instrument attaches to an existing seam: the
retrain record (`ml/retrain_log.py`), the training-data loader's
`last_load_stats` (`ml/history.py` → status `ml.load_stats` for free), or a
standalone offline script under `scripts/`. No decision path reads any new
value. New ML-* codes are detection-only log lines (scout-confirmed: the
dashboard decode-coverage test enforces SZ/CV/PT families only — no
CODE_LABELS / dashboard-JSON regeneration needed for ML-*).

**Tech Stack:** numpy-only in ml/ (no pandas/scipy — verified convention),
stdlib + repo imports in scripts/.

## Global Constraints

- CLAUDE.md hard invariants 1–7 untouched. Report-only means: no new value
  is read by any sizing, gating, ordering, or exit path — reviewer will
  grep-verify.
- Public interfaces stay stable: extend with trailing defaults, never
  rename/reorder (hard invariant #7; precedent language ml/history.py:763
  "Interface extended, not changed").
- Every new tunable lives in config.json with core/config_guard.py checks
  (FATAL for incoherent values) + a sibling `_<block>_doc` key; guards are
  inline in `validate(config) -> list` using `_f()` + the `fatal`/`warn`
  closures (pattern: drought_floor block at config_guard.py:909-924).
- New behavior = registered code in core/codes.py + same-commit test.
  Numbering (scout-verified next free): ML_LINEAGE_AGREEMENT="ML-077",
  ML_SIM_DIVERGENCE="ML-078", ML_LINKAGE_REPORT="ML-079". ML-* codes need
  NO CODE_LABELS entry (tests/test_trading_dashboard.py:277 enforces only
  `value[:2] in ("SZ","CV","PT")`).
- No wall-clock in decision paths; loaders/scripts may use row timestamps.
  Seeding idiom: `np.random.default_rng(seed)`, seed as a constructor
  kwarg defaulting to 7 — never bare `np.random.*` (ml/models.py:88).
- No bare print in engine/library code; scripts' human output is fine
  (lessons_digest/interpret_report precedent). Module loggers:
  `logging.getLogger("liquiditybot.ml.<module>")`.
- pyright shipped scope includes ml/ — new ml/linkage.py must be 0-error.
  tests/test_import_integrity.py auto-sweeps ml/*.py — must import
  standalone (numpy-only ⇒ no optional-dep exemption).
- status['ml'] extensions are additive via `getattr(bot, "...", default)`
  (precedent runner.py:627). Naming: never reuse `calibration_gap` (that
  key is status['monitor']'s live-window ECE, already exported to Grafana
  as `liquiditybot_ml_calibration_gap` by scripts/gc_pusher.py:486) — the
  retrain-time metric ships as `retrain_calib_gap`.
- Run the full battery at Task 7 (phase end); per-task gate = the task's
  covering tests + the focused files named in each task. Foreground
  commands only; pass a long Bash timeout (600000) for full-suite runs.
- Committer identity per commit: `git config user.email
  noreply@anthropic.com && git config user.name Claude`; verify after
  commit with `git log -1 --format='%ae %ce'`. Commit trailers verbatim:

```
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01TgfcWLtZtVMQhbiPZCCV8h
```

- Do NOT push and do NOT touch main; the controller pushes after review.
  Branch: claude/remote-control-e3h815 (already checked out).

---

### Task 1: Skimmer promotion double-count guard fix

Observed CRITICAL on the operator's PC (2026-07-25): after the skimmer
promoted 6 pairs, `merge_skimmer_universe` (runner.py:45-73, called at
runner.py:1052 BEFORE LiquidityBot's `enforce_config` at main.py:421)
rewrote `trading_pairs = core + extra`, so config_guard's capacity check
(config_guard.py:1632: `len(core) + max_extra > 12`) saw core=12 and
double-counted the already-consumed promotion budget → 12+6=18 > 12 FATAL.
Fix seam (scout-verified): stash the promoted list on the config at the
merge write-back; guard subtracts it before counting. Guard stays pure
(dict-only, no file I/O).

**Files:**
- Modify: `runner.py:69-72` (merge write-back)
- Modify: `core/config_guard.py:1625-1635` (skimmer capacity check)
- Create: `tests/test_config_guard_skimmer.py`
- Modify: `tests/test_skimmer_boot.py` (assert the new marker in the
  existing merge tests)

**Interfaces:**
- Produces: `config["skimmer"]["_merged_promoted"]: list[str]` — runtime
  marker set ONLY by `merge_skimmer_universe`; underscore prefix = not an
  operator knob (do not add to config.json, do not guard its absence).

- [ ] **Step 1: Write the failing tests**

`tests/test_config_guard_skimmer.py` (new file — the guard block has ZERO
direct coverage today, scout-verified):

```python
"""config_guard skimmer capacity envelope — incl. the merged-promotion
double-count regression (observed CRITICAL 2026-07-25: 6 core + 6 merged
promotions + max_extra 6 read as 18 > 12). Promoted pairs already consumed
the promotion budget; the guard must subtract the runner's
`skimmer._merged_promoted` marker before comparing against the 12-pair
REST-fallback envelope."""
import json

from core.config_guard import validate
from runner import merge_skimmer_universe


def _fatals(cfg):
    return [m for s, m in validate(cfg) if s == "FATAL"]


def _envelope_fatals(cfg):
    return [m for m in _fatals(cfg) if "REST-fallback" in m]


def _cfg(pairs, max_extra=6, promoted=None):
    cfg = {"system": {"dry_run": True},
           "exchanges": {"kraken": {"trading_pairs": list(pairs)}},
           "skimmer": {"enabled": True, "max_extra": max_extra}}
    if promoted is not None:
        cfg["skimmer"]["_merged_promoted"] = list(promoted)
    return cfg


_P = ["ETH/USD", "BTC/USD", "SOL/USD", "XRP/USD", "ADA/USD", "DOGE/USD",
      "DOT/USD", "AVAX/USD", "LINK/USD", "LTC/USD", "UNI/USD", "ATOM/USD",
      "NEAR/USD", "ALGO/USD"]


def test_base_beyond_envelope_still_fatal():
    assert _envelope_fatals(_cfg(_P[:8], max_extra=6))


def test_base_within_envelope_ok():
    assert not _envelope_fatals(_cfg(_P[:6], max_extra=6))


def test_merged_promotions_do_not_double_count():
    # the exact observed scenario: 6 base + 6 merged promotions, budget 6
    assert not _envelope_fatals(
        _cfg(_P[:12], max_extra=6, promoted=_P[6:12]))


def test_oversized_base_with_promotions_still_fatal():
    # effective base 8 + budget 6 = 14 > 12 even after subtracting merges
    assert _envelope_fatals(
        _cfg(_P[:14], max_extra=6, promoted=_P[8:14]))


def test_merge_then_validate_sequence(tmp_path):
    # end-to-end pin of the boot ordering that produced the CRITICAL
    active = tmp_path / "skimmer_active.json"
    active.write_text(json.dumps(
        {"version": 1, "updated": 0, "extra_pairs": _P[6:12], "scores": {}}),
        encoding="utf-8")
    cfg = _cfg(_P[:6], max_extra=6)
    extra = merge_skimmer_universe(cfg, active_path=str(active))
    assert extra == _P[6:12]
    assert cfg["skimmer"]["_merged_promoted"] == _P[6:12]
    assert cfg["exchanges"]["kraken"]["trading_pairs"] == _P[:12]
    assert not _envelope_fatals(cfg)
```

- [ ] **Step 2: Run to verify the regression tests fail**

Run: `.venv/bin/python -m pytest tests/test_config_guard_skimmer.py -q`
Expected: `test_merged_promotions_do_not_double_count` and
`test_merge_then_validate_sequence` FAIL (envelope fatal present);
`test_base_beyond_envelope_still_fatal` / `test_base_within_envelope_ok`
PASS (pre-existing behavior). If `merge_skimmer_universe` requires a
skimmer-enabled/dry-run shape different from `_cfg`, read runner.py:45-73
and adjust `_cfg` — do not weaken the assertions.

- [ ] **Step 3: Implement**

runner.py — at the write-back (currently
`config.setdefault("exchanges", {}).setdefault("kraken", {})["trading_pairs"] = core + extra`,
line ~70), add immediately after it:

```python
    # Guard-visible provenance: promoted pairs already consumed the
    # promotion budget, so config_guard must not count max_extra against
    # them again (2026-07-25 false FATAL: 6 core + 6 merged read as 18).
    config.setdefault("skimmer", {})["_merged_promoted"] = list(extra)
```

core/config_guard.py — in the skimmer block, replace the capacity check:

```python
        core = _f(config, "exchanges.kraken.trading_pairs", []) or []
        promoted = set(_f(config, "skimmer._merged_promoted", []) or [])
        base = [c for c in core if c not in promoted]
        max_extra = int(_f(config, "skimmer.max_extra", 6))
        ...
        if len(base) + max_extra > 12:
            fatal(f"skimmer: core ({len(base)}) + max_extra ({max_extra}) "
                  f"exceeds the 12-pair REST-fallback envelope - a WS outage "
                  f"would starve the book poll at 3 req/s")
```

Keep every other check in the block reading `core` (the full merged list)
unchanged unless it has the same double-count shape — read lines 1624-1652
and report in your notes which variable each surviving check uses and why.

tests/test_skimmer_boot.py — in the existing merge test(s) that call
`merge_skimmer_universe` and assert the `trading_pairs` write-back
(`test_dry_run_merges_promotions`, `test_merge_validates_and_caps`), add
one assertion each that `cfg["skimmer"]["_merged_promoted"]` equals the
returned `extra` list. In `test_missing_file_is_noop` assert the marker is
either absent or `[]`.

- [ ] **Step 4: Run the covering tests**

Run: `.venv/bin/python -m pytest tests/test_config_guard_skimmer.py tests/test_skimmer_boot.py tests/test_skimmer.py tests/test_config_guard_coherence.py -q`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add runner.py core/config_guard.py tests/test_config_guard_skimmer.py tests/test_skimmer_boot.py
git commit -m "fix(skimmer): merged promotions no longer double-count against max_extra envelope"
```
(with the two standard trailers)

---

### Task 2: T2.1 — calib-gap surfacing (retrain record + status)

The per-family expected-calibration-error is already computed at
ml/walkforward.py:302 (`gap_cal = calibration_gap(cat_y, cat_p_cal)`) and
stored in `results[name]["calib_gap"]` (line 311) — then discarded:
`retrain_record` (ml/retrain_log.py:16) pulls only `mean_brier` per
family. Surface it additively into retrain_history.jsonl and status.

**Files:**
- Modify: `ml/retrain_log.py`
- Modify: `main.py` (`_maybe_auto_retrain` ~line 4659ff; `__init__` init)
- Modify: `runner.py:613-638` (status `ml` dict — scout note: one map
  attributed this dict to main.py:613, the other to runner.py:613; grep
  `"retrain_flag"` to locate the real literal before editing, and edit
  only the build_status producer)
- Modify: `tests/test_performance_records.py`
- Modify: `tests/test_context_integration.py` (build_status harness —
  smallest existing fixture that exercises the real status producer)

**Interfaces:**
- Produces: `family_metric(results: dict, metric: str) -> dict` in
  ml/retrain_log.py; retrain_history.jsonl rows gain trailing key
  `"family_calib_gap"`; status gains `ml.retrain_calib_gap: dict`
  (empty {} until first retrain); engine attr
  `self._last_retrain_calib_gap: dict` (not persisted — rebuilt each
  retrain, report-only).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_performance_records.py`:

```python
def test_retrain_record_family_calib_gap():
    results = {"selected": "logistic",
               "logistic": {"mean_brier": 0.21, "calib_gap": 0.041},
               "gbt": {"mean_brier": 0.23}}          # no calib_gap: omitted
    rec = retrain_record(1000.0, "auto", results, 2000, 71,
                         oof_brier=0.19, champion_bar=None, deployed=False)
    assert rec["family_calib_gap"] == {"logistic": 0.041}
    assert rec["family_brier"] == {"logistic": 0.21, "gbt": 0.23}


def test_family_metric_helper_rounds_and_filters():
    from ml.retrain_log import family_metric
    results = {"gbt": {"calib_gap": 0.123456}, "mlp": "not-a-dict"}
    assert family_metric(results, "calib_gap") == {"gbt": 0.12346}
    assert family_metric(results, "absent") == {}
```

Append to `tests/test_context_integration.py` (reuses its `_bot`/`_cfg`
harness and the frozen-clock idiom already present in
`test_runner_build_status_includes_serializable_context_section`):

```python
def test_status_ml_retrain_calib_gap_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bot = _bot(_cfg(), {"ETH": 2000.0, "BTC": 60000.0})
    runner = BotRunner(bot.config, bot=bot)
    status = runner.build_status(1_700_000_000.0)
    assert status["ml"]["retrain_calib_gap"] == {}      # pre-first-retrain
    bot._last_retrain_calib_gap = {"gbt": 0.05}
    status = runner.build_status(1_700_000_000.0)
    assert status["ml"]["retrain_calib_gap"] == {"gbt": 0.05}
    json.dumps(status)                                   # stays JSON-safe
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_performance_records.py tests/test_context_integration.py -q`
Expected: the three new tests FAIL (`family_metric` ImportError /
KeyError `family_calib_gap` / KeyError `retrain_calib_gap`); every
pre-existing test PASSES.

- [ ] **Step 3: Implement**

ml/retrain_log.py — extract the family-scan into a helper and reuse it
(DRY; keep the exact families tuple and rounding of the existing code):

```python
_FAMILIES = ("logistic", "gbt", "blend", "mlp", "adaptive_gbt")


def family_metric(results: dict, metric: str) -> dict:
    """Per-family {name: round(value,5)} for one metric out of the
    evaluate_and_select results dict; families missing the metric (or not
    dicts) are omitted. Report-only accessor - never a decision input."""
    return {k: round(float(results[k][metric]), 5) for k in _FAMILIES
            if isinstance(results.get(k), dict) and metric in results[k]}
```

In `retrain_record`, replace the inline `fams = {...}` comprehension with
`fams = family_metric(results, "mean_brier")` and add ONE trailing key to
the returned dict: `"family_calib_gap": family_metric(results, "calib_gap")`.
Do not reorder or rename any existing key (structural test
`test_both_retrain_paths_write_history` greps source text — keep the
`append_retrain(` call sites and the `retrain_history.jsonl` literal
untouched).

main.py — in `__init__` near the other retrain counters (grep
`_retrain_failures`), add `self._last_retrain_calib_gap: dict = {}`.
In `_maybe_auto_retrain`, immediately after `results = evaluate_and_select(...)`
(line ~4659), add:

```python
        self._last_retrain_calib_gap = family_metric(results, "calib_gap")
```

and extend the existing `from ml.retrain_log import ...` import with
`family_metric`.

Status producer (build_status `ml` dict, located per Files note) — add one
line inside the dict literal, following the getattr precedent:

```python
            "retrain_calib_gap": getattr(bot, "_last_retrain_calib_gap", {}),
```

scripts/train_meta.py needs NO change (retrain_record builds the new key
internally; the CLI path inherits it).

- [ ] **Step 4: Run the covering tests**

Run: `.venv/bin/python -m pytest tests/test_performance_records.py tests/test_context_integration.py tests/test_walkforward.py -q`
Expected: ALL PASS. Also run
`rtk grep -n "retrain_calib_gap" scripts/gc_pusher.py` → no hits
(name-collision check against the exported monitor metric).

- [ ] **Step 5: Commit**

```bash
git add ml/retrain_log.py main.py runner.py tests/test_performance_records.py tests/test_context_integration.py
git commit -m "feat(ml): surface per-family calib_gap into retrain history + status (T2.1)"
```

---

### Task 3: T2.2b — lineage-pair agreement stat (dedup twins)

`load_training_data`'s clash guard (ml/history.py:448-469) DROPS every
candidate row whose `position_id` matches a live row's `candidate_id` —
today only a count (`dropped_clash`, log-only at :513). Those dropped
pairs are (proxy label, realized label) twins: capture their agreement
rate + Wilson 95% CI as the free simulator-fidelity stat (prior
exploratory estimate: 80 pairs, 86.3%, [0.77, 0.92]).

**Files:**
- Modify: `ml/history.py` (`load_training_data` two-pass block; module
  helper; `last_load_stats`)
- Modify: `core/codes.py` (ML_LINEAGE_AGREEMENT = "ML-077")
- Modify: `config.json` + `core/config_guard.py` (`ml.telemetry` block)
- Create: `tests/test_lineage_agreement.py`

**Interfaces:**
- Produces: `last_load_stats["lineage_agreement"] = {"n_pairs": int,
  "agreement": float|None, "wilson95": [lo, hi]|None}` (reaches status
  for free via `ml.load_stats`); helper
  `wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]`
  in ml/history.py (module-level, reused by Task 6's report);
  `Code.ML_LINEAGE_AGREEMENT`; config `ml.telemetry.lineage_min_pairs`
  (default 10) — the minimum pair count before the ML-077 log line fires
  (the stat itself is always computed and surfaced).

- [ ] **Step 1: Write the failing tests**

`tests/test_lineage_agreement.py`:

```python
"""T2.2b lineage-pair agreement: dedup-discarded candidate twins carry a
proxy label; their live twin carries the realized label. Agreement rate +
Wilson CI must surface in last_load_stats - and the dedup DROP behavior
itself must stay byte-identical (pairs are captured, rows still dropped)."""
import numpy as np
import pytest

from ml.features import FEATURE_NAMES
from ml.history import HistoryStore, wilson_interval


def _feats(seed):
    rng = np.random.default_rng(seed)
    return {n: float(v) for n, v in
            zip(FEATURE_NAMES, rng.normal(0, 1, len(FEATURE_NAMES)))}


def _store(tmp_path):
    return HistoryStore(path=str(tmp_path / "hist.csv"))


def _pair(store, i, cand_label, live_label):
    cid = f"cand-{i}"
    store._append_row(cid, "ETH", "long", _feats(i), cand_label, 0.0,
                      "candidate", signal_ts=1000.0 + i)
    store._append_row(f"live-{i}", "ETH", "long", _feats(1000 + i),
                      live_label, 5.0, "live", signal_ts=1000.0 + i,
                      probe="0", candidate_id=cid)


def test_wilson_interval_known_values():
    lo, hi = wilson_interval(8, 10)
    assert 0.49 < lo < 0.51 and 0.93 < hi < 0.95
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_agreement_captured_and_rows_still_dropped(tmp_path):
    store = _store(tmp_path)
    for i in range(8):
        _pair(store, i, 1.0, 1.0)      # 8 agreeing twins
    for i in range(8, 10):
        _pair(store, i, 1.0, 0.0)      # 2 disagreeing twins
    X, y, w = store.load_training_data()
    la = store.last_load_stats["lineage_agreement"]
    assert la["n_pairs"] == 10
    assert la["agreement"] == pytest.approx(0.8)
    lo, hi = la["wilson95"]
    assert 0.0 <= lo <= 0.8 <= hi <= 1.0
    # twins still deduped: 10 live rows survive, 10 candidate twins drop
    assert len(X) == 10
    assert store.last_load_stats["dropped_clash"] == 10


def test_no_pairs_yields_none_fields(tmp_path):
    store = _store(tmp_path)
    store._append_row("solo-1", "ETH", "long", _feats(1), 1.0, 0.0,
                      "candidate", signal_ts=1000.0)
    store.load_training_data()
    la = store.last_load_stats["lineage_agreement"]
    assert la == {"n_pairs": 0, "agreement": None, "wilson95": None}
```

Adapt `_append_row`'s exact signature from ml/history.py (read it first);
keep the scenario shapes and assertions.

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_lineage_agreement.py -q`
Expected: FAIL — ImportError `wilson_interval`, then KeyError
`lineage_agreement`.

- [ ] **Step 3: Implement**

core/codes.py — after ML_CHAMP_BADGE_SYNC:

```python
    ML_LINEAGE_AGREEMENT = "ML-077"  # dedup-twin proxy-vs-realized label
    #   agreement stat (T2.2b): simulator-fidelity telemetry over
    #   gate-passing signals only - detection-only, weights untouched
```

ml/history.py — module-level helper (near the top-level functions):

```python
def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion; (0,1) when n=0."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1.0 + z * z / n
    center = p + z * z / (2 * n)
    half = z * ((p * (1.0 - p) / n + z * z / (4.0 * n * n)) ** 0.5)
    return ((center - half) / denom, (center + half) / denom)
```

In `load_training_data`: first pass (live scan, :413-442) additionally
builds `live_label_by_cid: dict[str, float]` mapping each live row's
`candidate_id` → `float(row["label"])` (skip empty cids). Second pass, in
the lineage-match drop branch (:459-462), before `continue`:

```python
                    lv = live_label_by_cid.get(self_id)
                    if lv is not None:
                        try:
                            pair_flags.append(
                                1 if float(row["label"]) == lv else 0)
                        except (KeyError, ValueError):
                            pass
```

(`pair_flags: list[int]` initialized alongside `dropped_clash`.) The
exact-vector fallback branch (:464-467) captures nothing — no lineage key,
no defensible pairing. After the passes, next to the existing ML-074
fold-in (:592-599):

```python
        n_pairs = len(pair_flags)
        if n_pairs:
            agree = sum(pair_flags) / n_pairs
            lo, hi = wilson_interval(sum(pair_flags), n_pairs)
            la = {"n_pairs": n_pairs, "agreement": round(agree, 4),
                  "wilson95": [round(lo, 4), round(hi, 4)]}
            if n_pairs >= int(_tele_cfg.get("lineage_min_pairs", 10)):
                log.info(
                    "%s: lineage-twin agreement %.1f%% over %d pairs "
                    "(Wilson95 [%.2f, %.2f]) - gate-passing signals only; "
                    "detection-only, weights untouched",
                    Code.ML_LINEAGE_AGREEMENT.value, 100 * agree, n_pairs,
                    lo, hi)
        else:
            la = {"n_pairs": 0, "agreement": None, "wilson95": None}
        self.last_load_stats["lineage_agreement"] = la
```

where `_tele_cfg` is read once near the weights-cfg handling:
`_tele_cfg = (weights_cfg or {}).get("_telemetry") ...` — NO: keep config
plumbing simple and explicit. `load_training_data` has no config access
beyond `weights_cfg`; thread the knob the same way main.py threads
`weights_cfg`: add trailing kwarg `telemetry_cfg: dict | None = None` to
`load_training_data` (interface extended with a default — legacy callers
unaffected), and in main.py `_maybe_auto_retrain` pass
`telemetry_cfg=self.config.get("ml", {}).get("telemetry", {})`. In the
loader: `_tele_cfg = telemetry_cfg or {}`.

config.json — under `"ml"` (sibling of `"exploration"`):

```json
"telemetry": {
  "lineage_min_pairs": 10,
  "divergence_window_h": 24.0
},
"_telemetry_doc": "T2.2 report-only sim-to-live instruments (learnaccel Phase 2). lineage_min_pairs: minimum dedup-twin pairs before the ML-077 agreement log line fires (the stat itself always computes into last_load_stats). divergence_window_h: bucket width for the ML-078 live-covered-window divergence score (Task 4). Neither value is read by any decision path.",
```

(`divergence_window_h` ships now so Task 4 doesn't re-touch config.json.)

core/config_guard.py — inline in validate(), near the ml.sample_weights
block (:656-685):

```python
    tele = config.get("ml", {}).get("telemetry", {}) or {}
    if tele:
        lmp = int(_f(config, "ml.telemetry.lineage_min_pairs", 10))
        if not (1 <= lmp <= 10000):
            fatal(f"ml.telemetry.lineage_min_pairs ({lmp}) outside "
                  f"[1, 10000] - reporting threshold, not a gate")
        dwh = float(_f(config, "ml.telemetry.divergence_window_h", 24.0))
        if not (1.0 <= dwh <= 168.0):
            fatal(f"ml.telemetry.divergence_window_h ({dwh}) outside "
                  f"[1, 168] hours - must bucket meaningfully within a "
                  f"trading week")
```

- [ ] **Step 4: Run the covering tests**

Run: `.venv/bin/python -m pytest tests/test_lineage_agreement.py tests/test_sample_weights.py tests/test_signal_time_ordering.py tests/test_data_contracts.py tests/test_config_guard_coherence.py -q`
Expected: ALL PASS (the sample-weights/time-ordering suites pin that the
loader's existing behavior is untouched).

- [ ] **Step 5: Commit**

```bash
git add ml/history.py core/codes.py config.json core/config_guard.py main.py tests/test_lineage_agreement.py
git commit -m "feat(ml): lineage-twin agreement stat ML-077 in load stats (T2.2b)"
```

---

### Task 4: T2.2a — live-covered-window divergence score

Detection-only score: within time buckets that contain BOTH live and
candidate labels, how far apart are their label means; plus the coverage
stat (what fraction of candidate mass is live-validated at all). C4's
surviving form — no reweighting, no authority.

**Files:**
- Modify: `ml/history.py` (pure helper + capture in `load_training_data`
  + `last_load_stats`)
- Modify: `core/codes.py` (ML_SIM_DIVERGENCE = "ML-078")
- Create: `tests/test_sim_divergence.py`

(config knob `divergence_window_h` + guard shipped in Task 3.)

**Interfaces:**
- Consumes: `telemetry_cfg` kwarg (Task 3), `divergence_window_h` knob.
- Produces: module-level pure function
  `sim_live_divergence(times, sources, labels, window_sec) -> dict`
  returning `{"score": float|None, "coverage": float, "windows_both": int,
  "n_cand": int}`; `last_load_stats["sim_live_divergence"]` = that dict +
  `{"window_h": <cfg>}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_sim_divergence.py`:

```python
"""T2.2a divergence score: only windows containing BOTH live and candidate
labels contribute (weighted by candidate count); coverage = candidate rows
in live-covered windows / all candidate rows. Pure function + loader
capture. Report-only."""
import pytest

from ml.history import sim_live_divergence


def test_two_windows_weighted_score_and_coverage():
    # window 0 (t<3600): live mean 1.0, cand mean 0.5, 2 cand rows
    # window 1: live mean 0.0, cand mean 0.0, 1 cand row
    # window 2: candidate-only - excluded from score, dilutes coverage
    times = [0, 10, 20, 30, 3700, 3800, 7300, 7400]
    srcs = ["live", "cand", "cand", "live", "live", "cand", "cand", "cand"]
    labels = [1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0]
    d = sim_live_divergence(times, srcs, labels, 3600.0)
    assert d["windows_both"] == 2
    assert d["n_cand"] == 5
    # weighted: (0.5*2 + 0.0*1) / 3
    assert d["score"] == pytest.approx(1.0 / 3.0, abs=1e-9)
    assert d["coverage"] == pytest.approx(3 / 5)


def test_no_overlap_yields_none_score_zero_coverage():
    d = sim_live_divergence([0, 5000], ["live", "cand"], [1.0, 0.0], 3600.0)
    assert d == {"score": None, "coverage": 0.0, "windows_both": 0,
                 "n_cand": 1}


def test_empty_inputs():
    assert sim_live_divergence([], [], [], 3600.0)["score"] is None
```

Plus a loader-capture test appended to the same file: build a
`HistoryStore` in tmp (reuse Task 3's `_feats` helper shape), append 2
live + 2 candidate rows sharing one hour-bucket with differing labels,
call `load_training_data(telemetry_cfg={"divergence_window_h": 1.0})`, and
assert `store.last_load_stats["sim_live_divergence"]["score"]` matches the
hand-computed value and `["window_h"] == 1.0`.

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_sim_divergence.py -q`
Expected: FAIL with ImportError `sim_live_divergence`.

- [ ] **Step 3: Implement**

core/codes.py — after ML_LINEAGE_AGREEMENT:

```python
    ML_SIM_DIVERGENCE = "ML-078"  # candidate-vs-live label-mean divergence
    #   inside live-covered time windows + coverage stat (T2.2a, C4
    #   surviving form) - detection-only, no reweighting authority
```

ml/history.py — module-level pure function:

```python
def sim_live_divergence(times, sources, labels,
                        window_sec: float) -> dict:
    """Weighted |mean(live label) - mean(candidate label)| over time
    buckets containing BOTH sources (weight = candidate count in bucket);
    coverage = candidate rows in such buckets / all candidate rows.
    Report-only: quantifies where the simulator's labels disagree with
    realized outcomes, only where realized outcomes exist to compare."""
    buckets: dict = {}
    n_cand = 0
    for t, s, y in zip(times, sources, labels):
        b = buckets.setdefault(int(float(t) // window_sec),
                               [0.0, 0, 0.0, 0])
        if s == "live":
            b[0] += y; b[1] += 1
        else:
            b[2] += y; b[3] += 1
            n_cand += 1
    num = den = covered = 0.0
    windows_both = 0
    for b in buckets.values():
        if b[1] and b[3]:
            windows_both += 1
            covered += b[3]
            num += abs(b[0] / b[1] - b[2] / b[3]) * b[3]
            den += b[3]
    return {"score": (round(num / den, 4) if den else None),
            "coverage": round((covered / n_cand) if n_cand else 0.0, 4),
            "windows_both": windows_both, "n_cand": n_cand}
```

In `load_training_data`: during the second pass, for every row that
SURVIVES into the dataset AND every candidate row (including deduped
drops? NO — measure the corpus the model actually trains on: capture only
surviving rows), append `(sig_time, "live"|"cand", label)` to three
parallel lists. After the loop:

```python
        dwh = float(_tele_cfg.get("divergence_window_h", 24.0))
        div = sim_live_divergence(_div_t, _div_s, _div_y, dwh * 3600.0)
        div["window_h"] = dwh
        self.last_load_stats["sim_live_divergence"] = div
        if div["score"] is not None:
            log.info(
                "%s: sim-live divergence %.3f over %d shared window(s), "
                "coverage %.0f%% of candidate rows - detection only",
                Code.ML_SIM_DIVERGENCE.value, div["score"],
                div["windows_both"], 100 * div["coverage"])
```

- [ ] **Step 4: Run the covering tests**

Run: `.venv/bin/python -m pytest tests/test_sim_divergence.py tests/test_lineage_agreement.py tests/test_sample_weights.py tests/test_signal_time_ordering.py -q`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add ml/history.py core/codes.py tests/test_sim_divergence.py
git commit -m "feat(ml): live-covered-window sim divergence ML-078 (T2.2a)"
```

---

### Task 5: T2.3 — offline learning-curve report

retrain_history.jsonl is degenerate (156 byte-identical rows), so the
curve comes from TIME-PREFIX REFITS of signal_history.csv through the
DEPLOYED walkforward — never a parallel implementation. Offline script;
no config knobs (DEFAULTS + CLI); prices the probe label for the
operator.

**Files:**
- Create: `scripts/learning_curve.py`
- Create: `tests/test_learning_curve.py`

**Interfaces:**
- Consumes: `HistoryStore.load_training_data(return_label_times=True,
  weights_cfg=...)` (X, y, w, sig, res — sig-ascending, ml/history.py:609);
  `evaluate_and_select(X, y, sample_weight=, feature_names=, label_span=,
  sig=, res=, n_live=)` with its DEFAULT n_splits=5 (deployed parity —
  main.py:4659 passes no n_splits); `ml.contracts.get_contract()
  .check_matrix(X)["keep"]` poison filter (main.py:4628);
  `regime_stratified_oof` + `REGIME_STRATA` (ml/overfit.py:512/473);
  regime one-hot column indices via
  `FEATURE_NAMES.index(f"regime_{s}")` (overfit_check.py:364).
- Produces: `outputs/learning_curve.md` + `outputs/learning_curve.json`.

- [ ] **Step 1: Write the script**

`scripts/learning_curve.py`, skeleton per scripts/interpret_report.py
(argparse; `ROOT = Path(__file__).resolve().parents[1]`;
`sys.path.insert(0, str(ROOT))`; `# noqa: E402` imports; DEFAULTS dict;
report-only docstring):

```python
"""Learning-curve report (T2.3, learnaccel Phase 2). REPORT-ONLY: refits
the DEPLOYED walkforward selector on time-prefixes of
outputs/signal_history.csv and writes outputs/learning_curve.{md,json} -
never touches config, state, or the registry.

Why prefixes: retrain_history.jsonl is degenerate at this corpus size
(near-identical rows), so the honest curve is oof-Brier / calib-gap vs
corpus size, computed by replaying the deployed selection on each prefix.
Stratified by regime (one-hot argmax) and annotated with the per-prefix
probe share from the raw CSV. Extrapolation is CAPPED at
extrapolate_max_mult x the observed live-N - beyond that is fiction.

Usage: python scripts/learning_curve.py [--config config.json]
       [--history outputs/signal_history.csv] [--fracs 0.4,0.55,0.7,0.85,1.0]
       [--n-splits 5] [--out-dir outputs]
"""
```

DEFAULTS:

```python
DEFAULTS = {"fracs": "0.4,0.55,0.7,0.85,1.0", "n_splits": 5,
            "min_prefix_rows": 240, "extrapolate_max_mult": 2.0}
```

Core flow (complete function bodies required — this is the shape):

```python
def probe_share_by_cutoff(history_path: str, cutoff_sig: float) -> float | None:
    """Probe share among live rows with signal_ts <= cutoff (raw CSV scan,
    header-resolved column indices - never positional)."""

def prefix_report(X, y, w, sig, res, n_frac, cfg, n_splits) -> dict:
    """One curve point: slice the first int(frac*n) rows (sig-ascending
    slices are time-prefixes by construction), require min positives per
    the fold constraint, run evaluate_and_select with deployed kwargs
    (label_span from cfg ml.label_max_bars default 96; n_live = count of
    live rows inside the prefix - see below), and return
    {frac, n_rows, n_live, selected, oof_brier, calib_gap, regime: {...}}."""

def main(argv=None) -> int:
    # argparse -> load config.json -> HistoryStore(history_path)
    # X, y, w, sig, res = store.load_training_data(return_label_times=True,
    #     weights_cfg=cfg.get("ml", {}).get("sample_weights", {}))
    # keep = get_contract().check_matrix(X)["keep"]; filter all five arrays
    # per-prefix n_live: live rows have net_pnl semantics only in the CSV -
    #   count from the raw CSV: live rows with signal_ts <= sig[prefix_end-1]
    # for each frac: point = prefix_report(...); point["probe_share"] = ...
    # regime strata: sel = results["selected"];
    #   oof_idx = results["oof_idx"]; oof_p = results[sel]["oof_p"]
    #   one_hot = X[np.asarray(oof_idx, int)][:, regime_cols]
    #   point["regime"] = regime_stratified_oof(y_prefix, oof_idx, oof_p,
    #        one_hot, pooled_brier=point["oof_brier"])
    # extrapolation: least-squares oof_brier ~ a + b*log2(n_live) over
    #   points with n_live >= 2; project ONLY to
    #   [live_now, extrapolate_max_mult * live_now]; if b >= 0 report
    #   "no measurable improvement with corpus growth" honestly.
    # write outputs/learning_curve.json (all points + projection + meta)
    # and outputs/learning_curve.md (table of points, the projection line,
    # the probe-label price paragraph); print the md. return 0
```

The implementer writes the full bodies; every numeric behavior above is
binding (fracs list, min positives skip rule with an explicit "skipped:
insufficient labels" entry, cap rule, b>=0 honesty rule).

- [ ] **Step 2: Write the failing tests**

`tests/test_learning_curve.py` — build a 160-row synthetic corpus through
the real `HistoryStore` API in tmp_path (alternating labels, two regimes
via the regime one-hot features, ~30 live rows with `probe` mixed "0"/"1",
signal_ts strictly increasing), then:

```python
def test_learning_curve_end_to_end(tmp_path, monkeypatch):
    ...build corpus...
    monkeypatch.chdir(tmp_path)            # outputs/ lands in tmp
    rc = learning_curve.main([
        "--history", str(hist), "--config", str(cfg_path),
        "--fracs", "0.5,1.0", "--n-splits", "3"])
    assert rc == 0
    data = json.loads((tmp_path / "outputs" / "learning_curve.json")
                      .read_text(encoding="utf-8"))
    assert [p["frac"] for p in data["points"]] == [0.5, 1.0]
    assert data["points"][1]["n_rows"] > data["points"][0]["n_rows"]
    for p in data["points"]:
        assert 0.0 <= (p["probe_share"] or 0.0) <= 1.0
        assert p["oof_brier"] is None or 0.0 <= p["oof_brier"] <= 1.0
    assert data["projection"]["cap_live_n"] == \
        2.0 * data["points"][-1]["n_live"]
    assert (tmp_path / "outputs" / "learning_curve.md").exists()


def test_determinism(tmp_path, monkeypatch):
    ...run main twice with identical args...
    assert json1 == json2
```

- [ ] **Step 3: Run tests to verify they fail, then implement fully, then pass**

Run: `.venv/bin/python -m pytest tests/test_learning_curve.py -q`
Expected first: FAIL (module missing) → implement → ALL PASS. Keep the
test corpus small enough that the file runs < 60 s.

- [ ] **Step 4: Run the script once against the real corpus**

Run: `.venv/bin/python scripts/learning_curve.py`
Expected: exit 0, outputs/learning_curve.{md,json} written, md printed.
Paste the md table into your report (this is the first real learning-curve
reading — the operator deliverable).

- [ ] **Step 5: Commit**

```bash
git add scripts/learning_curve.py tests/test_learning_curve.py
git commit -m "feat(scripts): time-prefix learning-curve report via deployed walkforward (T2.3)"
```

---

### Task 6: T2.4 — Fellegi–Sunter EM linkage (ml/linkage.py + report)

Port fast-er's latent-class EM (operator-directed integration; MIT
license, Copyright (c) 2024 Jacob Morrier, Sulekha Kishore, and R. Michael
Alvarez — full MIT notice reproduced in the module docstring). Strip:
CUDA/CuPy string kernels, blocking (pair space is tiny), pandas. Replace:
unseeded `np.random.dirichlet` init → `np.random.default_rng(seed)`;
`print()` → `log.info`. Purpose: extend Task 3's exact-lineage pairing to
probabilistically-linked pairs (rows with no exact key), expanding the
sim-to-live agreement sample. Report-only; feeds weights ONLY via the
Phase-4 density-ratio item's own gates (spec).

**Files:**
- Create: `ml/linkage.py`
- Create: `scripts/corpus_linkage_report.py`
- Modify: `core/codes.py` (ML_LINKAGE_REPORT = "ML-079")
- Modify: `config.json` + `core/config_guard.py` (`ml.linkage` block)
- Create: `tests/test_linkage.py`
- Create: `tests/test_config_guard_linkage.py`

**Interfaces:**
- Produces: `class FellegiSunterEM` in ml/linkage.py:
  `__init__(self, k_fuzzy: int, k_exact: int, counts, seed: int = 7)`,
  `fit(self, tol: float = 1e-4, max_iter: int = 5000) -> "FellegiSunterEM"`,
  properties `lam: float`, `match_posterior: np.ndarray` (Ksi, aligned to
  `patterns` rows), `patterns: np.ndarray`, `converged: bool`; module
  helpers `discretize_fuzzy(values, near, far) -> np.ndarray` (2 = |v| ≤
  near, 1 = ≤ far, 0 = beyond — level 2 is most-similar, matching the
  ascending-sorted match-class init) and
  `discretize_exact(a, b) -> np.ndarray` (1 = equal, 0 = not).
- Consumes (report script): `wilson_interval` from ml/history.py (Task 3),
  `FEATURE_NAMES`, `HistoryStore` CSV via raw csv.DictReader (header-
  resolved).
- Config: `ml.linkage {posterior_threshold: 0.9, seed: 7}` +
  `_linkage_doc`; guard: threshold FATAL outside [0.5, 0.999], seed FATAL
  if not int-castable ≥ 0.

- [ ] **Step 1: Write the failing tests**

`tests/test_linkage.py`:

```python
"""FS-EM port: synthetic-truth recovery, determinism, refit guard, edge
shapes. Counts are EXPECTED (deterministic) counts from a planted model -
no sampling noise, so recovery tolerances are tight."""
import numpy as np
import pytest

from ml.linkage import FellegiSunterEM, discretize_fuzzy, discretize_exact


def _planted_counts(lam=0.25, n=100_000):
    # 1 fuzzy var (3 levels), 1 exact var (2 levels)
    pi_m = [np.array([0.05, 0.15, 0.80]), np.array([0.10, 0.90])]
    pi_u = [np.array([0.70, 0.20, 0.10]), np.array([0.85, 0.15])]
    est = FellegiSunterEM(1, 1, np.zeros(6))
    pats = est.patterns
    counts = np.zeros(len(pats))
    for i, g in enumerate(pats):
        pm = pi_m[0][g[0]] * pi_m[1][g[1]]
        pu = pi_u[0][g[0]] * pi_u[1][g[1]]
        counts[i] = n * (lam * pm + (1 - lam) * pu)
    return counts


def test_synthetic_truth_recovery():
    est = FellegiSunterEM(1, 1, _planted_counts(), seed=7).fit()
    assert est.converged
    assert est.lam == pytest.approx(0.25, abs=0.05)
    pats = est.patterns
    post = est.match_posterior
    # most-similar pattern (2, 1) must dominate least-similar (0, 0)
    hi = post[np.flatnonzero((pats == [2, 1]).all(axis=1))[0]]
    lo = post[np.flatnonzero((pats == [0, 0]).all(axis=1))[0]]
    assert hi > 0.9 > 0.1 > lo


def test_determinism_same_seed():
    a = FellegiSunterEM(1, 1, _planted_counts(), seed=7).fit()
    b = FellegiSunterEM(1, 1, _planted_counts(), seed=7).fit()
    assert np.array_equal(a.match_posterior, b.match_posterior)
    assert a.lam == b.lam


def test_refit_raises():
    est = FellegiSunterEM(1, 1, _planted_counts()).fit()
    with pytest.raises(RuntimeError):
        est.fit()


def test_discretizers():
    f = discretize_fuzzy(np.array([0.0, 0.1, 5.0]), near=0.05, far=1.0)
    assert f.tolist() == [2, 1, 0]
    e = discretize_exact(np.array(["ETH", "ETH"]), np.array(["ETH", "BTC"]))
    assert e.tolist() == [1, 0]


def test_exact_only_and_fuzzy_only_shapes():
    assert len(FellegiSunterEM(0, 2, np.zeros(4)).patterns) == 4
    assert len(FellegiSunterEM(2, 0, np.zeros(9)).patterns) == 9
```

`tests/test_config_guard_linkage.py` — copy the
test_config_guard_probe_throttle.py idiom (`validate` import, `_fatals`
substring asserts): threshold 0.3 → fatal containing
"linkage.posterior_threshold"; 0.9 → clean; 1.0 → fatal; seed -1 → fatal.

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_linkage.py tests/test_config_guard_linkage.py -q`
Expected: FAIL — ModuleNotFoundError ml.linkage, then guard substrings
missing.

- [ ] **Step 3: Implement ml/linkage.py**

READ THE UPSTREAM SOURCE FIRST — the algorithm being ported:
`/tmp/claude-0/-home-user-liquiditybot-ab/c6d473e4-1320-5144-8fa7-88f0c50f903d/scratchpad/fast-er/faster/estimation.py`
(≈120 lines: `_Gamma` pattern enumeration, `_match_probability` E-step,
`fit` EM loop with the per-variable Pi M-step dot products). License text
to reproduce: same directory, `LICENSE.txt`.

Structure (numpy + itertools only; logger
`liquiditybot.ml.linkage`; full MIT notice from
the fast-er LICENSE.txt reproduced verbatim in the docstring):

```python
class FellegiSunterEM:
    def __init__(self, k_fuzzy: int, k_exact: int, counts, seed: int = 7):
        self.k_fuzzy, self.k_exact = int(k_fuzzy), int(k_exact)
        self.counts = np.asarray(counts, dtype=float)
        self.seed = int(seed)
        self.patterns = self._patterns()          # (P, K) int matrix
        if len(self.counts) != len(self.patterns):
            raise ValueError(...)
        self.lam: float = 0.0
        self._pi_m: list = []; self._pi_u: list = []
        self.converged = False; self._fitted = False

    def _patterns(self):
        levels = [3] * self.k_fuzzy + [2] * self.k_exact
        return np.array(list(itertools.product(
            *(range(n) for n in levels))), dtype=int)

    def _posterior(self):
        # log-space per-class pattern likelihoods, then Bayes (upstream
        # _match_probability, float64 not float32)

    def fit(self, tol: float = 1e-4, max_iter: int = 5000):
        if self._fitted:
            raise RuntimeError("FellegiSunterEM.fit() is one-shot")
        rng = np.random.default_rng(self.seed)
        levels = [3] * self.k_fuzzy + [2] * self.k_exact
        self._pi_u = [-np.sort(-rng.dirichlet(np.arange(1, n * 50 + 1, 50)))
                      for n in levels]           # non-match mass on low sims
        self._pi_m = [np.sort(rng.dirichlet(np.arange(1, n * 50 + 1, 50)))
                      for n in levels]           # match mass on high sims
        self.lam = 0.1
        # EM loop per upstream fit(): E-step ksi = self._posterior();
        # M-step lam + per-variable pi via the Gamma-mask dot products;
        # convergence = max |new_pi - old_pi| < tol
        # on exit: log.info("linkage EM %s in %d iter(s)",
        #     "converged" if self.converged else "hit max_iter", it)
        self._fitted = True
        return self

    @property
    def match_posterior(self):
        if not self._fitted:
            raise RuntimeError("call fit() first")
        return self._posterior()
```

The implementer fills the E/M steps faithfully from
the upstream algorithm (documented in the plan's header note; the
reviewer will check E/M math against the docstring's own equations —
write the update equations INTO the docstring). Guard the degenerate
`den == 0` Bayes cell with `np.errstate` + `np.nan_to_num(..., nan=0.0)`.

- [ ] **Step 4: Implement config + guard + code**

config.json under `"ml"`:

```json
"linkage": {
  "posterior_threshold": 0.9,
  "seed": 7
},
"_linkage_doc": "T2.4 Fellegi-Sunter EM record linkage (ported from fast-er, MIT, Morrier/Kishore/Alvarez 2024; seeded + print-free). Report-only: scripts/corpus_linkage_report.py links live closes to candidate twins beyond exact lineage keys and expands the T2.2b agreement sample. posterior_threshold: minimum P(match|pattern) to count a pair as linked - [0.5, 0.999] guarded; below 0.5 would link majority-non-match patterns. seed: EM init determinism. Feeds NO weights - density-ratio consumption is Phase 4, own gates.",
```

core/config_guard.py inline block (next to ml.telemetry from Task 3):

```python
    lk = config.get("ml", {}).get("linkage", {}) or {}
    if lk:
        thr = float(_f(config, "ml.linkage.posterior_threshold", 0.9))
        if not (0.5 <= thr <= 0.999):
            fatal(f"ml.linkage.posterior_threshold ({thr}) outside "
                  f"[0.5, 0.999] - below 0.5 links majority-non-match "
                  f"patterns; 1.0 links nothing")
        lseed = _f(config, "ml.linkage.seed", 7)
        if not isinstance(lseed, int) or isinstance(lseed, bool) or lseed < 0:
            fatal(f"ml.linkage.seed ({lseed!r}) must be a non-negative "
                  f"integer - EM init determinism")
```

core/codes.py after ML_SIM_DIVERGENCE:

```python
    ML_LINKAGE_REPORT = "ML-079"  # FS-EM corpus linkage report emitted
    #   (T2.4): probabilistically-linked live/candidate pairs + expanded
    #   agreement stat - report-only, no weight authority (Phase-4 gated)
```

- [ ] **Step 5: Implement scripts/corpus_linkage_report.py**

interpret_report.py skeleton. Flow: read config (`ml.linkage.*`), scan
signal_history.csv via csv.DictReader (header-resolved indices); pair
space = for each live row, candidate rows of the SAME asset+side within
±`window_h` (DEFAULTS: 24.0) of its signal_ts, EXCLUDING exact-lineage
matches (those are Task 3's exact pairs — report both populations
side-by-side); per pair compute pattern:
fuzzy 1 = `discretize_fuzzy(|Δsignal_ts| minutes, near=ts_near_min,
far=ts_far_min)` (DEFAULTS 10.0 / 60.0), fuzzy 2 =
`discretize_fuzzy(mean |Δfeature| over FEATURE_NAMES, near=feat_near,
far=feat_far)` (DEFAULTS 0.05 / 0.25), exact 1 = label present on both
(always 1 — keep the variable anyway? NO: drop it; k_exact=0, asset/side
equality is enforced by the pairing itself). So `FellegiSunterEM(2, 0,
counts, seed=cfg_seed)`. Count patterns → fit → linked = pairs whose
pattern posterior ≥ threshold → agreement over linked pairs' labels with
`wilson_interval`. Write outputs/corpus_linkage_report.{md,json}: pair
counts (exact vs linked), lambda, posterior table per pattern, agreement
both ways, the gate-passing-only caveat, and a
`log.info("%s: ...", Code.ML_LINKAGE_REPORT.value, ...)` line. Print the
md. Exit 0 even when the corpus yields zero pairs (report says so).

Add an end-to-end test to tests/test_linkage.py: small tmp CSV (real
header via HistoryStore, ~6 live + 8 candidate rows, some within the time
window with near-identical features), run
`corpus_linkage_report.main(["--config", ..., "--history", ...,
"--out-dir", ...])`, assert exit 0, json exists with keys
`{"n_exact_pairs", "n_linked_pairs", "lambda", "agreement_linked"}`, and
determinism (two runs → identical json).

- [ ] **Step 6: Run all covering tests + type gate**

Run: `.venv/bin/python -m pytest tests/test_linkage.py tests/test_config_guard_linkage.py tests/test_import_integrity.py -q`
Expected: ALL PASS.
Run: `/root/.local/bin/pyright ml/linkage.py` → 0 errors.

- [ ] **Step 7: Commit**

```bash
git add ml/linkage.py scripts/corpus_linkage_report.py core/codes.py config.json core/config_guard.py tests/test_linkage.py tests/test_config_guard_linkage.py
git commit -m "feat(ml): seeded Fellegi-Sunter EM linkage + corpus report (T2.4, fast-er port)"
```

---

### Task 7: Full battery + report

- [ ] **Step 1: Run the complete CLAUDE.md battery in order**

```
.venv/bin/python -m pytest tests/ -q                     (timeout 600000)
.venv/bin/python scripts/smoke_test.py
.venv/bin/python scripts/assurance_check.py
.venv/bin/python scripts/overfit_check.py
.venv/bin/ruff check core data execution ml risk regime strategies sentiment api main.py runner.py tests scripts/quant_trials.py scripts/overfit_check.py
/root/.local/bin/pyright core data execution ml risk regime strategies sentiment api main.py runner.py
.venv/bin/bandit -c pyproject.toml -r . -x ./.venv,./tests -q
.venv/bin/python -m compileall -q . -x '.venv'
```

Expected: pytest all green; smoke 219+/0; assurance 47/0; overfit at the
conscious baseline 5/3 — if the count differs, STOP and report
NEEDS_CONTEXT with the per-check verdict lines (the controller runs the
inertness protocol; do NOT re-baseline yourself); ruff clean; pyright 0;
bandit no findings; compileall OK.

- [ ] **Step 2: Grep-prove zero authority paths**

```
rtk grep -rn "lineage_agreement\|sim_live_divergence\|retrain_calib_gap\|match_posterior\|linkage" core/ execution/ risk/ regime/ strategies/ main.py | grep -v "config_guard\|codes.py"
```

Expected: no hits outside config_guard/codes (i.e. no decision path reads
any Phase-2 stat). Paste the command + empty output into the report.

- [ ] **Step 3: Report**

Write the phase report (battery outputs, the real learning-curve md table
from Task 5, the real corpus_linkage_report numbers, grep proof) and
report DONE. NO push, NO main fast-forward — the controller runs the
whole-phase review first.
