# PowerShell Security Audit Script for Foreclosure Intelligence
param (
    [switch]$Quick = $false
)

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Foreclosure Intelligence - Security Audit" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

$VenvPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"

# 1. Run Automated Security Regression Tests
Write-Host "`n[1/3] Running Automated Security Test Suite..." -ForegroundColor Yellow
if (Test-Path $VenvPython) {
    & $VenvPython -m pytest tests/test_security_audit.py tests/test_source_security.py tests/test_auth_unit.py -v
} else {
    python -m pytest tests/test_security_audit.py tests/test_source_security.py tests/test_auth_unit.py -v
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Security regression tests failed!"
    exit $LASTEXITCODE
}
Write-Host "Security regression tests passed cleanly." -ForegroundColor Green

# 2. Frontend Dependency Audit
Write-Host "`n[2/3] Auditing Frontend Dependencies..." -ForegroundColor Yellow
Push-Location (Join-Path $PSScriptRoot "..\frontend")
try {
    npm audit --audit-level=high
} finally {
    Pop-Location
}

# 3. Python Dependency Security Check
Write-Host "`n[3/3] Checking Python Security Vulnerabilities..." -ForegroundColor Yellow
$banditCheck = Get-Command bandit -ErrorAction SilentlyContinue
if ($banditCheck) {
    bandit -r app/ -ll
} else {
    Write-Host "Bandit static analysis tool not in PATH (optional). Skipping AST security scan." -ForegroundColor Gray
}

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "  Security Audit Verification Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
