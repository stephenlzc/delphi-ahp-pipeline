# Delphi-AHP Pipeline Installer (Windows)
#
# Usage:
#   irm https://raw.githubusercontent.com/stephenlzc/delphi-ahp-pipeline/main/install.ps1 | iex
#
# Or download and run:
#   Invoke-WebRequest -Uri "https://raw.githubusercontent.com/stephenlzc/delphi-ahp-pipeline/main/install.ps1" -OutFile install.ps1; .\install.ps1
#

$SCRIPT_DIR = $PSScriptRoot
if (-not $SCRIPT_DIR) {
    $SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
}

Write-Host ""
Write-Host "=== Delphi-AHP Pipeline Installer (Windows) ===" -ForegroundColor Cyan
Write-Host ""

$PythonCmd = $null
$PythonVersion = $null

# 1. Detect Python
try {
    $pythonOut = python --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $PythonCmd = "python"
        $PythonVersion = $pythonOut
    }
} catch {}

if (-not $PythonCmd) {
    try {
        $pythonOut = python3 --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $PythonCmd = "python3"
            $PythonVersion = $pythonOut
        }
    } catch {}
}

if ($PythonVersion) {
    Write-Host "[OK] Python found: $PythonVersion" -ForegroundColor Green
} else {
    Write-Host "[INFO] Python not found. Installing Python 3.12..." -ForegroundColor Yellow

    # Try Winget first (Windows 10/11 with App Installer)
    $hasWinget = $null -ne (Get-Command winget -ErrorAction SilentlyContinue)
    if ($hasWinget) {
        Write-Host "[INFO] Using Winget to install Python..." -ForegroundColor Yellow
        winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements --silent
    } else {
        Write-Host "[INFO] Winget not found. Downloading Python installer..." -ForegroundColor Yellow
        $installerUrl = "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe"
        $installerPath = "$env:TEMP\python-3.12-installer.exe"
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
        Write-Host "[INFO] Running installer (silent)..." -ForegroundColor Yellow
        Start-Process -FilePath $installerPath -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1" -Wait
        # Refresh PATH for current session
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    }

    # Verify after install
    Start-Sleep -Seconds 3
    try {
        $PythonVersion = (python --version 2>&1)
        if ($LASTEXITCODE -eq 0) {
            $PythonCmd = "python"
            Write-Host "[OK] Python installed: $PythonVersion" -ForegroundColor Green
        }
    } catch {
        Write-Host "[ERROR] Python installation failed. Please install Python 3 manually from https://python.org" -ForegroundColor Red
        exit 1
    }
}

# 2. Create virtual environment
Write-Host ""
Write-Host "[INFO] Creating virtual environment..." -ForegroundColor Yellow
& python -m venv "$SCRIPT_DIR\.venv"

# 3. Install dependencies
Write-Host "[INFO] Installing dependencies..." -ForegroundColor Yellow
& "$SCRIPT_DIR\.venv\Scripts\Activate.ps1" -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0) {
    # Try batch activation fallback
    & "$SCRIPT_DIR\.venv\Scripts\activate.bat"
}
pip install --upgrade pip -q
pip install -r "$SCRIPT_DIR\requirements.txt" -q

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Run the application:" -ForegroundColor Cyan
Write-Host "  cd $SCRIPT_DIR" -ForegroundColor White
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "  python app.py" -ForegroundColor White
Write-Host ""
Write-Host "Or simply double-click:" -ForegroundColor Cyan
Write-Host "  run.bat" -ForegroundColor White
Write-Host ""
