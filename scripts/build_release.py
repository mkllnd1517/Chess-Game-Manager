#!/usr/bin/env python3
"""Construye el paquete de escritorio reproducible de ChessStudio.

Uso:
    python -m pip install -e ".[build]"
    python scripts/build_release.py

El resultado principal es ``dist/ChessStudio/``. En Windows, si Inno Setup 6
(``ISCC.exe``) está instalado y disponible en PATH, también se crea
``dist/installer/ChessStudio-Setup-<versión>.exe`` con acceso directo opcional
en el escritorio.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "ChessStudio.spec"
WINDOWS_INSTALLER = ROOT / "packaging" / "windows" / "ChessStudio.iss"


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def has_shared_python_library() -> bool:
    """Comprueba el requisito de PyInstaller en Linux con un mensaje útil."""
    if not sys.platform.startswith("linux"):
        return True
    library = sysconfig.get_config_var("LDLIBRARY")
    if not library:
        return False
    candidates = [
        Path(sysconfig.get_config_var("LIBDIR") or "") / library,
        Path(sys.base_prefix) / "lib" / library,
        Path("/usr/lib") / library,
        Path("/usr/lib/x86_64-linux-gnu") / library,
    ]
    return any(path.is_file() for path in candidates)


def main() -> int:
    if not has_shared_python_library():
        print(
            "No se encontró la biblioteca compartida de Python necesaria para "
            "PyInstaller. En Debian/Ubuntu instala el paquete de desarrollo de "
            "tu versión de Python (por ejemplo, python3.11-dev) y vuelve a "
            "ejecutar este comando.",
            file=sys.stderr,
        )
        return 2
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC)])
    print(f"\nAplicación creada: {ROOT / 'dist' / 'ChessStudio'}")

    if sys.platform != "win32":
        print(
            "\nEn Linux, distribuye la carpeta dist/ChessStudio completa. "
            "Para integrar el acceso directo, consulta packaging/linux/README.md."
        )
        return 0

    compiler = shutil.which("ISCC") or shutil.which("ISCC.exe")
    if compiler is None:
        print(
            "\nPyInstaller terminó correctamente. Para crear el instalador de Windows "
            "con acceso directo de escritorio, instala Inno Setup 6 y ejecuta:\n"
            f'  ISCC "{WINDOWS_INSTALLER}"'
        )
        return 0
    run([compiler, str(WINDOWS_INSTALLER)])
    print(f"\nInstalador creado: {ROOT / 'dist' / 'installer'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
