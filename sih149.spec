# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# We need to collect submodules for magika and other dynamic imports
hiddenimports = []
hiddenimports += collect_submodules('magika')
hiddenimports += collect_submodules('magic')  # absent on Windows (python-magic not installed there); collect_submodules then returns []
hiddenimports += collect_submodules('ppdeep')
hiddenimports += ['PySide6.QtSvg']  # icons are rendered with QSvgRenderer

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app/gui/assets', 'app/gui/assets'),  # Include GUI assets if any
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SIH_149_Data_Recovery_and_Erasure',
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
    icon='app/gui/assets/icon.ico' if os.path.exists('app/gui/assets/icon.ico') else None,
)
