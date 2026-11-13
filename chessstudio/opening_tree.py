"""Explorador de aperturas (panel derecho).

Pestaña "Base local": estadísticas de la base principal y, en columnas
verdes, las del rival cuando hay una preparación activa.

Pestaña "Lichess": explorador online (Maestros / Lichess) vía API, con
filtros de ritmo y Elo, token gratuito, actualización automática al mover
(con rebote de 450 ms para no saturar la API) y descarga de partidas
destacadas con doble clic.
"""
from __future__ import annotations

import chess
from PySide6.QtCore import Qt, QTimer, QSettings, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chessstudio.lichess_explorer import (
    ALL_SPEEDS,
    RATING_PRESETS,
    SPEED_LABELS,
    TOKEN_URL,
    LichessExplorer,
)
from chessstudio.secure_store import get_token, set_token, storage_description

REF_BG = QColor("#e8f5e9")
COMMON_BG = QColor("#fff8e1")
ERROR_STYLE = "color:#c62828;"
OK_STYLE = "color:#2e7d32;"


class OpeningTreeWidget(QWidget):
    moveRequested = Signal(str)
    remoteGameRequested = Signal(object)  # chess.pgn.Game

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.database = None
        # reference_db es la base de preparación del rival. repertoire_db es
        # independiente: contiene únicamente el repertorio elegido por el
        # usuario (blancas o negras) y puede compararse contra el rival.
        self.reference_db = None
        self.ref_player = ""
        self.ref_color = "both"
        self.repertoire_db = None
        self.repertoire_name = ""
        self.repertoire_color = "both"
        self._scope = "main"  # main | rival | compare | repertoire | repertoire_compare
        self._fen = chess.STARTING_FEN
        self._lichess_key = ""
        self._settings = QSettings("ChessStudio", "ChessStudio")

        self.explorer = LichessExplorer(self)
        self.explorer.set_token(get_token())
        self.explorer.dataReady.connect(self._on_lichess_data)
        self.explorer.failed.connect(self._on_lichess_error)
        self.explorer.gameReady.connect(self._on_remote_game)
        self.explorer.gameFailed.connect(lambda msg: self._set_lichess_status(msg, error=True))

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(450)
        self._debounce.timeout.connect(self._fetch_lichess)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_local_tab(), "Base local")
        self.tabs.addTab(self._build_lichess_tab(), "Lichess")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.tabs)
        self._rebuild_scope_choices()

    # ------------------------------------------------------------------ #
    # Construcción de UI
    # ------------------------------------------------------------------ #
    def _build_local_tab(self) -> QWidget:
        widget = QWidget()

        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Ver:"))
        self.scope_combo = QComboBox()
        self.scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        self.scope_combo.setEnabled(False)
        scope_row.addWidget(self.scope_combo, 1)
        scope_widget = QWidget()
        scope_widget.setLayout(scope_row)

        self.info = QLabel("Sin base de datos abierta.")
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.PlainText)  # nombres del PGN no confiables
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Jugada", "Partidas", "%B", "%T", "%N", "Año", "Rival", "R %B"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(46)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for column in range(1, 8):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setColumnHidden(6, True)
        self.table.setColumnHidden(7, True)
        self.table.cellDoubleClicked.connect(self._on_local_double_click)

        hint = QLabel("Doble clic en una jugada para jugarla en el tablero.")
        hint.setStyleSheet("color:#777;")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(scope_widget)
        layout.addWidget(self.info)
        layout.addWidget(self.table, 1)
        layout.addWidget(hint)
        return widget

    def _build_lichess_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 0)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Fuente:"))
        self.source_combo = QComboBox()
        self.source_combo.addItem("Maestros (OTB)", "masters")
        self.source_combo.addItem("Lichess (online)", "lichess")
        saved_source = self._settings.value("lichess/source", "masters", str)
        idx = self.source_combo.findData(saved_source)
        if idx >= 0:
            self.source_combo.setCurrentIndex(idx)
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        row1.addWidget(self.source_combo, 1)
        self.auto_check = QCheckBox("Auto")
        self.auto_check.setToolTip("Consultar automáticamente al cambiar la posición del tablero")
        self.auto_check.setChecked(self._settings.value("lichess/auto", True, bool))
        self.auto_check.toggled.connect(self._on_auto_toggled)
        row1.addWidget(self.auto_check)
        self.refresh_button = QPushButton("Actualizar")
        self.refresh_button.clicked.connect(self._fetch_lichess)
        row1.addWidget(self.refresh_button)
        layout.addLayout(row1)

        self.filters_row = QWidget()
        filters_layout = QHBoxLayout(self.filters_row)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        self.speed_checks: dict[str, QCheckBox] = {}
        saved_speeds = self._settings.value("lichess/speeds", ["blitz", "rapid", "classical"])
        if isinstance(saved_speeds, str):
            saved_speeds = saved_speeds.split(",") if saved_speeds else []
        for speed in ALL_SPEEDS:
            check = QCheckBox(SPEED_LABELS[speed])
            check.setChecked(speed in saved_speeds)
            check.toggled.connect(self._on_filters_changed)
            self.speed_checks[speed] = check
            filters_layout.addWidget(check)
        self.rating_combo = QComboBox()
        for label in RATING_PRESETS:
            self.rating_combo.addItem(label)
        saved_rating = self._settings.value("lichess/ratings", "Todos los Elo", str)
        if saved_rating in RATING_PRESETS:
            self.rating_combo.setCurrentText(saved_rating)
        self.rating_combo.currentTextChanged.connect(self._on_filters_changed)
        filters_layout.addWidget(self.rating_combo, 1)
        layout.addWidget(self.filters_row)

        token_row = QHBoxLayout()
        token_row.addWidget(QLabel("Token:"))
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.Password)
        self.token_edit.setPlaceholderText("Token gratuito de Lichess (obligatorio desde 2026)")
        self.token_edit.setText(get_token())
        self.token_edit.editingFinished.connect(self._on_token_changed)
        token_row.addWidget(self.token_edit, 1)
        self.token_help = QLabel(f'<a href="{TOKEN_URL}">Crear token</a>')
        self.token_help.setOpenExternalLinks(True)
        self.token_help.setToolTip(
            "Abre lichess.org/account/oauth/token en el navegador.\n"
            "Crea un token SIN marcar ningún permiso y pégalo aquí."
        )
        token_row.addWidget(self.token_help)
        layout.addLayout(token_row)

        self.token_storage_label = QLabel(f"Token guardado en: {storage_description()}.")
        self.token_storage_label.setStyleSheet("color:#888; font-size:8pt;")
        self.token_storage_label.setWordWrap(True)
        layout.addWidget(self.token_storage_label)

        self.lichess_status = QLabel("Pulsa Actualizar para consultar esta posición.")
        self.lichess_status.setWordWrap(True)
        layout.addWidget(self.lichess_status)

        self.lichess_table = QTableWidget(0, 6)
        self.lichess_table.setHorizontalHeaderLabels(
            ["Jugada", "Partidas", "%B", "%T", "%N", "Elo medio"]
        )
        self.lichess_table.verticalHeader().setVisible(False)
        self.lichess_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lichess_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lichess_table.setSelectionMode(QAbstractItemView.SingleSelection)
        header = self.lichess_table.horizontalHeader()
        header.setMinimumSectionSize(46)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for column in range(1, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.lichess_table.cellDoubleClicked.connect(self._on_lichess_double_click)
        layout.addWidget(self.lichess_table, 3)

        layout.addWidget(QLabel("Partidas destacadas (doble clic para abrirlas):"))
        self.games_list = QListWidget()
        self.games_list.itemDoubleClicked.connect(self._on_game_double_click)
        layout.addWidget(self.games_list, 2)

        self._on_source_changed()
        return widget

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def set_database(self, database) -> None:
        self.database = database
        self._rebuild_scope_choices()
        self.refresh()

    def set_reference_database(self, database, player: str = "", color: str = "both") -> None:
        """Activa o retira la base de preparación del rival."""
        self.reference_db = database
        self.ref_player = player
        self.ref_color = color
        if database is not None:
            # Se conserva el comportamiento original: al abrir una preparación
            # el explorador muestra primero el rival.
            self._scope = "rival"
            self.tabs.setCurrentIndex(0)
        elif self._scope in {"rival", "compare", "repertoire_compare"}:
            self._scope = "repertoire" if self.repertoire_db is not None else "main"
        self._rebuild_scope_choices()
        self.refresh()

    def set_repertoire_database(self, database, name: str = "", color: str = "both") -> None:
        """Activa un repertorio como fuente del explorador.

        La base se mantiene separada de la colección general y de la
        preparación del rival. El color es informativo: cada repertorio tiene
        una base independiente de blancas y otra de negras.
        """
        self.repertoire_db = database
        self.repertoire_name = name
        self.repertoire_color = color
        if database is not None:
            self._scope = "repertoire"
            self.tabs.setCurrentIndex(0)
        elif self._scope in {"repertoire", "repertoire_compare"}:
            self._scope = "rival" if self.reference_db is not None else "main"
        self._rebuild_scope_choices()
        self.refresh()

    def show_repertoire_comparison(self) -> bool:
        """Muestra las líneas coincidentes entre el repertorio y el rival."""
        if self.repertoire_db is None or self.reference_db is None:
            return False
        self._scope = "repertoire_compare"
        self._rebuild_scope_choices()
        self.tabs.setCurrentIndex(0)
        self.refresh()
        return True

    def _rebuild_scope_choices(self) -> None:
        """Actualiza el selector sin mostrar opciones que no tienen base."""
        entries: list[tuple[str, str]] = []
        if self.database is not None:
            entries.append(("Base principal", "main"))
        if self.repertoire_db is not None:
            color = {"white": "blancas", "black": "negras"}.get(self.repertoire_color, "ambos colores")
            entries.append((f"Repertorio: {self.repertoire_name or 'sin nombre'} ({color})", "repertoire"))
        if self.reference_db is not None:
            entries.append(("Solo rival (base de preparación)", "rival"))
            if self.database is not None:
                entries.append(("Base principal + rival", "compare"))
            if self.repertoire_db is not None:
                entries.append(("Repertorio + rival · líneas coincidentes", "repertoire_compare"))
        if not entries:
            entries.append(("Sin fuente disponible", "main"))
        if self._scope not in {value for _, value in entries}:
            self._scope = entries[0][1]
        self.scope_combo.blockSignals(True)
        self.scope_combo.clear()
        for label, value in entries:
            self.scope_combo.addItem(label, value)
        self.scope_combo.setCurrentIndex(max(0, self.scope_combo.findData(self._scope)))
        self.scope_combo.setEnabled(len(entries) > 1)
        self.scope_combo.blockSignals(False)

    def _on_scope_changed(self) -> None:
        self._scope = self.scope_combo.currentData() or "main"
        self.refresh()

    def update_reference_filter(self, player: str, color: str) -> None:
        self.ref_player = player
        self.ref_color = color
        self.refresh()

    def set_position(self, fen: str) -> None:
        if fen == self._fen:
            return
        self._fen = fen
        self.refresh()
        if self.tabs.currentIndex() == 1 and self.auto_check.isChecked():
            self._debounce.start()

    def show_local_tab(self) -> None:
        self.tabs.setCurrentIndex(0)

    # ------------------------------------------------------------------ #
    # Base local (+ rival)
    # ------------------------------------------------------------------ #
    def _safe_stats(self, db, player: str = "", color: str = "both") -> list:
        if db is None:
            return []
        try:
            return db.opening_stats(self._fen, player, color)
        except Exception:
            return []

    @staticmethod
    def _stat_values(move: str, stat) -> list:
        if stat and stat.games:
            draws = stat.draws / stat.games * 100.0
            white = stat.white_score
            black = max(0.0, 100.0 - white - draws)
            year = str(stat.last_game_year) if stat.last_game_year else "—"
            return [move, str(stat.games), f"{white:.0f}%", f"{draws:.0f}%", f"{black:.0f}%", year]
        return [move, "0", "—", "—", "—", "—"]

    def refresh(self) -> None:
        self.table.setRowCount(0)
        if self.database is None and self.reference_db is None and self.repertoire_db is None:
            self.info.setText("Sin base de datos abierta.")
            self.table.setColumnHidden(6, True)
            self.table.setColumnHidden(7, True)
            return

        scope = self._scope
        compare = scope in {"compare", "repertoire_compare"}
        self.table.setColumnHidden(6, not compare)
        self.table.setColumnHidden(7, not compare)
        self.table.setHorizontalHeaderLabels(
            ["Jugada", "Partidas", "%B", "%T", "%N", "Año", "Rival", "R %B"]
        )

        # Elegir una fuente principal no mezcla bases: así el usuario puede
        # estudiar su colección, el repertorio o el rival con el mismo tablero.
        if scope == "rival":
            primary_stats = self._safe_stats(self.reference_db, self.ref_player, self.ref_color)
            who = self.ref_player or "todos los jugadores"
            color_txt = {"white": " con blancas", "black": " con negras"}.get(self.ref_color, "")
            primary_label = f"Base del rival: {who}{color_txt}"
        elif scope in {"repertoire", "repertoire_compare"}:
            primary_stats = self._safe_stats(self.repertoire_db)
            color_txt = {"white": "blancas", "black": "negras"}.get(self.repertoire_color, "")
            primary_label = f"Repertorio «{self.repertoire_name or 'sin nombre'}» ({color_txt})"
        else:
            primary_stats = self._safe_stats(self.database)
            primary_label = "Base principal"

        ref_stats = self._safe_stats(self.reference_db, self.ref_player, self.ref_color) if compare else []
        primary_dict = {s.san: s for s in primary_stats}
        ref_dict = {s.san: s for s in ref_stats}
        all_moves = set(primary_dict) | set(ref_dict)
        if not all_moves:
            self.info.setText(f"{primary_label}: sin partidas en esta posición.")
            return

        primary_total = sum(s.games for s in primary_stats)
        text = f"{primary_label}: {primary_total} partidas"
        if compare:
            ref_total = sum(s.games for s in ref_stats)
            common = sum(1 for move in all_moves if move in primary_dict and move in ref_dict)
            text += f"  ·  Rival {self.ref_player or 'todos'}: {ref_total}"
            if scope == "repertoire_compare":
                if common:
                    text += f"  ·  {common} continuación(es) coincidente(s)"
                else:
                    text += "  ·  Sin continuaciones coincidentes"
        self.info.setText(text + ".")

        sorted_moves = sorted(
            all_moves,
            key=lambda m: (
                -(primary_dict[m].games if m in primary_dict else 0),
                -(ref_dict[m].games if m in ref_dict else 0),
                m,
            ),
        )
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(sorted_moves))
        for row, move in enumerate(sorted_moves):
            pstat = primary_dict.get(move)
            rstat = ref_dict.get(move)
            values = self._stat_values(move, pstat)
            if compare:
                if rstat and rstat.games:
                    values += [str(rstat.games), f"{rstat.white_score:.0f}%"]
                else:
                    values += ["—", "—"]
            else:
                values += ["", ""]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column > 0:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if compare and column >= 6 and rstat and rstat.games:
                    item.setBackground(REF_BG)
                if scope == "repertoire_compare" and pstat and rstat and column == 0:
                    item.setBackground(COMMON_BG)
                    item.setToolTip("Esta continuación aparece en el repertorio y en las partidas del rival.")
                self.table.setItem(row, column, item)
        self.table.setUpdatesEnabled(True)

    def _on_local_double_click(self, row: int, column: int) -> None:
        item = self.table.item(row, 0)
        if item is not None:
            self.moveRequested.emit(item.text())

    # ------------------------------------------------------------------ #
    # Lichess
    # ------------------------------------------------------------------ #
    def _on_tab_changed(self, index: int) -> None:
        if index == 1 and self.auto_check.isChecked():
            self._fetch_lichess()

    def _on_source_changed(self) -> None:
        source = self.source_combo.currentData()
        self.filters_row.setVisible(source == "lichess")
        self._settings.setValue("lichess/source", source)
        if self.tabs.currentIndex() == 1:
            self._fetch_lichess()

    def _on_filters_changed(self) -> None:
        self._settings.setValue(
            "lichess/speeds", [s for s, c in self.speed_checks.items() if c.isChecked()]
        )
        self._settings.setValue("lichess/ratings", self.rating_combo.currentText())
        if self.tabs.currentIndex() == 1:
            self._debounce.start()

    def _on_auto_toggled(self, checked: bool) -> None:
        self._settings.setValue("lichess/auto", checked)
        if checked and self.tabs.currentIndex() == 1:
            self._fetch_lichess()

    def _on_token_changed(self) -> None:
        token = self.token_edit.text().strip()
        set_token(token)
        self.explorer.set_token(token)
        self.token_storage_label.setText(f"Token guardado en: {storage_description()}.")
        if self.tabs.currentIndex() == 1:
            self._fetch_lichess()

    def _set_lichess_status(self, text: str, error: bool = False) -> None:
        self.lichess_status.setStyleSheet(ERROR_STYLE if error else "")
        self.lichess_status.setText(text)

    def _fetch_lichess(self) -> None:
        source = self.source_combo.currentData()
        speeds = [s for s, c in self.speed_checks.items() if c.isChecked()]
        if source == "lichess" and not speeds:
            self._set_lichess_status("Selecciona al menos un ritmo de juego.", error=True)
            return
        ratings = RATING_PRESETS.get(self.rating_combo.currentText(), RATING_PRESETS["Todos los Elo"])
        self._set_lichess_status("Consultando Lichess…")
        self._lichess_key = self.explorer.request(self._fen, source, speeds, ratings)

    def _on_lichess_error(self, key: str, message: str) -> None:
        if key != self._lichess_key:
            return
        self._set_lichess_status(message, error=True)

    def _on_lichess_data(self, key: str, data: dict) -> None:
        if key != self._lichess_key:
            return
        self.lichess_table.setRowCount(0)
        self.games_list.clear()

        total = int(data.get("white", 0)) + int(data.get("draws", 0)) + int(data.get("black", 0))
        opening = data.get("opening") or {}
        opening_text = ""
        if opening.get("eco") or opening.get("name"):
            opening_text = f"{opening.get('eco', '')} · {opening.get('name', '')} — "
        if total == 0:
            self._set_lichess_status(opening_text + "Sin partidas en esta posición.")
            return
        white_pct = int(data.get("white", 0)) / total * 100.0
        draw_pct = int(data.get("draws", 0)) / total * 100.0
        black_pct = int(data.get("black", 0)) / total * 100.0
        self._set_lichess_status(
            f"{opening_text}{total:,} partidas · B {white_pct:.0f}% / T {draw_pct:.0f}% / N {black_pct:.0f}%"
        )
        self.lichess_status.setStyleSheet(OK_STYLE)

        moves = data.get("moves") or []
        self.lichess_table.setUpdatesEnabled(False)
        self.lichess_table.setRowCount(len(moves))
        for row, move in enumerate(moves):
            games = int(move.get("white", 0)) + int(move.get("draws", 0)) + int(move.get("black", 0))
            if games:
                w = int(move.get("white", 0)) / games * 100.0
                d = int(move.get("draws", 0)) / games * 100.0
                b = int(move.get("black", 0)) / games * 100.0
                values = [move.get("san", "?"), f"{games:,}", f"{w:.0f}%", f"{d:.0f}%", f"{b:.0f}%"]
            else:
                values = [move.get("san", "?"), "0", "—", "—", "—"]
            rating = move.get("averageRating")
            values.append(str(rating) if rating else "—")
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column > 0:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.lichess_table.setItem(row, column, item)
        self.lichess_table.setUpdatesEnabled(True)

        featured = data.get("topGames") or data.get("recentGames") or []
        for game in featured[:8]:
            game_id = game.get("id", "")
            if not game_id:
                continue
            white = game.get("white") or {}
            black = game.get("black") or {}
            winner = game.get("winner")
            result = {"white": "1-0", "black": "0-1"}.get(winner, "½-½")
            year = game.get("year", "")
            text = (
                f"{white.get('name', '?')} ({white.get('rating', '?')}) - "
                f"{black.get('name', '?')} ({black.get('rating', '?')})  {result}  {year}"
            )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, game_id)
            self.games_list.addItem(item)

    def _on_lichess_double_click(self, row: int, column: int) -> None:
        item = self.lichess_table.item(row, 0)
        if item is not None:
            self.moveRequested.emit(item.text())

    def _on_game_double_click(self, item: QListWidgetItem) -> None:
        game_id = item.data(Qt.UserRole)
        if game_id:
            self._set_lichess_status("Descargando partida de Lichess…")
            self.explorer.fetch_game(str(game_id))

    def _on_remote_game(self, game) -> None:
        self._set_lichess_status("Partida descargada y abierta en una pestaña.")
        self.remoteGameRequested.emit(game)
