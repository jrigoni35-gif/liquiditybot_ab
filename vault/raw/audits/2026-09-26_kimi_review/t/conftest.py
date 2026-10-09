import importlib.util, sys
WT = r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\vscode-bridge-5548d1"
import os; sys.path.insert(0, WT); [sys.path.insert(0, p) for p in os.environ.get('FIXSRC','').split(';') if p]
_spec = importlib.util.spec_from_file_location("_repo_conftest", WT + r"\tests\conftest.py")
_m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_m)
for _n in dir(_m):
    if _n.startswith(("_isolated", "_sidecar", "_no_production", "pytest_")):
        globals()[_n] = getattr(_m, _n)
# re-assert the fix-source precedence AFTER the repo conftest ran (it may
# insert the repo root at sys.path[0] and import main itself)
for _p in [p for p in os.environ.get('FIXSRC', '').split(';') if p]:
    sys.path.insert(0, _p)
    sys.modules.pop("main", None)
