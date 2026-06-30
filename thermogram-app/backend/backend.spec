# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Thermogram backend sidecar.

Build from the backend/ directory:
    pyinstaller backend.spec --clean --noconfirm

Output: dist/backend (mac/linux) or dist/backend.exe (windows).
"""

import sys

from PyInstaller.utils.hooks import collect_submodules

# GNU strip on Windows (shipped via Git for Windows / MinGW) corrupts
# python3XX.dll: the loader then aborts with
#   "Failed to load Python DLL ... Invalid access to memory location".
# Keep strip on for mac/linux where the savings are real and safe.
STRIP_BINARIES = sys.platform != "win32"

hidden = []
hidden += collect_submodules("cv2")
hidden += collect_submodules("numpy")
hidden += collect_submodules("PIL")

datas = [
    ("configs/template_signatures.json", "configs"),
    ("configs/daily.json", "configs"),
    ("configs/four_day.json", "configs"),
    ("configs/weekly.json", "configs"),
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "_pytest",
        "pluggy",
        "tests",
        "tkinter",
        "matplotlib",
        "jupyter",
        "IPython",
        "notebook",
        "skimage",
        "scipy",
        "pandas",
        "numba",
        "llvmlite",
        "setuptools",
        "wheel",
        "pygments",
        "markupsafe",
        "yaml",
        "jaraco",
        "more_itertools",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=STRIP_BINARIES,
    upx=False,
    upx_exclude=[],
    name="backend",
)
