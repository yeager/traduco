# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Windows build

a = Analysis(
    ['src/linguaedit/app.py'],
    pathex=['src'],
    binaries=[],
    datas=[('resources/icon.png', 'resources'), ('src/linguaedit/translations/*.qm', 'linguaedit/translations')],
    hiddenimports=['linguaedit', 'PySide6'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['enchant', 'pyenchant'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LinguaEdit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='resources/icon.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name='LinguaEdit',
)
