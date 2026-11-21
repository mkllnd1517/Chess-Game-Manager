#!/usr/bin/env python3
"""Construye el paquete de escritorio reproducible de Chess Games Manager.

Uso:
    python -m pip install -e ".[build]"
    python scripts/build_release.py

El resultado principal es ``dist/ChessGamesManager/``. En Windows, si Inno Setup 6
(``ISCC.exe``) está instalado y disponible en PATH, también se crea
``dist/installer/Chess-Games-Manager-Setup-<versión>.exe`` con acceso directo opcional
en el escritorio.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import sysconfig
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "ChessGamesManager.spec"
WINDOWS_INSTALLER = ROOT / "packaging" / "windows" / "ChessGamesManager.iss"


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


def write_component_manifest(output: Path) -> Path:
    """Registra versiones y procedencia de las bibliotecas de ejecución.

    No sustituye los textos de licencia, pero permite revisar exactamente qué
    se incluyó en una compilación y enlazarlo con `THIRD_PARTY_NOTICES.md`.
    Los extras que no estén instalados no se anuncian como parte del binario.
    """
    known = (
        ("chess", "python-chess", "https://github.com/niklasf/python-chess"),
        ("PySide6-Essentials", "PySide6-Essentials", "https://doc.qt.io/qtforpython-6/"),
        ("shiboken6", "shiboken6", "https://doc.qt.io/qtforpython-6/"),
        ("keyring", "keyring (opcional)", "https://github.com/jaraco/keyring"),
    )
    components = []
    for package, display_name, source in known:
        try:
            package_metadata = metadata.metadata(package)
            version = metadata.version(package)
        except metadata.PackageNotFoundError:
            continue
        components.append(
            {
                "package": package,
                "name": display_name,
                "version": version,
                "license": package_metadata.get("License") or "Consultar la distribución exacta",
                "source": source,
            }
        )
    manifest = {
        "format": 1,
        "project": "Chess Games Manager",
        "components": components,
        "notice": "Consulta LICENSE, NOTICE y THIRD_PARTY_NOTICES.md para los avisos y obligaciones aplicables.",
    }
    target = output / "THIRD_PARTY_COMPONENTS.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


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
    app_directory = ROOT / "dist" / "ChessGamesManager"
    manifest = write_component_manifest(app_directory)
    print(f"\nAplicación creada: {app_directory}")
    print(f"Inventario de componentes: {manifest}")

    if sys.platform != "win32":
        print(
            "\nEn Linux, distribuye la carpeta dist/ChessGamesManager completa. "
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
