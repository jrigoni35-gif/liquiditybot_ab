# August champion vs today's champion - paired out-of-sample (2026-10-05)

Operator: "Is the model better now than before? August would be the best time to compare to."

**Inputs (snapshot-stamped):** outputs/signal_history.csv copied 2026-10-05T17:57:31Z (37,172 rows), read-only; model artifacts outputs/models/model_1ee3ae68c0df.json (last August champion, deployed 2026-08-25, logistic, v9, 6,729 rows) and model_3f62ef23f709.json (champion since 2026-09-23, blend, v10, 21,706 rows; byte-identical to the served outputs/meta_model.json).
**Design:** paired loss differential on rows neither model trained on (entries after today's champion's deploy), label era triple_barrier_h432; calibrated + clipped output; governor shrinkage EXCLUDED (policy dial). Benchmark = historical-average base rate known ex ante (Campbell & Thompson 2008, RFS 21(4):1509-1531, verified). Paired-forecast test per Diebold & Mariano 1995 (JBES 13:253-263, verified); day-block bootstrap per Politis & Romano 1994 (JASA 89(428):1303-1313, verified; affiliation not checked).
**Assumption [I]:** the v9 input = the v10 list minus the four dp_* columns (width 64 asserted; artifacts carry no names).

## Output (verbatim)
```
window: entries after 2026-09-23 10:09 UTC (today's champion deployed) | rows 4948 (dropped non-finite 0) | UTC days 13 | sources {'candidate': 4917, 'live': 31}
base rate in window 0.3644 | historical average before window p0 0.4396 (n=21828)
August 1ee3ae68 (logistic, v9)   Brier 0.2384  logloss 0.6699  AUC 0.539  mean p 0.452
Today  3f62ef23 (blend, v10)     Brier 0.2332  logloss 0.6590  AUC 0.531  mean p 0.393
Base-rate benchmark p0           Brier 0.2373  logloss 0.6676  AUC nan  mean p 0.440

PAIRED Brier differences (positive = second-named is MORE accurate), day-block 95% CI:
August minus Today            (>0: today better)           +0.0053  [-0.0050, +0.0164]  covers 0
Benchmark minus August        (>0: August beats base rate) -0.0012  [-0.0048, +0.0022]  covers 0
Benchmark minus Today         (>0: today beats base rate)  +0.0041  [-0.0049, +0.0138]  covers 0
Brier skill vs benchmark (Campbell-Thompson R2_OS analog): August -0.0049 | Today +0.0172

INSTRUMENT CHECKS (backpack 2 - the test must be able to see an effect):
PLANT: Today nudged 10% toward truth vs Today   (>0 expected) +0.0443  [+0.0416, +0.0467]  EXCLUDES 0
NULL:  Today vs itself                          (0 expected) +0.0000  [+0.0000, +0.0000]  covers 0
```

