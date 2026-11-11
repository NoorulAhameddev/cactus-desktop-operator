# Launcher for Cactus Desktop Operator
$ErrorActionPreference = "Stop"

Write-Host "Starting Cactus Multimodal Desktop Operator..." -ForegroundColor Cyan
Set-Location -Path $PSScriptRoot

# Use the verified working Python environment
$PythonExe = "C:\Users\Nooru\.dodaios\.venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python.exe"
}

& $PythonExe main.py

