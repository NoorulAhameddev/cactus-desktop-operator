# Launcher for Cactus Siri Desktop Orb
$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

$PythonExe = "C:\Users\Nooru\.dodaios\.venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python.exe"
}

Write-Host "Launching Siri Desktop Orb..." -ForegroundColor Magenta
& $PythonExe siri_orb.py

