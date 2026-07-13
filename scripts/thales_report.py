"""
scripts/thales_report.py

Turns a THALES shadow run into a promotion decision. THALES rides in
`influence=shadow`: its detectors score every candidate and record the
confidence multiplier they WOULD have applied, with zero live effect
(strategies/thales.py). This script reads that durable evidence out of
outputs/events.jsonl (+ current scores from status.json) and answers the
only question that matters before flipping to `advise`:

  is there a real, recurring lazy-bot footprint here, and would reacting
  to it have helped — or is the venue just too institutional to bother?

It reports, per detector and per asset:
  * firing frequency (how often each footprint actually appears)
  * would-shade distribution (up-shades chase predictable flow; down-
    shades dodge stop-cluster cascades)
  * a promotion-readiness verdict against a minimum-evidence bar

No thresholds are tuned here and nothing is promoted - this is the
evidence a human weighs to decide, consistent with THALES's shadow-first
ladder. Read-only: opens logs, writes a report, touches no live state.

Usage:
    python scripts/thales_report.py
    python scripts/thales_report.py --events outputs/events.jsonl --min-fires 30
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# TH-* reason codes (mirror core/codes.py; kept as literals so the report
# runs even if the engine package fails to import in a bare environment)
DETECTORS = {
    "TH-010": "grid_ladder     (Hummingbot order_levels / grid bots)",
    "TH-011": "metronome_mm    (Hummingbot order_refresh_time cadence)",
    "TH-012": "clockwork_flow  (scheduled time-of-day flow)",
    "TH-013": "stop_herding    (freqtrade fixed-stop cluster sweeps)",
    "TH-014": "feed_integrity  (hostile/unreliable venue: missing/rejected data)",
}
_WOULD_RE = re.compile(r"would x([0-9]+\.[0-9]+)")
_ASSET_RE = re.compile(r"^thales ([A-Z0-9]+):")
_CODE_RE = re.compile(r"TH-0\d\d")


def parse_events(path: Path):
    """Yield (ts, asset, would_mult, set_of_codes) per THALES advice line."""
    if not path.exists():
        return
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or "thales" not in line:
                continue
            try:
                rec = json.loads(line)
                msg = rec.get("msg", "")
            except ValueError:
                continue
            am = _ASSET_RE.match(msg)
            wm = _WOULD_RE.search(msg)
            if not am or not wm:
                continue
            codes = {c for c in _CODE_RE.findall(msg) if c in DETECTORS}
            yield (float(rec.get("ts", 0) or 0), am.group(1),
                   float(wm.group(1)), codes)


def load_labeled_rows(history_path: Path):
    """(ts, asset, label, net_pnl_usd) per labeled training row."""
    rows = []
    if not history_path.exists():
        return rows
    import csv
    with open(history_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                rows.append((float(r["ts"]), r["asset"],
                             int(float(r["label"])),
                             float(r["net_pnl_usd"] or 0)))
            except (KeyError, TypeError, ValueError):
                continue
    return rows


def counterfactual_join(fire_ts_by_asset: dict, rows: list,
                        window_sec: float) -> dict:
    """Exposure join: a labeled trade is EXPOSED to a detector when that
    detector fired on the same asset within window_sec before the row's
    label time (~ the trade's lifetime). Correlation-of-exposure evidence,
    not a full advice replay - per-trade shade recording is a future rung."""
    from bisect import bisect_left, bisect_right
    exposed, unexposed = [], []
    for ts, asset, label, net in rows:
        fires = fire_ts_by_asset.get(asset, [])
        lo = bisect_left(fires, ts - window_sec)
        hi = bisect_right(fires, ts)
        (exposed if hi > lo else unexposed).append((label, net))

    def bucket(b):
        n = len(b)
        wins = sum(1 for label, _ in b if label == 1)
        net = sum(net for _, net in b)
        return {"n": n, "win_rate": (100.0 * wins / n) if n else None,
                "net_usd": net}
    return {"exposed": bucket(exposed), "unexposed": bucket(unexposed)}


def build_report(events_path: Path, status_path: Path,
                 min_fires: int, history_path: Path | None = None,
                 exposure_hours: float = 8.0) -> str:
    fires = Counter()                       # code -> times fired
    by_asset = defaultdict(Counter)         # asset -> code -> count
    up = down = neutral = 0
    mults = []
    total = 0
    fire_ts = defaultdict(lambda: defaultdict(list))  # code -> asset -> [ts]
    for ts, asset, mult, codes in parse_events(events_path):
        total += 1
        mults.append(mult)
        if mult > 1.0001:
            up += 1
        elif mult < 0.9999:
            down += 1
        else:
            neutral += 1
        for c in codes:
            fires[c] += 1
            by_asset[asset][c] += 1
            fire_ts[c][asset].append(ts)

    lines = ["THALES shadow-evidence report",
             "=" * 42,
             f"advice events observed: {total}"]
    if total == 0:
        lines.append("")
        lines.append("no THALES advice recorded yet - detectors are warming "
                     "up or no footprint has fired. Let the shadow run "
                     "accrue, then re-check.")
        return "\n".join(lines)

    avg = sum(mults) / len(mults)
    lines += [f"would-shade: {up} up / {down} down / {neutral} flat "
              f"(mean x{avg:.3f})",
              "",
              "detector firing frequency:"]
    for code, label in DETECTORS.items():
        n = fires.get(code, 0)
        share = 100.0 * n / total
        lines.append(f"  {code} {label}: {n:>4}  ({share:4.1f}% of events)")

    lines.append("")
    lines.append("per-asset footprint counts:")
    for asset in sorted(by_asset):
        parts = ", ".join(f"{c}={by_asset[asset][c]}"
                          for c in DETECTORS if by_asset[asset][c])
        lines.append(f"  {asset}: {parts or 'none'}")

    # current live scores from status.json (snapshot, best-effort)
    try:
        st = json.loads(status_path.read_text(encoding="utf-8"))
        panel = st.get("thales") or {}
        if panel.get("assets"):
            lines.append("")
            lines.append(f"current scores (influence={panel.get('influence')}):")
            for a, sc in panel["assets"].items():
                lines.append(f"  {a}: grid={sc.get('grid')} "
                             f"metro={sc.get('metronome')} "
                             f"clock={sc.get('clockwork')} "
                             f"stop_zone={sc.get('stop_zone')}")
    except (OSError, ValueError):
        pass

    # promotion-readiness verdict: which detectors have enough evidence,
    # and does any of it point at an actionable, recurring footprint
    active = [c for c in DETECTORS if fires.get(c, 0) >= min_fires]
    lines += ["", "promotion readiness (bar: >= "
              f"{min_fires} fires per detector):"]
    if not active:
        lines.append("  NOT READY - no detector has cleared the evidence "
                     "bar. Every footprint is still too sparse to trust a "
                     "shade on. Keep THALES in shadow.")
    else:
        for c in active:
            lines.append(f"  {c} {DETECTORS[c].split('(')[0].strip()} has "
                         f"{fires[c]} fires - enough to evaluate a "
                         f"shadow->advise A/B on this detector alone.")
        lines.append("  NOTE: firing often only proves the footprint is "
                     "PRESENT. Whether reacting PROFITS still needs the "
                     "counterfactual joined to trade outcomes - do not "
                     "promote on frequency alone.")

    # counterfactual exposure join for every detector past the fires bar:
    # do OUR labeled trades that overlapped this footprint end differently?
    rows = load_labeled_rows(history_path) if history_path else []
    if active and rows:
        window = exposure_hours * 3600.0
        lines += ["", f"counterfactual (exposure join, window "
                  f"{exposure_hours:.0f}h, {len(rows)} labeled trades):"]
        for c in active:
            ts_map = {a: sorted(v) for a, v in fire_ts[c].items()}
            j = counterfactual_join(ts_map, rows, window)
            e, u = j["exposed"], j["unexposed"]
            def fmt(b):
                if not b["n"]:
                    return "n=0"
                return (f"n={b['n']} win={b['win_rate']:.0f}% "
                        f"net=${b['net_usd']:+.2f}")
            lines.append(f"  {c}: exposed {fmt(e)} | unexposed {fmt(u)}")
            if e["n"] < 10 or u["n"] < 10:
                lines.append(f"    -> data-starved (need >=10 per bucket; "
                             f"have {e['n']}/{u['n']}) - keep shadow, "
                             f"keep accruing rows.")
            else:
                edge = (e["win_rate"] or 0) - (u["win_rate"] or 0)
                lines.append(f"    -> exposed-vs-unexposed win-rate edge "
                             f"{edge:+.1f}pp on ${e['net_usd']:+.2f} vs "
                             f"${u['net_usd']:+.2f} net - weigh alongside "
                             f"would-shade direction before any promote.")
    elif active:
        lines += ["", "counterfactual: no labeled trades available yet - "
                  "the join activates as signal_history accrues."]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="outputs/events.jsonl")
    ap.add_argument("--status", default="outputs/status.json")
    ap.add_argument("--min-fires", type=int, default=30,
                    help="per-detector fires before it is worth A/B-ing")
    ap.add_argument("--history", default="outputs/signal_history.csv")
    ap.add_argument("--exposure-hours", type=float, default=8.0,
                    help="labeled-trade lifetime window joined to fires")
    ap.add_argument("--out", default="outputs/thales_report.txt")
    args = ap.parse_args()

    report = build_report(Path(args.events), Path(args.status),
                          args.min_fires, Path(args.history),
                          args.exposure_hours)
    print(report)
    try:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report + "\n", encoding="utf-8")
        print(f"\nwritten: {args.out}")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
