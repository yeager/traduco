# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/linguaedit/app.py'],
    pathex=[],
    binaries=[],
    datas=[('resources/icon.png', 'resources'), ('src/linguaedit/translations/*.qm', 'linguaedit/translations')],
    hiddenimports=['PySide6'],
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
    [],
    exclude_binaries=True,
    name='LinguaEdit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LinguaEdit',
)
app = BUNDLE(
    coll,
    name='LinguaEdit.app',
    icon='data/macos/LinguaEdit.app/Contents/Resources/linguaedit.icns',
    bundle_identifier='se.danielnylander.LinguaEdit',
)
