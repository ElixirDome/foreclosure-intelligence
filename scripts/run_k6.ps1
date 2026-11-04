# PowerShell runner script for k6 performance tests
param (
    [string]$Scenario = "smoke",
    [string]$BaseUrl = "http://localhost:8000"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Foreclosure Intelligence - k6 Benchmark" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Scenario: $Scenario" -ForegroundColor Yellow
Write-Host "Base URL: $BaseUrl" -ForegroundColor Yellow

$ScriptPath = Join-Path $PSScriptRoot "..\tests\performance\$Scenario.js"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Scenario script not found: $ScriptPath. Available scenarios: smoke, load, stress, spike, soak, large_dataset"
    exit 1
}

# Check if k6 executable is available
$k6Cmd = Get-Command k6 -ErrorAction SilentlyContinue

if (-not $k6Cmd) {
    Write-Warning "k6 is not installed or not in system PATH."
    Write-Host "To install k6 on Windows:" -ForegroundColor Green
    Write-Host "  winget install k6 --source winget" -ForegroundColor White
    Write-Host "  or: choco install k6" -ForegroundColor White
    Write-Host "  or download from: https://k6.io/docs/get-started/installation/" -ForegroundColor White
    exit 1
}

Write-Host "Executing k6 run for scenario: $Scenario..." -ForegroundColor Green
& k6 run -e BASE_URL=$BaseUrl $ScriptPath
