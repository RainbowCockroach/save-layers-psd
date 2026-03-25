# PyInstaller spec file for macOS .app bundle
# Build with: pyinstaller save_layers_macos.spec

import sys

block_cipher = None

a = Analysis(
    ['save_layers.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['psd_tools', 'PIL'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SaveLayersPSD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    argv_emulation=False,  # Must be False for tkinter compatibility
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SaveLayersPSD',
)

app = BUNDLE(
    coll,
    name='SaveLayersPSD.app',
    bundle_identifier='com.savelayerspsd.app',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'CFBundleDocumentTypes': [{
            'CFBundleTypeName': 'Photoshop Document',
            'CFBundleTypeExtensions': ['psd'],
            'CFBundleTypeRole': 'Viewer',
            'LSHandlerRank': 'Alternate',
        }],
        'NSHighResolutionCapable': True,
    },
)
