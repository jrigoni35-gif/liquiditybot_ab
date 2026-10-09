import pathlib
def sub(f, old, new):
    p = pathlib.Path(f); s = p.read_bytes().decode()
    assert s.count(old) == 1, (f, old[:60]); p.write_bytes(s.replace(old, new).encode())
pt = "risk/profit_tiers.py"
s = pathlib.Path(pt).read_bytes().decode()
a = s.index("    @staticmethod\n    def _snapshot_trigger(")
b = s.index("    # ---- exit-floor machinery")
NEW = '''    @staticmethod
    def _snapshot_sigma(position, tier_index: int) -> Optional[float]:
        """Frozen per-bar sigma for tier `tier_index`, or None (no snapshot
        / synthetic Position / corrupt value -> live sigma, the exact
        legacy behavior). R2: only the VOL INPUT is frozen; the engine's
        own tier scale (macro playbook tier_scale, inventory bleed x0.75 -
        main._tier_engine) still applies live, so R2 changes nothing but
        the post-fire vol path it was adjudicated for."""
        snaps = getattr(position, "tier_trigger_snapshots", None)
        if not isinstance(snaps, dict) or not snaps:
            return None
        sig = _f(snaps.get(str(tier_index)), float("nan"))
        return sig if math.isfinite(sig) and sig > 0.0 else None

    def _snapshot_next_tier_sigma(self, position, fired_index: int,
                                  sigma_bar_pct) -> None:
        """Freeze the MEASURED sigma the first time tier `fired_index`
        fires, keyed for tier `fired_index + 1`. Never overwritten by a
        later re-fire (tier_closed advances on FILL, so the tier re-fires
        every cycle while its take rests), and never stored while sigma is
        unmeasured (None = R1's transient no-vol-feed fallback, which must
        not become permanent)."""
        nxt = fired_index + 1
        if nxt >= len(self.tiers) or not self.vol_scaled:
            return
        snaps = getattr(position, "tier_trigger_snapshots", None)
        if not isinstance(snaps, dict) or str(nxt) in snaps:
            return
        sig = _f(sigma_bar_pct, float("nan")) if sigma_bar_pct is not None \
            else float("nan")
        if math.isfinite(sig) and sig > 0.0:
            snaps[str(nxt)] = sig

'''
s = s[:a] + NEW + s[b:]
old_eval = '''            trigger = self._snapshot_trigger(position, next_tier_index)
            if trigger is None:
                trigger = self._tier_trigger_pct(
                    tier, sigma_bar_pct, tier_index=next_tier_index,
                    est_cost_bps=_f(getattr(position, "est_cost_bps", 0.0)))
'''
new_eval = '''            frozen = self._snapshot_sigma(position, next_tier_index)
            trigger = self._tier_trigger_pct(
                tier, frozen if frozen is not None else sigma_bar_pct,
                tier_index=next_tier_index,
                est_cost_bps=_f(getattr(position, "est_cost_bps", 0.0)))
'''
assert s.count(old_eval) == 1; s = s.replace(old_eval, new_eval)
old_call = '''                self._snapshot_next_tier_trigger(position, next_tier_index,
                                                 sigma_bar_pct)
'''
new_call = '''                self._snapshot_next_tier_sigma(position, next_tier_index,
                                               sigma_bar_pct)
'''
assert s.count(old_call) == 1; s = s.replace(old_call, new_call)
pathlib.Path(pt).write_bytes(s.encode())
sub("core/persistence.py", '''        tier_trigger_snapshots={str(k): float(v) for k, v in
                                (d.get("tier_trigger_snapshots") or {}).items()},
''', '''        tier_trigger_snapshots=_tier_snapshots_from(
            d.get("tier_trigger_snapshots")),
''')
sub("core/persistence.py", "def position_from_dict(d: dict):\n", '''def _tier_snapshots_from(raw) -> dict:
    """R2: tolerant restore - a malformed entry is DROPPED (that tier
    falls back to live sigma), never raised: an exception here would
    abort the portfolio section and lose every later position."""
    out = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                f = float(v)
            except (TypeError, ValueError):
                continue
            if f == f and f not in (float("inf"), float("-inf")) and f > 0:
                out[str(k)] = f
    return out


def position_from_dict(d: dict):
''')
