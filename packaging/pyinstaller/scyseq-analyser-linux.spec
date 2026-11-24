# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, copy_metadata


repo_root = Path(SPECPATH).parents[1]
src_dir = repo_root / "src"
pmw_datas = collect_data_files("Pmw", include_py_files=True)
# Standalone Python distributions can keep Tcl/Tk outside the system linker paths.
python_lib = Path(sys.base_prefix) / "lib"
tk_binaries = [(str(path), ".") for pattern in ("libtcl[0-9]*.so", "libtk[0-9]*.so")
               for path in python_lib.glob(pattern)]

hiddenimports = [
    "Pmw",
    "numpy",
    "scyseq",
    "scyseq.algorithmic",
    "scyseq.information",
    "scyseq.io",
    "scyseq.operations",
    "scyseq.sequence",
    "scyseq.stochastic",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
]


a = Analysis(
    [str(src_dir / "scyseqtools" / "analyser" / "main.py")],
    pathex=[str(src_dir)],
    binaries=tk_binaries,
    datas=pmw_datas + copy_metadata("scyseqtools") + copy_metadata("scyseq"),
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={"matplotlib": {"backends": ["TkAgg", "SVG"]}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="scyseq-analyser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
)
