"""scripts/gate_ecology.py - Lane F (first cut): gate ecology + desk netting shadow.

WHY THIS EXISTS. The 2026-09-20 desk-instruments design (spec section 3)
downgraded "78% EN-030 absorb = pathology" to a HYPOTHESIS: in a
fee-dominated regime, high rejection may be correct risk perception. This
script is the echo-feud measurement - it tests whether gates absorb
independently of one another and of market state, or whether absorb
patterns are echo-coupled. ADVISORY PRINT ONLY: it changes nothing,
touches no engine file, and reads only outputs/ + the read-only corpus.

Five sections (spec 2026-09-20 desk-instruments-plan2 §3):
  1. Per-gate absorb counts/rates over the era window (EN-000 vector
     deltas + DE-010 captured dispositions; vocabulary derived from the
     records and core/codes.py, never assumed beyond EN-020/EN-030/
     passed_gate_stack).
  2. Conditional absorb structure from DE-010 per-arrival gate verdicts;
     pre-DE-010 arrivals carry no inputs BY CONSTRUCTION (the census
     measured this) -> UNIDENTIFIED, never imputed.
  3. Absorbs vs corpus-derived realized-vol regime of the universe
     assets' 1m bars in a trailing window (window DERIVED from
     vol_regime.fast_lookback_bars_5m; the percentile reference window is
     a stated ANALYSIS CHOICE - not a config tunable).
  4. WSLS aspiration shadow: per gate, what a Pavlov win/stay-lose/shift
     rule WOULD have done against the fee-floor aspiration (derived:
     (min_edge_cost_ratio - 1) x (maker + taker fee bps)). Prints only.
  5. Desk netting shadow: gross vs net cross-asset exposure from era-9
     fills; unrealized netting opportunities reported.

Refuse-on-inconsistency (census precedent): torn chain, unreadable
audit, missing corpus -> banner + nonzero exit. pandas/numpy for the
corpus; stdlib otherwise. Streams the audit JSONL (chain-verified per
core/audit.py semantics, seam-adopting like gradeability_census).

    python scripts/gate_ecology.py
    python scripts/gate_ecology.py --since 2026-09-08
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.fill_ledger import EXEC_ERA   # noqa: E402 - "12-10d4d0c2" (era-9)

REFUSAL_CHAIN_TORN = "CHAIN_TORN"
REFUSAL_AUDIT_UNREADABLE = "AUDIT_UNREADABLE"
REFUSAL_NO_EN000 = "NO_EN000_IN_WINDOW"
REFUSAL_CORPUS_MISSING = "CORPUS_MISSING"
REFUSAL_INCONSISTENT = "ECOLOGY_INCONSISTENT"

# cut-#12 runner restart (era-9 accrual begins), docs/HANDOFF.md.
CUT12_FLOOR = datetime(2026, 9, 8, tzinfo=timezone.utc).timestamp()

# core/audit.py:_GENESIS - the chain anchor every boot record points at.
_GENESIS = "0" * 16

# The three disposition families the spec names. Everything else numeric
# in an EN-000 tick is still counted, but as an UNREGISTERED-tail key and
# reported under its own name - the vocabulary is derived, not assumed.
KNOWN_ABSORB_KEYS = ("EN-020", "EN-030")
PASSED_STACK = "passed_gate_stack"

# ANALYSIS CHOICE (docs/quant/2026-09-20_gate_ecology.md, Method): the
# trailing reference window a tick's sigma is percentiled against. No
# existing config constant fits (vol_regime.fast_lookback_bars_5m sizes
# the sigma estimate itself, not its reference distribution). 30 days of
# 1m bars. NOT a config tunable - it lives here, documented, by design.
REFERENCE_WINDOW_MIN = 30 * 24 * 60


def _h(payload: str) -> str:
    # identical construction to core/audit.py:_h (sha256, first 16 hex).
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def read_chain_filtered(path, since: float, codes: frozenset):
    """Stream + verify with core.audit.verify_chain semantics (census
    parity: own-hash recompute, seam adoption, torn-tail tolerance,
    deletion/tamper -> refusal), yielding only records with ts >= since
    and code in `codes`. The trail is 77k+ records; nothing else is
    retained. Returns (records, refusal)."""
    out = []
    try:
        fh = open(path, encoding="utf-8")
    except OSError:
        return None, REFUSAL_AUDIT_UNREADABLE   # missing/unreadable
    seen, prev_h, broken = {_GENESIS}, _GENESIS, False
    with fh:
        for line in fh:
            line = line.strip().strip("\x00").strip()
            if not line:
                continue                     # torn-tail fragment guard
            if broken:
                return None, REFUSAL_CHAIN_TORN   # content past the break
            try:
                rec = json.loads(line)
            except ValueError:
                broken = True                # crash mid-append candidate
                continue
            if not isinstance(rec, dict):
                broken = True                # non-dict JSON: TORN
                continue
            h = rec.get("h")
            body = json.dumps({k: v for k, v in rec.items() if k != "h"},
                              sort_keys=True, default=str)
            if not h or _h(body) != h:
                return None, REFUSAL_CHAIN_TORN       # edited record
            rp = rec.get("prev")
            if rp != prev_h and rp not in seen:
                return None, REFUSAL_CHAIN_TORN       # dangling prev
            prev_h = h
            seen.add(h)
            if rec.get("ts", 0) >= since and rec.get("code") in codes:
                out.append(rec)
    return out, None


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _parse_since(raw: str) -> float:
    s = raw.strip()
    if s.replace(".", "", 1).isdigit():
        return float(s)
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


# ---------------------------------------------------------------- config

def derive_constants(cfg: dict) -> dict:
    """Every decision-shaping number is DERIVED from config.json
    (overfit discipline); nothing here is a fitted literal."""
    pre = cfg["pretrade"]
    maker = float(pre["maker_fee_bps"])
    taker = float(pre["taker_fee_bps"])
    round_trip_bps = maker + taker
    ratio = float(pre["min_edge_cost_ratio"])
    # aspiration = the NET-of-fee edge hurdle the EV gate demands:
    # gross edge must clear ratio x round trip, so net must clear
    # (ratio - 1) x round trip.
    aspiration_bps = (ratio - 1.0) * round_trip_bps
    horizon_min = int(cfg["ml"]["label_max_bars"]) * 5   # 5m bars -> min
    vr = cfg["vol_regime"]
    return {
        "maker_fee_bps": maker,
        "taker_fee_bps": taker,
        "round_trip_cost_bps": round_trip_bps,
        "min_edge_cost_ratio": ratio,
        "aspiration_bps": aspiration_bps,
        "horizon_min": horizon_min,
        "vol_window_min": int(vr["fast_lookback_bars_5m"]) * 5,
        "vol_low_pct": float(vr["low_pct"]),
        "vol_elevated_pct": float(vr["elevated_pct"]),
        "vol_extreme_pct": float(vr["extreme_pct"]),
    }


# ------------------------------------------------------------ corpus

def check_corpus(corpus_dir) -> tuple[list, str | None]:
    """Verify manifest coverage before trusting it; returns (symbols,
    refusal). missing_files non-empty or an absent parquet -> refusal."""
    cdir = Path(corpus_dir)
    try:
        manifest = json.loads((cdir / "manifest.json")
                              .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], REFUSAL_CORPUS_MISSING
    if manifest.get("missing_files"):
        return [], REFUSAL_CORPUS_MISSING
    symbols = [str(s) for s in manifest.get("symbols") or []]
    if not symbols:
        return [], REFUSAL_CORPUS_MISSING
    for s in symbols:
        if not (cdir / f"klines_1m_{s}.parquet").exists():
            return [], REFUSAL_CORPUS_MISSING
    return symbols, None


def load_sigma(corpus_dir, symbol: str, t0: float,
               vol_window_min: int) -> pd.Series | None:
    """Per-minute realized vol (RMS of 1m log returns over the trailing
    vol_window_min bars), indexed by bar open_time (ms epoch), restricted
    to the era window plus the reference window plus warmup."""
    path = Path(corpus_dir) / f"klines_1m_{symbol}.parquet"
    if not path.exists():
        return None
    lo_ms = int((t0 - REFERENCE_WINDOW_MIN * 60
                 - (vol_window_min + 60) * 60) * 1000)
    df = pd.read_parquet(path, columns=["open_time", "close"])
    df = df[df["open_time"] >= lo_ms]
    if len(df) < vol_window_min + 1:
        return None
    rets = np.log(df["close"].to_numpy(dtype=float))
    rets = np.diff(rets)
    sigma = pd.Series(rets, index=df["open_time"].to_numpy()[1:])
    return sigma.rolling(vol_window_min).std().dropna()


def vol_percentile(sigma: pd.Series, ts: float) -> float | None:
    """Percentile of the trailing-window sigma at ts within the asset's
    OWN trailing reference window (ends at ts - no lookahead). None when
    ts precedes warmup or sits past the corpus end (corpus gap)."""
    idx = sigma.index
    pos = idx.searchsorted(int(ts * 1000), side="right") - 1
    if pos < 0 or pos >= len(idx):
        return None
    ref_lo = int((ts - REFERENCE_WINDOW_MIN * 60) * 1000)
    lo = idx.searchsorted(ref_lo, side="left")
    ref = sigma.iloc[lo:pos + 1]
    if len(ref) < 60:                      # <1h of reference: too thin
        return None
    cur = sigma.iloc[pos]
    return float(100.0 * (ref <= cur).mean())


def regime_label(pct: float, low: float, elevated: float,
                 extreme: float) -> str:
    if pct <= low:
        return "low"
    if pct <= elevated:
        return "normal"
    if pct <= extreme:
        return "elevated"
    return "extreme"


# ------------------------------------------------------------- sections

def section1(ticks: list, events: list) -> dict:
    """Per-gate absorb counts/rates over the era window."""
    keys: dict[str, float] = {}
    for t in ticks:
        for k, v in t["delta"].items():
            keys[k] = keys.get(k, 0) + v
    arrivals = int(keys.get("arrivals", 0))
    absorb = {k: int(v) for k, v in keys.items() if k != "arrivals"}
    absorbed = sum(absorb.values())
    if absorbed > arrivals:
        return {"refused": REFUSAL_INCONSISTENT,
                "detail": f"absorbs {absorbed} > arrivals {arrivals}"}
    residual = arrivals - absorbed          # passed the gate stack
    span_h = 0.0
    if len(ticks) > 1:
        span_h = (ticks[-1]["ts"] - ticks[0]["ts"]) / 3600.0
    de_abs: dict[str, int] = {}
    for e in events:
        a = str(e.get("absorb") or "")
        de_abs[a] = de_abs.get(a, 0) + 1
    rates = {k: (100.0 * v / arrivals if arrivals else 0.0)
             for k, v in absorb.items()}
    per_hr = round(arrivals / span_h, 2) if span_h > 0 else None
    return {
        "refused": None, "arrivals": arrivals, "absorb_counts": absorb,
        "absorb_rates_pct": {k: round(v, 3) for k, v in rates.items()},
        PASSED_STACK: residual,
        "passed_rate_pct": round(100.0 * residual / arrivals, 4)
        if arrivals else 0.0,
        "span_hours": round(span_h, 2),
        "arrivals_per_hour": per_hr,
        "de010_events": len(events), "de010_by_absorb": de_abs,
        "known_keys_present": [k for k in KNOWN_ABSORB_KEYS if k in absorb],
        "unregistered_tail_keys": sorted(
            k for k in absorb if k not in KNOWN_ABSORB_KEYS),
    }


def section2(events: list) -> dict:
    """Conditional absorb structure from DE-010 per-arrival gate verdicts.

    The gate stack evaluates SIMULTANEOUSLY (strategies/informed_flow.py),
    not serially, so 'P(absorb at gate k | survived to k)' is reported as
    its identified analogs: the marginal fail rate, and the SOLE-ABSORBER
    rate P(gate k fails | every other gate passed) - the counterfactual
    'would this gate alone have absorbed'. Pre-capture arrivals carry no
    inputs BY CONSTRUCTION: UNIDENTIFIED, never imputed. The EN-020 stage
    (open-entry skip) never logs gate inputs at all: UNIDENTIFIED."""
    gated = [e for e in events if e.get("gates")]
    out = {"refused": None, "de010_events_with_gates": len(gated),
           "pre_capture": "UNIDENTIFIED",
           "pre_capture_reason": "per-arrival gate inputs not logged "
                                 "pre-DE-010 (census 2026-09-19: lost by "
                                 "construction)",
           "en020_stage_inputs": "UNIDENTIFIED",
           "gates": {}}
    if not gated:
        out["gates_note"] = "no DE-010 events carrying gate verdicts in " \
                            "window"
        return out
    names = sorted({g for e in gated for g in e["gates"]})
    n = len(gated)
    for g in names:
        fails = sum(1 for e in gated if not e["gates"].get(g))
        sole = sum(1 for e in gated
                   if not e["gates"].get(g)
                   and all(e["gates"].get(o) for o in names if o != g))
        out["gates"][g] = {
            "fail_rate": round(fails / n, 4),
            "sole_absorber_rate": round(sole / n, 4),
            "fails": fails, "sole_absorber": sole, "n": n,
        }
    # co-failure: how often gate pairs fail on the SAME arrival (the
    # echo-coupling observable on captured events)
    cofail = {}
    for i, g1 in enumerate(names):
        for g2 in names[i + 1:]:
            both = sum(1 for e in gated
                       if not e["gates"].get(g1) and not e["gates"].get(g2))
            if both:
                cofail[f"{g1}&{g2}"] = {"n": both,
                                        "rate": round(both / n, 4)}
    out["co_failure"] = cofail
    return out


def section3(ticks: list, sigma_by_asset: dict, consts: dict) -> dict:
    """Absorbs vs market state: desk absorb deltas per EN-000 tick joined
    to the vol regime of each universe asset at the tick instant.
    Pre-DE-010 absorbs carry no asset attribution, so the join is
    DESK-LEVEL (per-tick absorb count vs the cross-asset max vol
    percentile); that limitation is stated, not imputed around."""
    buckets: dict[str, dict] = {}
    gap_ticks = 0
    joined = 0
    for t in ticks:
        pcts = {a: vol_percentile(s, t["ts"])
                for a, s in sigma_by_asset.items() if s is not None}
        pcts = {a: p for a, p in pcts.items() if p is not None}
        if not pcts:
            gap_ticks += 1
            continue
        desk = max(pcts.values())
        label = regime_label(desk, consts["vol_low_pct"],
                             consts["vol_elevated_pct"],
                             consts["vol_extreme_pct"])
        b = buckets.setdefault(label, {"ticks": 0, "arrivals": 0,
                                       "absorbed": 0,
                                       "desk_pct_max": []})
        b["ticks"] += 1
        b["arrivals"] += int(t["delta"].get("arrivals", 0))
        b["absorbed"] += int(sum(v for k, v in t["delta"].items()
                                 if k != "arrivals"))
        b["desk_pct_max"].append(round(desk, 1))
        joined += 1
    for b in buckets.values():
        b["absorb_rate_pct"] = round(100.0 * b["absorbed"] / b["arrivals"], 2)\
            if b["arrivals"] else None
        b["mean_desk_pct_max"] = round(float(np.mean(b["desk_pct_max"])), 1)\
            if b["desk_pct_max"] else None
        b.pop("desk_pct_max")
    return {"refused": None, "joined_ticks": joined,
            "corpus_gap_ticks": gap_ticks, "by_regime": buckets,
            "vol_window_min": consts["vol_window_min"],
            "reference_window_min": REFERENCE_WINDOW_MIN}


def _direction_sign(d) -> int | None:
    s = str(d or "").lower()
    if s in ("long", "buy"):
        return 1
    if s in ("short", "sell"):
        return -1
    return None


def _counterfactual_bps(corpus_dir, symbol: str, ts: float, entry: float,
                        sign: int, horizon_min: int,
                        round_trip_bps: float) -> float | None:
    """Net-of-fee horizon return of the counterfactual trade, in bps.
    Close-to-close over the label horizon; None when the horizon runs
    past the corpus end."""
    path = Path(corpus_dir) / f"klines_1m_{symbol}.parquet"
    df = pd.read_parquet(path, columns=["open_time", "close"],
                         filters=[("open_time", ">=",
                                   int(ts * 1000) - 120_000)])
    if len(df) < 2:
        return None
    ot = df["open_time"].to_numpy()
    close = df["close"].to_numpy(dtype=float)
    end_ms = int((ts + horizon_min * 60) * 1000)
    if ot[-1] < end_ms:
        return None                          # horizon past corpus end
    j = ot.searchsorted(end_ms, side="right") - 1
    if j < 1:
        return None
    if entry <= 0:
        entry = close[0]
    gross = (close[j] / entry - 1.0) * sign * 1e4
    return gross - round_trip_bps


def section4(events: list, corpus_dir, sym_by_asset: dict,
             consts: dict) -> dict:
    """WSLS aspiration shadow (Posch-style memory, advisory only).

    Aspiration level = the fee-floor net-of-fee edge hurdle (derived).
    A Pavlov rule at gate g: STAY when the gate's last action was followed
    by a win (>= aspiration), SHIFT after a loss. For an ABSORBED arrival
    the gate's action was 'block'; the counterfactual outcome is computed
    from the corpus over the label horizon, net of the round-trip cost.
    Direction unknown (EN-030 carries none) -> BOTH directions evaluated:
    agreeing signs bound the advice; disagreement -> UNIDENTIFIED. Corpus
    gap -> UNIDENTIFIED. Prints what Pavlov WOULD have done; changes
    nothing."""
    asp = consts["aspiration_bps"]
    per_gate: dict[str, dict] = {}
    n_eval = n_unident = 0
    for e in events:
        gates = e.get("gates") or {}
        if not gates:
            continue
        sym = sym_by_asset.get(str(e.get("asset") or "").upper())
        if not sym:
            n_unident += 1
            continue
        entry = 0.0
        try:
            entry = float(e.get("decision_mid") or 0.0)
        except (TypeError, ValueError):
            entry = 0.0
        sign = _direction_sign(e.get("direction"))
        signs = [sign] if sign else [1, -1]
        outs = [_counterfactual_bps(corpus_dir, sym, float(e.get("ts", 0)),
                                    entry, s, consts["horizon_min"],
                                    consts["round_trip_cost_bps"])
                for s in signs]
        if any(o is None for o in outs):
            n_unident += 1                  # corpus gap / no coverage
            continue
        wins = [o >= asp for o in outs]
        if len(set(wins)) > 1:
            n_unident += 1                  # direction-bound disagreement
            continue
        n_eval += 1
        absorbed_win = wins[0]              # block cost us a win?
        for g, passed in gates.items():
            if passed:
                continue                    # only failing gates absorbed
            st = per_gate.setdefault(g, {"stay": 0, "shift": 0,
                                         "blocked_wins": 0, "n": 0})
            st["n"] += 1
            if absorbed_win:
                st["shift"] += 1            # blocked a win -> lose -> shift
                st["blocked_wins"] += 1
            else:
                st["stay"] += 1             # block was correct -> stay
    for st in per_gate.values():
        st["pavlov_would"] = "SHIFT" if st["shift"] > st["stay"] else "STAY"
    return {"refused": None, "aspiration_bps": round(asp, 2),
            "round_trip_cost_bps": consts["round_trip_cost_bps"],
            "horizon_min": consts["horizon_min"],
            "events_evaluated": n_eval, "events_unidentified": n_unident,
            "per_gate": per_gate,
            "note": "advisory shadow only - no gate state was changed"}


def section5(fills_path, since: float) -> dict:
    """Desk netting shadow: gross vs net cross-asset exposure from era
    fills. Per-position signed quantity (buy +q / sell -q, any purpose);
    exposure marked at each fill's own price (advisory approximation,
    stated). offsettable = min(long gross, short gross) = the exposure a
    netted desk would not have carried."""
    if not fills_path or not Path(fills_path).exists():
        return {"refused": None, "era_fills": 0,
                "note": "no fills ledger in window"}
    fills = []
    with open(fills_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("exec_era") != EXEC_ERA:
                continue
            try:
                ts = float(row["ts"])
                qty = float(row["fill_size"])
                px = float(row["fill_price"])
            except (TypeError, ValueError, KeyError):
                continue
            if ts < since:
                continue
            fills.append((ts, row.get("position_id") or row["order_id"],
                          (row.get("symbol") or "").split("/")[0],
                          qty if row.get("side") == "buy" else -qty, px))
    fills.sort()
    pos_qty: dict[str, float] = {}
    pos_asset: dict[str, str] = {}
    last_px: dict[str, float] = {}
    tw_gross = tw_net = tw_offset = 0.0
    peak_gross = peak_offset = 0.0
    offset_events = 0
    prev_ts = prev_gross = prev_net = prev_offset = None
    for ts, pid, asset, q, px in fills:
        last_px[asset] = px
        exp: dict[str, float] = {}
        for p, qty in pos_qty.items():
            if abs(qty) > 1e-12:
                a = pos_asset[p]
                mark = last_px.get(a)       # each asset at ITS last print
                if mark is not None:
                    exp[a] = exp.get(a, 0.0) + qty * mark
        gross = sum(abs(v) for v in exp.values())
        net = abs(sum(exp.values()))
        long_g = sum(v for v in exp.values() if v > 0)
        short_g = -sum(v for v in exp.values() if v < 0)
        offset = min(long_g, short_g)
        if prev_ts is not None and prev_gross is not None:
            dt = ts - prev_ts
            tw_gross += dt * prev_gross
            tw_net += dt * prev_net
            tw_offset += dt * prev_offset
        prev_ts, prev_gross, prev_net, prev_offset = ts, gross, net, offset
        peak_gross = max(peak_gross, gross)
        peak_offset = max(peak_offset, offset)
        if offset > 1e-9:
            offset_events += 1
        pos_qty[pid] = pos_qty.get(pid, 0.0) + q
        pos_asset[pid] = asset
    open_resid = {pos_asset[p]: round(q, 8)
                  for p, q in pos_qty.items() if abs(q) > 1e-12}
    return {
        "refused": None, "era_fills": len(fills),
        "time_weighted_gross_usd_h": round(tw_gross / 3600.0, 2),
        "time_weighted_net_usd_h": round(tw_net / 3600.0, 2),
        "time_weighted_offsettable_usd_h": round(tw_offset / 3600.0, 2),
        "peak_gross_usd": round(peak_gross, 2),
        "peak_offsettable_usd": round(peak_offset, 2),
        "offsetting_event_count": offset_events,
        "open_residual_qty_at_window_end": open_resid,
        "note": "advisory shadow; cross-asset netting assumes offsettable "
                "risk (correlation caveat in the record)",
    }


# ---------------------------------------------------------------- ticks

def en000_ticks(records: list) -> list:
    """Restart-aware positive deltas of the cumulative EN-000 vector,
    per tick (census parity for the arithmetic; the per-tick form is
    what the market-state join needs)."""
    ticks = sorted((r for r in records if r.get("code") == "EN-000"),
                   key=lambda r: r["ts"])
    out, prev = [], None
    for t in ticks:
        data = t.get("data") or {}
        delta = {}
        for k, v in data.items():
            if not isinstance(v, (int, float)):
                continue
            delta[k] = v if prev is None or k not in prev or v < prev[k] \
                else v - prev[k]
        out.append({"ts": t["ts"], "delta": delta})
        prev = data
    return out


def de010_events(records: list) -> list:
    out = []
    for r in records:
        if r.get("code") != "DE-010":
            continue
        for e in (r.get("data") or {}).get("events") or []:
            if isinstance(e, dict):
                out.append(e)
    return out


def _fmt_pct(x) -> str:
    return "n/a" if x is None else f"{x}%"


def print_report(rep: dict) -> None:
    c = rep["constants"]
    print("=" * 72)
    print("GATE ECOLOGY + DESK NETTING SHADOW (Lane F, advisory, read-only)")
    print(f"era = {EXEC_ERA} | window since {rep['since']} | "
          f"run {_iso(rep['run_ts'])}")
    print(f"derived constants: round_trip={c['round_trip_cost_bps']}bps "
          f"(maker {c['maker_fee_bps']} + taker {c['taker_fee_bps']}), "
          f"aspiration={c['aspiration_bps']:.2f}bps net "
          f"(= ({c['min_edge_cost_ratio']}-1) x round_trip), "
          f"horizon={c['horizon_min']}min, vol_window={c['vol_window_min']}min")
    print("=" * 72)

    s1 = rep["section1"]
    print("\n[1] PER-GATE ABSORB COUNTS/RATES (EN-000 deltas over window)")
    print(f"    arrivals N = {s1['arrivals']} over {s1['span_hours']}h "
          f"({s1['arrivals_per_hour']}/h)")
    for k, v in sorted(s1["absorb_counts"].items()):
        tag = "" if k in KNOWN_ABSORB_KEYS else "  [unregistered tail]"
        print(f"    {k}: {v}  ({s1['absorb_rates_pct'].get(k, 0)}%){tag}")
    print(f"    {PASSED_STACK} (residual): {s1[PASSED_STACK]}  "
          f"({s1['passed_rate_pct']}%)")
    print(f"    DE-010 captured events: {s1['de010_events']} "
          f"by absorb: {s1['de010_by_absorb']}")

    s2 = rep["section2"]
    print("\n[2] CONDITIONAL ABSORB STRUCTURE (per-arrival gate verdicts)")
    print(f"    pre-DE-010 window: {s2['pre_capture']} "
          f"({s2['pre_capture_reason']})")
    print(f"    EN-020 stage inputs: {s2['en020_stage_inputs']}")
    print(f"    DE-010 events with gate verdicts: "
          f"{s2['de010_events_with_gates']}")
    for g, st in sorted(s2["gates"].items()):
        print(f"    {g}: marginal fail {st['fail_rate']*100:.1f}%  "
              f"sole-absorber {st['sole_absorber_rate']*100:.1f}%  "
              f"(n={st['n']})")
    if s2.get("co_failure"):
        print("    co-failure pairs (echo-coupling observable):")
        for pair, st in sorted(s2["co_failure"].items()):
            print(f"      {pair}: {st['n']} ({st['rate']*100:.1f}%)")

    s3 = rep["section3"]
    print("\n[3] ABSORBS VS MARKET STATE (desk-level join; no per-asset "
          "attribution pre-DE-010)")
    print(f"    joined ticks: {s3['joined_ticks']}  corpus-gap ticks: "
          f"{s3['corpus_gap_ticks']}")
    for label in ("low", "normal", "elevated", "extreme"):
        b = s3["by_regime"].get(label)
        if not b:
            continue
        print(f"    {label:9s}: ticks={b['ticks']:4d} arrivals="
              f"{b['arrivals']:6d} absorb_rate="
              f"{_fmt_pct(b['absorb_rate_pct'])} mean_desk_vol_pct="
              f"{b['mean_desk_pct_max']}")

    s4 = rep["section4"]
    print("\n[4] WSLS ASPIRATION SHADOW (Pavlov vs fee-floor aspiration; "
          "advisory only)")
    print(f"    aspiration={s4['aspiration_bps']}bps net over "
          f"{s4['horizon_min']}min; events evaluated="
          f"{s4['events_evaluated']} UNIDENTIFIED="
          f"{s4['events_unidentified']}")
    if not s4["per_gate"]:
        print("    per-gate Pavlov advice: UNIDENTIFIED (no evaluable "
              "events - corpus gap or no captured direction)")
    for g, st in sorted(s4["per_gate"].items()):
        print(f"    {g}: STAY {st['stay']} / SHIFT {st['shift']} "
              f"-> Pavlov WOULD {st['pavlov_would']} "
              f"(blocked wins: {st['blocked_wins']}/{st['n']})")

    s5 = rep["section5"]
    print("\n[5] DESK NETTING SHADOW (era fills; advisory)")
    print(f"    era fills: {s5['era_fills']}")
    if s5["era_fills"]:
        print(f"    time-weighted gross exposure: "
              f"{s5['time_weighted_gross_usd_h']:,} USD*h")
        print(f"    time-weighted net exposure:   "
              f"{s5['time_weighted_net_usd_h']:,} USD*h")
        print(f"    time-weighted offsettable:    "
              f"{s5['time_weighted_offsettable_usd_h']:,} USD*h "
              f"(unrealized netting)")
        print(f"    peak gross ${s5['peak_gross_usd']:,} | peak offsettable "
              f"${s5['peak_offsettable_usd']:,} | offsetting events: "
              f"{s5['offsetting_event_count']}")
        print(f"    open residual qty at window end: "
              f"{s5['open_residual_qty_at_window_end']}")
    print("\n" + "=" * 72)


def ecology(*, audit_path, fills_path, corpus_dir, config_path,
            since) -> dict:
    import time
    cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
    consts = derive_constants(cfg)
    symbols, refusal = check_corpus(corpus_dir)
    if refusal:
        return {"refused": refusal}
    records, refusal = read_chain_filtered(
        audit_path, since, frozenset({"EN-000", "DE-010"}))
    if refusal:
        return {"refused": refusal}
    ticks = en000_ticks(records)
    if not ticks:
        return {"refused": REFUSAL_NO_EN000}
    events = de010_events(records)
    s1 = section1(ticks, events)
    if s1.get("refused"):
        return {"refused": s1["refused"], "detail": s1.get("detail")}
    sigma_by_asset = {}
    for s in symbols:
        sigma_by_asset[s.replace("USDT", "")] = load_sigma(
            corpus_dir, s, since, consts["vol_window_min"])
    sym_by_asset = {s.replace("USDT", ""): s for s in symbols}
    return {
        "refused": None, "since": _iso(since), "run_ts": time.time(),
        "constants": consts,
        "section1": s1,
        "section2": section2(events),
        "section3": section3(ticks, sigma_by_asset, consts),
        "section4": section4(events, corpus_dir, sym_by_asset, consts),
        "section5": section5(fills_path, since),
    }


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
    rep = ecology(audit_path=ns.audit, fills_path=ns.fills,
                  corpus_dir=ns.corpus, config_path=ns.config,
                  since=since)
    if rep["refused"]:
        detail = f" ({rep['detail']})" if rep.get("detail") else ""
        print(f"GATE-ECOLOGY REFUSED: {rep['refused']}{detail}")
        return 2
    print_report(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
