# Unified Test Execution Script for Foreclosure Intelligence
param (
    [switch]$IncludeE2E = $false,
    [switch]$IncludePerformance = $false
)

$ErrorActionPreference = "Stop"
$StartTime = Get-Date

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  Foreclosure Intelligence - Full Verification Suite  " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

$VenvPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
$FrontendDir = Join-Path $PSScriptRoot "..\frontend"

# Step 1: Backend Unit, Security, and Domain Logic
Write-Host "`n[Step 1/4] Running Backend Unit & Business Logic Tests..." -ForegroundColor Yellow
if (Test-Path $VenvPython) {
    & $VenvPython -m pytest -m "unit or security" -q
} else {
    python -m pytest -m "unit or security" -q
}
Write-Host "Backend unit and security tests passed." -ForegroundColor Green

# Step 2: Backend Integration & Migrations
Write-Host "`n[Step 2/4] Running Backend Integration & Migration Tests..." -ForegroundColor Yellow
if (Test-Path $VenvPython) {
    & $VenvPython -m pytest tests/test_api_integration.py tests/test_migrations_and_integrity.py tests/test_reliability_recovery.py -q
} else {
    python -m pytest tests/test_api_integration.py tests/test_migrations_and_integrity.py tests/test_reliability_recovery.py -q
}
Write-Host "Backend integration and migration tests passed." -ForegroundColor Green

# Step 3: Frontend Quality Checks (Typecheck + Component Tests + Production Build)
Write-Host "`n[Step 3/4] Running Frontend Quality Checks..." -ForegroundColor Yellow
Push-Location $FrontendDir
try {
    Write-Host "  -> Running TypeScript typecheck..." -ForegroundColor Gray
    npm run typecheck
    Write-Host "  -> Running Vitest component tests..." -ForegroundColor Gray
    npm test
    Write-Host "  -> Verifying production build..." -ForegroundColor Gray
    npm run build
} finally {
    Pop-Location
}
Write-Host "Frontend quality verification passed." -ForegroundColor Green

# Step 4: Optional End-to-End or Performance Runs
if ($IncludeE2E) {
    Write-Host "`n[Step 4/4] Running Playwright E2E Browser Tests..." -ForegroundColor Yellow
    Push-Location $FrontendDir
    try {
        npx playwright test --project=chromium
    } finally {
        Pop-Location
    }
    Write-Host "Playwright E2E tests passed." -ForegroundColor Green
} elseif ($IncludePerformance) {
    Write-Host "`n[Step 4/4] Running k6 Performance Smoke Test..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "run_k6.ps1") -Scenario "smoke"
} else {
    Write-Host "`n[Step 4/4] End-to-End & Performance tests skipped (pass -IncludeE2E or -IncludePerformance to run)." -ForegroundColor Gray
}

$Elapsed = [Math]::Round(((Get-Date) - $StartTime).TotalSeconds, 1)
Write-Host "`n======================================================" -ForegroundColor Cyan
Write-Host "  Verification Complete! All checks passed in ${Elapsed}s " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
