import sys, csv, numpy as np
tree, out = sys.argv[1], sys.argv[2]
sys.path.insert(0, tree)
from ml.features import FEATURE_NAMES as N
from ml.models import load_model
import ml.models as mm; print("models from", mm.__file__)
m = load_model(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\meta_model.json")
X = []
with open(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\outputs\signal_history.csv", newline="", encoding="utf-8") as f:
    r = csv.reader(f); next(r)
    for row in r: X.append([float(v) for v in row[3:3+len(N)]])
X = np.array(X)
pa, pb = m.a.predict_proba(X), m.predict_proba(X)
Xi = X[-50:].copy(); Xi[:, N.index("dp_vol_z")] = 0.5
Xf = X[-50:].copy(); Xf[:, N.index("sent_fear")] = 1.0
np.savez(out, pa=pa, pb=pb, inj_dp=m.a.predict_proba(Xi), inj_fear=m.a.predict_proba(Xf), base_tail=m.a.predict_proba(X[-50:]))
print("rows", X.shape)
