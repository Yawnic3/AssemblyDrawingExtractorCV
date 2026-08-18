VICTORIA MARINE BOM EXTRACTOR - UI / WINDOWS PACKAGE
=====================================================

WHAT THIS ADDS
--------------
A desktop UI around the existing PDFPartsPipeline project:

- PDF file picker
- Output-folder picker
- Per-page progress bar
- Live extraction log
- Automatic Excel export
- Open Excel / Open Output Folder buttons
- Processing runs in a background thread so the window stays responsive

FILES TO COPY TO YOUR PROJECT ROOT
----------------------------------
Copy these files beside your existing pipeline.py and excel_exporter.py:

    app.py
    VictoriaMarineBOM.spec
    runtime_hook.py
    build_windows.ps1
    build_windows.bat

Your existing project should look approximately like:

    PDFPartsPipeline/
        app.py
        pipeline.py
        excel_exporter.py
        VictoriaMarineBOM.spec
        runtime_hook.py
        build_windows.ps1
        build_windows.bat
        extractor/
            __init__.py
            pdfreader.py
            table_detector.py
            cell_splitter.py
            ocr_reader.py
            bom_parser.py
            assembly_parser.py
        .venv/

TEST THE UI BEFORE BUILDING
---------------------------
Activate the existing environment:

    .\.venv\Scripts\Activate.ps1

Then run:

    python app.py

Choose a PDF and click "Extract BOM to Excel".

BUILD THE WINDOWS APP
---------------------
From PowerShell in the project root:

    .\build_windows.ps1

If PowerShell blocks local scripts for the current terminal:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\build_windows.ps1

Or double-click / run:

    build_windows.bat

OUTPUT
------
After the build completes:

    dist\VictoriaMarine_BOM_Extractor\VictoriaMarine_BOM_Extractor.exe

IMPORTANT: this is an ONEDIR application. Share the entire
"VictoriaMarine_BOM_Extractor" folder in dist, not just the exe.

FIRST RUN ON ANOTHER PC
-----------------------
The OCR models may need to be downloaded the first time the app is run on a
computer where PaddleOCR's official model cache is not already present. For the
current prototype, internet access on first use is therefore recommended.

WHY ONEDIR
----------
This project contains Paddle/PaddleOCR native libraries and model tooling.
ONEDIR is more reliable and starts faster than unpacking a very large ML stack
from a single-file executable on every launch.

CURRENT OCR VERSION NOTE
------------------------
Keep the working PaddlePaddle version from the project environment (3.2.2 in
this prototype) when building. Do not upgrade PaddlePaddle during packaging if
the extraction pipeline is already passing its tests.
