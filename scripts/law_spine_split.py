"""Split CLAUDE.md/AGENTS.md into a session spine + docs/law/ detail files.

Relocation is verbatim: every original section either stays in the spine
unchanged or is copied byte-for-byte into a docs/law/ file. The only new
text is compact summaries and read-trigger pointers. Verification at the
end proves the no-loss claim mechanically.
"""
import re
import subprocess
from pathlib import Path

WT = Path(r"C:\Users\haird\Documents\liquiditybot\liquiditybot_ab\.claude\worktrees\decisioning-r123")
orig_claude = subprocess.run(
    ["git", "-C", str(WT), "show", "main:CLAUDE.md"],
    capture_output=True, text=True, check=True).stdout.replace("\r\n", "\n")
orig_agents = subprocess.run(
    ["git", "-C", str(WT), "show", "main:AGENTS.md"],
    capture_output=True, text=True, check=True).stdout.replace("\r\n", "\n")

# bodies must be identical between the two files (headers and the RTK
# tail differ)
c_head_end = orig_claude.index("## Hard invariants")
a_head_end = orig_agents.index("## Hard invariants")
claude_head = orig_claude[:c_head_end]
agents_head = orig_agents[:a_head_end]
rtk_marker = "<!-- rtk-instructions v2 -->"
a_rtk_start = orig_agents.index(rtk_marker)
rtk_tail = orig_agents[a_rtk_start:]
body = orig_claude[c_head_end:]
assert orig_agents[a_head_end:a_rtk_start].strip() == body.strip(), \
    "shared bodies diverged!"

# split body into sections
parts = re.split(r"(?m)^(?=## )", body)
sections = {}
order = []
for p in parts:
    if not p.strip():
        continue
    title = p.splitlines()[0]
    sections[title] = p
    order.append(title)

MOVE = {
    "## Architecture (do not re-tangle what is separated)":
        "architecture.md",
    "## Overfit discipline":
        "overfit_discipline.md",
    "## Accrual moratorium":
        "era9_moratorium.md",
    "## Definition of done":
        "definition_of_done.md",
    "## THE MINDSET":
        "mindset.md",
}

# resolve prefix keys to exact section titles
resolved = {}
for prefix, fname in MOVE.items():
    hits = [t for t in order if t.startswith(prefix)]
    assert len(hits) == 1, f"{prefix}: {hits}"
    resolved[hits[0]] = fname
MOVE = resolved

law_dir = WT / "docs" / "law"
law_dir.mkdir(parents=True, exist_ok=True)
for title, fname in MOVE.items():
    (law_dir / fname).write_text(sections[title], encoding="utf-8", newline="\n")

# Definition of done: keep the command matrix in the spine, move the essays
dod = sections["## Definition of done (every change, every session)"]
cut = dod.index("*(`./outputs` was added to bandit's exclusion")
dod_matrix = dod[:cut].rstrip() + "\n"
(law_dir / "definition_of_done.md").write_text(dod[cut:], encoding="utf-8", newline="\n")

