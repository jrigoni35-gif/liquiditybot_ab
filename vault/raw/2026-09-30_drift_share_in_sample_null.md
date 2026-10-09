# Raw — drift-share in-sample null (script verbatim + output, 2026-09-30T14:05Z)

Corpus: outputs/signal_history.csv via ml.history.store_for_config (engine seam), current label era triple_barrier_h432, 24,576 rows at read. Monitor rules exact: PSI >= 0.25, trigger 0.30, window 300, DRIFT_EXCLUDED_FEATURES excluded, tied deciles counted in the denominator.

## Output
```
read 2026-09-30T14:05:24Z rows 24576 psi_thr 0.25 trigger 0.3 window 300
voting 64 degenerate 36 measurable 28
iid          drift_share mean 0.014 p95 0.016 | measurable mean 0.031 | fires ML-031 0/300
consecutive  drift_share mean 0.184 p95 0.251 | measurable mean 0.420 | fires ML-031 2/300 | window spans median 10.8 h
   consecutive most-often 'drifting': turbulence_pct 300, sent_dir 300, vol_percentile 298, drawdown_pct 298, corr_fast 298, sigma_bar_pct 292, spread_bps 270, poc_dist 243 (of 300 windows)
```

## Script
```python
"""In-sample drift null: does the monitor's drift_share fire on data that has
NOT drifted (the training corpus against its own deciles)?  Exact monitor
rules; iid windows (the 09-05 null) vs CONSECUTIVE windows (how the live
buffer fills)."""
import json
import sys
import time
from pathlib import Path

import numpy as np

WT = Path(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1")
MAIN = Path(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab")
sys.path.insert(0, str(WT))
from ml.calibration import feature_deciles, psi  # noqa: E402
from ml.features import DRIFT_EXCLUDED_FEATURES, FEATURE_NAMES  # noqa: E402
from ml.history import store_for_config  # noqa: E402

cfg = json.loads((MAIN / "config.json").read_text(encoding="utf-8"))
ml = cfg["ml"]
mon = ml.get("monitor", {})
thr = float(mon.get("drift_psi_threshold", 0.25))
frac = float(mon.get("drift_frac_features", 0.30))
WIN = 300
sw = ml.get("sample_weights", {})
hs = store_for_config(ml, path=str(MAIN / "outputs" / "signal_history.csv"))
X, y, w, sig = hs.load_training_data(
    half_life_days=float(sw.get("half_life_days", 30)),
    candidate_weight=float(sw.get("candidate_weight", 0.4)),
    manip_discount=float(sw.get("manip_discount", 0.5)),
    return_sig=True, weights_cfg=sw, telemetry_cfg=ml.get("telemetry", {}),
    epoch_cfg=ml.get("epoch", {}), era_cfg=ml.get("era_exclusion", {}))
X, sig = np.asarray(X, float), np.asarray(sig, float)
o = np.argsort(sig, kind="stable")
X, sig = X[o], sig[o]
print("read", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rows", len(X),
      "psi_thr", thr, "trigger", frac, "window", WIN)
edges = feature_deciles(X)
vote = [j for j, n in enumerate(FEATURE_NAMES[:X.shape[1]])
        if n not in DRIFT_EXCLUDED_FEATURES]
degen = [j for j in vote if np.unique(edges[j]).size < len(edges[j])]
meas = [j for j in vote if j not in degen]
print(f"voting {len(vote)} degenerate {len(degen)} measurable {len(meas)}")


def share(idx):
    d = [j for j in vote if psi(edges[j], X[idx, j]) >= thr]
    return len(d) / len(vote), len(d) / max(len(meas), 1), d


rng = np.random.default_rng(0)
res = {}
for name in ("iid", "consecutive"):
    s1, s2, fired, hits = [], [], 0, {}
    for _ in range(300):
        if name == "iid":
            idx = rng.choice(len(X), WIN, replace=False)
        else:
            st = int(rng.integers(0, len(X) - WIN))
            idx = np.arange(st, st + WIN)
        a, b, d = share(idx)
        s1.append(a)
        s2.append(b)
        fired += a >= frac
        for j in d:
            hits[FEATURE_NAMES[j]] = hits.get(FEATURE_NAMES[j], 0) + 1
    span = None
    if name == "consecutive":
        spans = [(sig[st + WIN - 1] - sig[st]) / 3600 for st in
                 rng.integers(0, len(X) - WIN, 200)]
        span = float(np.median(spans))
    top = sorted(hits.items(), key=lambda kv: -kv[1])[:8]
    print(f"{name:12s} drift_share mean {np.mean(s1):.3f} p95 {np.percentile(s1, 95):.3f} | "
          f"measurable mean {np.mean(s2):.3f} | fires ML-031 {fired}/300"
          + (f" | window spans median {span:.1f} h" if span else ""))
    print("   most-often 'drifting':", top)
```
