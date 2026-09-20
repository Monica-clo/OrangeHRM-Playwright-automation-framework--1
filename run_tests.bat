@echo off
REM Usage: run_tests.bat [api^|workflow^|positive^|negative^|smoke^|regression^|perf] [extra options]
REM   run_tests.bat                     -> all 5 E2E workflows (UI + API)
REM   run_tests.bat api                 -> API-only contract suite (no browser)
REM   run_tests.bat negative            -> the negative workflow only
REM   run_tests.bat positive --headed   -> the 4 positive workflows with a visible browser
REM   run_tests.bat perf                -> k6 performance test (login + employee creation API)
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
set SUITE=%1
if "%SUITE%"=="perf" goto perf
if "%SUITE%"=="api" goto marker
if "%SUITE%"=="workflow" goto marker
if "%SUITE%"=="positive" goto marker
if "%SUITE%"=="negative" goto marker
if "%SUITE%"=="smoke" goto marker
if "%SUITE%"=="regression" goto marker
python -m pytest -m workflow %*
goto end
:marker
shift
python -m pytest -m %SUITE% %1 %2 %3 %4 %5 %6 %7 %8 %9
goto end
:perf
shift
if not exist reports\performance mkdir reports\performance
REM k6 is used from PATH; K6_BIN lets you point at an installed copy instead,
REM e.g.  set K6_BIN=C:\Program Files\k6\k6.exe
set K6=k6
if defined K6_BIN set K6=%K6_BIN%
if not defined K6_BIN if exist "C:\Program Files\k6\k6.exe" set K6="C:\Program Files\k6\k6.exe"
%K6% run %1 %2 %3 %4 %5 %6 %7 %8 %9 performance\k6\api-performance.js
:end
