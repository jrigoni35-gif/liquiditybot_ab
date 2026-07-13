"""
scripts/pipeline_audit.py — stage-by-stage decision-funnel audit.

Breaks the whole pipeline into its stages and measures where flow dies,
so "is it on a profit-gaining frequency" is answerable per stage instead
of by staring at equity:

    DATA -> SIGNAL -> LEARNING SLOT -> SIZING -> EXECUTION -> LABELS -> P&L

Read-only: parses outputs/events.jsonl, outputs/audit.jsonl,
outputs/signal_history.csv and outputs/status.json over a time window
(default 24h). Writes outputs/pipeline_audit.md and prints the summary.

Usage: python scripts/pipeline_audit.py [--hours 24]
"""
import argparse
import csv
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SZ_CODE = re.compile(r"SZ-\d{3}")


def _read_events(path: Path, since: float) -> list:
    out = []
    if not path.exists():
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if float(e.get("ts", 0)) >= since:
                out.append(e)
    return out


def funnel_from_events(events: list) -> dict:
    """Count each pipeline stage from the event stream."""
    f = {"signals_confirmed": Counter(), "exploration_entries": Counter(),
         "exploration_yielded": Counter(), "sizer_vetoes": Counter(),
         "entries_filled": Counter(), "closes": 0, "dust_flats": 0,
         "venue_min_rejects": 0, "errors": 0}
    for e in events:
        msg, level = e.get("msg", ""), e.get("level", "")
        if level in ("ERROR", "CRITICAL"):
            f["errors"] += 1
        m = re.match(r"IF3 signal (\w+)", msg)
        if m:
            f["signals_confirmed"][m.group(1)] += 1
            continue
        m = re.match(r"\[(\w+)\] EXPLORATION paper entry", msg)
        if m:
            f["exploration_entries"][m.group(1)] += 1
            continue
        m = re.match(r"\[(\w+)\] exploration (yielded|skipped)", msg)
        if m:
            f["exploration_yielded"][m.group(1)] += 1
            continue
        m = re.match(r"\[(\w+)\] sizer veto: (.*)", msg)
        if m:
            codes = SZ_CODE.findall(m.group(2))
            f["sizer_vetoes"][codes[-1] if codes else "SZ-???"] += 1
            continue
        m = re.match(r"ENTRY \w+ (\w+)/", msg)
        if m:
            f["entries_filled"][m.group(1)] += 1
            continue
        if msg.startswith("CLOSE "):
            f["closes"] += 1
        elif msg.startswith("DUST FLAT"):
            f["dust_flats"] += 1
        elif "OM-012" in msg:
            f["venue_min_rejects"] += 1
    return f


def labels_in_window(history_csv: Path, since: float) -> dict:
    """Label flow + per-trade economics from the training CSV."""
    out = {"rows": 0, "wins": 0, "net_pnl": 0.0, "by_asset": Counter(),
           "by_source": Counter()}
    if not history_csv.exists():
        return out
    with open(history_csv, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                if float(row.get("ts") or 0) < since:
                    continue
                out["rows"] += 1
                out["wins"] += int(row.get("label") or 0)
                out["net_pnl"] += float(row.get("net_pnl_usd") or 0.0)
                out["by_asset"][row.get("asset", "?")] += 1
                out["by_source"][row.get("source", "?")] += 1
            except (TypeError, ValueError):
                out["by_source"]["malformed"] += 1
    return out


def audit_code_mix(audit_jsonl: Path, since: float) -> Counter:
    mix: Counter = Counter()
    if not audit_jsonl.exists():
        return mix
    with open(audit_jsonl, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if float(r.get("ts", 0)) >= since:
                mix[str(r.get("code", "?"))] += 1
    return mix


def verdict(f: dict, labels: dict, status: dict) -> list:
    """Per-stage findings: where does profit frequency die?"""
    findings = []
    sig = sum(f["signals_confirmed"].values())
    exp = sum(f["exploration_entries"].values())
    fills = sum(f["entries_filled"].values())
    vetoes = sum(f["sizer_vetoes"].values())
    if sig == 0:
        findings.append("SIGNAL DROUGHT: no confirmed signals in window - "
                        "nothing downstream can happen")
    if sig and exp == 0 and fills == 0:
        findings.append("LEARNING SLOT UNUSED: signals confirm but neither "
                        "exploration nor sized entries fire")
    if vetoes and fills == 0:
        top = f["sizer_vetoes"].most_common(1)[0]
        findings.append(f"SIZING WALL: {vetoes} vetoes, 0 fills - dominant "
                        f"veto {top[0]} x{top[1]}")
    if fills and labels["rows"] == 0:
        findings.append("LABEL STALL: fills happen but no labeled rows "
                        "landed (check pending labels / candle flow)")
    if labels["rows"]:
        wr = labels["wins"] / labels["rows"]
        avg = labels["net_pnl"] / labels["rows"]
        if avg <= 0:
            findings.append(f"NEGATIVE FREQUENCY: {labels['rows']} labels, "
                            f"win rate {wr:.0%}, avg net ${avg:+.2f}/trade "
                            f"- costs are beating the edge")
        else:
            findings.append(f"PROFIT-POSITIVE: {labels['rows']} labels, win "
                            f"rate {wr:.0%}, avg net ${avg:+.2f}/trade")
    mon = status.get("monitor", {})
    if mon.get("level", 0) >= 2:
        findings.append("GOVERNOR L2: model output disabled - recovery "
                        "needs labels -> retrain -> deploy")
    if f["errors"]:
        findings.append(f"{f['errors']} ERROR/CRITICAL events in window")
    return findings


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24.0)
    args = ap.parse_args(argv)
    since = time.time() - args.hours * 3600.0

    events = _read_events(ROOT / "outputs" / "events.jsonl", since)
    f = funnel_from_events(events)
    labels = labels_in_window(ROOT / "outputs" / "signal_history.csv", since)
    mix = audit_code_mix(ROOT / "outputs" / "audit.jsonl", since)
    try:
        status = json.loads((ROOT / "outputs" / "status.json")
                            .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        status = {}

    finds = verdict(f, labels, status)
    lines = [f"# Pipeline audit — last {args.hours:.0f}h",
             "",
             f"- signals confirmed: {sum(f['signals_confirmed'].values())} "
             f"{dict(f['signals_confirmed'])}",
             f"- exploration entries: "
             f"{sum(f['exploration_entries'].values())} "
             f"(yielded/skipped {sum(f['exploration_yielded'].values())})",
             f"- sizer vetoes: {dict(f['sizer_vetoes'])}",
             f"- entries filled: {sum(f['entries_filled'].values())} "
             f"{dict(f['entries_filled'])} | closes {f['closes']} | dust "
             f"{f['dust_flats']} | venue-min rejects "
             f"{f['venue_min_rejects']}",
             f"- labels: {labels['rows']} (wins {labels['wins']}) "
             f"net ${labels['net_pnl']:+.2f} | by asset "
             f"{dict(labels['by_asset'])} | by source "
             f"{dict(labels['by_source'])}",
             f"- audit code mix (top 8): {dict(mix.most_common(8))}",
             "", "## Findings"]
    lines += [f"- {x}" for x in (finds or ["clean window"])]
    report = "\n".join(lines) + "\n"
    out = ROOT / "outputs" / "pipeline_audit.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
