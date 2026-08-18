# Victoria Marine BOM Extractor

A Windows desktop application that converts **Bill of Material (BOM) tables from engineering drawing PDFs into structured Excel files**.

The extractor processes each PDF page, detects the BOM table in the upper-left area, reads the corresponding **ASSEMBLY** value from the title block, performs OCR on the table cells, validates the extracted values, and exports the results into an Excel workbook.

## Features

- Select an engineering drawing PDF from a desktop UI
- Detect BOM tables automatically with OpenCV
- Dynamically expand the BOM search region for long tables
- Split detected tables into individual rows and cells
- Read CAD text with PaddleOCR
- Extract the page-level `ASSEMBLY` value from the title block
- Associate every BOM row with its assembly
- Validate and normalize OCR results
- Recover obvious item-number OCR errors using row sequencing
- Export all extracted data to Excel
- Record page-level extraction errors for review
- Show extraction progress and logs in the desktop application
- Package the application as a Windows executable with PyInstaller

## Example Output

The generated workbook contains a master BOM similar to:

| Page | Assembly | Item | Part Name | Qty | Stock Name | Weight (kg) | Rev |
|---:|---|---:|---|---:|---|---:|---|
| 1 | MARCURIUS | 1 | BOTTOM PARTS | 1 | N/A | 378 | |
| 1 | MARCURIUS | 2 | DECK | 1 | N/A | 286 | |
| 1 | MARCURIUS | 3 | DRONE LOCKER | 1 | N/A | 42 | |
| 1 | MARCURIUS | 8 | TRANSOM | 1 | N/A | 42 | |

The workbook also includes an **Extraction Errors** sheet so pages that fail can be reviewed without stopping the entire PDF job.

## How It Works

```text
Engineering Drawing PDF
        |
        v
Read each PDF page
        |
        +---------------------------+
        |                           |
        v                           v
Top-left BOM search          Bottom-right title block
        |                           |
        v                           v
OpenCV line detection          PaddleOCR
        |                           |
        v                           v
Dynamic table detection      Extract ASSEMBLY value
        |
        v
Split table into cells
        |
        v
PaddleOCR each cell
        |
        v
Validate / normalize values
        |
        +-------------+
                      |
                      v
          Associate Assembly + BOM rows
                      |
                      v
                 Excel export
```

## Project Structure

```text
PDFPartsPipeline/
|
|-- app.py                  # Tkinter desktop UI
|-- pipeline.py             # End-to-end PDF processing pipeline
|-- excel_exporter.py       # Excel workbook generation
|-- package_app.py          # PyInstaller packaging script
|
|-- extractor/
|   |-- __init__.py
|   |-- pdfreader.py        # PDF page access and rendering
|   |-- table_detector.py   # OpenCV BOM table detection
|   |-- cell_splitter.py    # Row / column / cell extraction
|   |-- ocr_reader.py       # PaddleOCR cell recognition
|   |-- bom_parser.py       # Validation and structured BOM parsing
|   `-- assembly_parser.py  # Title-block ASSEMBLY extraction
|
|-- input/                  # Optional development/test PDFs
|-- output/                 # Development output
`-- README.md
```

## Technologies

- **Python**
- **PyMuPDF** — PDF reading and high-resolution page-region rendering
- **OpenCV** — thresholding, line extraction, grid detection, and table localization
- **NumPy** — image-processing utilities
- **PaddlePaddle 3.2.2** — OCR inference runtime
- **PaddleOCR** — CAD text recognition
- **pandas / openpyxl** — Excel generation and formatting
- **Tkinter** — Windows desktop UI
- **PyInstaller** — Windows application packaging

## Running from Source

