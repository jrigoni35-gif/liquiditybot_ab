@echo off
REM test_windows.bat - the FULL Definition-of-Done matrix (CLAUDE.md).
REM Every stage must pass before a change is "done". Check counts inside
REM each stage grow over time, so no numbers are hardcoded here.
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"
set PY=python
if exist .venv\Scripts\python.exe set PY=.venv\Scripts\python.exe
echo using interpreter: %PY%

echo === pytest acceptance suite ===
REM -n 8: pytest-xdist, adopted 2026-08-07 after the evidence gate (two
REM clean full runs, 623s serial -> ~400s on the 5600X's 12 threads;
REM the one flake between them was a load-starved 5s client timeout in
REM the REST test harness, hardened to 30s in 00bd0e52). 8 workers, not
REM 12: SMT threads share execution units and the LIVE runner needs
REM headroom - it runs BelowNormal and a Normal-priority battery on all
REM 12 threads outcompetes it (measured stalls up to 88s are documented
REM in runner.py). /belownormal puts the battery UNDER the bot, never
REM the bot under the battery: tests can be slow, exits cannot.
REM `start /b /wait cmd || (...)` NEVER fires the || - start's own launch
REM success satisfies the conditional; the awaited child's exit code only
REM lands in ERRORLEVEL. Discovered 2026-08-08 when a red pytest stage
REM (1 failed) sailed through to ALL GREEN - the first false arm this
REM gate ever produced (prior "failed" batteries were caught by LATER
REM stages whose engines broke on the same bugs). `if errorlevel 1` reads
REM the awaited child's code and is the documented-reliable form.
REM Two passes since 2026-08-08 (owed item 44): the honest gate above
REM immediately exposed a rotating one-red-per-battery family - tests
REM whose assertions measure WALL CLOCK (burst-gap spacing, elapsed
REM upper bounds, hard 120s subprocess timeouts). Under 8 saturated
REM workers any of them can fail with no code defect (measured:
REM TimeoutExpired on overfit_check subprocesses; burst gaps compressed
REM by stamp descheduling - each verified green solo on the same tree).
REM They carry @pytest.mark.timing (registered strict in pyproject.toml)
REM and run in the SERIAL pass below on a quiet machine; everything else
REM keeps xdist. The split is pinned by tests/test_battery_gate.py.
start /belownormal /b /wait "" %PY% -m pytest tests -q -n 8 -m "not timing"
if errorlevel 1 (echo PYTEST FAILED - do not arm & exit /b 1)

echo.
echo === pytest timing family (serial - wall-clock-sensitive) ===
start /belownormal /b /wait "" %PY% -m pytest tests -q -m timing
if errorlevel 1 (echo PYTEST TIMING FAILED - do not arm & exit /b 1)

echo.
echo === smoke_test (end-to-end checks) ===
%PY% scripts\smoke_test.py || (echo SMOKE FAILED - do not arm & exit /b 1)

echo.
echo === assurance_check (invariant PBIT) ===
%PY% scripts\assurance_check.py || (echo ASSURANCE FAILED - do not arm & exit /b 1)

echo.
echo === overfit_check (OF-1..OF-7 battery) ===
%PY% scripts\overfit_check.py || (echo OVERFIT GATES FAILED - do not arm & exit /b 1)

echo.
echo === ruff lint ===
%PY% -m ruff check core data execution ml risk regime strategies sentiment api main.py runner.py tests scripts\quant_trials.py scripts\overfit_check.py || (echo RUFF FAILED & exit /b 1)

echo.
echo === pyright type ratchet (shipped scope, must stay at zero) ===
REM A missing tool is a RED stage, not a skip (2026-08-07): this stage
REM silently printed SKIPPED for weeks while CLAUDE.md claimed a
REM zero-error ratchet - a gate that can quietly not exist is a gate
REM that lies. pyright now ships in the venv (pip install pyright).
set "PYRIGHT=pyright"
if exist .venv\Scripts\pyright.exe set "PYRIGHT=.venv\Scripts\pyright.exe"
%PYRIGHT% --version >nul 2>nul || (echo PYRIGHT MISSING - install: %PY% -m pip install pyright & exit /b 1)
%PYRIGHT% core data execution ml risk regime strategies sentiment api main.py runner.py || (echo PYRIGHT FAILED - type ratchet regressed & exit /b 1)

echo.
echo === bandit security scan ===
%PY% -m bandit -c pyproject.toml -r . -x ./.venv,./tests,./.claude,./outputs -q || (echo BANDIT FAILED & exit /b 1)

echo.
echo === compileall ===
REM -j 0 (auto workers): measured 9.32s -> 1.71s cold, 4.07s -> 3.48s
REM warm on the 5600X; .pyc output is byte-identical, -q hides the
REM interleaved worker output.
%PY% -m compileall -q -j 0 . -x ".venv" || (echo COMPILE FAILED & exit /b 1)

echo.
echo === quant trials (risk protocol A/B gates) ===
%PY% scripts\quant_trials.py || (echo QUANT GATES FAILED - do not arm & exit /b 1)

echo.
echo ALL GREEN.
endlocal
