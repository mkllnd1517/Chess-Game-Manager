"""Panel para construir y consultar repertorios personales de aperturas."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from chessstudio.database import ChessDatabase, PgnSource
from chessstudio.repertoire_store import Repertoire, RepertoireError, RepertoireLibrary
from chessstudio.workers import PgnImportWorker, PgnSourceRemovalWorker, run_in_thread

COLOR_DATA = ("white", "black")
COLOR_LABELS = {"white": "Con blancas", "black": "Con negras"}


class RepertoireWidget(QWidget):
    """Gestiona perfiles nombrados y sus fuentes PGN por color.

    Cada archivo aparece como una fuente independiente: al retirarlo se borran
    solo las partidas que introdujo, lo que permite mantener un repertorio
    vivo sin reimportar todo el conjunto.
    """

    repertoireDatabaseReady = Signal(object, str, str)  # ChessDatabase|None, nombre, color
    comparisonRequested = Signal()
    statusMessage = Signal(str)

    def __init__(self, parent: QWidget | None = None, library: RepertoireLibrary | None = None):
        super().__init__(parent)
        self.library = library or RepertoireLibrary()
        self._profiles: list[Repertoire] = []
        self._current: Repertoire | None = None
        self._databases: dict[str, ChessDatabase] = {}
        self._active_in_explorer = False
        self._thread = None
        self._worker = None
        self._setup_ui()
        self.reload_profiles()

    # ------------------------------------------------------------------ #
    # Interfaz
    # ------------------------------------------------------------------ #
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        group = QGroupBox("Repertorio")
        group_layout = QVBoxLayout(group)
        chooser = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip("Elige el repertorio que quieres editar o estudiar.")
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        chooser.addWidget(self.profile_combo, 1)
        self.new_button = QPushButton("Nuevo...")
        self.new_button.clicked.connect(self._create_profile)
        chooser.addWidget(self.new_button)
        self.rename_button = QPushButton("Renombrar...")
        self.rename_button.clicked.connect(self._rename_profile)
        chooser.addWidget(self.rename_button)
        self.delete_button = QPushButton("Eliminar...")
        self.delete_button.clicked.connect(self._delete_profile)
        chooser.addWidget(self.delete_button)
        group_layout.addLayout(chooser)

        self.profile_info = QLabel()
        self.profile_info.setWordWrap(True)
        self.profile_info.setTextFormat(Qt.PlainText)
        self.profile_info.setStyleSheet("color:#667085;")
        group_layout.addWidget(self.profile_info)
        layout.addWidget(group)

        self.color_tabs = QTabWidget()
        self.color_tabs.addTab(QWidget(), COLOR_LABELS["white"])
        self.color_tabs.addTab(QWidget(), COLOR_LABELS["black"])
        self.color_tabs.currentChanged.connect(self._on_color_changed)
        layout.addWidget(self.color_tabs)

        source_group = QGroupBox("Archivos PGN incluidos")
        sources_layout = QVBoxLayout(source_group)
        self.sources_label = QLabel("Crea o selecciona un repertorio para añadir PGN.")
        self.sources_label.setWordWrap(True)
        self.sources_label.setTextFormat(Qt.PlainText)
        sources_layout.addWidget(self.sources_label)
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.source_list.setAlternatingRowColors(True)
        self.source_list.setToolTip("Cada fila es un PGN importado. Selecciona uno o varios para retirarlos.")
        sources_layout.addWidget(self.source_list, 1)
        source_actions = QHBoxLayout()
        self.add_button = QPushButton("Añadir PGN...")
        self.add_button.clicked.connect(self._add_pgn)
        source_actions.addWidget(self.add_button)
        self.remove_button = QPushButton("Quitar seleccionados")
        self.remove_button.clicked.connect(self._remove_sources)
        source_actions.addWidget(self.remove_button)
        sources_layout.addLayout(source_actions)
        layout.addWidget(source_group, 1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        self.import_status = QLabel("")
        self.import_status.setWordWrap(True)
        self.import_status.setTextFormat(Qt.PlainText)
        self.import_status.setVisible(False)
        layout.addWidget(self.import_status)

        explorer_group = QGroupBox("Analizar")
        explorer_layout = QVBoxLayout(explorer_group)
        self.use_button = QPushButton("Usar este repertorio en Aperturas")
        self.use_button.setToolTip(
            "Muestra las continuaciones de este color en el explorador de aperturas.")
        self.use_button.clicked.connect(self._use_in_explorer)
        explorer_layout.addWidget(self.use_button)
        self.compare_button = QPushButton("Comparar este repertorio con el rival")
        self.compare_button.setToolTip(
            "Resalta en Aperturas las continuaciones que el rival juega y que coinciden con este repertorio.")
        self.compare_button.clicked.connect(self._compare_with_opponent)
        explorer_layout.addWidget(self.compare_button)
        layout.addWidget(explorer_group)

    # ------------------------------------------------------------------ #
    # Perfiles y bases por color
    # ------------------------------------------------------------------ #
    @property
    def current_color(self) -> str:
        return COLOR_DATA[max(0, self.color_tabs.currentIndex())]

    def reload_profiles(self, selected_id: str | None = None) -> None:
        try:
            self._profiles = self.library.list()
        except RepertoireError as exc:
            self._profiles = []
            QMessageBox.critical(self, "Repertorios", str(exc))
        if selected_id is None and self._current is not None:
            selected_id = self._current.identifier
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for profile in self._profiles:
            self.profile_combo.addItem(profile.name, profile.identifier)
        self.profile_combo.blockSignals(False)
        index = self.profile_combo.findData(selected_id) if selected_id else -1
        if index < 0 and self.profile_combo.count():
            index = 0
        self.profile_combo.setCurrentIndex(index)
        self._set_current_by_id(self.profile_combo.currentData() if index >= 0 else None)

    def _set_current_by_id(self, identifier: str | None) -> None:
        profile = next((item for item in self._profiles if item.identifier == identifier), None)
        if profile is self._current or (profile and self._current and profile.identifier == self._current.identifier):
            self._refresh_sources()
            self._update_controls()
            return
        self._clear_explorer_reference()
        self._close_databases()
        self._current = profile
        self._refresh_sources()
        self._update_controls()

    def _database(self, color: str | None = None) -> ChessDatabase | None:
        if self._current is None:
            return None
        color = color or self.current_color
        db = self._databases.get(color)
        if db is None:
            db = ChessDatabase(self.library.database_path(self._current, color))
            # Los repertorios creados antes de la indexación por variantes se
            # actualizan una vez al abrirse. Las partidas habituales no usan
            # esta ruta y continúan indexando solo la línea principal.
            converted = db.enable_variation_index_for_sources()
            self._databases[color] = db
            if converted:
                self.statusMessage.emit(
                    f"Repertorio actualizado: {converted} partida(s) indexada(s) con todas sus variantes."
                )
        return db

    def _close_databases(self) -> None:
        for db in self._databases.values():
            try:
                db.close()
            except Exception:
                pass
        self._databases.clear()

    def _clear_explorer_reference(self) -> None:
        if self._active_in_explorer:
            self.repertoireDatabaseReady.emit(None, "", "both")
        self._active_in_explorer = False

    def _on_profile_changed(self, _index: int) -> None:
        if self._thread is None:
            self._set_current_by_id(self.profile_combo.currentData())

    def _on_color_changed(self, _index: int) -> None:
        self._refresh_sources()
        if self._active_in_explorer:
            self._emit_active_database()

    def _create_profile(self) -> None:
        name, accepted = QInputDialog.getText(self, "Nuevo repertorio", "Nombre:")
        if not accepted:
            return
        try:
            profile = self.library.create(name)
        except RepertoireError as exc:
            QMessageBox.warning(self, "Nuevo repertorio", str(exc))
            return
        self.reload_profiles(profile.identifier)
        self.statusMessage.emit(f"Repertorio «{profile.name}» creado.")

    def _rename_profile(self) -> None:
        if self._current is None:
            return
        name, accepted = QInputDialog.getText(
            self, "Renombrar repertorio", "Nombre:", text=self._current.name
        )
        if not accepted:
            return
        try:
            renamed = self.library.rename(self._current.identifier, name)
        except RepertoireError as exc:
            QMessageBox.warning(self, "Renombrar repertorio", str(exc))
            return
        was_active = self._active_in_explorer
        self._current = renamed
        self.reload_profiles(renamed.identifier)
        if was_active:
            self._emit_active_database()
        self.statusMessage.emit(f"Repertorio renombrado a «{renamed.name}».")

    def _delete_profile(self) -> None:
        if self._current is None:
            return
        answer = QMessageBox.question(
            self,
            "Eliminar repertorio",
            f"¿Eliminar «{self._current.name}» y sus repertorios de blancas y negras?\n"
            "Los PGN originales no se borrarán, pero esta base no se puede recuperar.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        deleted_name = self._current.name
        identifier = self._current.identifier
        self._clear_explorer_reference()
        self._close_databases()
        try:
            self.library.delete(identifier)
        except RepertoireError as exc:
            QMessageBox.warning(self, "Eliminar repertorio", str(exc))
            return
        self._current = None
        self.reload_profiles()
        self.statusMessage.emit(f"Repertorio «{deleted_name}» eliminado.")

    # ------------------------------------------------------------------ #
    # Archivos PGN
    # ------------------------------------------------------------------ #
    def _refresh_sources(self) -> None:
        self.source_list.clear()
        if self._current is None:
            self.sources_label.setText("Crea o selecciona un repertorio para añadir PGN.")
            self.profile_info.setText("Los repertorios de blancas y negras se guardan por separado.")
            return
        db = self._database()
        if db is None:
            return
        sources = db.list_sources()
        color_text = COLOR_LABELS[self.current_color].lower()
        total = db.game_count()
        self.profile_info.setText(
            f"«{self._current.name}» · {color_text}: {total} partida(s) en {len(sources)} archivo(s)."
        )
        if sources:
            self.sources_label.setText(
                "Cada archivo puede quitarse por separado. Sus partidas se retirarán del repertorio actual."
            )
        else:
            self.sources_label.setText(f"Aún no hay PGN añadidos al repertorio {color_text}.")
        for source in sources:
            indexed = "todas las variantes" if source.include_variations else "línea principal"
            item = QListWidgetItem(f"{source.label}  —  {source.game_count} partida(s) · {indexed}")
            item.setData(Qt.UserRole, source.id)
            item.setToolTip(f"Importado: {source.imported_at}\nÍndice: {indexed}.")
            self.source_list.addItem(item)

    def _add_pgn(self) -> None:
        db = self._database()
        if db is None or self._thread is not None:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Añadir PGN al repertorio", "", "PGN (*.pgn);;Todos los archivos (*)"
        )
        if not paths:
            return
        labels = [Path(path).name for path in paths]
        self._worker = PgnImportWorker(
            str(db.path), paths, source_labels=labels, include_variations=True
        )
        self._worker.progress.connect(self._on_import_progress)
        self._worker.finished.connect(self._on_import_finished)
        self._worker.failed.connect(self._on_import_failed)
        self._thread = run_in_thread(self._worker, self)
        self._set_busy(True)
        self._thread.start()

    def _on_import_progress(self, percent: int, count: int) -> None:
        self.progress.setValue(percent)
        self.import_status.setText(f"Importando... {count} partida(s) ({percent}%).")

    def _on_import_finished(self, summary: dict) -> None:
        self._finish_import()
        self._refresh_sources()
        if self._active_in_explorer:
            self._emit_active_database()
        imported = int(summary.get("imported", 0))
        skipped = int(summary.get("skipped", 0))
        note = " (cancelada)" if summary.get("cancelled") else ""
        self.statusMessage.emit(f"Repertorio actualizado: {imported} partida(s) añadidas, {skipped} omitidas{note}.")

    def _on_import_failed(self, message: str) -> None:
        self._finish_import()
        QMessageBox.warning(self, "Añadir PGN", f"No se pudo importar el archivo:\n{message}")

    def _finish_import(self) -> None:
        self._thread = None
        self._worker = None
        self.progress.setVisible(False)
        self.import_status.setVisible(False)
        self._set_busy(False)

    def _remove_sources(self) -> None:
        db = self._database()
        items = self.source_list.selectedItems()
        if db is None or not items or self._thread is not None:
            return
        count = len(items)
        answer = QMessageBox.question(
            self,
            "Quitar archivos del repertorio",
            f"¿Quitar {count} archivo(s) y todas sus partidas del repertorio "
            f"{COLOR_LABELS[self.current_color].lower()}?\nLos archivos PGN originales no se borrarán.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        # Quitar miles de partidas e índices puede tardar; el worker usa una
        # conexión SQLite propia para que el tablero y la ventana sigan vivos.
        source_ids = [int(item.data(Qt.UserRole)) for item in items]
        self._worker = PgnSourceRemovalWorker(str(db.path), source_ids)
        self._worker.progress.connect(self._on_remove_progress)
        self._worker.finished.connect(self._on_remove_finished)
        self._worker.failed.connect(self._on_remove_failed)
        self._thread = run_in_thread(self._worker, self)
        self._set_busy(True)
        self.import_status.setText("Retirando partidas del repertorio...")
        self._thread.start()

    def _on_remove_progress(self, percent: int, count: int) -> None:
        self.progress.setValue(percent)
        self.import_status.setText(f"Retirando... {count} partida(s) ({percent}%).")

    def _on_remove_finished(self, removed: int) -> None:
        self._finish_import()
        self._refresh_sources()
        if self._active_in_explorer:
            self._emit_active_database()
        self.statusMessage.emit(f"{removed} partida(s) retirada(s) del repertorio.")

    def _on_remove_failed(self, message: str) -> None:
        self._finish_import()
        QMessageBox.warning(self, "Quitar archivos", f"No se pudieron retirar las partidas:\n{message}")

    # ------------------------------------------------------------------ #
    # Explorador de aperturas
    # ------------------------------------------------------------------ #
    def _use_in_explorer(self) -> None:
        if self._database() is None:
            return
        self._active_in_explorer = True
        self._emit_active_database()
        self.statusMessage.emit(
            f"Repertorio «{self._current.name}» ({COLOR_LABELS[self.current_color].lower()}) activo en Aperturas."
        )

    def _emit_active_database(self) -> None:
        db = self._database()
        if db is not None and self._current is not None:
            self.repertoireDatabaseReady.emit(db, self._current.name, self.current_color)

    def _compare_with_opponent(self) -> None:
        self._use_in_explorer()
        if self._active_in_explorer:
            self.comparisonRequested.emit()

    def _update_controls(self) -> None:
        active = self._current is not None
        busy = self._thread is not None
        for widget in (
            self.rename_button,
            self.delete_button,
            self.add_button,
            self.remove_button,
            self.use_button,
            self.compare_button,
            self.color_tabs,
        ):
            widget.setEnabled(active and not busy)
        self.profile_combo.setEnabled(not busy)
        self.new_button.setEnabled(not busy)

    def _set_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.import_status.setVisible(busy)
        if busy:
            self.progress.setValue(0)
            self.import_status.setText("Preparando importación...")
        self._update_controls()

    def shutdown(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                self._worker.progress.disconnect()
                self._worker.finished.disconnect()
                self._worker.failed.disconnect()
            except (RuntimeError, TypeError):
                pass
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
        self._clear_explorer_reference()
        self._close_databases()
