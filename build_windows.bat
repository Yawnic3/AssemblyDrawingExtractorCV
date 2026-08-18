@echo off
setlocal

echo.
echo Victoria Marine BOM Extractor - Windows Build
echo ================================================

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Could not find .venv.
    echo Run this script from the PDFPartsPipeline project root.
    pause
    exit /b 1
)

.venv\Scripts\python.exe -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error

.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean VictoriaMarineBOM.spec
if errorlevel 1 goto :error

echo.
echo BUILD COMPLETE
echo Executable:
echo dist\VictoriaMarine_BOM_Extractor\VictoriaMarine_BOM_Extractor.exe
echo.
echo Share the ENTIRE VictoriaMarine_BOM_Extractor folder in dist, not only the .exe.
pause
exit /b 0

:error
echo.
echo BUILD FAILED. Review the error above.
pause
exit /b 1
