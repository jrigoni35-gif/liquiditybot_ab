"""scripts/reject_inference_bounds.py - lane B' bounded doubly-robust retro pass.

WHY THIS EXISTS. The 2026-09-19 gradeability census measured 99.93% of
era-9 arrivals ungradeable: EN-000 carries counts only, so pre-DE-010
absorbed arrivals have no per-arrival record BY CONSTRUCTION. This script
answers the bounded reject-inference question from the 2026-09-20 desk-
instruments spec (docs/superpowers/specs/
2026-09-20-desk-instruments-plan2-sor-ipma-design.md, section 1): could
the absorbed strata of the era-9 arrivals hide net edge? It answers with
Manski worst/best bounds, never point estimates, and prints UNIDENTIFIED
where no bound can be computed. Report-plane only: reads outputs/,
research/corpus/ and config.json; writes nothing. Refuses rather than
approximates (census precedent).

    python scripts/reject_inference_bounds.py
    python scripts/reject_inference_bounds.py --since 2026-09-08

METHOD (stated here so the dated record can cite it):
- Strata come from scripts/gradeability_census.py census() itself (the
  seam); this script's independent streaming re-count must match it
  exactly or the run refuses CENSUS_INCONSISTENT.
- Outcome instrument: corpus 1m bars (research/corpus/binance_vision),
  entry at the OPEN of the arrival minute's bar, exit at the CLOSE of the
  bar H minutes later. H = ml.label_max_bars x 300 s (432 x 5m = 36 h):
  the bot's own evaluation horizon - the label vertical IS the live
  bracket deadline (config _label_max_bars_doc; main.py horizon_h =
  _label_max_bars * 300.0). 300 s/bar is the engine's own bar constant
  (main.py), not a new literal.
- Fee: fee_rt_bps = pretrade.maker_fee_bps + pretrade.taker_fee_bps
  (15 + 30 = 45 bps at cut #12), the horizon_edge_sweep.py precedent
  (read from config, never struck; cross-checked against
  ml.label_round_trip_cost_pct = (maker+taker)/100 by config_guard's own
  rule). Spread/impact are NOT in the corpus (klines carry no book), so
  every bound is optimistic in width on the cost side by the missing
  spread - stated, never silently absorbed.
- Manski bounds: worst/best net-of-fee outcome over the full empirical
  support. Unconditional strata (lost L, deep pipeline D) get the
  era-window bound: all corpus minutes in [era_start, corpus_end - H] x
  all universe assets x both directions. Conditional strata (CV records
  carry ts+asset; DE-010 events carry ts+asset+decision_mid) get
  per-record realized-path bounds, widened over both directions where
  direction is absent. Never fabricate a field.
- Gradeable stratum: the taken action's value is REALIZED (corpus
  forward path from the fill's own ts/asset/side). Under the
  deterministic policy the propensity of the taken action is 1.0, so the
  doubly-robust estimator reduces to the sample mean of realized
  outcomes (the IPW weight is 1/1.0 and the outcome-regression term
  cancels): stated, not assumed away. Counterfactual (had the arrival
  been absorbed) is BOUNDED by the era-window bound, never
  point-estimated.
- Venue proxy: corpus is Binance USDT-margined spot; the bot marks on
  Kraken USD. The basis is ignored (bound-widening caveat, stated).
- Right-censoring: arrivals in the final H of corpus coverage have no
  full-horizon path, and arrivals after the corpus end (the corpus stops
  2026-09-18; the era is still accruing) are unmeasurable by this
  instrument. Both are COUNTED (per-hour EN-000 deltas give the tail)
  and reported as their own line - the bounds apply to the covered
  window only and the record says so. Refusal is reserved for corpus
  absence, manifest/parquet mismatch, zero era overlap, a torn chain, or
  a census mismatch - the four instrument failures, not for the era
  outliving its corpus.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.gradeability_census import (  # noqa: E402 - the seam
    CUT12_FLOOR,
    REFUSAL_AUDIT_UNREADABLE,
    REFUSAL_CHAIN_TORN,
    REFUSAL_INCONSISTENT,
    _GENESIS,
    _h,
    _iso,
    _parse_since,
    census,
)

REFUSAL_CORPUS_MISSING = "CORPUS_MISSING"
REFUSAL_CORPUS_MISMATCH = "CORPUS_MANIFEST_MISMATCH"
REFUSAL_CORPUS_NO_COVERAGE = "CORPUS_NO_COVERAGE"
REFUSAL_CONFIG_UNREADABLE = "CONFIG_UNREADABLE"

BAR_SEC = 300.0  # the engine's own bar constant: main.py horizon_h =
                 # _label_max_bars * 300.0 (5m bars). Not a new literal.


class _ChainTorn(Exception):
    """Same refusal class as census read_chain returning None."""


class _AuditUnreadable(Exception):
    """Same refusal class as census read_chain returning AUDIT_UNREADABLE."""


def iter_chain(path):
    """Streaming twin of gradeability_census.read_chain: identical verify
    semantics (own-hash recompute, verify_chain seam adoption, torn-tail
    rules), but yields a minimal per-record projection and never holds the
    trail in memory. Tamper raises _ChainTorn; unreadable path raises
    _AuditUnreadable. The seen-hash set is the minimum state the verifier
    itself needs (seam adoption resolves prev against ANY verified hash).
    """
    try:
        fh = open(path, encoding="utf-8")
    except OSError:
        raise _AuditUnreadable(path) from None
    with fh:
        seen, prev_h, broken = {_GENESIS}, _GENESIS, False
        for line in fh:
            line = line.strip().strip("\x00").strip()
            if not line:
                continue                  # torn-tail fragment guard
            if broken:
                raise _ChainTorn("real content past the break")
            try:
                rec = json.loads(line)
            except ValueError:
                broken = True             # crash mid-append candidate
                continue
            if not isinstance(rec, dict):
                broken = True             # non-dict JSON: TORN, same class
                continue
            h = rec.get("h")
            body = json.dumps({k: v for k, v in rec.items() if k != "h"},
                              sort_keys=True, default=str)
            if not h or _h(body) != h:
                raise _ChainTorn("edited record")
            rp = rec.get("prev")
            if rp != prev_h and rp not in seen:
                raise _ChainTorn("dangling prev")
            prev_h = h
            seen.add(h)
            yield {"ts": rec.get("ts", 0), "src": rec.get("src"),
                   "code": str(rec.get("code", "")),
                   "data": rec.get("data") or {}}


def scan_audit(audit_path, since: float) -> dict:
    """One streaming pass: EN-000 ticks, CV records, DE-010 events."""
    ticks, cv, de010 = [], [], []
    for rec in iter_chain(audit_path):
        if rec["ts"] < since:
            continue
        code, data = rec["code"], rec["data"]
        if rec["src"] == "entry_sweep" and code == "EN-000":
            ticks.append((rec["ts"], data))
        elif code.startswith("CV-") and data.get("asset"):
            cv.append({"ts": rec["ts"], "asset": data["asset"], "code": code,
                       "est_edge_bps": data.get("est_edge_bps"),
                       "est_cost_bps": data.get("est_cost_bps")})
        elif code == "DE-010":
            for ev in data.get("events") or []:
                if isinstance(ev, dict):
                    de010.append(ev)
    return {"ticks": ticks, "cv": cv, "de010": de010}


def tick_deltas(ticks) -> dict:
    """Restart-aware positive deltas of the cumulative EN-000 vector -
    gradeability_census.en000_deltas' algorithm over the streamed ticks,
    plus per-tick arrival deltas for tail attribution."""
    by_key, per_tick, prev = {}, [], None
    for ts, data in sorted(ticks, key=lambda t: t[0]):
        arr_delta = 0
        for k, v in data.items():
            if not isinstance(v, (int, float)):
                continue
            delta = v if prev is None or k not in prev or v < prev[k] \
                else v - prev[k]
            by_key[k] = by_key.get(k, 0) + delta
            if k == "arrivals":
                arr_delta = delta
        per_tick.append((ts, arr_delta))
        prev = data
    return {"by_key": {k: int(v) for k, v in by_key.items()},
            "per_tick": per_tick}


def load_config(config_path) -> dict:
    """Derive (never strike) the fee and horizon constants."""
    try:
        cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
        pt, ml = cfg["pretrade"], cfg["ml"]
        fee_rt_bps = float(pt["maker_fee_bps"]) + float(pt["taker_fee_bps"])
        label_bars = int(ml["label_max_bars"])
        pairs = list(cfg["exchanges"]["kraken"]["trading_pairs"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise _ConfigUnreadable(str(exc)) from exc
    return {"fee_rt_bps": fee_rt_bps,
            "horizon_bars_1m": int(label_bars * BAR_SEC / 60.0),
            "label_max_bars": label_bars,
            "bases": sorted(p.split("/")[0] for p in pairs)}


class _ConfigUnreadable(Exception):
    """config.json missing/incoherent: the instrument cannot state its
    own cost basis (horizon_edge_sweep._fee_rt_from_config precedent)."""


def load_corpus(corpus_dir, bases, since: float) -> dict:
    """Verify the manifest against the parquets (instrument first), then
    keep only the era slice of each symbol's 1m bars.

    Refuses CORPUS_MISSING (file absent/unreadable) and
    CORPUS_MANIFEST_MISMATCH (row count, first/last, or the gap-free
    claim fails verification). Full-array diff check: the manifest's
    gap_events=0 claim is re-verified on the loaded arrays, not trusted.
    """
    import pandas as pd  # managed venv; parquet engine is pyarrow

    man_path = Path(corpus_dir) / "manifest.json"
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise _CorpusMissing(f"manifest: {exc}") from exc
    quality = man.get("quality") or {}
    out = {}
    for base in bases:
        sym = f"{base}USDT"
        q = quality.get(sym)
        if not q:
            raise _CorpusMissing(f"{sym}: no manifest quality block")
        pq = Path(corpus_dir) / q.get("parquet_1m", "")
        try:
            df = pd.read_parquet(pq, columns=["open_time", "open", "close"])
        except (OSError, ValueError) as exc:
            raise _CorpusMissing(f"{sym}: {exc}") from exc
        n = len(df)
        if n != int(q["rows_1m"]):
            raise _CorpusMismatch(
                f"{sym}: rows {n} != manifest {q['rows_1m']}")
        ot = df["open_time"].to_numpy()
        first_ms = int(datetime.fromisoformat(q["first"]).timestamp() * 1000)
        last_ms = int(datetime.fromisoformat(q["last"]).timestamp() * 1000)
        if int(ot[0]) != first_ms or int(ot[-1]) != last_ms:
            raise _CorpusMismatch(f"{sym}: first/last != manifest")
        if n > 1 and bool((ot[1:] - ot[:-1] != 60_000).any()):
            raise _CorpusMismatch(f"{sym}: 1m grid broken (gap claim false)")
        keep = df["open_time"] >= int(math.floor(since) // 60 * 60_000)
        sl = df[keep]
        out[base] = {"symbol": sym,
                     "open_time_ms": sl["open_time"].to_numpy(),
                     "open": sl["open"].to_numpy(dtype=float),
                     "close": sl["close"].to_numpy(dtype=float),
                     "first_ms": int(ot[0]), "last_ms": int(ot[-1]),
                     "rows_verified": n}
    return out


class _CorpusMissing(Exception):
    pass


class _CorpusMismatch(Exception):
    pass


def era_window(corpus: dict, since: float, horizon_bars: int) -> tuple:
    """[window_start_s, window_end_s]: minutes whose full H-path exists."""
    start = max(since, min(c["first_ms"] for c in corpus.values()) / 1000.0)
    end = min(c["last_ms"] for c in corpus.values()) / 1000.0 \
        - horizon_bars * 60.0
    return start, end


def _slice_at(c: dict, t0_s: float, horizon_bars: int):
    """(p0_open, pH_close) for the arrival minute, or None if t0's minute
    is absent / the exit bar is outside the loaded slice. The grid was
    verified gap-free at load, so index arithmetic IS timestamp arithmetic;
    both are checked anyway (instrument first)."""
    import numpy as np

    ot = c["open_time_ms"]
    m0 = int(math.floor(t0_s / 60.0)) * 60_000
    i0 = int(np.searchsorted(ot, m0))
    if i0 >= len(ot) or int(ot[i0]) != m0:
        return None
    i1 = i0 + horizon_bars
    if i1 >= len(ot) or int(ot[i1]) != m0 + horizon_bars * 60_000:
        return None
    return float(c["open"][i0]), float(c["close"][i1])


def net_bps_pair(p0: float, pH: float, fee_rt_bps: float) -> tuple:
    """(net_long_bps, net_short_bps) of the H-horizon round trip."""
    gross = (pH - p0) / p0 * 1e4
    return gross - fee_rt_bps, -gross - fee_rt_bps


def era_bound(corpus: dict, window: tuple, horizon_bars: int,
              fee_rt_bps: float) -> dict:
    """Unconditional Manski bound over the covered era window: every
    corpus minute with a full H-path, every asset, both directions.
    p01/p50/p99 are DESCRIPTIVE quantiles of the same pooled
    distribution - labeled, never presented as the bound."""
    import numpy as np

    start_ms, end_ms = int(window[0] * 1000), int(window[1] * 1000)
    pooled, per_asset = [], {}
    for base, c in corpus.items():
        ot, op, cl = c["open_time_ms"], c["open"], c["close"]
        i0 = int(np.searchsorted(ot, start_ms))
        # t0 indices i0..idx(end): exit bar i+H exists for every t0 up to
        # idx(end) = last_full_idx - H by construction of the window.
        i1 = int(np.searchsorted(ot, end_ms, side="right"))
        n = i1 - i0
        if n <= 0:
            per_asset[base] = None
            continue
        gross = (cl[i0 + horizon_bars:i0 + n + horizon_bars]
                 / op[i0:i0 + n] - 1.0) * 1e4
        both = np.concatenate([gross - fee_rt_bps, -gross - fee_rt_bps])
        per_asset[base] = {"n_minutes": int(n),
                           "worst": float(both.min()),
                           "best": float(both.max())}
        pooled.append(both)
    if not pooled:
        raise _NoCoverage("no corpus minute with a full horizon in window")
    allv = np.concatenate(pooled)
    return {"worst": float(allv.min()), "best": float(allv.max()),
            "p01": float(np.percentile(allv, 1)),
            "p50": float(np.percentile(allv, 50)),
            "p99": float(np.percentile(allv, 99)),
            "n_points": int(allv.size), "per_asset": per_asset}


class _NoCoverage(Exception):
    pass


def gradeable_rows(fills_path, since: float) -> list:
    """Era-stamped entry fills carrying arrival_ref, one per position -
    gradeability_census.gradeable_entries' filter, keeping the fields the
    counterfactual evaluation needs. Direction comes from the fill's own
    side; never fabricated."""
    from core.fill_ledger import EXEC_ERA
    out, seen = [], set()
    if not fills_path or not Path(fills_path).exists():
        return out
    with open(fills_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not (row.get("exec_era") == EXEC_ERA
                    and row.get("purpose") == "entry"
                    and (row.get("arrival_ref") or "")):
                continue
            pid = row.get("position_id") or row["order_id"]
            if pid in seen:
                continue
            seen.add(pid)
            try:
                ts = float(row["ts"])
            except (TypeError, ValueError):
                continue
            if ts < since:
                continue
            side = (row.get("side") or "").lower()
            out.append({"ts": ts,
                        "asset": (row.get("symbol") or "").split("/")[0],
                        "direction": {"buy": "long", "sell": "short"}.get(side),
                        "side": side})
    return out


def _dir_index(direction):
    if direction == "long":
        return 0
    if direction == "short":
        return 1
    return None                       # absent: widen over both directions


def eval_records(records, corpus, window, horizon_bars, fee_rt_bps,
                 p0_key=None):
    """Per-record realized-path bounds. Returns (covered, censored) where
    covered holds {'worst','best','taken'} per record ('taken' set only
    when direction is known). Censored = outside coverage or asset not in
    corpus: COUNTED, never imputed."""
    covered, censored = [], 0
    for r in records:
        c = corpus.get(r.get("asset") or "")
        if c is None or not (window[0] <= r["ts"] <= window[1]):
            censored += 1
            continue
        got = _slice_at(c, r["ts"], horizon_bars)
        if got is None:
            censored += 1
            continue
        p0 = got[0]
        if p0_key and r.get(p0_key) not in (None, ""):
            try:
                p0 = float(r[p0_key])     # DE-010 decision_mid: the real
            except (TypeError, ValueError):  # decision price, when carried
                p0 = got[0]
        nl, ns = net_bps_pair(p0, got[1], fee_rt_bps)
        di = _dir_index(r.get("direction"))
        pair = (nl, ns)
        covered.append({"worst": min(pair), "best": max(pair),
                        "taken": None if di is None else pair[di]})
    return covered, censored


def _mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def _r2(x):
    return None if x is None else round(x, 2)


def bounds_run(*, audit_path, fills_path, corpus_dir, config_path,
               since) -> dict:
    """The whole pass. Mirrors census()'s contract: a dict with a
    'refused' key - a refusal string on any inconsistency, else None."""
    cen = census(audit_path=audit_path, fills_path=fills_path,
                 since=since, doc_path=None)
    if cen["refused"]:
        return {"refused": cen["refused"]}
    try:
        scan = scan_audit(audit_path, since)
    except _ChainTorn:
        return {"refused": REFUSAL_CHAIN_TORN}
    except _AuditUnreadable:
        return {"refused": REFUSAL_AUDIT_UNREADABLE}
    deltas = tick_deltas(scan["ticks"])
    if (deltas["by_key"] != cen["by_key"]
            or len(scan["cv"]) != cen["cv_records_with_asset"]
            or len(scan["de010"]) != cen["de010_coverage"]):
        return {"refused": REFUSAL_INCONSISTENT}
    try:
        cfgd = load_config(config_path)
    except _ConfigUnreadable:
        return {"refused": REFUSAL_CONFIG_UNREADABLE}
    try:
        corpus = load_corpus(corpus_dir, cfgd["bases"], since)
    except _CorpusMissing:
        return {"refused": REFUSAL_CORPUS_MISSING}
    except _CorpusMismatch:
        return {"refused": REFUSAL_CORPUS_MISMATCH}
    window = era_window(corpus, since, cfgd["horizon_bars_1m"])
    if window[1] <= window[0]:
        return {"refused": REFUSAL_CORPUS_NO_COVERAGE}
    try:
        eb = era_bound(corpus, window, cfgd["horizon_bars_1m"],
                       cfgd["fee_rt_bps"])
    except _NoCoverage:
        return {"refused": REFUSAL_CORPUS_NO_COVERAGE}

    n = cen["arrivals"]
    tail = sum(d for ts, d in deltas["per_tick"] if ts > window[1])
    covered_n = n - int(tail)

    g_rows = gradeable_rows(fills_path, since)
    if len(g_rows) != cen["gradeable"]:
        return {"refused": REFUSAL_INCONSISTENT}
    g_cov, g_cens = eval_records(g_rows, corpus, window,
                                 cfgd["horizon_bars_1m"], cfgd["fee_rt_bps"])
    g_taken = [r["taken"] for r in g_cov if r["taken"] is not None]

    cv_cov, cv_cens = eval_records(scan["cv"], corpus, window,
                                   cfgd["horizon_bars_1m"], cfgd["fee_rt_bps"])
    de_cov, de_cens = eval_records(scan["de010"], corpus, window,
                                   cfgd["horizon_bars_1m"],
                                   cfgd["fee_rt_bps"], p0_key="decision_mid")

    def stratum(cov):
        return {"worst": _r2(_mean(r["worst"] for r in cov)),
                "best": _r2(_mean(r["best"] for r in cov))}

    by_gate = {}
    for code in ("CV-000", "CV-010", "CV-030"):
        recs = [r for r in scan["cv"] if r["code"] == code]
        cov = eval_records(recs, corpus, window, cfgd["horizon_bars_1m"],
                           cfgd["fee_rt_bps"])[0]
        est = [r["est_edge_bps"] for r in recs
               if isinstance(r.get("est_edge_bps"), (int, float))]
        by_gate[code] = {"count": len(recs), "covered": len(cov),
                         "bound": stratum(cov),
                         "mean_est_edge_bps": _r2(_mean(est)) if est else None}

    strata = {
        "gradeable": {
            "n": cen["gradeable"], "covered": len(g_cov),
            "censored": g_cens,
            "dr_taken_mean_bps": _r2(_mean(g_taken)),
            "propensity_taken": 1.0,
            "counterfactual_bound": [_r2(eb["worst"]), _r2(eb["best"])],
        },
        "lost_forever": {
            "n": cen["lost_forever"],
            "bound_per_arrival": [_r2(eb["worst"]), _r2(eb["best"])],
            "note": "no per-arrival record exists; era-window bound",
        },
        "deep_pipeline": {
            "n": cen["deep_pipeline"],
            "bound_per_arrival": [_r2(eb["worst"]), _r2(eb["best"])],
            "note": "residual stratum; era-window bound",
        },
        "cv_with_asset": {
            "n": cen["cv_records_with_asset"], "covered": len(cv_cov),
            "censored": cv_cens, "mean_bound": stratum(cv_cov),
            "note": "ts+asset known, direction absent: both-direction "
                    "realized-path bounds",
        },
        "de010_captured": {
            "n": cen["de010_coverage"], "covered": len(de_cov),
            "censored": de_cens, "mean_bound": stratum(de_cov),
            "note": "post-capture events; decision_mid as p0 when carried",
        },
    }
    return {
        "refused": None,
        "since": _iso(since),
        "fee_rt_bps": cfgd["fee_rt_bps"],
        "horizon_minutes": cfgd["horizon_bars_1m"],
        "window": [_iso(window[0]), _iso(window[1])],
        "arrivals": n,
        "arrivals_in_covered_window": int(covered_n),
        "arrivals_tail_uncovered": int(tail),
        "era_bound_bps": {k: _r2(eb[k]) for k in
                          ("worst", "best", "p01", "p50", "p99")},
        "era_bound_per_asset": {k: (None if v is None else {
            "n_minutes": v["n_minutes"], "worst": _r2(v["worst"]),
            "best": _r2(v["best"])})
            for k, v in eb["per_asset"].items()},
        "strata": strata,
        "by_gate": by_gate,
        "absorb_keys": cen["by_key"],
    }


def _table(headers, rows):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    out = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    out.append("  ".join("-" * w for w in widths))
    for row in rows:
        out.append("  ".join(str(c).ljust(widths[i])
                             for i, c in enumerate(row)))
    return "\n".join(out)


def render(out: dict) -> str:
    lines = []
    lines.append(f"=== reject-inference bounds (lane B') — era window "
                 f"since {out['since']} ===")
    lines.append(f"fee_rt_bps = {out['fee_rt_bps']:.1f} "
                 f"(pretrade.maker+taker)   horizon = "
                 f"{out['horizon_minutes']} min (ml.label_max_bars x 300s)")
    lines.append(f"covered corpus window: {out['window'][0]} .. "
                 f"{out['window'][1]}")
    lines.append(f"arrivals N = {out['arrivals']}  "
                 f"(covered {out['arrivals_in_covered_window']}, "
                 f"tail beyond corpus coverage "
                 f"{out['arrivals_tail_uncovered']} - UNMEASURABLE, "
                 f"counted, not imputed)")
    eb = out["era_bound_bps"]
    lines.append(f"era-window Manski bound (net bps/arrival): "
                 f"[{eb['worst']}, {eb['best']}]  "
                 f"descriptive p01/p50/p99 = "
                 f"{eb['p01']}/{eb['p50']}/{eb['p99']} (NOT the bound)")
    lines.append("")
    s = out["strata"]
    lines.append("PER-STRATUM BOUNDS (net-of-fee bps per arrival)")
    g = s["gradeable"]
    rows = [
        ("gradeable g", g["n"], f"{g['covered']}+{g['censored']}cens",
         f"DR taken mean {g['dr_taken_mean_bps']}",
         f"counterfactual [{g['counterfactual_bound'][0]}, "
         f"{g['counterfactual_bound'][1]}]"),
        ("lost L", s["lost_forever"]["n"], "unconditional",
         f"[{s['lost_forever']['bound_per_arrival'][0]}, "
         f"{s['lost_forever']['bound_per_arrival'][1]}]", "no record"),
        ("deep D", s["deep_pipeline"]["n"], "unconditional",
         f"[{s['deep_pipeline']['bound_per_arrival'][0]}, "
         f"{s['deep_pipeline']['bound_per_arrival'][1]}]", "residual"),
        ("CV asset", s["cv_with_asset"]["n"],
         f"{s['cv_with_asset']['covered']}+{s['cv_with_asset']['censored']}"
         f"cens",
         f"[{s['cv_with_asset']['mean_bound']['worst']}, "
         f"{s['cv_with_asset']['mean_bound']['best']}]", "both dirs"),
        ("DE-010", s["de010_captured"]["n"],
         f"{s['de010_captured']['covered']}+{s['de010_captured']['censored']}"
         f"cens",
         f"[{s['de010_captured']['mean_bound']['worst']}, "
         f"{s['de010_captured']['mean_bound']['best']}]", "both dirs"),
    ]
    lines.append(_table(("stratum", "n", "coverage", "bound/value", "note"),
                        rows))
    lines.append("")
    lines.append("DR-IPMA PER GATE (importance = DR marginal effect on net "
                 "edge where identified, else UNIDENTIFIED; performance = "
                 "absorb rate + bound width)")
    n = out["arrivals"]
    en020 = out["absorb_keys"].get("EN-020", 0)
    en030 = out["absorb_keys"].get("EN-030", 0)
    w = eb["best"] - eb["worst"]
    rows = [
        ("EN-020", en020, f"{en020 / n:.4%}" if n else "n/a",
         f"[{eb['worst']}, {eb['best']}]" if en020 else "n/a (0 absorbed)",
         f"width {round(w, 2)}" if en020 else "n/a"),
        ("EN-030", en030, f"{en030 / n:.4%}" if n else "n/a",
         f"[{eb['worst']}, {eb['best']}]" if en030 else "n/a (0 absorbed)",
         f"width {round(w, 2)}" if en030 else "n/a"),
    ]
    for code, blk in out["by_gate"].items():
        share = blk["count"] / n if n else 0
        if blk["bound"]["worst"] is None:
            imp, perf = ("UNIDENTIFIED (no covered record)"
                         if blk["count"] else "n/a (0 records)"), "n/a"
        else:
            bw = blk["bound"]["best"] - blk["bound"]["worst"]
            imp = (f"[{blk['bound']['worst']}, {blk['bound']['best']}]"
                   if code != "CV-000"
                   else "n/a (admission gate; value realized downstream)")
            perf = f"width {round(bw, 2)}"
        rows.append((code, blk["count"], f"{share:.4%}", imp, perf))
    rows.append(("deep-pipeline gates (SZ/RP/PT/OM…)", s["deep_pipeline"]["n"],
                 "residual", "UNIDENTIFIED (no per-arrival attribution "
                 "pre-DE-010)", "n/a"))
    lines.append(_table(("gate", "absorbed", "share of N", "importance",
                         "performance"), rows))
    lines.append("")
    lines.append("propensity of every taken action = 1.0 (deterministic "
                 "policy): the DR estimator of taken-action value reduces "
                 "to the realized sample mean; counterfactuals are "
                 "BOUNDED, never point-estimated.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", default="outputs/audit.jsonl")
    ap.add_argument("--fills", default="outputs/fills.csv")
    ap.add_argument("--corpus", default="research/corpus/binance_vision")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--since", default=None,
                    help="epoch seconds or ISO 8601 (default: cut-#12 floor)")
    ns = ap.parse_args()
    since = _parse_since(ns.since) if ns.since else CUT12_FLOOR
    out = bounds_run(audit_path=ns.audit, fills_path=ns.fills,
                     corpus_dir=ns.corpus, config_path=ns.config,
                     since=since)
    if out["refused"]:
        print(f"BOUNDS REFUSED: {out['refused']}")
        return 2
    print(render(out))
    print()
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
