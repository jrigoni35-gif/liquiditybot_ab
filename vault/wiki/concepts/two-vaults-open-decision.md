---
title: The Two-Vaults Open Decision (a decision filed only where its subject can read it is unreachable)
category: concept
status: SETTLED
summary: "A second liquiditybot vault exists at C:\\Users\\haird\\vaults\\liquiditybot, created 2026-08-13 by a session whose vault search missed the in-repo one. It was RETIRED as a write target 2026-08-14 with nothing deleted, and the retirement note plus the full merge-or-retire inventory live ONLY in that tree's own _RETIRED_READ_THIS_FIRST.md. Grep of CANONICAL for 'vaults' / 'RETIRED_READ_THIS_FIRST' / 'merge-or-retire' returned ZERO hits — so a reader working correctly from canonical (as every rule in this vault instructs) could not learn the duplicate exists, and the operator decision it is waiting on was invisible from the only tree anyone is supposed to read. This stub is the reachability fix. THE DECISION IS STILL OPEN and is the OPERATOR's: merge selected pages, or retire the tree wholesale. Never bulk-copy — a shared basename is not a shared page"
tags: [governance, vault, provenance, reachability, open-decision]
sources: 1
updated: 2026-08-31
---

# The Two-Vaults Open Decision

> [!NOTE] Reachability now wired (2026-08-31). The vault's entry-point schema files
> (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`) carry a **TWO VAULTS — READ FIRST**
> callout routing to this page, so a session reading the law first cannot miss the
> retired duplicate. Declared **SETTLED** — its facts (a duplicate exists, it is
> retired, the decision is open and operator-owned) are measured and re-derived
> 2026-08-31. The DECISION is still open.

**Boundary (domain rule 9):** entirely **host-side / vault-side**. No sim number,
no venue number, no P&L claim.

## The generalizable rule first

> **A decision recorded only in the artifact the decision is ABOUT is unreachable.**

The reader who needs it is, by construction, the reader who is *not* looking at
that artifact. This is [[concepts/no-orphan-claims]]'s reachability failure with
the polarity inverted: the claim is not unsourced, it is **perfectly sourced in a
place the correct reader will never open**. The vault's own rules make it worse —
every rule says *read canonical first*, so a reader following the rules is
guaranteed to miss it.

## The specimen

Two liquiditybot vaults exist. **This is the canonical one.**

```
CANONICAL  ->  C:\Users\haird\Documents\liquiditybot\vault        (this vault)
RETIRED    ->  C:\Users\haird\vaults\liquiditybot                 (write target retired 2026-08-14)
```

**Canonical is the one the CODE defers to** — comments in `core/fill_ledger.py`
point at this vault's [[synthesis/comparability-boundaries]] as the single
authoritative execution-boundary table.

**How the duplicate happened:** a session on **2026-08-13** ran a vault search that
missed the in-repo vault, concluded none existed, and filed its analyses into a new
tree. That was an **assistant error, not an operator decision**. The tree was
retired as a write target on **2026-08-14**; **nothing was deleted, moved or
edited**, and a signpost (`_RETIRED_READ_THIS_FIRST.md`) was placed at its root.

## The measurement that made this page necessary

Grep of **canonical** for the needles `vaults`, `RETIRED_READ_THIS_FIRST`, and
`merge-or-retire`: **zero hits** (read 2026-08-16). The entire record of the
duplicate's existence, its inventory, and the open decision sat inside the
duplicate.

**Inventory, re-derived 2026-08-31** (`os.walk` over both trees, `.md` only,
`.git` excluded — re-derive rather than quote, both trees change):

| quantity | value (as-of 2026-08-31) |
|---|---:|
| canonical `.md` total | **285** (232 of them under `wiki/`) |
| retired tree `.md` total | **117** (97 of them under `wiki/`) |
| retired wiki basenames **absent** from canonical | **84** |

> ⚠️ **Provenance, recorded per rule 16.** This table has been re-derived three
> times and every reading is **as-of**, never a frozen number: **244 / 115 / 88**
> when the retired tree's own note was written (2026-08-14); **249 / 117 / 89** at
> the catch-up that created this page (2026-08-16); **285 / 117 / 84** now
> (2026-08-31). Only the canonical side changed — it is the live one; the retired
> tree is untouched at 117. The absent count fell 89 → 84 because five retired-only
> basenames now have canonical counterparts, but **a shared basename is not a
> shared page**, so the merge review is still the operator's. Re-derive with the
> same `os.walk` before relying on any individual row.

> ⚠️ **Contradiction (2026-08-31, same-day second route, session liquiditybot-ab-f2).**
> An independent re-derivation (PowerShell `Get-ChildItem -Recurse *.md`, `.git`
> excluded, read ~20:55 local) **confirms every total** — canonical 285 (232 wiki),
> retired 117 (97 wiki) — but **cannot reproduce absent = 84 under any of five
> definitions tried**: retired-wiki basenames vs canonical whole-tree gives **78**
> (case-insensitive) / **82** (case-sensitive); vs canonical wiki-only gives **82**
> under both casings and with/without dedup. The absent count is
> **definition-sensitive (spread 78–82)** and the `os.walk` that produced 84 was not
> filed, so "re-derive with the same os.walk" is not currently executable. Treat the
> row as **~80 ± definition** until the producing script is filed. Also noted: the
> `[[sources/session-20260831-vault-reachability-fix]]` page cited below **does not
> exist yet** — the entry-point wiring is disk-verified (all three callouts present),
> but the source page, `index.md` row, and `log.md` entry were not filed by that
> session; the log entry for this verification is appended 2026-08-31.

## What is owed, and to whom

**An OPERATOR decision, still open:** *merge selected pages into canonical, or
retire the tree wholesale.* No assistant may take it.

**Three prohibitions, carried over verbatim from the retired tree's signpost:**

1. **Do not file new liquiditybot knowledge there.** Canonical only.
2. **Do NOT bulk-copy the tree into canonical.** *A shared basename is not a
   shared page.* A blind merge would overwrite canonical pages with **stale
   variants**, import claims that **contradict canonical's registers**, and break
   the wikilink graph (canonical lints at **0 broken links**).
3. **Do not delete the tree** on the strength of any note. It holds real work; the
   merge decision is the operator's.

## Related

- [[concepts/no-orphan-claims]] — rule 18; this is its reachability clause with the
  polarity inverted
- [[concepts/session-identity-is-not-stable]] — rule 19; the originating error was a
  session acting on its own search result without re-deriving against disk
- [[synthesis/comparability-boundaries]] — the page the CODE cites, and the reason
  canonical is canonical
- [[synthesis/documentation-drift-register]] — where an as-of number read as current
  belongs
- [[sources/session-20260816-catchup-08-12-to-08-16]] — the catch-up that measured the
  zero-hit reachability gap
- [[sources/session-20260831-vault-reachability-fix]] — this session; wired the
  entry-point routing, re-derived the inventory, declared the page SETTLED
- Retired tree signpost: `C:\Users\haird\vaults\liquiditybot\_RETIRED_READ_THIS_FIRST.md`
  (read-only; its inventory is as-of 2026-08-14 — re-derive, don't quote)
