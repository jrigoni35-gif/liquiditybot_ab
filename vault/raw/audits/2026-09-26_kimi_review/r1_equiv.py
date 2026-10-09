"""R1 equivalence: old main._measured_sigma (pre-f3b5f9e1a) vs shipped delegate.
Exhaustive over the production type (VolState) + known stub shapes."""
import sys, itertools, types, os
sys.path.insert(0, os.getcwd())
from types import SimpleNamespace
from unittest.mock import MagicMock
import main
from regime.vol_regime import VolState
MUT = os.environ.get("R1_MUTATE")
if MUT == "prop_always":   # mutation: property ignores measured flag
    VolState.sigma_bar_pct_measured = property(lambda s: s.sigma_bar_pct)

def old(st):
    return st.sigma_bar_pct if getattr(st, "measured", True) else None

def new(st):
    fake = SimpleNamespace(vol=SimpleNamespace(state=lambda a: st))
    return main.LiquidityBot._measured_sigma(fake, "BTC")

cases = []
for m, s in itertools.product([True, False], [0.05, 0.0, 0.31, -1.0, float("nan"), 1e9]):
    cases.append(("VolState", VolState(asset="BTC", sigma_bar_pct=s, measured=m)))
cases.append(("VolState-default", VolState(asset="X")))
for s in [0.05, 0.31]:
    cases.append(("stub-noflag", SimpleNamespace(sigma_bar_pct=s)))
    cases.append(("stub-flagF", SimpleNamespace(sigma_bar_pct=s, measured=False)))
    cases.append(("stub-flagT", SimpleNamespace(sigma_bar_pct=s, measured=True)))
div = 0
for name, st in cases:
    o, n = old(st), new(st)
    same = (o is None and n is None) or (o == n) or (o != o and n != n)
    if not same:
        div += 1; print("DIVERGE", name, st, o, n)
mm = MagicMock()
print("MagicMock: old is mock", isinstance(old(mm), MagicMock), "new is mock", isinstance(new(mm), MagicMock), "same obj", old(mm) is new(mm))
print(f"cases={len(cases)} divergences={div} mutate={MUT}")
