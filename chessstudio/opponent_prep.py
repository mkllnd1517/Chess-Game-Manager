"""Preparación de rival con un flujo guiado de 3 pasos.

1. Cargar el PGN del rival (importación en segundo plano con barra de
   progreso y botón de cancelar; la interfaz nunca se congela).
2. Confirmar el rival detectado automáticamente y el color a preparar.
3. Abrir el explorador de aperturas: la base del rival queda como referencia
   (columnas verdes) en el panel "Aperturas", y se puede saltar a él con un
   clic. También se listan las partidas del rival para abrirlas directamente.

La base de preparación se guarda en la carpeta de documentos de Chess Games
Manager, dentro de ``prep``, y conserva
todas las partidas del PGN; el filtro por rival/color se aplica en las
consultas, así que cambiar de rival o de color es instantáneo.
"""
from __future__ import annotations

import collections
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from chessstudio.app_paths import preparation_directory
from chessstudio.database import ChessDatabase, parse_stored_game
from chessstudio.game_list import GameListWidget
from chessstudio.game_model import GameDoc
from chessstudio.workers import PgnImportWorker, run_in_thread

# QStandardPaths resuelve correctamente «Documentos» en Windows, macOS y
# escritorios Linux localizados; se conserva el nombre público por
# compatibilidad con el resto del módulo.
PREP_DIR = preparation_directory()
COLOR_MAP = {"Ambos colores": "both", "Con blancas": "white", "Con negras": "black"}


class AddGamesDialog(QDialog):
    """Selector de partidas de la base principal para añadir a la preparación."""

    def __init__(self, db: ChessDatabase, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Añadir partidas de la base principal")
        self.resize(640, 480)
        self._db = db
        self._rows = db.search(limit=5000)

        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filtrar por jugador o evento...")
        self.filter_edit.textChanged.connect(self._apply_filter)

        self.list = GameListWidget()
        self.list.set_rows(self._rows)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Añadir seleccionadas")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selecciona una o varias partidas (Ctrl/Clic para múltiple):"))
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.list, 1)
        layout.addWidget(buttons)

    def _apply_filter(self, text: str) -> None:
        text = text.strip().lower()
        if not text:
            self.list.set_rows(self._rows)
            return
        filtered = [
            row for row in self._rows
            if text in row.white.lower() or text in row.black.lower() or text in row.event.lower()
        ]
        self.list.set_rows(filtered)

    def selected_ids(self) -> list[int]:
        return self.list.selected_ids()


