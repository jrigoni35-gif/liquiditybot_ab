import subprocess, sys, pathlib
PY = r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.venv\Scripts\python.exe"
MUTS = [
 ("risk/profit_tiers.py", "        snaps = getattr(position, \"tier_trigger_snapshots\", None)\n        if not snaps:\n            return None", "        snaps = getattr(position, \"tier_trigger_snapshots\", None)\n        if True:\n            return None"),
 ("risk/profit_tiers.py", "            snaps[str(nxt)] = trig", "            pass"),
 ("core/persistence.py", "        \"tier_trigger_snapshots\": dict(pos.tier_trigger_snapshots or {}),\n", ""),
 ("core/persistence.py", "tier_trigger_snapshots={str(k): float(v) for k, v in", "tier_trigger_snapshots=dict() if True else {str(k): float(v) for k, v in"),
]
def run():
    r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_coupling_r123.py"], capture_output=True, text=True)
    return r.returncode, r.stdout.strip().splitlines()[-1]
print("CONTROL", run())
for f, old, new in MUTS:
    p = pathlib.Path(f); b = p.read_bytes(); s = b.decode()
    assert s.count(old) == 1, (f, old[:40], s.count(old))
    try:
        p.write_bytes(s.replace(old, new).encode()); print("MUT", f, old.strip()[:50].replace("\n"," | "), "->", run())
    finally:
        p.write_bytes(b)
print("RESTORED", run())
