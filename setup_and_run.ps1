# =============================================================================
#  OrangeHRM automation - setup and run (Windows / PowerShell)
#
#  Usage, from inside the project folder (the one containing pytest.ini):
#
#      .\setup_and_run.ps1              # setup, then run API + UI + performance
#      .\setup_and_run.ps1 -Only api    # API contract suite only  (no browser)
#      .\setup_and_run.ps1 -Only ui     # 5 E2E workflows only
#      .\setup_and_run.ps1 -Only perf   # k6 performance only
#      .\setup_and_run.ps1 -SetupOnly   # create the venv and install, run nothing
#
#  If PowerShell refuses to run this file, allow local scripts once:
#      Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
# =============================================================================
param(
    [ValidateSet('all', 'api', 'ui', 'perf')]
    [string]$Only = 'all',
    [switch]$SetupOnly,
    [string]$Browser = 'chromium'
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "  $text"       -ForegroundColor Green }
function Warn($text) { Write-Host "  $text"       -ForegroundColor Yellow }

# --------------------------------------------------------------- sanity check
if (-not (Test-Path 'pytest.ini')) {
    throw "Run this from the project folder - the one that contains pytest.ini, conftest.py and tests\."
}

# --------------------------------------------------------------- virtualenv
Step 'Virtual environment'
if (Test-Path '.venv\Scripts\python.exe') {
    Ok 'Reusing the existing .venv'
} else {
    if (Test-Path '.venv') {
        Warn 'Removing an incomplete .venv'
        Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
        Remove-Item '.venv' -Recurse -Force
    }
    Ok 'Creating .venv'
    python -m venv .venv
}

$py = Resolve-Path '.venv\Scripts\python.exe'
Ok "Python: $(& $py --version)"

# --------------------------------------------------------------- dependencies
Step 'Dependencies'
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r requirements.txt --quiet
Ok 'Python packages installed'

& $py -m playwright install $Browser
Ok "Playwright browser '$Browser' ready"

# --------------------------------------------------------------- folders
New-Item -ItemType Directory -Force -Path 'reports\performance' | Out-Null

if ($SetupOnly) { Step 'Setup complete - nothing was run'; exit 0 }

$failed = @()

# --------------------------------------------------------------- 1. API
if ($Only -in @('all', 'api')) {
    Step '1/3  API contract tests (ReqRes - no browser)'
    & $py -m pytest -m api `
        --html=reports/html/api-report.html `
        --junitxml=reports/junit/api-results.xml
    if ($LASTEXITCODE -ne 0) { $failed += 'api' }
}

# --------------------------------------------------------------- 2. UI + API
if ($Only -in @('all', 'ui')) {
    Step "2/3  E2E workflows - UI + API hybrid ($Browser)"
    Warn 'This drives a real browser against the OrangeHRM demo site and takes several minutes.'
    & $py -m pytest -m workflow --browser $Browser `
        --html=reports/html/e2e-report.html `
        --junitxml=reports/junit/e2e-results.xml
    if ($LASTEXITCODE -ne 0) { $failed += 'ui' }
}

# --------------------------------------------------------------- 3. performance
if ($Only -in @('all', 'perf')) {
    Step '3/3  k6 performance (login API + employee creation API)'

    $k6 = $null
    if ($env:K6_BIN -and (Test-Path $env:K6_BIN)) { $k6 = $env:K6_BIN }
    elseif (Get-Command k6 -ErrorAction SilentlyContinue) { $k6 = 'k6' }
    elseif (Test-Path 'C:\Program Files\k6\k6.exe')  { $k6 = 'C:\Program Files\k6\k6.exe' }

    if ($null -eq $k6) {
        Warn 'k6 not found. Install it with:  winget install k6 --source winget'
        Warn 'or set K6_BIN to the full path of k6.exe, then re-run with -Only perf'
        $failed += 'perf (k6 missing)'
    } else {
        Ok "Using k6: $k6"
        & $k6 run performance/k6/api-performance.js
        if ($LASTEXITCODE -ne 0) { $failed += 'perf' }
    }
}

# --------------------------------------------------------------- summary
Step 'Summary'
if ($failed.Count -eq 0) {
    Ok 'All requested suites passed.'
} else {
    Warn "Suites that did not pass: $($failed -join ', ')"
}

Write-Host ''
Write-Host '  Reports:' -ForegroundColor Cyan
Write-Host '    reports\html\api-report.html          API contract results'
Write-Host '    reports\html\e2e-report.html          UI workflow results (videos embedded)'
Write-Host '    reports\performance\k6-report.html    k6 performance results'
Write-Host '    reports\videos\  reports\screenshots\  reports\traces\'
Write-Host ''

if ($failed.Count -gt 0) { exit 1 }
