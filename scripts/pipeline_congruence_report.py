"""scripts/pipeline_congruence_report.py - is the corpus congruent with what
the pipeline actually saw? (REPORT-ONLY, reads outputs/, writes nothing)

Operator (2026-09-30): "Look at our pipeline in general and if the corpus is
congruent with the rows it's attained."

Four independent checks, each CS-1 reconciled (every row lands in exactly
one bucket, summed to n):

  A FUNNEL      candidate ids are `cand-<salt>-<seq>` and seq is persisted
                across restarts (state.json), so the era's registrations form
                ONE sequence: seqs minted - seqs written = candidates that
                never became a row. Still pending in state.json are counted
                apart. A seq written under TWO salts = a crash reused the
                counter (registrations after the last state save were lost).
  B LABELS      re-derive every era candidate row's triple-barrier outcome
                from the bot's OWN 5m bars (candle store lane bot_cache - the
                ring the labeler itself read, byte-comparable to entry_price)
                with the row's own stamped pt_frac/sl_frac, stop-first, 432
                bars (ml.label_max_bars). Compares entry_price, barrier,
                exit_price. A mismatch means the corpus does not say what the
                price path said.
  C LIVE ROWS   each live row's net_pnl_usd vs the net the fills ledger
                books for the same position (sells - buys - fees).
  D TRAINING    rows on disk vs rows the production loader returns, the
                store built through ml.history.store_for_config (the engine's
                own seam). NEVER the bare HistoryStore(path): its max_bars
                default of 96 selects the legacy label era - the exact
                complement of what the engine trains on (this script's first
                run fell into it: 5,287 vs the engine's 24,573). Reconciled by
                label era from the loader's own last_load_stats; any residual
                prints as `unexplained`, never absorbed.

Usage: python scripts/pipeline_congruence_report.py [--root DIR] [--since TS]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.cohort import reconcile  # noqa: E402

ERA9_START = 1788911265.0          # cut #12 restart 2026-09-08T23:47:45Z
BAR_S = 300
CAND = re.compile(r"^cand-([0-9a-f]{8})-(\d+)$")
PX_TOL = 1e-9                      # relative; entry_price is %.10g of the same close


def _f(x, d=None):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return d
    return v if np.isfinite(v) else d


def _rows(path: Path):
    with open(path, newline="", encoding="utf-8") as fh:
        yield from csv.DictReader(fh)


# ------------------------------------------------------------------ A funnel
def funnel(rows: list, pending_ids: set, since: float) -> dict:
    """seq accounting over candidate rows with signal_ts >= since."""
    seq_salts = collections.defaultdict(set)
    ids = collections.Counter()
    bare = 0
    for r in rows:
        if r.get("source") != "candidate":
            continue
        st = _f(r.get("signal_ts"), 0.0)
        if st < since:
            continue
        pid = r.get("position_id") or ""
        ids[pid] += 1
        m = CAND.match(pid)
        if not m:
            bare += 1
            continue
        seq_salts[int(m.group(2))].add(m.group(1))
    if not seq_salts:
        return {"n_rows": sum(ids.values()), "note": "no salted ids"}
    lo, hi = min(seq_salts), max(seq_salts)
    pend = set()
    for pid in pending_ids:
        m = CAND.match(pid)
        if m and lo <= int(m.group(2)) <= hi:
            pend.add(int(m.group(2)))
    span = hi - lo + 1
    written = set(seq_salts)
    never = span - len(written | pend)
    reused = sum(1 for s in seq_salts.values() if len(s) > 1)
    dup_ids = sum(c - 1 for c in ids.values() if c > 1)
    return {"seq_lo": lo, "seq_hi": hi, "minted": span,
            "written": len(written), "pending_now": len(pend - written),
            "never_written": never, "seq_reused_across_salts": reused,
            "duplicate_row_ids": dup_ids, "bare_ids": bare,
            "counting": reconcile(span, {
                "written": len(written),
                "pending_now": len(pend - written),
                "never_written": never})}


# ------------------------------------------------------------------ B labels
def rederive(t, c, h, lo_, i, side, pt, sl, horizon):
    """triple_barrier on the stamped fracs: (barrier, bars_held) or
    (None, n) when the window is not complete. Stop checked first, exactly
    as ml/labeling.triple_barrier."""
    entry = c[i]
    end = i + horizon
    last = len(c) - 1
    for j in range(i + 1, min(end, last) + 1):
        if t[j] - t[j - 1] != BAR_S:
            return "gap", j - i
        up = h[j] / entry - 1.0
        dn = 1.0 - lo_[j] / entry
        if side > 0:
            if dn >= sl:
                return "tb_sl", j - i
            if up >= pt:
                return "tb_pt", j - i
        else:
            if up >= sl:
                return "tb_sl", j - i
            if dn >= pt:
                return "tb_pt", j - i
    if end <= last:
        return "tb_time", horizon
    return None, last - i


def labels(rows: list, tape: dict, since: float, horizon: int) -> dict:
    out = collections.Counter()
    examples = collections.defaultdict(list)
    n = 0
    for r in rows:
        if r.get("source") != "candidate":
            continue
        st = _f(r.get("signal_ts"), 0.0)
        if st < since:
            continue
        n += 1
        a = r.get("asset") or ""
        s = tape.get(a)
        pt, sl = _f(r.get("pt_frac"), 0.0), _f(r.get("sl_frac"), 0.0)
        side = 1 if _f(r.get("direction"), 0) > 0 else -1
        if s is None:
            out["no_tape_asset"] += 1
            continue
        t, c, h, lo_ = s
        k = np.searchsorted(t, st)
        if k >= len(t) or t[k] != st:
            out["entry_bar_not_on_tape"] += 1
            continue
        ep = _f(r.get("entry_price"), 0.0)
        if not ep or abs(c[k] / ep - 1.0) > PX_TOL:
            out["entry_price_mismatch"] += 1
            examples["entry_price_mismatch"].append(
                (r["position_id"], ep, float(c[k])))
            continue
        if pt <= 0 or sl <= 0:
            out["no_stamped_fracs"] += 1
            continue
        bar, held = rederive(t, c, h, lo_, int(k), side, pt, sl, horizon)
        stored = r.get("barrier") or ""
        if bar is None:
            out["window_incomplete_on_tape"] += 1
        elif bar == "gap":
            out["tape_gap_in_window"] += 1
        elif bar != stored:
            out["barrier_mismatch"] += 1
            examples["barrier_mismatch"].append(
                (r["position_id"], a, stored, bar, held))
        else:
            xp = _f(r.get("exit_price"), 0.0)
            jj = min(int(k) + max(held, 1), len(c) - 1)
            if xp and abs(c[jj] / xp - 1.0) > PX_TOL:
                out["exit_price_mismatch"] += 1
                examples["exit_price_mismatch"].append(
                    (r["position_id"], xp, float(c[jj])))
            else:
                out["match"] += 1
    return {"counts": dict(out), "examples": {k: v[:5] for k, v in
                                               examples.items()},
            "counting": reconcile(n, out)}


def load_tape(root: Path, assets) -> dict:
    from data import candle_journal as cj
    tape = {}
    for a in assets:
        v = cj.load_view(a, BAR_S, series=cj.Series("bot_cache", "USD"),
                         root=root)
        bars = [] if v.unreadable else v.bars(0, 2 ** 31)
        bars = [b for b in bars if not b.conflicted]
        if bars:
            tape[a] = tuple(np.array(x, float) for x in zip(
                *[(b.t_open_s, b.close, b.high, b.low) for b in bars],
                strict=True))
    return tape


# ------------------------------------------------------------------ C live
def live_vs_fills(rows: list, fills: Path, since: float) -> dict:
    cash = collections.defaultdict(float)
    purposes = collections.defaultdict(set)
    rem = {}
    for r in _rows(fills):
        if r.get("purpose") == "hedge":
            continue
        pid = r["position_id"]
        px, sz = _f(r.get("fill_price"), 0.0), abs(_f(r.get("fill_size"), 0.0))
        sgn = 1 if (r.get("side") or "").lower().startswith("s") else -1
        cash[pid] += sgn * px * sz - _f(r.get("fees_delta_usd"), 0.0)
        purposes[pid].add(r.get("purpose"))
        if r.get("purpose") == "exit":
            rem[pid] = _f(r.get("remaining"), 0.0)
    out = collections.Counter()
    diffs, examples = [], []
    n = 0
    for r in rows:
        if r.get("source") != "live":
            continue
        if _f(r.get("signal_ts"), 0.0) < since:
            continue
        n += 1
        pid = r.get("position_id") or ""
        if pid not in cash:
            out["no_fills"] += 1
            continue
        if not ({"entry", "exit"} <= purposes[pid]) or rem.get(pid, 1) > 1e-9:
            out["fills_not_closed"] += 1
            continue
        d = _f(r.get("net_pnl_usd"), 0.0) - cash[pid]
        diffs.append(d)
        if abs(d) <= 0.01:
            out["match"] += 1
        else:
            out["pnl_mismatch"] += 1
            examples.append((pid, _f(r.get("net_pnl_usd"), 0.0),
                             round(cash[pid], 4)))
    return {"counts": dict(out), "examples": examples[:5],
            "max_abs_diff": max((abs(x) for x in diffs), default=0.0),
            "counting": reconcile(n, out)}


# ------------------------------------------------------------------ D train
def training(root: Path, n_disk: int) -> dict:
    from ml.history import store_for_config, triple_barrier_era
    cfg = json.loads((root / "config.json").read_text(encoding="utf-8"))
    ml = cfg.get("ml", {})
    sw = ml.get("sample_weights", {})
    hs = store_for_config(ml, path=str(root / "outputs" / "signal_history.csv"))
    X, y, w, sig, res = hs.load_training_data(
        half_life_days=float(sw.get("half_life_days", 30)),
        candidate_weight=float(sw.get("candidate_weight", 0.4)),
        manip_discount=float(sw.get("manip_discount", 0.5)),
        return_label_times=True, weights_cfg=sw,
        telemetry_cfg=ml.get("telemetry", {}), epoch_cfg=ml.get("epoch", {}),
        era_cfg=ml.get("era_exclusion", {}))
    ls = hs.last_load_stats or {}
    stats = {k: v for k, v in ls.items()
             if isinstance(v, (int, float, str, bool)) or v is None}
    eras = {e: int((b or {}).get("rows", 0))
            for e, b in (ls.get("label_era") or {}).items()}
    current = triple_barrier_era(hs.max_bars)
    buckets = {"trained": int(len(y))}
    for e, n in eras.items():
        if e != current:
            buckets[f"era_excluded:{e}"] = n
    for k in ("dropped_clash", "dropped_dirty", "dropped_parse",
              "epoch_excluded", "dropped_duplicate", "long_book_skipped"):
        v = ls.get(k)
        if isinstance(v, int) and v:
            buckets[k] = v
    resid = n_disk - sum(buckets.values())
    if resid:
        buckets["unexplained"] = resid
    counting = reconcile(n_disk, buckets)
    if resid < 0:        # a forced residual must never hide a double count
        counting["ok"] = False
        counting["line"] = counting["line"].replace(
            "[OK]", f"[DOUBLE-COUNT: buckets exceed n by {-resid}]")
    return {"trained_rows": int(len(y)), "positives": int(np.sum(y)),
            "current_era": current, "eras": eras, "stats": stats,
            "counting": counting}


def pending_ids(root: Path) -> set:
    """Candidate ids still in the labeler pool (state.json), read-only."""
    try:
        s = json.loads((root / "outputs" / "state.json").read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    found = set()

    def walk(o):
        if isinstance(o, dict):
            v = o.get("id")
            if isinstance(v, str) and CAND.match(v):
                found.add(v)
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(s)
    return found


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--since", type=float, default=ERA9_START)
    ap.add_argument("--skip-training", action="store_true")
    a = ap.parse_args(argv)
    out = a.root / "outputs"
    read_at = time.time()
    rows = list(_rows(out / "signal_history.csv"))
    cfg = json.loads((a.root / "config.json").read_text(encoding="utf-8"))
    horizon = int(cfg.get("ml", {}).get("label_max_bars", 432))
    print(f"pipeline_congruence read {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(read_at))}"
          f" rows={len(rows)} since={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(a.since))}")
    A = funnel(rows, pending_ids(a.root), a.since)
    print("\nA FUNNEL", json.dumps({k: v for k, v in A.items()
                                    if k != "counting"}))
    if "counting" in A:
        print("  " + A["counting"]["line"])
    assets = sorted({r.get("asset") for r in rows
                     if r.get("source") == "candidate"} - {None, ""})
    B = labels(rows, load_tape(out / "candles", assets), a.since, horizon)
    print("\nB LABELS vs the bot's own 5m bars (bot_cache lane)")
    print("  " + B["counting"]["line"])
    for k, v in B["examples"].items():
        print(f"  {k}: {v}")
    C = live_vs_fills(rows, out / "fills.csv", a.since)
    print("\nC LIVE ROWS vs fills.csv")
    print("  " + C["counting"]["line"] + f"  max|diff| {C['max_abs_diff']:.4f} USD")
    for e in C["examples"]:
        print(f"  mismatch {e}")
    if not a.skip_training:
        D = training(a.root, len(rows))
        print("\nD TRAINING LOAD (engine seam store_for_config, main.py's "
              "loader arguments)")
        print(f"  current label era {D['current_era']}: rows on disk "
              f"{len(rows)} -> trained {D['trained_rows']} "
              f"(positives {D['positives']})")
        print("  " + D["counting"]["line"])
        print("  loader stats: " + json.dumps(D["stats"], default=str)[:800])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
