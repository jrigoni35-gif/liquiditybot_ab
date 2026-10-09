---
name: local-compute-directive
description: "Standing operator directive — seek out and implement anything that distributes/improves local PC compute (pytest-xdist class); box is a Ryzen 5 5600X, 6C/12T"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 63d8f842-8108-448c-b2d9-fa9a4c8a2da4
  modified: 2026-10-04T22:53:28.479Z
---

Operator directive (2026-08-07, verbatim intent): "make sure anything similar to pytest-xdist that will improve/distribute my PC's load or computational abilities need to be sought after and implemented."

**Why:** The serial pytest battery (~10 min) is the recurring wall in every change cycle, and the box (AMD Ryzen 5 5600X, 6 cores/12 threads, 16GB, RTX 3070 Ti) sat mostly idle during it. The operator wants proactive discovery of such wins, not just on request.

**How to apply:** When a recurring local workload is serial and parallelizable, propose AND implement the parallel version with an evidence gate (green + zero flakes vs a serial control) before adopting. Known landscape as of 2026-08-07: pytest-xdist installed, `-n 8` is the sweet spot (leave headroom for the live runner — it has a 300s stall bound; verified healthy under load). GPU is NOT useful for this repo's workloads (328-row logistic, 9.7k-row corpus — transfer overhead exceeds compute; told operator honestly). Other candidates: `compileall -j`, keeping BLAS multithreaded, per-file ruff already fast. Do not parallelize the live trading loop itself.

**2026-10-04 correction — `-n 8` is HALF the invocation.** `@pytest.mark.timing` tests (wall-clock-sensitive; registered in pyproject.toml) must be excluded from the parallel pass and run serially after it, exactly as `test_windows.bat` does: `pytest tests -q -n 8 -m "not timing"` then `pytest tests -q -m timing`. A plain `-n 8` run produced a false red (test_pbo_variants subprocess timeout under 8-worker load; passes alone). Also: do not hand pytest a long `--basetemp` (a 130-char one broke git fixtures past MAX_PATH; tests/conftest.py now sets core.longpaths for the session, but short is still better), and the default basetemp is safe again since conftest tolerates the elevated runs' undeletable dead `pytest-current` link (it prints one line naming it).
