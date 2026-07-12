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
    """Yield (asset, would_mult, set_of_codes) per THALES advice line."""
    if not path.exists():
        return
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or "thales" not in line:
                continue
            try:
                msg = json.loads(line).get("msg", "")
            except ValueError:
                continue
            am = _ASSET_RE.match(msg)
            wm = _WOULD_RE.search(msg)
            if not am or not wm:
                continue
            codes = {c for c in _CODE_RE.findall(msg) if c in DETECTORS}
            yield am.group(1), float(wm.group(1)), codes


def build_report(events_path: Path, status_path: Path,
                 min_fires: int) -> str:
    fires = Counter()                       # code -> times fired
    by_asset = defaultdict(Counter)         # asset -> code -> count
    up = down = neutral = 0
    mults = []
    total = 0
    for asset, mult, codes in parse_events(events_path):
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
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="outputs/events.jsonl")
    ap.add_argument("--status", default="outputs/status.json")
    ap.add_argument("--min-fires", type=int, default=30,
                    help="per-detector fires before it is worth A/B-ing")
    ap.add_argument("--out", default="outputs/thales_report.txt")
    args = ap.parse_args()

    report = build_report(Path(args.events), Path(args.status),
                          args.min_fires)
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
