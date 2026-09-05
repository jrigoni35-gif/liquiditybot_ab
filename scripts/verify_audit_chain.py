"""scripts/verify_audit_chain.py — SECOND ROUTE over the audit trail.

`core/audit.py` ships its own `verify_chain`. This is not a replacement
for it and must never import it: the point is that a hash chain checked
only by the module that writes it is one instrument reporting on itself,
and this repo's standing rule is that one number from one tool is a
hypothesis until a second, independently written route agrees.

So the scheme below is reimplemented from the SPEC, not shared:

    body = json.dumps({seq,ts,src,code,msg,data,prev},
                      sort_keys=True, default=str)
    h    = sha256(body).hexdigest()[:16]

Classification — the two alarm classes are kept strictly apart from the
benign one, because conflating them is how a real deletion gets filed as
"just a concurrent writer":

  INTEGRITY  a record's content does not match its own stored hash.
             Someone edited a committed record. ALARM.
  DANGLING   a record's `prev` resolves to no hash anywhere in the file.
             A committed record was DELETED — or a forged record was
             written with a recomputed hash, which orphans its successor
             exactly the same way. ALARM.
  SEAM       `prev` resolves to an EARLIER verified hash (or genesis).
             Two writers overlapped and one resumed from a stale tip.
             No committed record was altered: benign for integrity.

A seam is benign for INTEGRITY and not benign for UNIQUENESS — a forked
writer re-issues sequence numbers, so `seq` stops being a primary key.
Duplicate and divergent seqs are counted separately for that reason; a
reader that dedupes on `seq` silently drops records.

    python scripts/verify_audit_chain.py outputs/audit.jsonl
    python scripts/verify_audit_chain.py <path> --events

Exit status: 0 when no ALARM class fired (seams alone do not fail),
1 on any integrity failure or dangling prev, 2 on an unreadable file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field

GENESIS = "0000000000000000"
_CHAIN_FIELDS = ("h",)


def canonical_body(record: dict) -> str:
    """The exact string the writer hashed: the record minus its own `h`."""
    return json.dumps(
        {k: v for k, v in record.items() if k not in _CHAIN_FIELDS},
        sort_keys=True,
        default=str,
    )


def record_hash(record: dict) -> str:
    return hashlib.sha256(canonical_body(record).encode("utf-8")).hexdigest()[:16]


@dataclass
class ChainReport:
    records: int = 0
    malformed: int = 0
    integrity: list = field(default_factory=list)   # (lineno, seq, stored, calc)
    dangling: list = field(default_factory=list)    # (lineno, seq, prev)
    seams: list = field(default_factory=list)       # (lineno, seq, prev, prev_seq)
    duplicate_seqs: int = 0
    divergent_seqs: int = 0
    surplus_records: int = 0
    missing_seqs: int = 0
    double_writes: int = 0

    @property
    def tampered(self) -> bool:
        """True iff an ALARM class fired. Seams alone are NOT tampering."""
        return bool(self.integrity or self.dangling)


def verify_chain(path, check_events: bool = False) -> ChainReport:
    rep = ChainReport()
    seen: dict[str, int] = {GENESIS: 0}
    by_seq: dict = defaultdict(list)
    prev_h = GENESIS
    tight: Counter = Counter()

    with open(path, encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                rec = json.loads(raw)
            except ValueError:
                rep.malformed += 1
                continue
            rep.records += 1
            stored = rec.get("h")
            calc = record_hash(rec)
            seq = rec.get("seq")
            by_seq[seq].append(rec)
            if check_events:
                tight[json.dumps(
                    {k: v for k, v in rec.items() if k not in ("seq", "prev", "h")},
                    sort_keys=True, default=str)] += 1

            if calc != stored:
                rep.integrity.append((lineno, seq, stored, calc))
                if isinstance(stored, str):
                    seen.setdefault(stored, seq)
                    prev_h = stored
                continue

            rp = rec.get("prev")
            if rp != prev_h:
                if rp in seen:
                    rep.seams.append((lineno, seq, rp, seen[rp]))
                else:
                    rep.dangling.append((lineno, seq, rp))
            seen.setdefault(calc, seq)
            prev_h = calc

    dup = {s: rs for s, rs in by_seq.items() if len(rs) > 1}
    rep.duplicate_seqs = len(dup)
    rep.divergent_seqs = sum(
        1 for rs in dup.values()
        if len({(x.get("code"), x.get("h")) for x in rs}) > 1
    )
    rep.surplus_records = sum(len(rs) - 1 for rs in dup.values())
    numeric = [s for s in by_seq if isinstance(s, int)]
    if numeric:
        rep.missing_seqs = len(set(range(1, max(numeric) + 1)) - set(numeric))
    rep.double_writes = sum(n - 1 for n in tight.values() if n > 1)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", default="outputs/audit.jsonl")
    ap.add_argument("--events", action="store_true",
                    help="also count true double-writes (same event AND same ts)")
    ap.add_argument("--limit", type=int, default=12, help="rows to print per class")
    args = ap.parse_args()

    try:
        rep = verify_chain(args.path, check_events=args.events)
    except OSError as exc:
        print(f"cannot read {args.path}: {exc}")
        return 2

    print(f"file      {args.path}")
    print(f"records   {rep.records:,}   malformed {rep.malformed}")
    print(f"integrity {'PASS' if not rep.integrity else 'FAIL'}"
          f"  ({len(rep.integrity)} record(s) not matching their own hash)  [ALARM]")
    print(f"dangling  {len(rep.dangling)}  (deleted/forged-record signature)  [ALARM]")
    print(f"seams     {len(rep.seams)}  (concurrent-writer forks; benign for integrity)")
    print(f"complete  {'yes' if not rep.missing_seqs else f'NO — {rep.missing_seqs} gap(s)'}"
          f"  (no seq missing below the maximum)")
    print(f"seq key   {'unique' if not rep.duplicate_seqs else 'NOT UNIQUE'}"
          f" — {rep.duplicate_seqs} duplicated seq(s), {rep.divergent_seqs} divergent,"
          f" {rep.surplus_records} surplus record(s)")
    if args.events:
        print(f"double-writes (identical event AND ts): {rep.double_writes}")

    for label, rows, fmt in (
        ("INTEGRITY FAILURES", rep.integrity,
         lambda r: f"  line {r[0]} seq {r[1]}: stored {r[2]} != recomputed {r[3]}"),
        ("DANGLING PREV", rep.dangling,
         lambda r: f"  line {r[0]} seq {r[1]}: prev {r[2]} resolves nowhere"),
        ("SEAMS", rep.seams,
         lambda r: f"  line {r[0]} seq {r[1]}: prev {r[2]} (produced at seq {r[3]})"),
    ):
        if rows:
            print(f"\n{label} (showing {min(len(rows), args.limit)} of {len(rows)}):")
            for r in rows[:args.limit]:
                print(fmt(r))

    if rep.tampered:
        print("\nVERDICT: TAMPERED — a committed record was altered or removed.")
        return 1
    print("\nVERDICT: no record altered or removed."
          + (f" {len(rep.seams)} benign writer seam(s)." if rep.seams else ""))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
