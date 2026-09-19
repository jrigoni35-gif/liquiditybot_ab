"""handoff_packet.py — token-frugal context packer for agent task starts.

SAFE-class developer tool (measurement/report only): it assembles TEXT for
an agent to read and never touches decisioning, config, or runtime state.
Everything it emits is DERIVED from the tree at run time, never remembered.

The packet it builds replaces the expensive default opening move (read the
law files whole, read every candidate module whole) with three derived
sections:

  1. GIT CONTEXT   — the working diff as hunks vs a base ref, not whole
                     files; status one-liner.
  2. MODULE INDEX  — an AST signature index (class/def names + first
                     docstring line) of the modules the task touches:
                     ~5% of the source's tokens, zero behavior detail.
  3. LAW EXCERPTS  — only the docs/law/ paragraphs whose keywords overlap
                     the task words; the spine itself is auto-loaded by the
                     CLI and is pointed at, never duplicated.

Usage:
    python scripts/handoff_packet.py "fix fee reconciliation drift" [--since main]

Exit code 0 always (a best-effort packet beats no packet); errors land in
the packet's own WARNINGS section, matching the reading discipline: say
what the instrument could not measure.
"""
import argparse
import ast
import subprocess
import sys
import time
from pathlib import Path

STOPWORDS = {
    "the", "this", "that", "with", "from", "into", "and", "for", "fix",
    "when", "then", "than", "them", "they", "their", "there", "where",
    "what", "which", "while", "every", "should", "would", "could",
    "task", "change", "review", "check", "make", "add", "use", "via",
}


def _words(text: str) -> list[str]:
    return [w.strip(".,;:()[]{}\"'`").lower()
            for w in text.split()
            if len(w.strip(".,;:()[]{}\"'`")) >= 3]


def _keywords(text: str) -> list[str]:
    return [w for w in _words(text) if w not in STOPWORDS]


def _doc_first_line(node) -> str:
    d = ast.get_docstring(node)
    if not d:
        return ""
    return d.splitlines()[0].strip()


def _stem_match(k: str, sw: str) -> bool:
    """Word-boundary-ish stem match: exact always; substring only at
    length >= 4, so 'fee' does not ride on 'feed'."""
    return k == sw or (len(k) >= 4 and k in sw) \
        or (len(sw) >= 4 and sw in k)