## Script
```python
"""August champion vs today's champion, paired, on rows NEITHER trained on.

Read-only: corpus snapshot (argv[1]) + model artifacts. Design:
  - Diebold & Mariano (1995): compare two forecasts on the SAME sample via
    the per-row loss differential, dependence-robust inference.
  - Campbell & Thompson (2008): the bar is the historical-average forecast
    known ex ante (here: the label base rate before the window).
  - Dependence: UTC-day block bootstrap (Politis & Romano 1994 family),
    4000 reps, seed 7 - the repo's registered CI method.
Model output compared = calibrated, clipped [0.05, 0.95]; the governor's
time-varying shrinkage toward 0.5 is a policy dial and is EXCLUDED.
"""
import csv, json, math, random, sys, time, collections
from pathlib import Path
import numpy as np

REPO = Path(r"C:/Users/haird/Documents/liquiditybot/liquiditybot_ab")
sys.path.insert(0, str(REPO))
from ml.features import FEATURE_NAMES                     # noqa: E402  (v10, 68)
from ml.models import load_model, auc_score              # noqa: E402
from ml.calibration import IsotonicCalibrator            # noqa: E402

AUG, CUR = "1ee3ae68c0df", "3f62ef23f709"
REG = [json.loads(l) for l in open(REPO / "outputs/models/registry.jsonl", encoding="utf-8") if l.strip()]
dep = {r["model_id"]: r["ts"] for r in REG if r["event"] == "deployed"}
CUTOFF = dep[CUR]                                         # rows after this: unseen by BOTH
ERA = "triple_barrier_h432"
DP = ("dp_surge_z", "dp_vol_z", "dp_hhi", "avail_dp")
V9 = [f for f in FEATURE_NAMES if f not in DP]            # v10 minus the dark-pool block = 64


def served(mid, X):
    art = json.load(open(REPO / f"outputs/models/model_{mid}.json", encoding="utf-8"))
    raw = load_model(str(REPO / f"outputs/models/model_{mid}.json")).predict_proba(X)
    cal = IsotonicCalibrator.from_dict(art.get("calibration")).transform(raw)
    return np.clip(np.asarray(cal, float), 0.05, 0.95), art


rows = list(csv.DictReader(open(sys.argv[1], newline="", encoding="utf-8")))
missing = [f for f in FEATURE_NAMES if f not in rows[0]]
assert not missing, f"corpus lacks feature columns: {missing}"

def fnum(x):
    try:
        v = float(x); return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None

lab = [r for r in rows if r.get("label") in ("0", "1") and r.get("label_era") == ERA and fnum(r.get("ts"))]
before = [r for r in lab if float(r["ts"]) <= CUTOFF]
win = [r for r in lab if float(r["ts"]) > CUTOFF]
p0 = sum(int(r["label"]) for r in before) / len(before)  # historical average, known ex ante
X10, y, day, src, dropped = [], [], [], [], 0
for r in win:
    v = [fnum(r.get(f)) for f in FEATURE_NAMES]
    if any(x is None for x in v):
        dropped += 1; continue
    X10.append(v); y.append(int(r["label"])); day.append(int(float(r["ts"]) // 86400)); src.append(r.get("source"))
X10 = np.array(X10); y = np.array(y); day = np.array(day)
X9 = X10[:, [FEATURE_NAMES.index(f) for f in V9]]
p_aug, a_art = served(AUG, X9)
p_cur, c_art = served(CUR, X10)
assert len(a_art["w"]) == X9.shape[1], "August model width != v9 vector"
p_bm = np.full(len(y), p0)

fmt = lambda t: time.strftime("%Y-%m-%d %H:%M", time.gmtime(t))
print(f"window: entries after {fmt(CUTOFF)} UTC (today's champion deployed) | rows {len(y)} "
      f"(dropped non-finite {dropped}) | UTC days {len(set(day))} | sources {dict(collections.Counter(src))}")
print(f"base rate in window {y.mean():.4f} | historical average before window p0 {p0:.4f} (n={len(before)})")

def brier(p): return (p - y) ** 2
def logloss(p): return -(y * np.log(p) + (1 - y) * np.log(1 - p))
for name, p in (("August 1ee3ae68 (logistic, v9)", p_aug), ("Today  3f62ef23 (blend, v10)", p_cur), ("Base-rate benchmark p0", p_bm)):
    auc = auc_score(y, p) if name[0] != "B" else float("nan")
    print(f"{name:32} Brier {brier(p).mean():.4f}  logloss {logloss(p).mean():.4f}  AUC {auc:.3f}  mean p {p.mean():.3f}")

days = sorted(set(day)); idx = {d: np.where(day == d)[0] for d in days}
def ci(diff, reps=4000, seed=7):
    rng = random.Random(seed); bs = []
    for _ in range(reps):
        take = np.concatenate([idx[rng.choice(days)] for _ in days])
        bs.append(float(diff[take].mean()))
    bs.sort(); return float(diff.mean()), bs[int(.025 * reps)], bs[int(.975 * reps) - 1]

def show(label, diff):
    m, lo, hi = ci(diff)
    verdict = "EXCLUDES 0" if lo > 0 or hi < 0 else "covers 0"
    print(f"{label:58} {m:+.4f}  [{lo:+.4f}, {hi:+.4f}]  {verdict}")

print("\nPAIRED Brier differences (positive = second-named is MORE accurate), day-block 95% CI:")
show("August minus Today            (>0: today better)", brier(p_aug) - brier(p_cur))
show("Benchmark minus August        (>0: August beats base rate)", brier(p_bm) - brier(p_aug))
show("Benchmark minus Today         (>0: today beats base rate)", brier(p_bm) - brier(p_cur))
bss = lambda p: 1 - brier(p).mean() / brier(p_bm).mean()
print(f"Brier skill vs benchmark (Campbell-Thompson R2_OS analog): August {bss(p_aug):+.4f} | Today {bss(p_cur):+.4f}")

print("\nINSTRUMENT CHECKS (backpack 2 - the test must be able to see an effect):")
show("PLANT: Today nudged 10% toward truth vs Today   (>0 expected)", brier(p_cur) - brier(0.9 * p_cur + 0.1 * y))
show("NULL:  Today vs itself                          (0 expected)", brier(p_cur) - brier(p_cur.copy()))
```
