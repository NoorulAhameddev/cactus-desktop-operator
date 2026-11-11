# Launcher for Cactus Floating Bubble Assistant
$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

$PythonExe = "C:\Users\Nooru\.dodaios\.venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python.exe"
}

Write-Host "Starting Cactus AI Floating Bubble..." -ForegroundColor Cyan
& $PythonExe bubble_ui.py

