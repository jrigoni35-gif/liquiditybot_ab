# Windows setup

## Two commands (recommended)

```bat
install.bat              # one-time: creates .venv, installs everything, verifies
start.bat                # runs the bot
```

Observability lives in Grafana Cloud (see `docs/PHONE_SESSIONS.md`); the
legacy Streamlit dashboard has been retired.

`stop.bat` stops the bot cleanly. `test_windows.bat` runs the full
offline verification matrix before you trust it with anything.

## Manual setup (equivalent)

```bat
install.bat                              # creates .venv, installs requirements
test_windows.bat                         # runs the verification checks (offline)
python runner.py                         # starts the bot (dry_run=true by default)
```

(The former `setup_windows.bat` / `run_windows.bat` / `dashboard_windows.bat`
wrappers were redundant one-liners around the commands above and were removed.)

## In VS Code

Open the `liquiditybot_ab` folder in VS Code (not the parent). The
included `.vscode/` folder configures:

- **Python interpreter** — auto-selects `.venv\Scripts\python.exe`.
- **Terminal** — new terminals get `PYTHONUTF8=1` and
  `PYTHONIOENCODING=utf-8` in the environment (protects against Windows
  console code-page crashes on unicode).
- **Debug configs** (Run and Debug panel, `F5`):
  - Run Bot (runner.py)
  - Assurance Check (47 invariants)
  - Smoke Test (188 checks)
  - Replay Session
- **Tasks** (Terminal → Run Task…):
  - Assurance Check (`Ctrl+Shift+B` — default test task)
  - Smoke Test
  - Verify Audit Chain
  - Run Bot (dry_run)
  - Setup (create venv + install deps)

## Windows compatibility fixes applied

- Every `open()`, `read_text()`, `write_text()` explicitly uses UTF-8
  (Windows defaults to cp1252, which raises `UnicodeEncodeError` on
  em-dashes and other characters that appear in log lines).
- All temp paths route through `tempfile.gettempdir()` — resolves to
  `%LOCALAPPDATA%\Temp` on Windows, `/tmp` on posix.
- All `strftime` format strings use portable codes (`%Y-%m-%d %H:%M:%S`
  in place of POSIX-only `%F %T`, which crashes the Windows CRT).
- Atomic writes use `os.replace` (cross-platform), not `os.rename`
  (fails on Windows if the target exists).
- CWD-independent path resolution: `runner.py` `os.chdir`s to the
  package directory before anything opens files, and `load_config`
  has a `BASE_DIR` fallback — running the bot from any directory works.
- Runner reconfigures `stdout`/`stderr` to UTF-8 with `errors="replace"`
  so redirected output and legacy code-page consoles never crash on a
  unicode character in a log line.

## Verify a live session's audit chain

```bash
python -c "from core.audit import get_audit; print(get_audit().verify())"
```

Expected: `{'ok': True, 'records': N, 'first_break': None, 'dropped_writes': 0}`

Any other output means the audit trail was tampered with or the disk
had a write failure. `first_break` names the exact record.

## Live trading

The bot ships `dry_run: true` in `config.json`. To arm live:

1. Set your real Kraken fee tier in
   `pretrade.maker_fee_bps` / `pretrade.taker_fee_bps` (config guard
   refuses to start live below Kraken's 25/40bps public floor unless
   `pretrade.allow_sub_floor_fees` is explicitly set).
2. Put credentials in `exchanges.kraken.api_key` /
   `exchanges.kraken.api_secret` (config guard refuses to start live
   without them).
3. Set `system.dry_run: false`.
4. At the PC console, type `ARM LIVE` (the hard gate the runner requires
   before it will actually route live orders).

Anything short of all four steps keeps you in paper mode.
