import argparse
import importlib.metadata
import subprocess
import sys

import paddlex


parser = argparse.ArgumentParser()

parser.add_argument(
    "--file",
    required=True,
    help="Entry Python file, e.g. app.py",
)

args = parser.parse_args()


# ---------------------------------------------------------
# Find installed PaddleX runtime dependencies
# ---------------------------------------------------------

installed_packages = [
    dist.metadata["Name"]
    for dist in importlib.metadata.distributions()
    if dist.metadata["Name"]
]


# IMPORTANT:
# Official PaddleOCR packaging docs use BASE_DEP_SPECS.
paddlex_dependencies = list(
    paddlex.utils.deps.BASE_DEP_SPECS.keys()
)


metadata_dependencies = [
    package
    for package in installed_packages
    if package in paddlex_dependencies
]


print("PaddleX version:", paddlex.__version__)

print(
    "Metadata dependencies:",
    metadata_dependencies
)


# ---------------------------------------------------------
# PyInstaller command
# ---------------------------------------------------------

command = [
    "pyinstaller",

    args.file,

    # Rebuild from scratch
    "--clean",
    "--noconfirm",

    # Windows GUI instead of console application
    "--windowed",

    # Use a directory instead of one huge exe.
    # This is much safer for Paddle/PaddleOCR.
    "--onedir",

    "--name",
    "VictoriaMarine_BOM_Extractor",

    # Official PaddleOCR packaging requirements
    "--collect-data",
    "paddlex",

    "--collect-binaries",
    "paddle",

    # Explicitly collect PaddleOCR
    "--collect-all",
    "paddleocr",

    # OpenCV native files
    "--collect-all",
    "cv2",
]


# ---------------------------------------------------------
# Copy dependency metadata
#
# PaddleX checks installed package metadata at runtime.
# ---------------------------------------------------------

for dependency in metadata_dependencies:

    command.extend(
        [
            "--copy-metadata",
            dependency,
        ]
    )


print()
print("=" * 80)
print("BUILD COMMAND")
print("=" * 80)
print()
print(" ".join(command))
print()


try:

    subprocess.run(
        command,
        check=True,
    )

except subprocess.CalledProcessError as error:

    print()
    print(
        "Packaging failed:",
        error,
    )

    sys.exit(1)


print()
print("=" * 80)
print("BUILD COMPLETE")
print("=" * 80)

print()
print(
    "Application:"
)

print(
    r"dist\VictoriaMarine_BOM_Extractor\VictoriaMarine_BOM_Extractor.exe"
)