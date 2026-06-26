# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Thermogram backend sidecar.

Build from the backend/ directory:
    pyinstaller backend.spec --clean --noconfirm

Output: dist/backend (mac/linux) or dist/backend.exe (windows).
"""

from PyInstaller.utils.hooks import collect_submodules

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
        "pkg_resources",
        "pygments",
        "markupsafe",
        "yaml",
        "jaraco",
        "more_itertools",
        "importlib_metadata",
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
    strip=True,
    upx=False,
    upx_exclude=[],
    name="backend",
)
