import subprocess, pathlib
PY = r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.venv\Scripts\python.exe"
F = "execution/order_manager.py"
MUTS = [
 ("drop label cascade key", '''                    "ml.label_round_trip_cost_pct":
                        (prop_maker + prop_taker) / 100.0},''', '''                    },'''),
 ("drop stale unlink", '''                    os.remove(_FEE_PROPOSAL_REL_PATH)''', '''                    pass'''),
 ("R3 disabled entirely (pre-R3 main)", '''                self._write_fee_proposal(now, pair_results, mismatched,
                                         volume_30d, volume_currency)''', '''                pass'''),
]
def run():
    r = subprocess.run([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_coupling_r123.py"], capture_output=True, text=True)
    return r.returncode, r.stdout.strip().splitlines()[-1]
print("CONTROL", run())
for name, old, new in MUTS:
    p = pathlib.Path(F); b = p.read_bytes(); s = b.decode()
    assert s.count(old) == 1, name
    try:
        p.write_bytes(s.replace(old, new).encode()); print("MUT", name, "->", run())
    finally:
        p.write_bytes(b)
print("RESTORED", run())
