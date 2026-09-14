"""scripts/local_review_eval.py - A/B two local models on security review.

WHY THIS EXISTS
---------------
`scripts/local_security_review.py` runs a local model over a diff. Choosing
WHICH model is otherwise an argument about published benchmarks, and published
coding benchmarks measure code GENERATION, which is a weak proxy for
vulnerability DETECTION. This measures the thing we actually care about, on
this machine, with this prompt.

THE METRIC THAT MAKES OR BREAKS IT
----------------------------------
Detection rate alone is a broken score: a model that answers "CRITICAL |
everything" catches 100% of planted defects and is useless. So the corpus
carries NEGATIVE CONTROLS, and the sharpest of them are SAFE versions of the
vulnerable cases - a parameterised query, a list-form subprocess call,
`ast.literal_eval` instead of `eval`. A model that flags those is
pattern-matching on vocabulary, not reading the code.

Four numbers per model, and you need all four:
  RECALL     planted defects correctly named        (higher better)
  FALSE POS  findings raised on clean/safe diffs    (LOWER better)
  FORMAT     replies parseable without the retry    (higher better)
  LATENCY    median seconds per diff                (lower better)

A model wins on the PAIR (recall, false positives). Quoting one without the
other is the failure this file exists to prevent.

USAGE
    python scripts/local_review_eval.py --models qwen2.5:7b-instruct
    python scripts/local_review_eval.py --models a:tag,b:tag --json out.json

SAFE class: reads nothing from the repo, calls localhost, prints a table.
Runs models SEQUENTIALLY and pauses between cases, because a live trading bot
shares this machine and a starved heartbeat makes its supervisor relaunch it.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from local_security_review import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    review,
)


@dataclass
class Case:
    name: str
    diff: str
    # Words that must appear in SOME finding for a hit. Empty = clean control.
    needles: list[str] = field(default_factory=list)

    @property
    def is_control(self) -> bool:
        return not self.needles


# ---------------------------------------------------------------------------
# THE CORPUS.
#
# DELIBERATE VULNERABILITIES, INERT BY CONSTRUCTION. Everything below lives
# inside string literals that are only ever sent to a model as text. Nothing
# is executed, imported, or written to disk; the keys are invented constants
# that authenticate nothing. Pattern scanners will flag these lines - that is
# expected and is the cost of having a corpus with teeth.
# ---------------------------------------------------------------------------
def _d(path: str, body: str) -> str:
    return (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
            f"@@ -1,2 +1,9 @@\n" + "".join(f"+{ln}\n" for ln in body.strip().split("\n")))


POSITIVES = [
    Case("hardcoded-secret", _d("cfg.py",
         'AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"\n'
         'def client():\n    return connect(AWS_SECRET)'),
         ["secret", "hardcod", "credential", "key"]),
    Case("command-injection", _d("ops.py",
         'import subprocess\n'
         'def purge(name):\n'
         '    subprocess.run("rm -rf /var/data/" + name, shell=True)'),
         ["inject", "shell", "command"]),
    Case("eval-untrusted", _d("rules.py",
         'def apply(rule_text):\n    return eval(rule_text)'),
         ["eval", "arbitrary", "code execution"]),
    Case("sql-injection", _d("db.py",
         'def lookup(cur, uid):\n'
         '    cur.execute("SELECT * FROM users WHERE id = \'%s\'" % uid)'),
         ["sql", "inject"]),
    Case("unsafe-pickle", _d("net.py",
         'import pickle\n'
         'def handle(payload_from_socket):\n'
         '    return pickle.loads(payload_from_socket)'),
         ["pickle", "deserial", "arbitrary"]),
    Case("path-traversal", _d("files.py",
         'def read_report(name):\n'
         '    return open("/srv/reports/" + name).read()'),
         ["traversal", "path", "directory"]),
    Case("tls-disabled", _d("api.py",
         'import requests\n'
         'def fetch(u):\n    return requests.get(u, verify=False)'),
         ["tls", "ssl", "verif", "certificate"]),
    Case("credential-logged", _d("auth.py",
         'def login(user, password):\n'
         '    log.info("login attempt user=%s password=%s", user, password)'),
         ["log", "password", "credential"]),
    Case("swallowed-auth-error", _d("guard.py",
         'def check(tok):\n'
         '    try:\n        verify(tok)\n'
         '    except Exception:\n        pass\n'
         '    return True'),
         ["except", "swallow", "bypass", "always"]),
]

# The controls. The last three are the ones that separate reading from
# vocabulary-matching: they are the SAFE forms of cases above.
CONTROLS = [
    Case("docs-only", _d("README.md",
         '# Reporting\n\nThe daily report now includes the fee tier.')),
    Case("pure-rename", _d("calc.py",
         'def total(rows):\n'
         '    subtotal = sum(r.amount for r in rows)\n'
         '    return subtotal')),
    Case("SAFE-parameterised-sql", _d("db.py",
         'def lookup(cur, uid):\n'
         '    cur.execute("SELECT * FROM users WHERE id = ?", (uid,))')),
    Case("SAFE-subprocess-list", _d("ops.py",
         'import subprocess\n'
         'def purge(name):\n'
         '    subprocess.run(["rm", "-rf", "/var/data/" + name], check=True)')),
    Case("SAFE-literal-eval", _d("rules.py",
         'import ast\n'
         'def apply(rule_text):\n    return ast.literal_eval(rule_text)')),
]


def _hit(findings: list[str], needles: list[str]) -> bool:
    blob = " ".join(findings).lower()
    return any(n.lower() in blob for n in needles)


def run_model(model: str, base_url: str, cases: list[Case],
              pause: float, timeout: float) -> dict:
    hits = misses = fp = clean = fmt_ok = errors = 0
    lat: list[float] = []
    detail: list[dict] = []
    for c in cases:
        t0 = time.monotonic()
        try:
            # retries=0 first so FORMAT compliance is measured honestly, then
            # fall back to the shipped behaviour so a format slip is not
            # scored as a miss.
            try:
                found = review(c.diff, base_url, model, timeout=timeout,
                               retries=0)
                fmt_ok += 1
            except ValueError:
                found = review(c.diff, base_url, model, timeout=timeout,
                               retries=1)
        except Exception as exc:                       # noqa: BLE001
            # NOT in a finally: the time a FAILED call took is not a latency
            # sample. Averaging it in makes a model that errors out fast look
            # quick. Measured cost of getting this wrong: a median computed
            # over aborted calls.
            errors += 1
            detail.append({"case": c.name, "error": str(exc)[:120]})
            continue
        lat.append(time.monotonic() - t0)
        if c.is_control:
            clean += 1
            if found:
                fp += 1
            detail.append({"case": c.name, "control": True,
                           "flagged": len(found)})
        else:
            ok = _hit(found, c.needles)
            hits += 1 if ok else 0
            misses += 0 if ok else 1
            detail.append({"case": c.name, "control": False, "caught": ok,
                           "n": len(found)})
        time.sleep(pause)
    n_pos = hits + misses
    return {
        "model": model,
        "recall": f"{hits}/{n_pos}" if n_pos else "n/a",
        "recall_pct": round(100 * hits / n_pos, 1) if n_pos else None,
        "false_pos": f"{fp}/{clean}" if clean else "n/a",
        "false_pos_pct": round(100 * fp / clean, 1) if clean else None,
        "format_ok": f"{fmt_ok}/{len(cases)}",
        "median_sec": round(statistics.median(lat), 1) if lat else None,
        "errors": errors,
        "detail": detail,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--models", default=DEFAULT_MODEL,
                    help="comma-separated ollama tags to compare")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--timeout", type=float, default=240.0)
    ap.add_argument("--pause", type=float, default=1.0,
                    help="seconds between cases; protects the co-resident bot")
    ap.add_argument("--json", help="also write the full result here")
    a = ap.parse_args(argv)

    cases = POSITIVES + CONTROLS
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    print(f"corpus: {len(POSITIVES)} planted, {len(CONTROLS)} controls "
          f"(3 are SAFE look-alikes)")

    rows = []
    for m in models:
        print(f"\n--- {m} ---")
        r = run_model(m, a.base_url, cases, a.pause, a.timeout)
        rows.append(r)
        for d in r["detail"]:
            if "error" in d:
                print(f"  ERROR {d['case']}: {d['error']}")
            elif d["control"]:
                mark = "ok " if d["flagged"] == 0 else "FP "
                print(f"  {mark}{d['case']}: {d['flagged']} finding(s)")
            else:
                print(f"  {'hit' if d['caught'] else 'MISS'} {d['case']}")

    print(f"\n{'model':<34} {'recall':>9} {'falsepos':>9} "
          f"{'format':>8} {'med s':>7} {'err':>4}")
    for r in rows:
        print(f"{r['model']:<34} {r['recall']:>9} {r['false_pos']:>9} "
              f"{r['format_ok']:>8} {str(r['median_sec']):>7} {r['errors']:>4}")
    print("\nRead recall and false positives TOGETHER. A model that flags the "
          "SAFE look-alikes is matching vocabulary, not reading code.")

    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"\nwrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