class OpponentPrepWidget(QWidget):
    gameSelected = Signal(object)                 # GameDoc
    prepDatabaseReady = Signal(object, str, str)  # ChessDatabase|None, jugador, color
    referenceFilterChanged = Signal(str, str)     # jugador, color
    explorerRequested = Signal()                  # pedir que se muestre el explorador
    statusMessage = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._main_db: ChessDatabase | None = None
        self._prep_db: ChessDatabase | None = None
        self._prep_db_path: Path | None = None
        self._opponent = ""
        self._color = "both"
        self._thread = None
        self._worker = None
        self._setup_ui()
        self._set_steps_enabled(False)

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Paso 1
        step1 = QGroupBox("Paso 1 · Cargar PGN del rival")
        s1 = QVBoxLayout(step1)
        row = QHBoxLayout()
        self.btn_import = QPushButton("Cargar PGN...")
        self.btn_import.clicked.connect(self._import_opponent_pgn)
        row.addWidget(self.btn_import)
        self.btn_open_db = QPushButton("Abrir base existente...")
        self.btn_open_db.clicked.connect(self._open_existing)
        row.addWidget(self.btn_open_db)
        row.addStretch(1)
        s1.addLayout(row)
        self.file_label = QLabel("Ningún archivo cargado.")
        self.file_label.setStyleSheet("color:#777;")
        self.file_label.setWordWrap(True)
        s1.addWidget(self.file_label)
        progress_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        progress_row.addWidget(self.progress, 1)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_import)
        progress_row.addWidget(self.btn_cancel)
        s1.addLayout(progress_row)
        self.load_status = QLabel("")
        self.load_status.setWordWrap(True)
        s1.addWidget(self.load_status)
        layout.addWidget(step1)

        # Paso 2
        step2 = QGroupBox("Paso 2 · Confirmar rival y color")
        s2 = QVBoxLayout(step2)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Rival:"))
        self.rival_combo = QComboBox()
        self.rival_combo.setMinimumWidth(160)
        self.rival_combo.currentTextChanged.connect(self._on_rival_changed)
        row2.addWidget(self.rival_combo, 1)
        s2.addLayout(row2)
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Preparar:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(list(COLOR_MAP))
        self.color_combo.currentTextChanged.connect(self._on_color_changed)
        row3.addWidget(self.color_combo, 1)
        s2.addLayout(row3)
        self.rival_info = QLabel("")
        self.rival_info.setWordWrap(True)
        self.rival_info.setTextFormat(Qt.PlainText)  # nombres del PGN no confiables
        s2.addWidget(self.rival_info)
        layout.addWidget(step2)

        # Paso 3
        step3 = QGroupBox("Paso 3 · Explorar aperturas")
        s3 = QVBoxLayout(step3)
        self.btn_explorer = QPushButton("Abrir explorador de aperturas")
        self.btn_explorer.setStyleSheet("font-weight:bold; padding:6px;")
        self.btn_explorer.clicked.connect(self._open_explorer)
        s3.addWidget(self.btn_explorer)
        self.explorer_hint = QLabel(
            "El panel «Aperturas» mostrará las estadísticas del rival en las columnas verdes."
        )
        self.explorer_hint.setWordWrap(True)
        self.explorer_hint.setTextFormat(Qt.PlainText)  # nombres del PGN no confiables
        self.explorer_hint.setStyleSheet("color:#777;")
        s3.addWidget(self.explorer_hint)
        self.btn_clear = QPushButton("Quitar rival del explorador")
        self.btn_clear.clicked.connect(self._clear_prep)
        s3.addWidget(self.btn_clear)
        layout.addWidget(step3)

        # Partidas del rival
        self.games_label = QLabel("Partidas del rival:")
        layout.addWidget(self.games_label)
        self.prep_list = QListWidget()
        self.prep_list.itemDoubleClicked.connect(self._on_prep_double_click)
        layout.addWidget(self.prep_list, 1)
        self.btn_add_game = QPushButton("Añadir partidas de la base principal...")
        self.btn_add_game.clicked.connect(self._add_games_from_main)
        layout.addWidget(self.btn_add_game)

    def _set_steps_enabled(self, enabled: bool) -> None:
        self.rival_combo.setEnabled(enabled)
        self.color_combo.setEnabled(enabled)
        self.btn_explorer.setEnabled(enabled)
        self.btn_clear.setEnabled(enabled)
        self.btn_add_game.setEnabled(enabled and self._main_db is not None)

    # ------------------------------------------------------------------ #
    # Base principal
    # ------------------------------------------------------------------ #
    def set_main_database(self, db: ChessDatabase | None) -> None:
        self._main_db = db
        self.btn_add_game.setEnabled(self._prep_db is not None and db is not None)

    # ------------------------------------------------------------------ #
    # Paso 1: importar PGN
    # ------------------------------------------------------------------ #
    def _import_opponent_pgn(self) -> None:
        if self._thread is not None:
            QMessageBox.information(self, "Importación en curso", "Espera a que termine la importación actual.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Cargar PGN del rival", "", "PGN (*.pgn);;Todos (*)")
        if not path:
            return
        self._start_import(Path(path))

    def _start_import(self, pgn_path: Path) -> None:
        # Soltar la referencia anterior en el explorador antes de cerrar nada.
        self.prepDatabaseReady.emit(None, "", "both")
        self._close_prep_db()
        try:
            PREP_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo crear la carpeta de preparación:\n{exc}")
            return
        prep_path = PREP_DIR / (pgn_path.stem + ".csdb")
        self._prep_db_path = prep_path
        self.file_label.setText(f"Archivo: {pgn_path.name}")
        self.load_status.setText("Leyendo PGN...")
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.btn_cancel.setVisible(True)
        self.btn_import.setEnabled(False)
        self.btn_open_db.setEnabled(False)
        self._set_steps_enabled(False)

        self._worker = PgnImportWorker(str(prep_path), [str(pgn_path)], detect_players=True, fresh=True)
        self._worker.progress.connect(self._on_import_progress)
        self._worker.finished.connect(self._on_import_finished)
        self._worker.failed.connect(self._on_import_failed)
        self._thread = run_in_thread(self._worker, self)
        self._thread.start()

    def _cancel_import(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.load_status.setText("Cancelando...")

    def _on_import_progress(self, percent: int, count: int) -> None:
        self.progress.setValue(percent)
        self.load_status.setText(f"Importando... {count} partidas ({percent}%)")

    def _on_import_finished(self, summary: dict) -> None:
        self._finish_import_ui()
        imported = summary.get("imported", 0)
        players: collections.Counter | None = summary.get("players")
        if imported == 0:
            self.load_status.setText("El PGN no contiene partidas válidas.")
            QMessageBox.warning(self, "Sin partidas", "El PGN no contiene partidas válidas.")
            return
        try:
            self._prep_db = ChessDatabase(self._prep_db_path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo abrir la base de preparación:\n{exc}")
            return
        self._populate_rivals(players)
        note = " (cancelado)" if summary.get("cancelled") else ""
        self.load_status.setText(f"Listo: {imported} partidas importadas{note}.")
        self._set_steps_enabled(True)
        self._activate_prep()
        self.statusMessage.emit(f"Preparación lista: {self._opponent} ({imported} partidas).")

    def _on_import_failed(self, message: str) -> None:
        self._finish_import_ui()
        self.load_status.setText("Error al importar.")
        QMessageBox.critical(self, "Error", f"No se pudo importar el PGN:\n{message}")

    def _finish_import_ui(self) -> None:
        self.progress.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.btn_import.setEnabled(True)
        self.btn_open_db.setEnabled(True)
        self._thread = None
        self._worker = None

    def _populate_rivals(self, players: collections.Counter | None) -> None:
        self.rival_combo.blockSignals(True)
        self.rival_combo.clear()
        if players:
            for name, count in players.most_common():
                self.rival_combo.addItem(f"{name}  ({count})", name)
        self.rival_combo.blockSignals(False)
        if self.rival_combo.count():
            self.rival_combo.setCurrentIndex(0)
            self._opponent = self.rival_combo.currentData() or ""
        self._refresh_rival_info()

    # ------------------------------------------------------------------ #
    # Abrir base existente
    # ------------------------------------------------------------------ #
    def _open_existing(self) -> None:
        if self._thread is not None:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Abrir base de preparación", str(PREP_DIR), "Bases Chess Games Manager (*.csdb);;Todos (*)")
        if not path:
            return
        self.prepDatabaseReady.emit(None, "", "both")
        self._close_prep_db()
        try:
            self._prep_db = ChessDatabase(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo abrir la base:\n{exc}")
            return
        self._prep_db_path = Path(path)
        self.file_label.setText(f"Base: {Path(path).name}")
        self.load_status.setText(f"{self._prep_db.game_count()} partidas.")
        self._populate_rivals(self._prep_db.player_counts())
        self._set_steps_enabled(True)
        self._activate_prep()

    # ------------------------------------------------------------------ #
    # Paso 2: rival / color
    # ------------------------------------------------------------------ #
    def _on_rival_changed(self, _text: str) -> None:
        self._opponent = self.rival_combo.currentData() or ""
        self._refresh_rival_info()
        self._refresh_prep_list()
        if self._prep_db is not None:
            self.referenceFilterChanged.emit(self._opponent, self._color)

    def _on_color_changed(self, text: str) -> None:
        self._color = COLOR_MAP.get(text, "both")
        self._refresh_rival_info()
        self._refresh_prep_list()
        if self._prep_db is not None:
            self.referenceFilterChanged.emit(self._opponent, self._color)

    def _refresh_rival_info(self) -> None:
        if self._prep_db is None or not self._opponent:
            self.rival_info.setText("")
            return
        try:
            white, black = self._prep_db.player_color_counts(self._opponent)
        except Exception:
            white = black = 0
        self.rival_info.setText(
            f"{self._opponent}: {white + black} partidas ({white} con blancas, {black} con negras)."
        )

    # ------------------------------------------------------------------ #
    # Paso 3: explorador
    # ------------------------------------------------------------------ #
    def _activate_prep(self) -> None:
        self._refresh_prep_list()
        self.prepDatabaseReady.emit(self._prep_db, self._opponent, self._color)
        self.explorerRequested.emit()
        self.explorer_hint.setText(
            f"✓ Rival activo: {self._opponent}. El panel «Aperturas» muestra sus estadísticas "
            "en las columnas verdes. Mueve en el tablero para explorar su repertorio."
        )
        self.explorer_hint.setStyleSheet("color:#2e7d32;")

    def _open_explorer(self) -> None:
        if self._prep_db is None:
            return
        self.prepDatabaseReady.emit(self._prep_db, self._opponent, self._color)
        self.explorerRequested.emit()

    def _clear_prep(self) -> None:
        self.prepDatabaseReady.emit(None, "", "both")
        self._close_prep_db()
        self._prep_db_path = None
        self._opponent = ""
        self.rival_combo.blockSignals(True)
        self.rival_combo.clear()
        self.rival_combo.blockSignals(False)
        self.prep_list.clear()
        self.rival_info.setText("")
        self.games_label.setText("Partidas del rival:")
        self.file_label.setText("Ningún archivo cargado.")
        self.load_status.setText("")
        self.explorer_hint.setText(
            "El panel «Aperturas» mostrará las estadísticas del rival en las columnas verdes."
        )
        self.explorer_hint.setStyleSheet("color:#777;")
        self._set_steps_enabled(False)
        self.statusMessage.emit("Preparación de rival desactivada.")

    def _close_prep_db(self) -> None:
        if self._prep_db is not None:
            try:
                self._prep_db.close()
            except Exception:
                pass
            self._prep_db = None

    # ------------------------------------------------------------------ #
    # Lista de partidas del rival
    # ------------------------------------------------------------------ #
    def _refresh_prep_list(self) -> None:
        self.prep_list.clear()
        if self._prep_db is None:
            self.games_label.setText("Partidas del rival:")
            return
        rows = self._prep_db.search(player=self._opponent, player_color=self._color, limit=5000)
        self.games_label.setText(f"Partidas del rival ({len(rows)}):")
        for row in rows:
            item = QListWidgetItem(f"{row.white} - {row.black}  ({row.result})  {row.event}  {row.date}")
            item.setData(Qt.UserRole, row.id)
            self.prep_list.addItem(item)

    def _on_prep_double_click(self, item: QListWidgetItem) -> None:
        if self._prep_db is None:
            return
        row = self._prep_db.get_game(item.data(Qt.UserRole))
        if row is None:
            return
        game = parse_stored_game(row.movetext, row.headers)
        if game is None:
            return
        doc = GameDoc(game)
        doc.mark_saved()
        self.gameSelected.emit(doc)

    def _add_games_from_main(self) -> None:
        if self._main_db is None or self._prep_db is None:
            return
        dialog = AddGamesDialog(self._main_db, self)
        if dialog.exec() != QDialog.Accepted:
            return
        ids = dialog.selected_ids()
        if not ids:
            return
        added = 0
        for game_id in ids:
            row = self._main_db.get_game(game_id)
            if row is None:
                continue
            game = parse_stored_game(row.movetext, row.headers)
            if game is None:
                continue
            try:
                self._prep_db.add_game(game)
                added += 1
            except Exception:
                continue
        self._refresh_prep_list()
        self._refresh_rival_info()
        self.referenceFilterChanged.emit(self._opponent, self._color)
        self.statusMessage.emit(f"{added} partida(s) añadidas a la preparación.")

    # ------------------------------------------------------------------ #
    # Cierre
    # ------------------------------------------------------------------ #
    def shutdown(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                self._worker.finished.disconnect()
                self._worker.failed.disconnect()
                self._worker.progress.disconnect()
            except (RuntimeError, TypeError):
                pass
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
        self._close_prep_db()
