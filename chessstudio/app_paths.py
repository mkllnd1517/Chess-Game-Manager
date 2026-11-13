"""Rutas de recursos y datos para la aplicación instalada.

Centralizar las rutas evita asumir que la carpeta del usuario se llama
literalmente ``Documents`` (no es así en todos los idiomas ni sistemas) y
permite que la misma aplicación funcione desde código fuente o congelada con
PyInstaller.
"""
from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path

from PySide6.QtCore import QStandardPaths

from chessstudio import APP_NAME


def resource_path(*parts: str) -> Path:
    """Devuelve una ruta de solo lectura incluida con la aplicación.

    PyInstaller expone los datos empaquetados temporalmente en ``_MEIPASS``;
    durante el desarrollo se usa la raíz del repositorio. No se deben guardar
    datos del usuario en esta ubicación.
    """
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base.joinpath(*parts)


def legal_document_path(filename: str) -> Path | None:
    """Localiza un aviso legal en código fuente, binario o rueda instalada."""
    bundled = resource_path(filename)
    if bundled.is_file():
        return bundled
    try:
        distribution = metadata.distribution("chess-game-manager")
        files = distribution.files or []
        # setuptools instala ``license-files`` bajo dist-info/licenses/.
        for file in files:
            if str(file).replace("\\", "/").endswith(f"licenses/{filename}"):
                candidate = Path(distribution.locate_file(file))
                if candidate.is_file():
                    return candidate
        for file in files:
            if file.name == filename:
                candidate = Path(distribution.locate_file(file))
                if candidate.is_file():
                    return candidate
    except metadata.PackageNotFoundError:
        pass
    return None


def documents_directory() -> Path:
    """Carpeta de documentos del sistema, con una alternativa segura."""
    location = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
    return Path(location) if location else Path.home() / "Documents"


def app_documents_directory() -> Path:
    """Carpeta de datos visibles del usuario para bases y preparaciones."""
    return documents_directory() / APP_NAME


def preparation_directory() -> Path:
    """Ubicación por defecto de las bases de preparación de rivales."""
    return app_documents_directory() / "prep"
