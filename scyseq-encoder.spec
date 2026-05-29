# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


pymediainfo_datas = [
    item for item in collect_data_files("pymediainfo")
    if not item[0].lower().endswith(".dll")
]
pymediainfo_binaries = collect_dynamic_libs("pymediainfo")


a = Analysis(
    ["src/scyseqtools/encoder/main.py"],
    pathex=["src"],
    binaries=pymediainfo_binaries,
    datas=[
        ("src/scyseqtools/encoder/config.ini", "scyseqtools/encoder"),
        *pymediainfo_datas,
    ],
    hiddenimports=["pymediainfo", "vlc"],
    hookspath=[],
    hooksconfig={},
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
    name="ScySeq Encoder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
