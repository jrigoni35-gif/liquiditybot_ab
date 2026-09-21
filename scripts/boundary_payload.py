# scripts/boundary_payload.py
"""Boundary evidence payload — one JSON file for the 09-22 sitting (Lane C).

Collects every SAFE-plane instrument's verdict into a single payload the
operator can carry into the era-9 boundary adjudication:

    era_readout          (subprocess `era_readout.py --json` — its own
                          documented machine interface)
    gradeability_census  (imported census(); no doc write)
    reject_bounds        (imported bounds_run())
    gate_ecology         (imported ecology())
    quant_db             (imported second-engine crosscheck)

DISCIPLINE: every section is recorded with an explicit status
(ok / refused / error) — an instrument that fails lands IN the payload as
a marked hole, never silently dropped (the refuse-on-inconsistency rule
applied to evidence assembly). Exit 0 only when every section is ok;
exit 2 with a banner otherwise. Read-only: writes exactly one file
(--out, default outputs/boundary_payload.json).
"""
from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404 - runs this repo's own script via sys.executable
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ERA_READOUT_TIMEOUT_S = 1800


def _iso(ts: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def _section(fn):
    """Run one instrument; return {"status", ...} — never raises."""
    try:
        out = fn()
    except Exception as exc:  # noqa: BLE001 - the payload must record, not crash
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
    if isinstance(out, dict) and out.get("refused"):
        return {"status": "refused", "code": out["refused"],
                "detail": out.get("detail")}
    return {"status": "ok", "data": out}


def run_era_readout(repo_root: Path,
                    timeout: int = ERA_READOUT_TIMEOUT_S) -> dict:
    """era_readout via its documented `--json` interface (subprocess)."""
    proc = subprocess.run(  # nosec B603 - fixed argv, own script, sys.executable
        [sys.executable, str(repo_root / "scripts" / "era_readout.py"),
         "--json"],
        capture_output=True, text=True, cwd=str(repo_root),
        timeout=timeout, check=False)
    if proc.returncode != 0:
        return {"refused": "ERA_READOUT_EXIT",
                "detail": (proc.stderr or proc.stdout)[-500:]}
    return json.loads(proc.stdout)


def _meta() -> dict:
    from core.fill_ledger import EXEC_ERA  # noqa: PLC0415 - lazy, scripts-only
    head = subprocess.run(  # nosec B603 B607 - fixed argv; git resolved from PATH exactly as the operator's own shell does
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
        cwd=str(ROOT), check=False).stdout.strip()
    return {"generated_at": _iso(time.time()), "git_head": head,
            "exec_era": EXEC_ERA}


def collect(*, meta_fn, era_fn, census_fn, bounds_fn, ecology_fn,
            quantdb_fn) -> dict:
    """Assemble the payload. Every dependency is injectable (tests)."""
    sections = {
        "gradeability_census": _section(census_fn),
        "reject_bounds": _section(bounds_fn),
        "gate_ecology": _section(ecology_fn),
        "quant_db": _section(quantdb_fn),
        "era_readout": _section(era_fn),  # slowest (bootstrap): last
    }
    complete = all(s["status"] == "ok" for s in sections.values())
    return {"meta": meta_fn(), "complete": complete, "sections": sections}


def _real_collect(repo_root: Path, since: float | None) -> dict:
    from scripts.gate_ecology import (  # noqa: PLC0415 - lazy imports keep
        CUT12_FLOOR, ecology,  #         # `--help` and tests fast
    )
    from scripts.gradeability_census import census  # noqa: PLC0415
    from scripts.reject_inference_bounds import bounds_run  # noqa: PLC0415

    if since is None:
        since = CUT12_FLOOR  # each instrument's own default is this floor

    def _quantdb() -> dict:
        from scripts.quant_db import (  # noqa: PLC0415
            QuantDbRefusal, connect, crosscheck, register_views,
        )
        try:
            con = connect()
            inv = register_views(con)
            return {"views": inv, "crosscheck": crosscheck(con)}
        except QuantDbRefusal as ref:
            return {"refused": ref.code, "detail": str(ref)}

    kw = {"audit_path": "outputs/audit.jsonl",
          "fills_path": "outputs/fills.csv",
          "corpus_dir": "research/corpus/binance_vision",
          "config_path": "config.json", "since": since}
    return collect(
        meta_fn=_meta,
        era_fn=lambda: run_era_readout(repo_root),
        census_fn=lambda: census(
            audit_path=kw["audit_path"], fills_path=kw["fills_path"],
            since=since, doc_path=None),
        bounds_fn=lambda: bounds_run(**kw),
        ecology_fn=lambda: ecology(**kw),
        quantdb_fn=_quantdb)


def _banner(line: str) -> None:
    print("=" * 70)
    print(line)
    print("=" * 70)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "outputs"
                                         / "boundary_payload.json"))
    ap.add_argument("--since", default=None,
                    help="epoch seconds or ISO 8601 (default: each "
                         "instrument's own era floor)")
    ns = ap.parse_args(argv)
    since = None
    if ns.since is not None:
        try:
            since = float(ns.since)
        except ValueError:
            since = time.mktime(  # noqa: DTZ001 - epoch-only conversion
                time.strptime(ns.since, "%Y-%m-%dT%H:%M:%SZ"))
    payload = _real_collect(ROOT, since)
    out_path = Path(ns.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=1, sort_keys=True,
                                   default=str) + "\n", encoding="utf-8")
    print(f"boundary payload -> {out_path}")
    print(f"generated {payload['meta']['generated_at']} "
          f"git={payload['meta']['git_head'][:9]} "
          f"era={payload['meta']['exec_era']}")
    for name, sec in payload["sections"].items():
        line = f"  {name}: {sec['status']}"
        if sec["status"] == "refused":
            line += f" ({sec['code']})"
        elif sec["status"] == "error":
            line += f" ({sec['error'][:80]})"
        print(line)
    if not payload["complete"]:
        _banner("BOUNDARY PAYLOAD INCOMPLETE — sections above are marked; "
                "rule on the holes, do not read around them")
        return 2
    print("payload COMPLETE — all sections ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
