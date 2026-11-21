"""Punto de entrada de Chess Games Manager.

Este módulo alimenta el comando instalado ``chess-games-manager`` y el
ejecutable de escritorio. ``main.py`` se mantiene como lanzador de
compatibilidad para ejecutar directamente un clon del código fuente.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from chessstudio import APP_NAME, __version__
from chessstudio.app_paths import resource_path
from chessstudio.launch import pgn_path_from_arguments
from chessstudio.main_window import MainWindow


def main() -> int:
    """Crea y ejecuta la interfaz gráfica de Chess Games Manager."""
    # Partidas muy largas con variantes profundas pueden superar el límite
    # de recursión por defecto al exportar árboles PGN.
    sys.setrecursionlimit(10_000)

    # Da a Windows una agrupación e identidad correctas en la barra de tareas.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "io.github.mkllnd1517.chessgamesmanager"
            )
        except (AttributeError, OSError):
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    app.setOrganizationDomain("github.com/mkllnd1517")
    app.setDesktopFileName("io.github.mkllnd1517.ChessGamesManager")
    app.setStyle("Fusion")

    icon_path = resource_path("chessstudio", "assets", "chessstudio.svg")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()

    # El instalador registra Chess Games Manager como visor de .pgn. Programar la
    # apertura permite que la ventana se pinte antes de iniciar el parseo en
    # segundo plano y también funciona al invocarlo desde un acceso directo.
    pgn_path = pgn_path_from_arguments(sys.argv)
    if pgn_path:
        QTimer.singleShot(0, lambda: window.start_open_pgn(pgn_path))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
