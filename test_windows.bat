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
%PY% -m pytest tests -q || (echo PYTEST FAILED - do not arm & exit /b 1)

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
where pyright >nul 2>nul
if %ERRORLEVEL%==0 (
    pyright core data execution ml risk regime strategies sentiment api main.py runner.py || (echo PYRIGHT FAILED - type ratchet regressed & exit /b 1)
) else (
    echo pyright not installed - stage SKIPPED. Install: pip install pyright
)

echo.
echo === bandit security scan ===
%PY% -m bandit -c pyproject.toml -r . -x ./.venv,./tests,./.claude -q || (echo BANDIT FAILED & exit /b 1)

echo.
echo === compileall ===
%PY% -m compileall -q . -x ".venv" || (echo COMPILE FAILED & exit /b 1)

echo.
echo === quant trials (risk protocol A/B gates) ===
%PY% scripts\quant_trials.py || (echo QUANT GATES FAILED - do not arm & exit /b 1)

echo.
echo ALL GREEN.
endlocal
