# start-backend.ps1
# Startup script for the TAO Lens backend.
# Checks AWS SSO credentials before starting, and only prompts
# for login if the refresh token has expired (~90 days).

$ErrorActionPreference = "Continue"
$profile = "DtcReadOnly-017521386069"

Write-Host ""
Write-Host "=== TAO Lens Backend Startup ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if AWS credentials are valid
Write-Host "Checking AWS SSO credentials..." -ForegroundColor Yellow
$null = aws sts get-caller-identity --profile $profile 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "SSO session expired or not found." -ForegroundColor Red
    Write-Host "Opening browser for SSO login..." -ForegroundColor Yellow
    Write-Host "(You only need to do this once every ~90 days)" -ForegroundColor DarkGray
    Write-Host ""
    aws sso login --profile $profile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "SSO login failed. Exiting." -ForegroundColor Red
        exit 1
    }
    Write-Host "SSO login successful!" -ForegroundColor Green
} else {
    Write-Host "AWS SSO credentials are valid." -ForegroundColor Green
}

Write-Host ""

# Step 2: Start the FastAPI backend
Write-Host "Starting FastAPI backend..." -ForegroundColor Yellow
Write-Host "(Background SSO token refresh will keep credentials alive)" -ForegroundColor DarkGray
Write-Host ""

Set-Location "$PSScriptRoot\agent"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