POINTERS = {
    "## Architecture":
"""## Architecture — `docs/law/architecture.md`

Module boundaries, the runner loop, state files, logging, serializability:
read `docs/law/architecture.md` BEFORE touching module boundaries, the
runner lifecycle loop, or state-file schemas. Do not re-tangle what is
separated.

""",
    "## Overfit discipline":
"""## Overfit discipline — `docs/law/overfit_discipline.md`

No fitted-looking literals in decision paths; thresholds live in
`config.json` behind `core/config_guard.py`; model/gate changes must keep
the overfit battery and quant-trial gates green. Read
`docs/law/overfit_discipline.md` BEFORE touching any tunable, model, or
gate.

""",
    "## Accrual moratorium":
"""## Accrual moratorium — era-9 (summary; full text `docs/law/era9_moratorium.md`)

Era-9 accrues from the cut #12 runner restart (2026-09-08) under operator
approval. **READ `docs/law/era9_moratorium.md` BEFORE any change that could
place, size, or exit an order** — the full text carries the cut record, the
price of a mint, and the four mechanisms the law does not name. The binding
core:

- **COHORT-RESETTING — forbidden without operator adjudication** (any of
  these mints the next boundary and restarts accrual): entry decisioning,
  position sizing, stop/exit geometry (placement, nudges, time limits),
  the fill simulator, fee booking, the order lifecycle, the universe, the
  hedger, the probe ticket, or the heat cap. Exactly two exemptions: a
  **SAFETY INVARIANT** (hard invariants 1–7 above) and a **WRONG VENUE
  CONSTANT** making the bot trade on a false cost. Nothing else.
- An era runs a **MINIMUM OF 14 DAYS** before a discretionary boundary may
  be called; a mint must be justified in writing, in its decision record,
  against the price enumerated in the full text.
- **SAFE class** (no adjudication needed): measurement/report tools,
  dashboards, tests, wiki, telemetry export, and bug fixes that do not
  alter which orders are placed or how they fill.
- Read points are REGISTERED: **n=50 = the lean** (sign + CI), **n=100 =
  the verdict**. The registration is the law; readouts never decide.
- Model-side investment is FROZEN (2026-08-10 operator adjudication); the
  retrain loop itself continues by design. Do not retune on accruing
  gate numbers.

""",
    "## Definition of done":
"""## Definition of done — `docs/law/definition_of_done.md`

""" + dod_matrix + """
Gate-degradation caveats (synthetic corpus substitution, dark overfit
rungs, effective-n deflation, the never-lower-a-floor rule): read
`docs/law/definition_of_done.md` BEFORE declaring any gate green — a green
is only as big as its corpus.

""",
    "## THE MINDSET":
"""## THE MINDSET — `docs/law/mindset.md`

The instrument is the first suspect: a surprising number gets its
instrument verified before it gets a theory, and one number from one tool
is a hypothesis. The seven measured recurrences, the binding operating
consequences, and the durable coordination rules: `docs/law/mindset.md` —
read before trusting any measurement, referees included.

""",
}

resolved_p = {}
for prefix, block in POINTERS.items():
    hits = [t for t in order if t.startswith(prefix)]
    assert len(hits) == 1, f"POINTER {prefix}: {hits}"
    resolved_p[hits[0]] = block

new_body = ""
for title in order:
    new_body += resolved_p.get(title, sections[title])

new_claude = claude_head + new_body
new_agents = agents_head + new_body + "\n" + rtk_tail

# --- verification: no original text lost -------------------------------
ok = True
for title, fname in MOVE.items():
    moved = (law_dir / fname).read_text(encoding="utf-8")
    if fname == "definition_of_done.md":
        # original section = spine matrix + moved essays (both verbatim)
        if sections[title] != dod_matrix + moved:
            print(f"FAIL: {fname} does not reconstruct the original section")
            ok = False
        else:
            print(f"OK  {fname}: original section = spine matrix + file, verbatim")
    else:
        if sections[title] != moved:
            print(f"FAIL: {fname} is not a verbatim copy of {title}")
            ok = False
        else:
            print(f"OK  {fname}: verbatim copy of original section")
kept = [t for t in order if t not in MOVE]
for t in kept:
    print(f"OK  spine keeps verbatim: {t}")
print(f"\nspine: {len(new_body.splitlines())} lines (was {len(body.splitlines())})")

if ok:
    (WT / "CLAUDE.md").write_text(new_claude, encoding="utf-8", newline="\n")
    (WT / "AGENTS.md").write_text(new_agents, encoding="utf-8", newline="\n")
    print("VERIFIED LOSSLESS — wrote CLAUDE.md, AGENTS.md, docs/law/*.md")
else:
    raise SystemExit("verification failed; nothing written")
