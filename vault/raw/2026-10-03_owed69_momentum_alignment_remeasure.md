# Owed 69 re-measure — momentum alignment vs h432 label win rate (2026-10-03)

Raw measurement record. Operator ask: "continue with the 37% phenomena … something was correlating before".
The "37%" = owed 69's anti-momentum pattern (era-9 survey "shorts 54%, longs 37%"; item 69 pooled split).

**Inputs (snapshot-stamped):** `outputs/signal_history.csv` copied 2026-10-03T23:35:20Z (36,349 rows),
read-only; cohort timeline from live `outputs/audit.jsonl` (read). Live outputs never written.
**Filter:** source=candidate, label_era=triple_barrier_h432 (derived from config label_max_bars),
label in {0,1}, finite ret_12_dir, direction ±1 -> 25,840 rows. All are post capital epoch
(1786403127 = 2026-08-10T23:05:27Z), so "lifetime" == "clean" for this era.
**Buckets:** ret_12_dir (side-relative) with >= +0.5, against < -0.5, flat between — the
`defensive_cadence_report.py` §2b cut points.
**Gap stat:** win(against) - win(with); 95% CI = UTC day-block bootstrap, 4,000 reps, seed 7.
**Validation (detector proven both ways):** scrambled labels -> gap covers 0; planted lift on
"against" -> CI excludes 0. **CS-1:** cohorts via core/cohort.fp_at, reconcile OK.
Script: kept with this page as owed69.py (below).

## Output (verbatim)
```
snapshot=sh_snap.csv era=triple_barrier_h432 eligible=25840 of 36349 raw rows
base win rate post-epoch: 42.7% (n=25840)

### LIFETIME pooled (context only)  (n=25840)
side  | bucket  |    n | win%  [95% Wilson]
long  | with    | 7520 |  48.5% [47.4%, 49.7%]
long  | flat    | 5633 |  47.9% [46.6%, 49.2%]
long  | against | 2864 |  49.7% [47.9%, 51.6%]
short | with    | 4200 |  33.4% [32.0%, 34.8%]
short | flat    | 3733 |  31.2% [29.8%, 32.7%]
short | against | 1890 |  37.1% [34.9%, 39.3%]
GAP against-with long : +1.2% [-3.1%, +6.2%] days=53  covers 0
GAP against-with short: +3.7% [-1.1%, +9.0%] days=53  covers 0
GAP against-with both : +1.6% [-3.0%, +6.2%] days=53  covers 0

### POST capital epoch - clean cohort (measurement of record)  (n=25840)
side  | bucket  |    n | win%  [95% Wilson]
long  | with    | 7520 |  48.5% [47.4%, 49.7%]
long  | flat    | 5633 |  47.9% [46.6%, 49.2%]
long  | against | 2864 |  49.7% [47.9%, 51.6%]
short | with    | 4200 |  33.4% [32.0%, 34.8%]
short | flat    | 3733 |  31.2% [29.8%, 32.7%]
short | against | 1890 |  37.1% [34.9%, 39.3%]
GAP against-with long : +1.2% [-3.1%, +6.2%] days=53  covers 0
GAP against-with short: +3.7% [-1.1%, +9.0%] days=53  covers 0
GAP against-with both : +1.6% [-3.0%, +6.2%] days=53  covers 0

VALIDATION scrambled labels: gap -0.0% [-1.5%, +1.7%] (expect covers 0)
VALIDATION planted +10pp-ish on against: gap +6.9% [+2.2%, +11.8%] (expect shifts up)

## BY ASSET (post-epoch, both sides)
ETH    n= 5241 gap -0.0% [-7.3%, +7.3%]
PAXG   n= 4039 gap +3.9% [-2.0%, +10.0%]
LINK   n= 4005 gap -2.7% [-13.7%, +8.9%]
ARB    n= 2206 gap +0.2% [-9.3%, +10.2%]
MINA   n= 1783 gap +10.0% [-3.0%, +22.9%]
BTC    n= 1768 gap +4.0% [-5.8%, +14.3%]
DOGE   n= 1405 gap +11.3% [-1.1%, +24.9%]
SUI    n= 1307 gap +0.0% [-11.9%, +12.0%]
XRP    n=  994 gap -7.9% [-21.1%, +6.2%]
DOT    n=  972 gap -3.7% [-21.8%, +13.2%]
FLOW   n=  751 gap +6.8% [-6.5%, +19.8%]
SOL    n=  508 gap -6.1% [-21.6%, +11.8%]
ADA    n=  463 gap -0.4% [-23.1%, +30.0%]
AVAX   n=  228 gap +11.8% [-20.0%, +36.8%]
LTC    n=  170 gap +3.9% [-41.1%, +35.4%]

## BY VOL TERCILE (post-epoch; edges 0.4/0.6)
low  n= 8634 gap +1.6% [-5.4%, +8.6%]
mid  n= 8618 gap +1.5% [-4.4%, +7.3%]
high n= 8588 gap +1.7% [-5.5%, +8.8%]

## BY DECISION-FINGERPRINT COHORT (core/cohort.fp_at)
CS-1 reconcile: {'standard': 'CS-1', 'n': 25840, 'sum': 25840, 'ok': True, 'buckets': {'legacy': 23643, '0f773bf5fc67': 264, '75e19fa38ffb': 266, '281334f23604': 101, '6709bb74df3e': 367, '6709bb58cd7c': 14, '6709bbc2778d': 1184, '575386195006': 1}, 'line': 'counting CS-1: n=25840 = legacy=23643 + 0f773bf5fc67=264 + 75e19fa38ffb=266 + 281334f23604=101 + 6709bb74df3e=367 + 6709bb58cd7c=14 + 6709bbc2778d=1184 + 575386195006=1 [OK]'}
legacy         from_ts=1786568178 n=23643 days= 48 gap +0.7% [-4.2%, +5.5%]
0f773bf5fc67   from_ts=1790566476 n=  264 days=  1 gap -23.7% [-23.7%, -23.7%]
75e19fa38ffb   from_ts=1790605255 n=  266 days=  2 gap +28.5% [+18.4%, +50.6%]
281334f23604   from_ts=1790690782 n=  101 days=  1 gap +2.7% [+2.7%, +2.7%]
6709bb74df3e   from_ts=1790707945 n=  367 days=  2 gap -7.8% [-10.6%, +0.0%]
6709bb58cd7c   from_ts=1790778944 n=   14 days=  1 gap -23.3% [-23.3%, -23.3%]
6709bbc2778d   from_ts=1790784957 n= 1184 days=  4 gap +22.3% [+2.1%, +53.8%]
575386195006   from_ts=1791069027 n=    1 days=  1 gap n/a
```

