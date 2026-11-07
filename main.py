import sys

from PySide6.QtWidgets import QApplication

from chessstudio import APP_NAME, __version__
from chessstudio.main_window import MainWindow


def main() -> int:
    # Partidas muy largas con variantes profundas pueden superar el límite
    # de recursión por defecto al renderizar/exportar el árbol.
    sys.setrecursionlimit(10000)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