### 1. Create and activate a virtual environment

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install paddlepaddle==3.2.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python -m pip install paddleocr pymupdf opencv-python numpy pandas openpyxl pyinstaller
```

Verify PaddlePaddle:

```powershell
python -c "import paddle; print(paddle.__version__)"
```

Expected:

```text
3.2.2
```

Verify Tkinter:

```powershell
python -m tkinter
```

A small Tk window should open.

### 3. Launch the desktop app

```powershell
python app.py
```

## Using the Application

1. Click **Browse PDF** and select the engineering drawing PDF.
2. Choose an **Output folder**.
3. Click **Extract BOM to Excel**.
4. The application will:
   - load the OCR models,
   - process each page,
   - display progress and logs,
   - write the final Excel workbook to the selected output folder.
5. Use **Open Excel** or **Open Output Folder** when processing completes.

Temporary rendered pages, OCR crops, and debug images are stored in the Windows temporary directory rather than the user's selected output folder.

## Dynamic BOM Detection

BOM tables vary significantly in length across engineering drawings. The pipeline does not rely on a single fixed crop height.

It progressively tests larger page regions until the detected BOM is safely separated from the bottom of the crop:

```text
15% -> 25% -> 35% -> 45% -> 60% -> 75% page height
```

This prevents long tables from being silently truncated.

## OCR Validation

OCR output is cleaned based on the expected field type.

Examples:

- `Item`, `Qty` -> integer normalization
- `Weight (kg)` -> numeric normalization
- `Part Name`, `Stock Name`, `Rev` -> text normalization

The parser also uses established row sequencing to recover obvious low-confidence item-number OCR errors. Corrections are recorded as warnings rather than silently applied.

## Building the Windows Executable

The application is packaged using **PyInstaller `--onedir`** because PaddleOCR/PaddlePaddle rely on a large set of Python packages, native DLLs, model resources, and runtime metadata.

Before building, verify that the application works normally:

```powershell
python app.py
```

Then remove previous builds:

```powershell
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
```

Build:

```powershell
python package_app.py --file app.py
```

The packaged application will be created at:

```text
dist/
`-- VictoriaMarine_BOM_Extractor/
    |-- VictoriaMarine_BOM_Extractor.exe
    `-- _internal/
```

### Distribution

Distribute the **entire** folder:

```text
dist\VictoriaMarine_BOM_Extractor\
```

Do not distribute the `.exe` by itself. The `_internal` directory contains required Paddle, OCR, Python, Tk/Tcl, DLL, and package resources.

The receiving Windows user does **not** need the source code, `.venv`, or Python installation when using the packaged build.

## First-Run OCR Models

PaddleOCR uses official OCR model files. If they are not already bundled or cached on the computer, the first run may download them.

The application disables PaddleX's preliminary model-source connectivity probe with:

```python
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
```

For a fully offline deployment, the OCR model directories should be included in the packaged application in a future release.

## Troubleshooting

### `No module named 'tkinter'`

The Python interpreter used to build the application does not include Tcl/Tk.

Verify:

```powershell
python -m tkinter
```

Build the application only from a Python environment where this command works.

### PaddleOCR / Paddle dependency errors after packaging

Confirm the source application works before freezing it:

```powershell
python app.py
```

The packaging script must collect Paddle binaries, PaddleOCR/PaddleX resources, and package metadata required at runtime.

### `WinError 5: Access is denied` on `debug_pages`

Older versions created temporary debug folders inside the selected output directory. This could conflict with OneDrive-synced folders.

The current UI uses the Windows temporary directory for intermediate processing files and only writes the finished Excel workbook to the selected output directory.

### `No ccache found`

Paddle may print a warning that `ccache` is unavailable. This warning is not fatal for normal CPU OCR inference.

### OCR model takes time to load

The OCR models are initialized once when an extraction begins. On CPU, startup and processing can take time, especially on large multi-page drawings.

## Current Limitations

- Designed around the Victoria Marine engineering drawing layout and BOM structure.
- Expected BOM columns are:
  - `#`
  - `Part Name`
  - `Qty`
  - `Stock Name`
  - `Wt (kg)`
  - `Rev`
- The system assumes the BOM is located near the upper-left of each drawing page.
- The title block / `ASSEMBLY` field is expected near the lower-right.
- Very faint or unusual CAD fonts can still produce OCR errors.
- PaddleOCR may miss isolated single-character values in some drawings.
- The current packaged version may require an internet connection on first launch if OCR model files are not already included.

## Future Improvements

- Bundle PaddleOCR models for fully offline deployment
- Add second-pass OCR for low-confidence or blank numeric fields
- Normalize stock-name formatting such as `X`, `x`, and multiplication-symbol variants
- Add confidence-based highlighting in Excel
- Allow manual review/editing of uncertain cells before export
- Support additional engineering drawing templates
- Add drag-and-drop PDF support
- Add batch processing of multiple PDFs
- Add optional CSV export
- Add an internal web version using the same extraction backend

## Output Privacy

The desktop version processes PDFs locally on the user's Windows machine. Engineering drawings do not need to be uploaded to an external web service for extraction.

## Author / Organization

Developed for **Victoria Marine, LLC** as an automated engineering-drawing BOM extraction workflow.

---

> This project is intended for internal engineering workflow automation. Extracted values should be reviewed when source drawings are low quality or OCR warnings are present.
