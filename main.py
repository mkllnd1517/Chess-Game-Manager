"""Lanzador de compatibilidad para ejecutar desde un clon del repositorio.

Las instalaciones desde el código fuente usan el comando
``chess-games-manager``. Las compilaciones locales también pueden crear un
acceso directo; no es necesario abrir ni ejecutar este archivo.
"""
from chessstudio.app import main


if __name__ == "__main__":
    raise SystemExit(main())
