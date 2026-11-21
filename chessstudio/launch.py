"""Utilidades de lanzamiento que no dependen de la interfaz Qt."""
from __future__ import annotations

from pathlib import Path


def pgn_path_from_arguments(arguments: list[str]) -> str | None:
    """Devuelve el primer PGN existente indicado al abrir la aplicación.

    Se utiliza desde el acceso directo y la asociación de archivos del
    instalador. Otros argumentos de Qt o rutas inexistentes se ignoran de
    forma intencionada: abrir un archivo siempre requiere una ruta PGN real.
    """
    for argument in arguments[1:]:
        path = Path(argument).expanduser()
        if path.suffix.lower() == ".pgn" and path.is_file():
            return str(path)
    return None
