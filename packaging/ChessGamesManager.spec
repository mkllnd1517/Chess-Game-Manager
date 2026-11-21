# -*- mode: python ; coding: utf-8 -*-
"""Especificación PyInstaller para Chess Games Manager.

Genera una carpeta autosuficiente en ``dist/ChessGamesManager``. En Windows, el
script ``scripts/build_release.py`` encadena después Inno Setup y crea un
instalador que deja un acceso directo en el escritorio.
"""
from pathlib import Path
import sys

block_cipher = None
ICON = Path(SPECPATH).resolve().parent / "packaging" / "windows" / "chessgamesmanager.ico"
ROOT = Path(SPECPATH).resolve().parent

# Todos estos datos se usan en tiempo de ejecución: piezas SVG, icono y los
# textos legales accesibles desde Ayuda. Mantenerlos aquí evita instaladores
# que funcionen pero pierdan el tablero o los avisos de licencia.
datas = [
    (str(ROOT / "chessstudio" / "assets"), "chessstudio/assets"),
    (str(ROOT / "chessstudio" / "pieces"), "chessstudio/pieces"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    (str(ROOT / "NOTICE"), "."),
]

a = Analysis(
    [str(ROOT / "chessstudio" / "app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=["PySide6.QtSvg"],
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
    name="ChessGamesManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON) if sys.platform == "win32" else None,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ChessGamesManager",
)
