@echo off
REM test_windows.bat - full offline verification matrix
REM stages: assurance PBIT -> smoke suite -> pytest acceptance -> quant trials
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"
set PY=python
if exist .venv\Scripts\python.exe set PY=.venv\Scripts\python.exe
echo using interpreter: %PY%

echo === assurance_check (47 invariants) ===
%PY% scripts\assurance_check.py || (echo ASSURANCE FAILED - do not arm & exit /b 1)

echo.
echo === smoke_test (188 end-to-end checks) ===
%PY% scripts\smoke_test.py || (echo SMOKE FAILED - do not arm & exit /b 1)

echo.
echo === pytest acceptance (rev3 + overfit battery + risk protocols) ===
%PY% -m pytest tests -q || (echo PYTEST FAILED - do not arm & exit /b 1)

echo.
echo === quant trials (risk protocol A/B gates) ===
%PY% scripts\quant_trials.py || (echo QUANT GATES FAILED - do not arm & exit /b 1)

echo.
echo ALL GREEN.
endlocal
