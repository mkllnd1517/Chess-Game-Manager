"""Ventana principal de ChessStudio: pestañas de partidas, bases, explorador,
motor y preparación de rival. Sin referencias a productos de terceros.
"""
from __future__ import annotations

from pathlib import Path

import chess
import chess.pgn
from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QStyle,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from chessstudio.board_widget import BoardWidget
from chessstudio.database import (
    DEFAULT_HEADERS,
    ChessDatabase,
    GameRow,
    import_game,
    parse_stored_game,
)
from chessstudio.engine_panel import EnginePanel
from chessstudio.game_list import GameListWidget
from chessstudio.game_model import GameDoc
from chessstudio.notation_view import NotationView
from chessstudio.opening_tree import OpeningTreeWidget
from chessstudio.opponent_prep import OpponentPrepWidget
from chessstudio.pgn_utils import display_comment
from chessstudio.search_dialog import SearchDialog
from chessstudio.workers import (
    GameParseWorker,
    GameTextParseWorker,
    PgnImportWorker,
    run_in_thread,
)


class GamePropertiesDialog(QDialog):
    def __init__(self, headers: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Propiedades de la partida")
        self.setMinimumWidth(360)
        self.fields: dict[str, QLineEdit] = {}
        form = QFormLayout()
        for header in DEFAULT_HEADERS:
            if header == "Result":
                self.result_combo = QComboBox()
                self.result_combo.addItems(["*", "1-0", "0-1", "1/2-1/2"])
                current = headers.get(header, "*")
                if current in ["*", "1-0", "0-1", "1/2-1/2"]:
                    self.result_combo.setCurrentText(current)
                form.addRow("Resultado:", self.result_combo)
            else:
                edit = QLineEdit(str(headers.get(header, "")))
                self.fields[header] = edit
                form.addRow(f"{header}:", edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> dict:
        data = {header: edit.text().strip() for header, edit in self.fields.items()}
        data["Result"] = self.result_combo.currentText()
        return data


class VariationChooserDialog(QDialog):
    def __init__(self, entries: list[tuple[int, str]], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Elegir continuación")
        self.setMinimumWidth(360)
        self._ids = [node_id for node_id, _ in entries]
        label = QLabel("Esta posición tiene varias continuaciones.\n"
                       "Usa las flechas \u2191 \u2193 para elegir y pulsa Enter:")
        label.setWordWrap(True)
        self.list_widget = QListWidget()
        for _, text in entries:
            self.list_widget.addItem(QListWidgetItem(text))
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self.accept())
        for key in (Qt.Key_Return, Qt.Key_Enter):
            QShortcut(QKeySequence(key), self.list_widget, activated=self.accept)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(self.list_widget)
        layout.addWidget(buttons)

    def selected_id(self) -> int | None:
        row = self.list_widget.currentRow()
        if 0 <= row < len(self._ids):
            return self._ids[row]
        return None


class GameWindow(QWidget):
    positionChanged = Signal(chess.Board)
    titleChanged = Signal(str)

    def __init__(self, doc: GameDoc, db_id: int | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.doc = doc
        self.db_id = db_id
        self.last_move: chess.Move | None = None
        self.board_widget = BoardWidget()
        self.notation = NotationView()
        self.notation.set_document(doc)

        self.header_label = QLabel()
        self.header_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        # Texto plano: los nombres del PGN no son confiables y no deben
        # interpretarse como HTML (evita inyección y cargas de recursos externos).
        self.header_label.setTextFormat(Qt.PlainText)

        nav_layout = QHBoxLayout()
        for label, slot in (
            ("|<", doc.goto_start),
            ("<", doc.goto_previous),
            (">", self._goto_next),
            (">|", doc.goto_end),
        ):
            button = QPushButton(label)
            button.setFixedWidth(34)
            button.clicked.connect(slot)
            nav_layout.addWidget(button)
        nav_layout.addSpacing(8)
        flip_button = QPushButton("\u21bb")
        flip_button.setFixedWidth(34)
        flip_button.setToolTip("Girar tablero")
        flip_button.clicked.connect(self.board_widget.flip)
        nav_layout.addWidget(flip_button)
        nav_layout.addStretch(1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.addLayout(nav_layout)
        left_layout.addWidget(self.board_widget, 1)
        left_layout.addWidget(self.header_label)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.notation)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        doc.positionChanged.connect(self._on_position)
        doc.structureChanged.connect(self._on_structure)
        doc.headersChanged.connect(self._on_headers)
        doc.drawingsChanged.connect(self._on_drawings_changed)
        self.board_widget.moveMade.connect(doc.play_move)
        self.board_widget.drawingsChanged.connect(self._on_board_drawings_changed)
        self.notation.nodeSelected.connect(doc.go_to)
        self._build_shortcuts()
        self._on_headers()
        self._on_position(doc.board)
        self._on_drawings_changed()

    def _goto_next(self) -> None:
        variations = self.doc.node.variations
        if not variations:
            return
        if len(variations) == 1:
            self.doc.goto_next()
            return
        board = self.doc.board
        entries: list[tuple[int, str]] = []
        for child in variations:
            if child.move is None:
                continue
            try:
                san = board.san(child.move)
            except Exception:
                san = board.uci(child.move)
            if board.turn == chess.WHITE:
                text = f"{board.fullmove_number}. {san}"
            else:
                text = f"{board.fullmove_number}... {san}"
            comment = display_comment(child.comment)
            if comment:
                if len(comment) > 60:
                    comment = comment[:60] + "\u2026"
                text += f"    {{{comment}}}"
            entries.append((id(child), text))
        if not entries:
            return
        dialog = VariationChooserDialog(entries, self)
        if dialog.exec() == QDialog.Accepted:
            node_id = dialog.selected_id()
            if node_id is not None:
                node = self.doc.find_node(node_id)
                if node is not None:
                    self.doc.go_to(node)

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence(Qt.Key_Right), self, activated=self._goto_next,
                  context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_Left), self, activated=self.doc.goto_previous,
                  context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_Home), self, activated=self.doc.goto_start,
                  context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence(Qt.Key_End), self, activated=self.doc.goto_end,
                  context=Qt.WidgetWithChildrenShortcut)
        QShortcut(QKeySequence("F"), self, activated=self.board_widget.flip,
                  context=Qt.WidgetWithChildrenShortcut)

    def _on_position(self, board: chess.Board) -> None:
        self.last_move = self.doc.node.move
        self.board_widget.set_board(board, self.last_move)
        self.notation.select_node(self.doc.node)
        self.positionChanged.emit(board)
        self.titleChanged.emit(self.doc.title())

    def _on_structure(self) -> None:
        self.notation.rebuild()

    def _on_headers(self) -> None:
        headers = self.doc.game.headers
        parts = [
            headers.get("White", "?") or "?",
            headers.get("Black", "?") or "?",
            headers.get("Result", "*") or "*",
            headers.get("Event", ""),
            headers.get("Date", ""),
        ]
        self.header_label.setText(" - ".join(p for p in parts if p))
        self.titleChanged.emit(self.doc.title())

    def _on_drawings_changed(self) -> None:
        self.board_widget.set_drawings(self.doc.current_drawings())

    def _on_board_drawings_changed(self) -> None:
        self.doc.set_current_drawings(self.board_widget.get_drawings())

    def play_san(self, san: str) -> None:
        self.doc.play_san(san)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("ChessStudio", "ChessStudio")
        self.db: ChessDatabase | None = None
        self._import_thread = None
        self._import_worker = None
        self._import_dialog = None
        self._open_thread = None
        self._open_worker = None
        self._pending_open_path = ""
        self._pending_open_id: int | None = None
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

        self.game_list = GameListWidget()
        self.game_list.gameActivated.connect(self._open_game_by_id)
        self.opening_tree = OpeningTreeWidget()
        self.opening_tree.moveRequested.connect(self._opening_move)
        self.opening_tree.remoteGameRequested.connect(self._open_remote_game)
        self.engine_panel = EnginePanel()
        self.opponent_prep = OpponentPrepWidget()
        self.opponent_prep.gameSelected.connect(self._open_opponent_game)
        self.opponent_prep.prepDatabaseReady.connect(self._on_prep_database_ready)
        self.opponent_prep.referenceFilterChanged.connect(self.opening_tree.update_reference_filter)
        self.opponent_prep.explorerRequested.connect(self._show_explorer)
        self.opponent_prep.statusMessage.connect(lambda msg: self.statusBar().showMessage(msg, 6000))

        self._build_docks()
        self._build_actions()
        self._build_menus()
        self.setWindowTitle("ChessStudio")
        self.resize(1280, 820)

        geometry = self.settings.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        last = self.settings.value("db/last", "", str)
        if last and Path(last).exists():
            default_path = Path(last)
        else:
            default_path = Path.home() / "Documents" / "ChessStudio" / "default.csdb"
        self.open_database(default_path, quiet=True)

        # Arrancar el motor automáticamente (si está configurado) una vez que
        # la ventana esté visible y el bucle de eventos en marcha.
        QTimer.singleShot(200, self.engine_panel.maybe_autostart)

    # ------------------------------------------------------------------ #
    # Construcción de UI
    # ------------------------------------------------------------------ #
    def _build_docks(self) -> None:
        self.list_dock = QDockWidget("Partidas", self)
        self.list_dock.setWidget(self.game_list)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.list_dock)

        self.tree_dock = QDockWidget("Aperturas", self)
        self.tree_dock.setWidget(self.opening_tree)
        self.addDockWidget(Qt.RightDockWidgetArea, self.tree_dock)

        self.engine_dock = QDockWidget("Motor", self)
        self.engine_dock.setWidget(self.engine_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, self.engine_dock)

        self.prep_dock = QDockWidget("Preparar rival", self)
        self.prep_dock.setWidget(self.opponent_prep)
        self.addDockWidget(Qt.RightDockWidgetArea, self.prep_dock)
        self.tabifyDockWidget(self.engine_dock, self.prep_dock)
        self.engine_dock.raise_()
        self.resizeDocks([self.tree_dock, self.engine_dock], [470, 330], Qt.Vertical)

    def _build_actions(self) -> None:
        style = self.style()
        self.act_new_game = QAction(style.standardIcon(QStyle.SP_FileIcon), "Nueva partida", self)
        self.act_new_game.setShortcut(QKeySequence.New)
        self.act_new_game.triggered.connect(lambda: self.new_game_tab())

        self.act_new_db = QAction("Nueva base...", self)
        self.act_new_db.triggered.connect(self.new_database)

        self.act_open_db = QAction(style.standardIcon(QStyle.SP_DirOpenIcon), "Abrir base...", self)
        self.act_open_db.setShortcut(QKeySequence.Open)
        self.act_open_db.triggered.connect(self.open_database_dialog)

        self.act_open_pgn = QAction("Abrir PGN...", self)
        self.act_open_pgn.setShortcut("Ctrl+Shift+O")
        self.act_open_pgn.setToolTip("Abrir un archivo PGN directamente en una pestaña (conserva flechas y variantes)")
        self.act_open_pgn.triggered.connect(self.open_pgn_file)

        self.act_import = QAction("Importar PGN a la base...", self)
        self.act_import.triggered.connect(self.import_pgn)

        self.act_export = QAction("Exportar partida...", self)
        self.act_export.setToolTip(
            "Exporta únicamente la partida abierta en este momento,\n"
            "con sus comentarios, variantes y flechas (incluye cambios sin guardar)."
        )
        self.act_export.triggered.connect(self.export_pgn)

        self.act_delete_games = QAction(
            style.standardIcon(QStyle.SP_TrashIcon), "Eliminar de la base...", self
        )
        self.act_delete_games.setToolTip(
            "Elimina las partidas seleccionadas en la lista (pide confirmación)."
        )
        self.act_delete_games.triggered.connect(self.delete_selected_games)

        self.act_save = QAction(style.standardIcon(QStyle.SP_DialogSaveButton), "Guardar en base", self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.triggered.connect(self.save_current_game)

        self.act_search = QAction(style.standardIcon(QStyle.SP_FileDialogContentsView), "Buscar...", self)
        self.act_search.setShortcut("Ctrl+F")
        self.act_search.triggered.connect(self.search_games)

        self.act_properties = QAction("Propiedades...", self)
        self.act_properties.triggered.connect(self.edit_properties)

        self.act_flip = QAction("Girar tablero", self)
        self.act_flip.triggered.connect(self.flip_board)

        self.act_prep = QAction("Preparar rival", self)
        self.act_prep.setToolTip("Abrir el panel de preparación de rival")
        self.act_prep.triggered.connect(self._show_prep)

        self.act_close = QAction("Salir", self)
        self.act_close.setShortcut(QKeySequence.Quit)
        self.act_close.triggered.connect(self.close)

        toolbar = QToolBar("Principal")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for action in (self.act_new_game, self.act_open_db, self.act_open_pgn, self.act_save,
                       self.act_search, self.act_import, self.act_export, self.act_delete_games,
                       self.act_flip, self.act_prep):
            toolbar.addAction(action)

    def _build_menus(self) -> None:
        menu_file = self.menuBar().addMenu("Archivo")
        menu_file.addAction(self.act_new_db)
        menu_file.addAction(self.act_open_db)
        menu_file.addSeparator()
        menu_file.addAction(self.act_open_pgn)
        menu_file.addAction(self.act_import)
        menu_file.addAction(self.act_export)
        menu_file.addSeparator()
        menu_file.addAction(self.act_close)

        menu_game = self.menuBar().addMenu("Partida")
        menu_game.addAction(self.act_new_game)
        menu_game.addAction(self.act_save)
        menu_game.addAction(self.act_export)
        menu_game.addAction(self.act_delete_games)
        menu_game.addAction(self.act_properties)
        menu_game.addSeparator()
        menu_game.addAction(self.act_flip)
        menu_game.addAction(self.act_search)

        menu_view = self.menuBar().addMenu("Ver")
        menu_view.addAction(self.list_dock.toggleViewAction())
        menu_view.addAction(self.tree_dock.toggleViewAction())
        menu_view.addAction(self.engine_dock.toggleViewAction())
        menu_view.addAction(self.prep_dock.toggleViewAction())

        # Lista de partidas: tecla Supr y menú contextual (abrir / eliminar).
        self.game_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.game_list.customContextMenuRequested.connect(self._game_list_menu)
        del_shortcut = QShortcut(QKeySequence.Delete, self.game_list)
        del_shortcut.setContext(Qt.WidgetShortcut)
        del_shortcut.activated.connect(self.delete_selected_games)

    def _game_list_menu(self, pos) -> None:
        index = self.game_list.indexAt(pos)
        selection = self.game_list.selectionModel()
        if index.isValid() and selection is not None \
                and not selection.isRowSelected(index.row(), index.parent()):
            self.game_list.selectRow(index.row())
        menu = QMenu(self)
        act_open = menu.addAction("Abrir partida")
        act_open.setEnabled(index.isValid())
        menu.addSeparator()
        act_delete = menu.addAction("Eliminar de la base...")
        act_delete.setEnabled(bool(self.game_list.selected_ids()))
        chosen = menu.exec(self.game_list.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_open and index.isValid():
            self._open_game_by_id(self.game_list._model.game_id(index.row()))
        elif chosen == act_delete:
            self.delete_selected_games()

    # ------------------------------------------------------------------ #
    # Bases de datos
    # ------------------------------------------------------------------ #
    def open_database(self, path: Path, quiet: bool = False) -> None:
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if self.db is not None:
                self.db.close()
            self.db = ChessDatabase(path)
        except Exception as exc:
            if not quiet:
                QMessageBox.critical(self, "Error", f"No se pudo abrir la base:\n{exc}")
            return
        self.settings.setValue("db/last", str(path))
        self.opening_tree.set_database(self.db)
        self.opponent_prep.set_main_database(self.db)
        self.refresh_game_list()
        self._update_title()
        if not quiet:
            self.statusBar().showMessage(f"Base abierta: {path} ({self.db.game_count()} partidas)")

    def open_database_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir base", "", "Bases ChessStudio (*.csdb);;Todos (*)")
        if path:
            self.open_database(path)

    def new_database(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Nueva base", "", "Bases ChessStudio (*.csdb)")
        if path:
            if not path.lower().endswith(".csdb"):
                path += ".csdb"
            self.open_database(path)

    def _update_title(self) -> None:
        name = self.db.path.name if self.db is not None else "sin base"
        count = self.db.game_count() if self.db is not None else 0
        self.setWindowTitle(f"ChessStudio - {name} ({count} partidas)")

    def refresh_game_list(self, rows: list[GameRow] | None = None) -> None:
        if self.db is None:
            self.game_list.set_rows([])
            return
        if rows is None:
            rows = self.db.search(limit=5000)
        self.game_list.set_rows(rows)
        self._update_title()

    # ------------------------------------------------------------------ #
    # PGN
    # ------------------------------------------------------------------ #
    def open_pgn_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir PGN", "", "PGN (*.pgn);;Todos (*)")
        if not path:
            return
        self.start_open_pgn(path)

    def start_open_pgn(self, path: str) -> None:
        """Abre un PGN en segundo plano (testeable sin diálogo de archivo)."""
        if self._open_thread is not None:
            return  # ya hay una apertura en curso
        # Parseo en segundo plano: un PGN descargado puede ser enorme y no
        # debe congelar la ventana mientras se lee.
        self.statusBar().showMessage(f"Abriendo {Path(path).name}...")
        self._pending_open_path = path
        self._open_worker = GameParseWorker(path)
        # IMPORTANTE: conectar a un método bound (no a una lambda) para que la
        # señal se entregue en el hilo de la UI. Una lambda se ejecutaría en el
        # hilo worker y crearía widgets fuera del hilo de la GUI (crash).
        self._open_worker.ready.connect(self._on_pgn_parsed)
        self._open_worker.failed.connect(self._on_pgn_parse_failed)
        self._open_thread = run_in_thread(self._open_worker, self)
        self._open_thread.start()

    def _on_pgn_parsed(self, game, has_more: bool) -> None:
        self._open_thread = None
        self._open_worker = None
        path = self._pending_open_path
        if game is None:
            self.statusBar().clearMessage()
            QMessageBox.warning(self, "PGN vacío", "El archivo no contiene partidas válidas.")
            return
        doc = GameDoc(game)
        self.new_game_tab(doc)
        if has_more:
            QMessageBox.information(
                self, "PGN con varias partidas",
                "Este archivo contiene varias partidas. Se ha abierto la primera.\n"
                "Usa «Importar PGN a la base» para cargarlas todas, o «Preparar rival» "
                "si son las partidas de un oponente.",
            )
        else:
            self.statusBar().showMessage(f"PGN abierto: {Path(path).name}", 5000)

    def _on_pgn_parse_failed(self, message: str) -> None:
        self._open_thread = None
        self._open_worker = None
        self.statusBar().clearMessage()
        QMessageBox.critical(self, "Error", f"No se pudo leer el PGN:\n{message}")

    def import_pgn(self) -> None:
        if self.db is None:
            QMessageBox.warning(self, "Sin base", "Abre o crea una base de datos primero.")
            return
        if self._import_thread is not None:
            QMessageBox.information(self, "Importación en curso", "Ya hay una importación en marcha.")
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Importar PGN", "", "PGN (*.pgn);;Todos (*)")
        if not paths:
            return

        dialog = QProgressDialog("Importando PGN...", "Cancelar", 0, 100, self)
        dialog.setWindowTitle("Importar PGN")
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setValue(0)

        self._import_dialog = dialog
        self._import_worker = PgnImportWorker(str(self.db.path), paths)
        # Métodos bound (no lambdas) -> entregas en el hilo de la UI. El worker
        # vive en otro hilo; tocar el diálogo desde allí corrompería la memoria.
        self._import_worker.progress.connect(self._on_import_progress)
        dialog.canceled.connect(self._import_worker.cancel)
        self._import_worker.finished.connect(self._on_import_finished)
        self._import_worker.failed.connect(self._on_import_failed)
        self._import_thread = run_in_thread(self._import_worker, self)
        self._import_thread.start()

    def _on_import_progress(self, percent: int, count: int) -> None:
        dialog = self._import_dialog
        if dialog is None:
            return
        # QProgressDialog.setValue() procesa eventos internamente y puede
        # entregar la señal 'finished' de forma REENTRANTE (poniendo
        # _import_dialog a None y cerrando el diálogo). Por eso fijamos la
        # etiqueta ANTES de setValue y no volvemos a tocar el diálogo después.
        dialog.setLabelText(f"Importando... {count} partidas ({percent}%)")
        dialog.setValue(percent)

    def _on_import_finished(self, summary: dict) -> None:
        dialog = self._import_dialog
        self._import_dialog = None
        self._import_thread = None
        self._import_worker = None
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()
        self.refresh_game_list()
        self.opening_tree.refresh()
        imported = summary.get("imported", 0)
        skipped = summary.get("skipped", 0)
        note = " (cancelada)" if summary.get("cancelled") else ""
        QMessageBox.information(self, "Importación", f"Importadas {imported} partidas ({skipped} omitidas){note}.")

    def _on_import_failed(self, message: str) -> None:
        dialog = self._import_dialog
        self._import_dialog = None
        self._import_thread = None
        self._import_worker = None
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()
        QMessageBox.warning(self, "Error", f"No se pudo importar el PGN:\n{message}")

    def export_pgn(self) -> None:
        """Exporta únicamente la partida abierta en la pestaña actual.

        Incluye los cambios sin guardar (comentarios, variantes y flechas se
        reinyectan como tags PGN estándar). Escritura atómica.
        """
        window = self.current_game_window()
        if window is None:
            QMessageBox.information(
                self, "Sin partida abierta",
                "Abre una partida (doble clic en la lista o «Abrir PGN») para exportarla.",
            )
            return
        title = window.doc.title()
        safe = "".join(c for c in title if c not in '\\/:*?"<>|').strip() or "partida"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar partida", f"{safe}.pgn", "PGN (*.pgn)")
        if not path:
            return
        if not path.lower().endswith(".pgn"):
            path += ".pgn"
        target = Path(path)
        tmp = target.with_name(target.name + ".tmp")
        try:
            game = window.doc.export_game()
            tmp.write_text(str(game).strip() + "\n", encoding="utf-8")
            tmp.replace(target)  # atómico: nunca deja un archivo parcial
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            QMessageBox.warning(self, "Error", f"No se pudo exportar la partida:\n{exc}")
            return
        self.statusBar().showMessage(f"Partida exportada a {path}", 6000)

    def delete_selected_games(self) -> None:
        """Elimina de la base las partidas seleccionadas en la lista."""
        if self.db is None:
            QMessageBox.warning(self, "Sin base", "Abre una base primero.")
            return
        ids = self.game_list.selected_ids()
        if not ids:
            QMessageBox.information(
                self, "Sin selección",
                "Selecciona una o más partidas en la lista «Partidas» para eliminarlas.",
            )
            return
        answer = QMessageBox.question(
            self, "Eliminar partidas",
            f"¿Eliminar {len(ids)} partida(s) de la base?\nEsta acción no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.db.delete_games(ids)
        # Las pestañas abiertas de partidas eliminadas quedan como copias sin
        # vincular: si se guardan después, crearán una entrada nueva.
        deleted = set(ids)
        for i in range(self.tabs.count()):
            widget = self.tabs.widget(i)
            if isinstance(widget, GameWindow) and widget.db_id in deleted:
                widget.db_id = None
        self.refresh_game_list()
        self.opening_tree.refresh()
        self.statusBar().showMessage(f"{len(ids)} partida(s) eliminada(s) de la base.", 6000)

    # ------------------------------------------------------------------ #
    # Pestañas de partidas
    # ------------------------------------------------------------------ #
    def new_game_tab(self, doc: GameDoc | None = None, db_id: int | None = None) -> GameWindow:
        if doc is None:
            doc = GameDoc()
        window = GameWindow(doc, db_id=db_id)
        window.positionChanged.connect(self._on_board_changed)
        index = self.tabs.addTab(window, doc.title())
        window.titleChanged.connect(lambda title, w=window: self._rename_tab(w, title))
        self.tabs.setCurrentIndex(index)
        self._on_board_changed(doc.board)
        return window

    def _rename_tab(self, window: GameWindow, title: str) -> None:
        index = self.tabs.indexOf(window)
        if index >= 0:
            marker = " *" if window.doc.dirty else ""
            self.tabs.setTabText(index, f"{title}{marker}")

    def _close_tab(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if isinstance(widget, GameWindow) and widget.doc.dirty:
            answer = QMessageBox.question(
                self, "Cerrar partida",
                "La partida tiene cambios sin guardar. ¿Cerrar de todos modos?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        if isinstance(widget, GameWindow):
            try:
                widget.positionChanged.disconnect(self._on_board_changed)
            except (RuntimeError, TypeError):
                pass
        self.tabs.removeTab(index)
        if widget is not None:
            widget.deleteLater()

    def current_game_window(self) -> GameWindow | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, GameWindow) else None

    def _on_tab_changed(self, index: int) -> None:
        window = self.current_game_window()
        if window is not None:
            self._on_board_changed(window.doc.board)

    def _on_board_changed(self, board: chess.Board) -> None:
        self.opening_tree.set_position(board.fen())
        self.engine_panel.set_position(board)

    def _opening_move(self, san: str) -> None:
        window = self.current_game_window()
        if window is not None:
            window.play_san(san)

    def flip_board(self) -> None:
        window = self.current_game_window()
        if window is not None:
            window.board_widget.flip()

    def edit_properties(self) -> None:
        window = self.current_game_window()
        if window is None:
            return
        dialog = GamePropertiesDialog(dict(window.doc.game.headers), self)
        if dialog.exec() == QDialog.Accepted:
            window.doc.apply_headers(dialog.values())

    def save_current_game(self) -> None:
        window = self.current_game_window()
        if window is None:
            QMessageBox.information(self, "Sin partida", "No hay una partida abierta.")
            return
        if self.db is None:
            QMessageBox.warning(self, "Sin base", "Abre o crea una base primero.")
            return
        game = window.doc.export_game()
        if window.db_id is None:
            window.db_id = self.db.add_game(game)
        else:
            self.db.update_game(window.db_id, game)
        window.doc.mark_saved()
        self.refresh_game_list()
        self.opening_tree.refresh()
        self.statusBar().showMessage("Partida guardada (con comentarios y flechas).", 4000)
        self._rename_tab(window, window.doc.title())

    def search_games(self) -> None:
        if self.db is None:
            QMessageBox.warning(self, "Sin base", "Abre una base primero.")
            return
        window = self.current_game_window()
        dialog = SearchDialog(self)
        if window is not None:
            dialog.set_position(window.doc.board)
        if dialog.exec() == QDialog.Accepted:
            rows = self.db.search(**dialog.criteria())
            self.refresh_game_list(rows)
            self.statusBar().showMessage(f"{len(rows)} partida(s) encontradas.", 4000)

    def _open_game_by_id(self, game_id: int) -> None:
        if self.db is None:
            return
        row = self.db.get_game(game_id)
        if row is None:
            return
        # Las partidas normales se abren al instante en el hilo de la UI; las
        # muy grandes se parsean en segundo plano para no congelar la ventana.
        if len(row.movetext) < 20000 and self._open_thread is None:
            game = parse_stored_game(row.movetext, row.headers) or chess.pgn.Game()
            self._finish_open_db_game(game, game_id)
            return
        if self._open_thread is not None:
            return  # ya hay una apertura en curso
        self.statusBar().showMessage("Abriendo partida grande...")
        self._pending_open_id = game_id
        self._open_worker = GameTextParseWorker(row.movetext, row.headers)
        # Método bound (no lambda) -> la señal se entrega en el hilo de la UI.
        self._open_worker.ready.connect(self._on_db_game_parsed)
        self._open_worker.failed.connect(self._on_pgn_parse_failed)
        self._open_thread = run_in_thread(self._open_worker, self)
        self._open_thread.start()

    def _on_db_game_parsed(self, game) -> None:
        self._open_worker = None
        self.statusBar().clearMessage()
        self._finish_open_db_game(game, self._pending_open_id)

    def _finish_open_db_game(self, game, game_id: int | None) -> None:
        self._open_thread = None
        if game is None:
            game = chess.pgn.Game()
        doc = GameDoc(game)
        doc.mark_saved()
        self.new_game_tab(doc, db_id=game_id)

    def _open_opponent_game(self, doc: GameDoc) -> None:
        self.new_game_tab(doc)

    def _open_remote_game(self, game) -> None:
        doc = GameDoc(game)
        self.new_game_tab(doc)
        self.statusBar().showMessage("Partida de Lichess abierta en una pestaña.", 5000)

    # ------------------------------------------------------------------ #
    # Preparación de rival
    # ------------------------------------------------------------------ #
    def _on_prep_database_ready(self, database, player: str, color: str) -> None:
        self.opening_tree.set_reference_database(database, player, color)

    def _show_explorer(self) -> None:
        self.tree_dock.show()
        self.tree_dock.raise_()
        self.opening_tree.show_local_tab()

    def _show_prep(self) -> None:
        self.prep_dock.show()
        self.prep_dock.raise_()

    # ------------------------------------------------------------------ #
    # Cierre
    # ------------------------------------------------------------------ #
    def closeEvent(self, event) -> None:
        self.settings.setValue("window/geometry", self.saveGeometry())
        if self._import_worker is not None:
            self._import_worker.cancel()
            try:
                self._import_worker.finished.disconnect()
                self._import_worker.failed.disconnect()
                self._import_worker.progress.disconnect()
            except (RuntimeError, TypeError):
                pass
        if self._import_thread is not None:
            self._import_thread.quit()
            self._import_thread.wait(3000)
        if self._open_worker is not None:
            try:
                self._open_worker.ready.disconnect()
                self._open_worker.failed.disconnect()
            except (RuntimeError, TypeError):
                pass
        if self._open_thread is not None:
            self._open_thread.quit()
            self._open_thread.wait(3000)
        self.engine_panel.shutdown()
        self.opponent_prep.shutdown()
        if self.db is not None:
            self.db.close()
        super().closeEvent(event)