## owed69.py
```python
"""Owed-69 re-measure: momentum alignment vs h-label win rate, clean cohort,
disaggregated, with day-block CIs and a planted-effect validation.
Read-only: inputs are a snapshot CSV + the live audit.jsonl (read)."""
import csv, json, math, random, sys, collections
from pathlib import Path

REPO = Path(r"C:/Users/haird/Documents/liquiditybot/liquiditybot_ab")
sys.path.insert(0, str(REPO))
from core.cohort import fp_timeline, fp_at, reconcile  # noqa: E402

SNAP = Path(sys.argv[1])
CAPITAL_EPOCH_TS = 1786403127.0          # 2026-08-10T23:05:27Z (defensive_cadence_report.py:39)
LMB = json.loads((REPO / "config.json").read_text(encoding="utf-8"))["ml"]["label_max_bars"]
ERA = "triple_barrier" if LMB == 96 else f"triple_barrier_h{LMB}"
REPS, SEED = 4000, 7


def f(x):
    try:
        v = float(x); return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def bucket(m):
    return "with" if m >= 0.5 else ("against" if m < -0.5 else "flat")   # report §2b cut points


def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 3
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


def gap_ci(rows):
    """against-minus-with win rate; CI = day-block bootstrap (UTC day)."""
    days = collections.defaultdict(list)
    for r in rows: days[int(r["ts"] // 86400)].append(r)
    keys = list(days)
    def gap(rs):
        a = [r["y"] for r in rs if r["b"] == "against"]; w = [r["y"] for r in rs if r["b"] == "with"]
        return (sum(a) / len(a) - sum(w) / len(w)) if a and w else None
    pt = gap(rows); rng = random.Random(SEED); bs = []
    for _ in range(REPS):
        rs = [r for k in (rng.choice(keys) for _ in keys) for r in days[k]]
        g = gap(rs)
        if g is not None: bs.append(g)
    bs.sort()
    if pt is None or len(bs) < 100: return pt, None, None, len(keys)
    return pt, bs[int(.025 * len(bs))], bs[int(.975 * len(bs)) - 1], len(keys)


def table(rows, title):
    print(f"\n### {title}  (n={len(rows)})")
    print("side  | bucket  |    n | win%  [95% Wilson]")
    for side in ("long", "short"):
        for b in ("with", "flat", "against"):
            s = [r for r in rows if r["side"] == side and r["b"] == b]
            p, lo, hi = wilson(sum(r["y"] for r in s), len(s))
            print(f"{side:5} | {b:7} | {len(s):4} | {p:6.1%} [{lo:.1%}, {hi:.1%}]" if s else f"{side:5} | {b:7} |    0 |   -")
    for side in ("long", "short", "both"):
        s = rows if side == "both" else [r for r in rows if r["side"] == side]
        pt, lo, hi, nd = gap_ci(s)
        if pt is None: print(f"GAP against-with {side:5}: n/a"); continue
        tag = "" if lo is None else ("  EXCLUDES 0" if (lo > 0 or hi < 0) else "  covers 0")
        ci = "CI n/a" if lo is None else f"[{lo:+.1%}, {hi:+.1%}]"
        print(f"GAP against-with {side:5}: {pt:+.1%} {ci} days={nd}{tag}")


raw = list(csv.DictReader(open(SNAP, newline="", encoding="utf-8")))
rows = []
for r in raw:
    if r.get("source") != "candidate" or r.get("label_era") != ERA or r.get("label") not in ("0", "1"):
        continue
    ts, m, d = f(r.get("ts")), f(r.get("ret_12_dir")), f(r.get("direction"))
    if ts is None or m is None or d not in (1.0, -1.0):
        continue
    rows.append({"ts": ts, "y": int(r["label"]), "b": bucket(m), "side": "long" if d > 0 else "short",
                 "asset": r.get("asset", "?"), "vol": f(r.get("vol_percentile"))})
print(f"snapshot={SNAP.name} era={ERA} eligible={len(rows)} of {len(raw)} raw rows")
post = [r for r in rows if r["ts"] >= CAPITAL_EPOCH_TS]
print(f"base win rate post-epoch: {sum(r['y'] for r in post)/len(post):.1%} (n={len(post)})")

table(rows, "LIFETIME pooled (context only)")
table(post, "POST capital epoch - clean cohort (measurement of record)")

# --- validation: the instrument must read ~0 on scrambled labels and light on a plant
rng = random.Random(11); ys = [r["y"] for r in post]; rng.shuffle(ys)
scr = [dict(r, y=y) for r, y in zip(post, ys)]
pt, lo, hi, _ = gap_ci(scr); print(f"\nVALIDATION scrambled labels: gap {pt:+.1%} [{lo:+.1%}, {hi:+.1%}] (expect covers 0)")
pl = [dict(r, y=(1 if (r['b'] == 'against' and rng.random() < .10) else r["y"])) for r in post]
pt, lo, hi, _ = gap_ci(pl); print(f"VALIDATION planted +10pp-ish on against: gap {pt:+.1%} [{lo:+.1%}, {hi:+.1%}] (expect shifts up)")

# --- disaggregation (close terms): by asset, by vol tercile
print("\n## BY ASSET (post-epoch, both sides)")
for a, n in collections.Counter(r["asset"] for r in post).most_common():
    s = [r for r in post if r["asset"] == a]
    pt, lo, hi, nd = gap_ci(s)
    ci = "n/a" if (pt is None or lo is None) else f"{pt:+.1%} [{lo:+.1%}, {hi:+.1%}]"
    print(f"{a:6} n={n:5} gap {ci}")
vv = sorted(r["vol"] for r in post if r["vol"] is not None)
e1, e2 = vv[len(vv)//3], vv[2*len(vv)//3]
print(f"\n## BY VOL TERCILE (post-epoch; edges {e1:.1f}/{e2:.1f})")
for name, cond in (("low", lambda v: v <= e1), ("mid", lambda v: e1 < v <= e2), ("high", lambda v: v > e2)):
    s = [r for r in post if r["vol"] is not None and cond(r["vol"])]
    pt, lo, hi, nd = gap_ci(s)
    print(f"{name:4} n={len(s):5} gap {pt:+.1%} [{lo:+.1%}, {hi:+.1%}]" if lo is not None else f"{name} n={len(s)} n/a")

# --- CS-1: attribute by decision fingerprint through core/cohort.py, reconcile
tl = fp_timeline(REPO / "outputs" / "audit.jsonl")
by = collections.defaultdict(list)
for r in post: by[fp_at(r["ts"], tl)].append(r)
print("\n## BY DECISION-FINGERPRINT COHORT (core/cohort.fp_at)")
print("CS-1 reconcile:", reconcile(len(post), {k: len(v) for k, v in by.items()}))
for k, v in sorted(by.items(), key=lambda kv: min(r["ts"] for r in kv[1])):
    pt, lo, hi, nd = gap_ci(v)
    first = min(r["ts"] for r in v)
    ci = "n/a" if (pt is None or lo is None) else f"{pt:+.1%} [{lo:+.1%}, {hi:+.1%}]"
    print(f"{str(k)[:14]:14} from_ts={first:.0f} n={len(v):5} days={nd:3} gap {ci}")
```
