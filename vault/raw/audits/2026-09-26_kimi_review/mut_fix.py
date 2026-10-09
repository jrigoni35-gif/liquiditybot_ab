import subprocess, pathlib
PY = r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.venv\Scripts\python.exe"
MUTS = [
 ("keep-first guard", "risk/profit_tiers.py", "if not isinstance(snaps, dict) or str(nxt) in snaps:", "if not isinstance(snaps, dict):"),
 ("unmeasured guard", "risk/profit_tiers.py", 'if sigma_bar_pct is not None else float("nan"))', 'if sigma_bar_pct is not None else 1.0)'),
 ("positive guard on read", "risk/profit_tiers.py", "return sig if math.isfinite(sig) and sig > 0.0 else None", "return sig if math.isfinite(sig) else None"),
 ("tolerant restore", "core/persistence.py", "            try:\n                f = float(v)\n            except (TypeError, ValueError):\n                continue", "            f = float(v)"),
 ("freeze sigma not trigger (scale)", "risk/profit_tiers.py", "                tier, frozen if frozen is not None else sigma_bar_pct,", "                tier, frozen if frozen is not None else sigma_bar_pct,  # noop"),
]
def run():
    r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_coupling_r123.py"], capture_output=True, text=True)
    return r.returncode, r.stdout.strip().splitlines()[-1]
print("CONTROL", run())
for name, f, old, new in MUTS:
    p = pathlib.Path(f); b = p.read_bytes(); s = b.decode()
    assert s.count(old) == 1, (name, s.count(old))
    try:
        p.write_bytes(s.replace(old, new).encode()); print("MUT", name, "->", run())
    finally:
        p.write_bytes(b)
print("RESTORED", run())
