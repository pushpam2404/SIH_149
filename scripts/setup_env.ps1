<#
Windows setup: creates .venv, installs Python dependencies, and checks for
the optional PhotoRec binary.

Usage (from the project folder, in PowerShell):
    powershell -ExecutionPolicy Bypass -File scripts\setup_env.ps1

pytsk3 ships as a prebuilt wheel with libtsk included, so no Sleuth Kit
install is needed. python-magic is skipped on Windows (see requirements.txt).
The Windows CI job runs this script, so it is exercised on every push.
#>
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

function Test-PythonCommand([string]$exe, [string[]]$prefix) {
    # Returns $true if the interpreter exists and is Python 3.10-3.13.
    try {
        $out = & $exe @prefix -c "import sys; print(int((3, 10) <= sys.version_info[:2] < (3, 14)))" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq '1')
    } catch {
        return $false
    }
}

$pyExe = $null
$pyPrefix = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($version in @('3.12', '3.13', '3.11', '3.10')) {
        if (Test-PythonCommand 'py' @("-$version")) { $pyExe = 'py'; $pyPrefix = @("-$version"); break }
    }
}
if (-not $pyExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    if (Test-PythonCommand 'python' @()) { $pyExe = 'python' }
}
if (-not $pyExe) {
    Write-Host "Python 3.10-3.13 not found." -ForegroundColor Red
    Write-Host "Install Python 3.12 from https://www.python.org/downloads/ (tick 'Add python.exe to PATH')"
    Write-Host "or run: winget install Python.Python.3.12"
    exit 1
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host "Creating virtual environment in .venv using $pyExe $pyPrefix ..."
    & $pyExe @pyPrefix -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "Creating .venv failed." -ForegroundColor Red; exit 1 }
}

$venvPython = Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit 1 }
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed." -ForegroundColor Red; exit 1 }

Write-Host ""
$photorec = Get-Command photorec_win, photorec -ErrorAction SilentlyContinue | Select-Object -First 1
if ($photorec) {
    Write-Host "PhotoRec found: $($photorec.Source)"
} else {
    Write-Host "Optional: PhotoRec (signature carving) was not found on PATH."
    Write-Host "  Download 'TestDisk & PhotoRec' for Windows from https://www.cgsecurity.org/wiki/TestDisk_Download,"
    Write-Host "  unzip it, and add the folder containing photorec_win.exe to PATH."
    Write-Host "  Without it, recovery still works through pytsk3."
}

Write-Host ""
Write-Host "Done. Next steps:"
Write-Host "  .venv\Scripts\python.exe -m pytest tests"
Write-Host "  .venv\Scripts\python.exe -m app.main"
Write-Host "Erasing or scanning a physical drive needs the app to be started from an Administrator terminal."
exit 0
