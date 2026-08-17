"""scripts/reconcile_weekly.py — RP-070 weekly ledger vs fills.csv waterfall.

THE QUESTION. outputs/weekly_ledger.csv (RP-070, written by main.py's
_close_periods at each ISO-week boundary) reconciles with neither
fills-derived book at weekly grain. Three confounds were NAMED but never
QUANTIFIED: (1) the perf-ledger hedge exclusion (main.py's `if not
pos.is_hedge` guard), (2) the RP-041 sweep false-loss (a capital sweep
zeroes weekly_realized_pnl AND realized_pnl_total mid-week, so the sweep
week's ledger row carries post-sweep legs only), (3) tier-partial timing
(partial exits book at tier-event fill time; the trade closes later,
possibly in another week). This tool rebuilds the weekly numbers from
outputs/fills.csv applying each named exclusion IN TURN and reports the
residual per ISO week per stage, so the unexplained gap is isolated and
named instead of blended.

WHAT RP-070 ACTUALLY BOOKS (measured from code, not assumed — main.py
_handle_fill, `order.purpose == "exit"` branch; core/state.py
record_realized_pnl / maybe_close_week):
  * per EXIT FILL LEG, at leg fill time:  net = sgn*(fill_price -
    avg_entry)*fill_size - exit_fee_delta  (avg_entry = running VWAP of
    opening fills against CURRENT size, exits leave the average
    unchanged);
  * HEDGE-INCLUSIVE — record_realized_profit is called unconditionally
    in the exit branch; the `is_hedge` exclusion guards only the rolling
    PERF ledger, not the weekly counter;
  * entry-leg fees are NOT in the weekly number (they debit cash at fill
    time via record_entry_fee);
  * the week key is the ISO week (UTC) of the leg's `now`, the same
    clock fills.csv stamps as `ts`.
So stage s0 (raw leg-grain sum, hedges in) is the direct code-faithful
mirror and r0 is the direct RP-070 mismatch; s1..s3 quantify the three
named hypotheses on top of it.

THE WATERFALL (stages cumulative, per ISO week):
  s0  raw fills week-sum: every exit leg's net, at leg week
  s1  minus hedge-book legs (position opened by a purpose=="hedge" fill)
  s2  minus pre-sweep legs in each sweep's own ISO week (--sweep TS;
      a sweep re-zeroes the counter, so only post-sweep legs can reach
      that week's ledger row). The ledger's own realized_total chain is
      checked independently: rt[k]-rt[k-1] != weekly[k] is the sweep
      signature and is flagged whether or not --sweep was given.
  s3  tier-timing realignment: closed trades' surviving legs move to the
      trade's CLOSE week (leg-grain -> trade-grain attribution); the
      per-week shift is reported and sums to ~0 across weeks.
  r_i = ledger weekly_realized - s_i  (per week; blank when the week has
  no ledger row yet — the current ISO week closes at the next boundary).

THE OPENING-LEG FEE BRIDGE (first live run, 2026-08-17): the waterfall
proved RP-070 exact at its own grain (r0 == 0 on the sweep-free closed
weeks), and the headline gap against full-net cash-flow books turned out
to be NONE of the three named confounds: it is the opening-leg fee
stack. record_entry_fee debits entry/hedge fees straight to cash at fill
time, so they are IN equity but NEVER in any weekly_realized row — the
same invisible-population shape as the 2026-08-09 all-time-P&L finding,
here quantified per ISO week. The report carries these fees per week per
book so a cash-flow book can be bridged to RP-070 exactly:
  cashflow_week ~= s0_week - open_fees_week  (+/- cross-week attribution)

DEDUPLICATION: positions are deduped by FILL PATTERN, not position_id
(the restart-replay bug wrote one ETH position under 16 position_ids;
see scripts/cost_attribution.py — same signature tuple here).

READ-ONLY. Never writes outputs/ — report goes to stdout, or to an
explicit --out path of the operator's choosing. fills.csv and the ledger
are LIVE files: every figure is as-of the stamped read time.

NOT A STATISTIC: this is an accounting identity check (sums, not
estimates), so there is no SE and no effective-n deflation to apply —
the residual is exact for the rows read.

Usage:
    python scripts/reconcile_weekly.py                      # repo outputs/
    python scripts/reconcile_weekly.py --root DIR           # a live tree
    python scripts/reconcile_weekly.py --sweep 2026-08-11T23:05:27Z
    python scripts/reconcile_weekly.py --json [--out FILE]
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Opening legs — a hedge opens a position exactly as an entry does
# (scripts/cost_attribution.py, pinned by tests/test_opening_leg_pin.py).
_OPEN_PURPOSES = ("entry", "hedge")
# Engine closure test: pos.size <= original_size * 1e-4 (main.py's
# _handle_fill finalize condition), original_size = max size ever held.
_CLOSE_FRAC = 1e-4
# Ledger rows are rounded to 2dp at close; accumulation noise on top.
_TOL = 0.02


def _f(v, d=None):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return d
    return x if x == x and abs(x) != float("inf") else d


def iso_week_key(ts: float) -> str:
    """UTC ISO week key, byte-identical to core/state.py maybe_close_week
    ('%G-W%V' semantics via isocalendar)."""
    iso = datetime.fromtimestamp(ts, tz=timezone.utc).isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def parse_ts(s: str) -> float:
    """Epoch seconds from either a float or an ISO-8601 string (Z ok)."""
    try:
        return float(s)
    except ValueError:
        pass
    t = s.strip()
    if t.endswith(("Z", "z")):
        t = t[:-1] + "+00:00"
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _stamp(path: Path) -> dict:
    """as-of provenance for a LIVE file: mtime + the moment we read it."""
    st = path.stat()
    return {
        "path": str(path),
        "mtime_utc": datetime.fromtimestamp(
            st.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        "read_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


# --------------------------------------------------------------------------
# fills.csv -> positions -> exit legs
# --------------------------------------------------------------------------

def load_fills(path: Path):
    """Parsed, ts-sorted fill rows + a skip Counter (an exclusion of any
    size must be visible, never a bare `continue`)."""
    rows, skipped = [], Counter()
    with open(path, newline="", encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f)):
            ts = _f(r.get("ts"))
            sz = _f(r.get("fill_size"))
            px = _f(r.get("fill_price"))
            fee = _f(r.get("fees_delta_usd"))
            pid = (r.get("position_id") or "").strip()
            purpose = (r.get("purpose") or "").strip()
            if not pid:
                skipped["no_position_id"] += 1
                continue
            if purpose not in _OPEN_PURPOSES and purpose != "exit":
                skipped["unknown_purpose"] += 1
                continue
            if ts is None or sz is None or px is None or fee is None \
                    or sz <= 0 or px <= 0:
                skipped["malformed_row"] += 1     # torn/junk rows land here
                continue
            rows.append({"ts": ts, "pid": pid, "purpose": purpose,
                         "side": (r.get("side") or "").strip(),
                         "size": sz, "price": px, "fee": fee, "seq": i})
    rows.sort(key=lambda r: (r["ts"], r["seq"]))
    return rows, skipped


def build_positions(rows):
    """Replay each position's fills chronologically with the ENGINE's own
    arithmetic (running entry VWAP against current size; exits realize
    sgn*(px-avg)*size - exit_fee and leave the average unchanged).

    Returns (positions, skipped): positions deduped by fill pattern, each
      {pid, is_hedge, closed, close_week, legs:[{ts, week, net}],
       open_fees:[{week, fee}]}  (opening-leg fees ride along for the
      fee-bridge section — deduped with their position, so a replayed
      position's fees are not double-counted either).
    Orphan exits (no opening fill in the file) cannot price a basis and
    are counted, never guessed."""
    by_pid = defaultdict(list)
    for r in rows:
        by_pid[r["pid"]].append(r)
    positions, seen, skipped = [], set(), Counter()
    for pid, fills in by_pid.items():
        sig = tuple((f["purpose"], f["side"], round(f["size"], 6),
                     round(f["price"], 4)) for f in fills)
        if sig in seen:
            skipped["duplicate_fill_pattern"] += 1
            continue
        seen.add(sig)
        size = avg = max_size = 0.0
        sgn, is_hedge, legs, orphaned = 0.0, False, [], False
        open_fees = []
        for f in fills:
            if f["purpose"] in _OPEN_PURPOSES:
                if size <= 0.0 and sgn == 0.0:
                    sgn = 1.0 if f["side"] == "buy" else -1.0
                    is_hedge = f["purpose"] == "hedge"
                total = size + f["size"]
                avg = (avg * size + f["price"] * f["size"]) / total
                size = total
                max_size = max(max_size, size)
                open_fees.append({"week": iso_week_key(f["ts"]),
                                  "fee": f["fee"]})
            else:                                  # exit leg
                if sgn == 0.0:
                    orphaned = True
                    skipped["orphan_exit_leg"] += 1
                    continue
                gross = sgn * (f["price"] - avg) * f["size"]
                legs.append({"ts": f["ts"], "week": iso_week_key(f["ts"]),
                             "net": gross - f["fee"]})
                size = max(size - f["size"], 0.0)
        if not legs:
            skipped["no_exit_leg" if not orphaned else "orphan_only"] += 1
            continue
        closed = size <= max(max_size * _CLOSE_FRAC, 1e-12)
        positions.append({
            "pid": pid, "is_hedge": is_hedge, "closed": closed,
            "close_week": legs[-1]["week"] if closed else None,
            "legs": legs, "open_fees": open_fees})
    return positions, skipped


def opening_fee_bridge(positions):
    """Per-ISO-week opening-leg (entry/hedge) fees, split by book.

    RP-070's weekly number is exit-fee-net ONLY: record_entry_fee debits
    opening fees straight to cash, so they appear in NO weekly row. A
    full-net cash-flow book therefore reads lower than RP-070 by exactly
    this stack (+/- cross-week attribution) — the first live run's whole
    W32 headline gap (161.48 of 161.34) was these fees, not any of the
    three named confounds."""
    fees = defaultdict(lambda: {"entry": 0.0, "hedge": 0.0})
    for pos in positions:
        book = "hedge" if pos["is_hedge"] else "entry"
        for of in pos["open_fees"]:
            fees[of["week"]][book] += of["fee"]
    return {wk: {k: round(v, 2) for k, v in d.items()}
            for wk, d in fees.items()}


# --------------------------------------------------------------------------
# the waterfall
# --------------------------------------------------------------------------

def waterfall(positions, sweeps):
    """Per-ISO-week stage sums s0..s3 plus the per-stage explained deltas.

    sweeps: iterable of epoch seconds. Stage 2 drops legs strictly before
    the LATEST sweep inside that sweep's own ISO week (each sweep
    re-zeroes the counter, so only accrual after the last one survives
    to the ledger row)."""
    last_sweep = {}
    for t in sweeps:
        wk = iso_week_key(t)
        last_sweep[wk] = max(t, last_sweep.get(wk, t))
    s0, s1, s2, s3 = (defaultdict(float) for _ in range(4))
    d_hedge, d_sweep, d_tier = (defaultdict(float) for _ in range(3))
    for pos in positions:
        for leg in pos["legs"]:
            wk, net = leg["week"], leg["net"]
            s0[wk] += net
            if pos["is_hedge"]:
                d_hedge[wk] += net
                continue
            s1[wk] += net
            cut = last_sweep.get(wk)
            if cut is not None and leg["ts"] < cut:
                d_sweep[wk] += net
                continue
            s2[wk] += net
            # tier-timing realignment: closed trades' legs move to the
            # trade's close week (leg-grain -> trade-grain attribution)
            dest = pos["close_week"] if pos["closed"] else wk
            s3[dest] += net
            if dest != wk:
                d_tier[wk] -= net
                d_tier[dest] += net
    return {"s0": dict(s0), "s1": dict(s1), "s2": dict(s2), "s3": dict(s3),
            "hedge_legs": dict(d_hedge), "presweep_legs": dict(d_sweep),
            "tier_shift": dict(d_tier)}


# --------------------------------------------------------------------------
# the ledger side
# --------------------------------------------------------------------------

def load_ledger(path: Path):
    """weekly_ledger.csv rows in file order: [{week, weekly_realized,
    realized_total}]. File order IS close order (append-only ledger)."""
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            wk = (r.get("week") or "").strip()
            wr = _f(r.get("weekly_realized"))
            if not wk or wr is None:
                continue
            out.append({"week": wk, "weekly_realized": wr,
                        "realized_total": _f(r.get("realized_total"))})
    return out


def chain_check(ledger_rows, tol=_TOL):
    """The ledger's own internal sweep signature: realized_total is
    cumulative, so rt[k] - rt[k-1] must equal weekly_realized[k]. A
    nonzero chain residual means the lifetime counter was re-zeroed (a
    capital sweep) or externally edited between the two closes. The
    first row has no predecessor: its residual is rt[0] - wr[0] = the
    PRE-window accrual, reported as informational, never flagged."""
    findings = []
    prev = None
    for i, row in enumerate(ledger_rows):
        rt, wr = row["realized_total"], row["weekly_realized"]
        if rt is None:
            prev = None
            continue
        if prev is None:
            findings.append({"week": row["week"], "chain_residual": None,
                             "pre_window_accrual": round(rt - wr, 2),
                             "sweep_signature": False, "first_row": i == 0})
        else:
            resid = rt - prev - wr
            findings.append({"week": row["week"],
                             "chain_residual": round(resid, 2),
                             "sweep_signature": abs(resid) > tol})
        prev = rt
    return findings


# --------------------------------------------------------------------------
# report assembly
# --------------------------------------------------------------------------

def build_report(fills_path: Path, ledger_path: Path, sweeps):
    fills_stamp = _stamp(fills_path)
    rows, load_skips = load_fills(fills_path)
    fills_stamp["rows"] = len(rows)
    positions, pos_skips = build_positions(rows)
    ledger_stamp = _stamp(ledger_path) if ledger_path.exists() else \
        {"path": str(ledger_path), "missing": True}
    ledger_rows = load_ledger(ledger_path) if ledger_path.exists() else []
    if "missing" not in ledger_stamp:
        ledger_stamp["rows"] = len(ledger_rows)
    stages = waterfall(positions, sweeps)
    fee_bridge = opening_fee_bridge(positions)
    chain = chain_check(ledger_rows)
    ledger_by_week = {r["week"]: r["weekly_realized"] for r in ledger_rows}
    weeks = sorted(set(ledger_by_week) | set(fee_bridge)
                   | {w for s in ("s0", "s1", "s2", "s3")
                      for w in stages[s]})
    table = {}
    for wk in weeks:
        led = ledger_by_week.get(wk)
        row = {"ledger": led}
        for s in ("s0", "s1", "s2", "s3"):
            v = stages[s].get(wk, 0.0)
            row[s] = round(v, 2)
            row["r" + s[1]] = round(led - v, 2) if led is not None else None
        row["hedge_legs"] = round(stages["hedge_legs"].get(wk, 0.0), 2)
        row["presweep_legs"] = round(
            stages["presweep_legs"].get(wk, 0.0), 2)
        row["tier_shift"] = round(stages["tier_shift"].get(wk, 0.0), 2)
        fb = fee_bridge.get(wk, {"entry": 0.0, "hedge": 0.0})
        row["open_fees_entry"] = fb["entry"]
        row["open_fees_hedge"] = fb["hedge"]
        table[wk] = row
    n_hedge = sum(1 for p in positions if p["is_hedge"])
    n_closed = sum(1 for p in positions if p["closed"])
    return {
        "generated_utc": datetime.now(timezone.utc)
        .isoformat(timespec="seconds"),
        "inputs": {"fills": fills_stamp, "ledger": ledger_stamp},
        "sweeps": [{"ts": t, "utc": datetime.fromtimestamp(
            t, tz=timezone.utc).isoformat(timespec="seconds"),
            "week": iso_week_key(t)} for t in sorted(sweeps)],
        "skipped": dict(load_skips + pos_skips),
        "positions": {"total": len(positions), "closed": n_closed,
                      "open": len(positions) - n_closed,
                      "hedge": n_hedge},
        "weeks": table,
        "ledger_chain": chain,
    }


def _fmt(v, width=9):
    return f"{v:+{width}.2f}" if v is not None else " " * (width - 1) + "-"


def render_text(rep: dict) -> str:
    out = ["WEEKLY RECONCILIATION - RP-070 ledger vs fills.csv waterfall",
           "=" * 72, "[0] inputs (LIVE files - every figure is as-of "
           "the stamped read time)"]
    for name in ("fills", "ledger"):
        s = rep["inputs"][name]
        if s.get("missing"):
            out.append(f"  {name:6s} {s['path']}  MISSING")
            continue
        out.append(f"  {name:6s} {s['path']}")
        out.append(f"         rows={s['rows']}  mtime={s['mtime_utc']}  "
                   f"read={s['read_utc']}")
    if rep["sweeps"]:
        for sw in rep["sweeps"]:
            out.append(f"  sweep  {sw['utc']}  (week {sw['week']})")
    else:
        out.append("  sweeps: none supplied (--sweep); stage s2 == s1. "
                   "The ledger chain check below still flags sweep "
                   "signatures independently.")
    p = rep["positions"]
    out += ["", "[1] fills-book reconstruction (fill-pattern deduped)",
            f"  positions={p['total']} closed={p['closed']} "
            f"open={p['open']} hedge={p['hedge']}",
            f"  excluded rows/positions: {rep['skipped'] or '{}'}"]
    out += ["", "[2] ledger internal chain check "
            "(rt[k]-rt[k-1] vs weekly[k]; nonzero = sweep signature)"]
    if not rep["ledger_chain"]:
        out.append("  (no ledger rows)")
    for c in rep["ledger_chain"]:
        if c.get("chain_residual") is None:
            out.append(f"  {c['week']}  first-row baseline: pre-window "
                       f"accrual {c['pre_window_accrual']:+.2f} "
                       f"(informational)")
        else:
            flag = "  <-- SWEEP SIGNATURE" if c["sweep_signature"] else ""
            out.append(f"  {c['week']}  chain residual "
                       f"{c['chain_residual']:+.2f}{flag}")
    out += ["", "[3] waterfall per ISO week (USD, exit-fee-net leg sums; "
            "stages cumulative)",
            "      s0 raw -> s1 minus hedge legs -> s2 minus pre-sweep "
            "legs -> s3 tier-timing realigned",
            f"  {'week':9s} {'ledger':>9s} {'s0_raw':>9s} {'s1_nohdg':>9s} "
            f"{'s2_swp':>9s} {'s3_tier':>9s} | {'r0':>8s} {'r1':>8s} "
            f"{'r2':>8s} {'r3':>8s}"]
    for wk, row in rep["weeks"].items():
        out.append(
            f"  {wk:9s} {_fmt(row['ledger'])} {_fmt(row['s0'])} "
            f"{_fmt(row['s1'])} {_fmt(row['s2'])} {_fmt(row['s3'])} | "
            f"{_fmt(row['r0'], 8)} {_fmt(row['r1'], 8)} "
            f"{_fmt(row['r2'], 8)} {_fmt(row['r3'], 8)}")
    out += ["", "    per-week explained deltas: hedge legs / pre-sweep "
            "legs / tier-timing shift"]
    for wk, row in rep["weeks"].items():
        out.append(f"  {wk:9s} hedge={row['hedge_legs']:+9.2f}  "
                   f"presweep={row['presweep_legs']:+9.2f}  "
                   f"tier_shift={row['tier_shift']:+9.2f}")
    out += ["", "    opening-leg fee bridge (NOT in any weekly row - "
            "record_entry_fee debits",
            "    cash directly; a full-net cash-flow book ~= s0 minus "
            "these, +/- cross-week",
            "    attribution)"]
    for wk, row in rep["weeks"].items():
        tot = row["open_fees_entry"] + row["open_fees_hedge"]
        out.append(f"  {wk:9s} entry_open_fees={row['open_fees_entry']:8.2f}"
                   f"  hedge_open_fees={row['open_fees_hedge']:8.2f}"
                   f"  total={tot:8.2f}")
    out += ["", "[4] reading the residuals",
            "  RP-070 books per exit LEG, HEDGE-INCLUSIVE, exit-fee-net "
            "(measured from",
            "  main.py's exit branch + core/state.py) - so r0 is the "
            "direct mismatch and",
            "  s1..s3 quantify the three NAMED hypotheses on top of it. "
            "A week whose",
            "  residual only zeroes at s1/s2/s3 is explained by that "
            "stage's confound;",
            "  a residual no stage removes is the isolated UNEXPLAINED "
            "gap.",
            "", "[5] what this check could not see",
            "  * in-memory weekly accrual lost to a kill inside the "
            "snapshot cadence",
            "    (state books per leg, snapshots every ~30s: the ledger "
            "row can lag",
            "    the fills book by the unsnapshotted tail);",
            "  * OM-085 restart replays: the STATE may book a replayed "
            "fill twice while",
            "    fills.csv refuses the duplicate row - RP-070 rich, "
            "fills-book silent;",
            "  * fills rows lost to append failure (append_fill never "
            "raises into the",
            "    fill path - a lost row is invisible here);",
            "  * realized P&L accrued before fills.csv's first row "
            "(pre-ledger life",
            "    shows up only in the first ledger row's pre-window "
            "accrual);",
            "  * sweeps not passed via --sweep: stage s2 cannot split a "
            "week it was",
            "    never told about (the chain check names the week, not "
            "the instant);",
            "  * orphan exit legs (no opening fill on file) are COUNTED, "
            "never priced.",
            "  Accounting identity, not a statistic: sums over the rows "
            "read - no SE,",
            "  no effective-n; exact for this corpus, silent about "
            "anything outside it."]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="rebuild RP-070's weekly numbers from fills.csv, one "
                    "named exclusion at a time (report-only)")
    ap.add_argument("--root", default=str(ROOT),
                    help="repo root holding outputs/ (default: this "
                         "script's repo)")
    ap.add_argument("--fills", default=None,
                    help="override fills.csv path (default ROOT/outputs/"
                         "fills.csv)")
    ap.add_argument("--ledger", default=None,
                    help="override weekly_ledger.csv path")
    ap.add_argument("--sweep", action="append", default=[],
                    metavar="TS", help="capital-sweep instant (epoch or "
                    "ISO-8601, repeatable): stage s2 drops same-week "
                    "legs before it")
    ap.add_argument("--json", action="store_true",
                    help="emit the machine report instead of text")
    ap.add_argument("--out", default=None,
                    help="also write the report to this file (never "
                         "defaults into outputs/)")
    args = ap.parse_args()
    root = Path(args.root)
    fills = Path(args.fills) if args.fills else root / "outputs" / "fills.csv"
    ledger = Path(args.ledger) if args.ledger else \
        root / "outputs" / "weekly_ledger.csv"
    if not fills.exists():
        print(f"no fills ledger at {fills} - nothing to reconcile")
        return 2
    sweeps = [parse_ts(s) for s in args.sweep]
    rep = build_report(fills, ledger, sweeps)
    text = json.dumps(rep, indent=2) if args.json else render_text(rep)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
