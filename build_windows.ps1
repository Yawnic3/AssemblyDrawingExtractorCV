$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "Victoria Marine BOM Extractor - Windows Build" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    throw "Could not find .venv. Run this script from the PDFPartsPipeline project root."
}

$Python = ".\.venv\Scripts\python.exe"

Write-Host "Installing/updating UI build dependencies..." -ForegroundColor Yellow
& $Python -m pip install --upgrade pyinstaller

Write-Host "Building Windows application..." -ForegroundColor Yellow
& $Python -m PyInstaller --noconfirm --clean VictoriaMarineBOM.spec

Write-Host ""
Write-Host "BUILD COMPLETE" -ForegroundColor Green
Write-Host "Executable:" -ForegroundColor Green
Write-Host ".\dist\VictoriaMarine_BOM_Extractor\VictoriaMarine_BOM_Extractor.exe"
Write-Host ""
Write-Host "Share the ENTIRE VictoriaMarine_BOM_Extractor folder in dist, not only the .exe." -ForegroundColor Yellow
