---
name: python-write-text-crlf
description: "On this Windows box, Python Path.write_text()/open('w') silently rewrites a whole LF file to CRLF — use write_bytes or newline=\"\\n\" when editing repo/vault files"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 98da1b68-b33b-4df3-9ddf-8822e1aceeef
  modified: 2026-10-04T21:43:44.866Z
---

Measured 2026-10-04: a read_text() -> replace -> write_text() edit converted every line ending of the file to CRLF (universal-newline read, then os.linesep on write). Hit `docs/HANDOFF.md` (1,568 lines) and three vault pages (owed-measurements, index, log — 6,349 lines) that ended up 100% CRLF. HANDOFF was LF in git; the vault pages' prior endings cannot be proven (no history), but sampled peers are LF. Git masked it in the repo (normalizes on commit, "CRLF will be replaced by LF" warning); the vault is not git, so nothing flagged it there. Restored by `b.replace(b"\r\n", b"\n")`; each file shrank by exactly its CRLF count.

**Why:** an unannounced whole-file change in someone else's file; mixed-EOL pages already exist in the vault (`concepts/false-green.md`), so the drift compounds.

**How to apply:** for scripted edits of repo or vault text use `p.write_text(t, encoding="utf-8", newline="\n")` or bytes I/O; prefer the Edit tool, which preserves endings. After any scripted edit, a CRLF warning from git is the tell — check `b.count(b"\r\n")` before and after. Related: [[wiki-is-the-source-of-truth]], [[workflow-spend-protocol]].