def signature_index(path: Path) -> str:
    """AST signature index: names + one-line docstrings, no bodies."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError) as exc:
        return f"  [unparseable: {exc}]"
    lines = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            lines.append(f"class {node.name} — {_doc_first_line(node)}")
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sig = ast.unparse(sub.args)
                    lines.append(f"  def {sub.name}({sig}) — "
                                 f"{_doc_first_line(sub)}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = ast.unparse(node.args)
            lines.append(f"def {node.name}({sig}) — {_doc_first_line(node)}")
    return "\n".join(lines) or "  [no top-level definitions]"


def law_excerpts(task: str, law_dir: Path, cap: int = 6,
                 para_cap: int = 300) -> list[str]:
    """docs/law/ paragraphs whose keywords overlap the task words."""
    keys = _keywords(task)
    if not keys or not law_dir.is_dir():
        return []
    hits = []
    for md in sorted(law_dir.glob("*.md")):
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for para in text.split("\n\n"):
            flat = " ".join(para.split())
            low = flat.lower()
            if any(k in low for k in keys):
                hits.append(f"[{md.name}] {flat[:para_cap]}")
                if len(hits) >= cap:
                    return hits
    return hits


def diff_hunks(root: Path, since: str | None, line_cap: int = 400) -> str:
    """Working tree vs `since`, hunk format; capped."""
    if not since:
        return ""
    try:
        out = subprocess.run(
            ["git", "diff", since, "--", "*.py", "*.md", "*.json"],
            cwd=root, capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            return f"[git diff {since} failed: {out.stderr.strip()[:200]}]"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"[git diff {since} failed: {exc}]"
    lines = out.stdout.splitlines()
    truncated = len(lines) > line_cap
    body = "\n".join(lines[:line_cap])
    if truncated:
        body += f"\n[... truncated at {line_cap} lines: " \
                f"run `git diff {since}` for the rest]"
    return body or "[clean: no working-tree diff]"


def _module_candidates(task: str, root: Path, diff: str) -> list[Path]:
    """Score .py modules by task-keyword overlap (filename + module
    docstring), plus modules named in the diff. Top 3 win."""
    keys = _keywords(task)
    scored: dict[Path, int] = {}
    skip = {".venv", ".git", "__pycache__", ".claude", "worktrees", "outputs"}
    for p in root.rglob("*.py"):
        try:
            rel_parts = p.relative_to(root).parts
        except ValueError:
            continue
        if skip & set(rel_parts):
            continue
        if "tests" in rel_parts:
            continue                       # production modules win; tests
                                           # enter only via the diff below
        stem_words = set(_words(p.stem.replace("_", " ")))
        score = sum(1 for k in keys
                    if any(_stem_match(k, sw) for sw in stem_words)) * 3
        try:
            text = p.read_text(encoding="utf-8", errors="replace").lower()
            score += sum(1 for k in keys if k in text)
        except OSError:
            continue
        if score:
            scored[p] = score
    for line in diff.splitlines():
        if line.startswith("+++ b/") and line.endswith(".py"):
            p = root / line[6:].strip()
            if p.exists():
                scored[p] = scored.get(p, 0) + 5
    if not scored:                         # fallback: task words may name a
        for p in root.rglob("*.py"):       # test surface directly
            try:
                rel_parts = p.relative_to(root).parts
            except ValueError:
                continue
            if (skip & set(rel_parts)) or "tests" not in rel_parts:
                continue
            stem_words = set(_words(p.stem.replace("_", " ")))
            score = sum(1 for k in keys
                        if any(_stem_match(k, sw) for sw in stem_words))
            if score:
                scored[p] = score
    ranked = sorted(scored, key=lambda p: -scored[p])
    return ranked[:3]


def build_packet(task: str, root: Path, since: str | None = "main") -> str:
    root = Path(root)
    warnings = []
    diff = diff_hunks(root, since)
    modules = _module_candidates(task, root, diff)
    law = law_excerpts(task, root / "docs" / "law")

    branch = ""
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"], cwd=root,
            capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        warnings.append("git branch unavailable")

    out = [f"HANDOFF PACKET — generated {time.strftime('%Y-%m-%d %H:%M:%S')}",
           f"repo: {root}  branch: {branch or '(detached)'}",
           f"task: {task}",
           "",
           "== 1. GIT CONTEXT (hunks, not files)"
           f"   base: {since or 'n/a'}",
           diff or "[skipped]",
           "",
           "== 2. MODULE INDEX (signatures only — read source on demand)"]
    if not modules:
        out.append("[no module routed: name one explicitly]")
    for m in modules:
        rel = m.relative_to(root).as_posix()
        out.append(f"--- {rel} ({m.stat().st_size} B source; "
                   f"index below ≈ tokens) ---")
        out.append(signature_index(m))
    out += ["", "== 3. LAW EXCERPTS (docs/law/ paragraphs matching the task)"]
    if law:
        out.extend(law)
    else:
        out.append("[no law paragraph matched — read docs/law/ index if "
                   "the task touches behavior]")
    out += ["", "spine: CLAUDE.md / AGENTS.md auto-load — already in context.",
            "Do NOT paste whole modules back; quote only the hunk you edit."]
    if warnings:
        out += ["", "WARNINGS:", *[f"- {w}" for w in warnings]]
    packet = "\n".join(out)
    return packet


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("task", help="one-line task description (routing keys)")
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument("--since", default="main",
                    help="diff base ref (default: main; 'none' to skip)")
    args = ap.parse_args(argv)
    since = None if args.since.lower() in ("none", "", "null") else args.since
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    packet = build_packet(args.task, Path(args.root).resolve(), since)
    print(packet)
    print(f"\n[packet: ~{len(packet) // 4} tokens]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
