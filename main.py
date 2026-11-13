"""Lanzador de compatibilidad para ejecutar desde un clon del repositorio.

Las instalaciones normales usan el comando ``chessstudio`` o el acceso directo
creado por el instalador; no es necesario abrir ni ejecutar este archivo.
"""
from chessstudio.app import main


if __name__ == "__main__":
    raise SystemExit(main())
