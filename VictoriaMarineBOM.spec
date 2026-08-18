# PyInstaller spec for the Windows desktop package.
# Build with: python -m PyInstaller --noconfirm --clean VictoriaMarineBOM.spec

from PyInstaller.utils.hooks import collect_all, copy_metadata


datas = []
binaries = []
hiddenimports = []


def collect_package(module_name):
    global datas, binaries, hiddenimports
    try:
        d, b, h = collect_all(module_name)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:
        print(f"Warning: collect_all({module_name!r}) failed: {exc}")


# PaddleOCR/PaddleX use dynamic imports and native libraries, so collect them
# explicitly. Normal project modules (pipeline.py, extractor/, etc.) are found
# through imports from app.py.
for package in [
    "paddle",
    "paddlex",
    "paddleocr",
    "cv2",
    "numpy",
    "pandas",
    "openpyxl",
    "pymupdf",
]:
    collect_package(package)

# Packages that commonly query their installed distribution metadata at runtime.
for distribution in ["paddleocr", "paddlex", "paddlepaddle"]:
    try:
        datas += copy_metadata(distribution)
    except Exception as exc:
        print(f"Warning: copy_metadata({distribution!r}) failed: {exc}")


a = Analysis(
    ["app.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["runtime_hook.py"],
    excludes=[
        "matplotlib.tests",
        "numpy.tests",
        "pandas.tests",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VictoriaMarine_BOM_Extractor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VictoriaMarine_BOM_Extractor",
)
