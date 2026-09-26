# core/cohort.py
"""Decision-fingerprint cohorts - what "cohort-resetting" means since 2026-09-26.

THE OLD DEFINITION. A cohort was `core.fill_ledger.EXEC_ERA`, one string
minted by hand. Any change on an enumerated list (entry decisioning, sizing,
exits, fills, fees, universe, hedger, probe ticket, heat cap) required a mint,
and a mint reset accrual for EVERYTHING: the moratorium measured ~78% of
banked trips leaving the gate per mint, 1 of 6 closed eras ever reaching the
n=50 lean and none the n=100 verdict (docs/law/era9_moratorium.md).

THE NEW DEFINITION (operator ruling 2026-09-26). A cohort is the set of trips
whose ENTRY leg carries the same decision fingerprint, computed at boot by the
machine from exactly what decides trades:

  cfg_fp   sha256 over config.json minus the NON-DECISION sections/keys.
           FAIL-CLOSED: every key counts unless named below or it is a
           `_doc`/`description` string, so a new feature's key forks the
           cohort until someone argues it out of the fingerprint.
  code_fp  sha256 over ast.dump() of every DECISION_MODULES file with
           docstrings stripped: comments/formatting never fork, any
           semantic edit does (telemetry edits in main.py included - declare
           those equivalent rather than narrowing the module list).

A change no longer RESETS anything; it FORKS a new cohort. Banked trips keep
their fingerprint and finish their own read, and nobody has to remember to
mint because the stamp is derived. Behaviour-equivalent forks are pooled by
an evidence-bearing entry in docs/law/cohort_equivalence.json.

EXEC_ERA stays as a human epoch label for readers that predate this module.
It gates nothing any more. Pure module: no I/O at import, never raises into
boot (a failure yields fp "unknown", which is itself a distinct cohort).
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Sections that cannot change which orders are placed or how they fill.
# Credentials and webhooks live in some of these: they are removed BEFORE
# hashing, so no secret ever contributes to a logged digest.
NON_DECISION_SECTIONS = frozenset({
    "alerts", "api_server", "assurance", "exchanges", "markout",
})
NON_DECISION_SYSTEM_KEYS = frozenset({
    "log_level", "timezone", "state_path", "deploy_branch",
    "snapshot_interval_sec", "lock_progress_max_stall_sec",
})
# Decision-path source; directories are walked for *.py in sorted order.
# A module that can change an order and is missing here is a hole: add it.
DECISION_MODULES = (
    "main.py", "runner.py", "core/state.py", "core/venue_fees.py",
    "execution", "risk", "regime", "strategies", "ml",
)
UNKNOWN = "unknown"


def _strip_docs(node):
    if isinstance(node, dict):
        return {k: _strip_docs(v) for k, v in sorted(node.items())
                if not (isinstance(k, str)
                        and (k.startswith("_") or k == "description"))}
    if isinstance(node, list):
        return [_strip_docs(v) for v in node]
    return node


def decision_config(config: dict) -> dict:
    """The decision-relevant subtree of a config dict (pure)."""
    out = {}
    for sec, val in (config or {}).items():
        if sec in NON_DECISION_SECTIONS:
            continue
        if sec == "system" and isinstance(val, dict):
            val = {k: v for k, v in val.items()
                   if k not in NON_DECISION_SYSTEM_KEYS}
        out[sec] = val
    return _strip_docs(out)


def config_fingerprint(config: dict) -> str:
    blob = json.dumps(decision_config(config), sort_keys=True,
                      separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


class _DocStripper(ast.NodeTransformer):
    def _strip(self, node):
        body = getattr(node, "body", None)
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(getattr(body[0], "value", None), ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
        self.generic_visit(node)
        return node

    visit_Module = _strip
    visit_ClassDef = _strip
    visit_FunctionDef = _strip
    visit_AsyncFunctionDef = _strip


def _module_files(root: Path) -> list:
    files = []
    for rel in DECISION_MODULES:
        p = root / rel
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(f for f in sorted(p.rglob("*.py"))
                         if "__pycache__" not in f.parts)
    return files


def code_fingerprint(root: Path = ROOT) -> str:
    """AST digest of the decision path. An unparseable file hashes its raw
    bytes (it still forks; it never raises)."""
    h = hashlib.sha256()
    for f in _module_files(root):
        h.update(f.relative_to(root).as_posix().encode("utf-8") + b"\0")
        raw = f.read_bytes()
        try:
            tree = _DocStripper().visit(ast.parse(raw))
            h.update(ast.dump(tree, include_attributes=False).encode("utf-8"))
        except (SyntaxError, ValueError):
            h.update(raw)
        h.update(b"\1")
    return h.hexdigest()[:12]


def decision_fingerprint(config: dict, root: Path = ROOT) -> dict:
    """{'fp','cfg_fp','code_fp'}; fp is the cohort key stamped on fills.
    Never raises: any failure returns fp='unknown' (its own cohort)."""
    try:
        cfg_fp, code_fp = config_fingerprint(config), code_fingerprint(root)
    except Exception:  # noqa: BLE001 - boot must never die on a stamp
        return {"fp": UNKNOWN, "cfg_fp": UNKNOWN, "code_fp": UNKNOWN}
    return {"fp": f"{cfg_fp[:6]}{code_fp[:6]}", "cfg_fp": cfg_fp,
            "code_fp": code_fp}


# ------------------------------------------------------------ equivalence
EQUIVALENCE_PATH = ROOT / "docs" / "law" / "cohort_equivalence.json"


def load_equivalence(path: Path = EQUIVALENCE_PATH) -> dict:
    """{fp: same_as_fp}. Entries without non-empty `evidence` are ignored:
    pooling is a claim, and an unevidenced claim is what the old law could
    not see."""
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    out = {}
    for r in rows if isinstance(rows, list) else []:
        if (isinstance(r, dict) and r.get("fp") and r.get("same_as")
                and str(r.get("evidence", "")).strip()):
            out[str(r["fp"])] = str(r["same_as"])
    return out


def canonical(fp: str, equiv: dict) -> str:
    """Follow equivalence links to the root fingerprint (cycle-safe)."""
    seen = set()
    while fp in equiv and fp not in seen:
        seen.add(fp)
        fp = equiv[fp]
    return fp
