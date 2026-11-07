"""Configuración común de los tests.

Crea una única QApplication (offscreen) para toda la sesión y desactiva el
autoarranque del motor durante las pruebas, de modo que los tests de la
interfaz no lancen un proceso Stockfish real. Al terminar se restauran los
ajustes originales del usuario.
"""
from __future__ import annotations

import os
import sys

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_app = QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True, scope="session")
def _disable_engine_autostart():
    settings = QSettings("ChessStudio", "ChessStudio")
    prev_autostart = settings.value("engine/autostart", True, bool)
    settings.setValue("engine/autostart", False)
    settings.sync()
    yield
    settings.setValue("engine/autostart", prev_autostart)
    settings.sync()
