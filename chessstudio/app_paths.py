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

# Solo para migrar datos de usuarios de ediciones anteriores. No es un nombre
# mostrado por la interfaz ni se usa para crear datos nuevos.
_LEGACY_APP_DIRECTORY_NAME = "ChessStudio"


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
        distribution = metadata.distribution("chess-games-manager")
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
    """Carpeta de datos visibles del usuario para bases y preparaciones.

    En la primera ejecución tras el cambio de nombre se traslada de forma
    atómica la carpeta de datos anterior si todavía no existe la nueva. Si el
    sistema no permite el cambio de nombre, se sigue usando la carpeta antigua
    para no ocultar bases, repertorios o preparaciones ya creadas.
    """
    root = documents_directory()
    target = root / APP_NAME
    legacy = root / _LEGACY_APP_DIRECTORY_NAME
    if target.exists() or not legacy.is_dir():
        return target
    try:
        legacy.replace(target)
    except OSError:
        # Otra instancia pudo completar la migración, o el volumen no permite
        # renombrar en este momento. En ambos casos se conserva el acceso a
        # los datos existentes en vez de crear una colección vacía.
        return target if target.exists() else legacy
    return target


def preparation_directory() -> Path:
    """Ubicación por defecto de las bases de preparación de rivales."""
    return app_documents_directory() / "prep"


def repertoire_directory() -> Path:
    """Ubicación privada de las colecciones de repertorios del usuario.

    Cada repertorio se guarda en una carpeta independiente con bases separadas
    para blancas y negras. Nunca se utiliza la carpeta de instalación, que en
    una aplicación empaquetada puede ser de solo lectura.
    """
    return app_documents_directory() / "repertoires"
