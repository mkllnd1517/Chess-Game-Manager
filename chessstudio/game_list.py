"""Lista de partidas con modelo/vista (QTableView + QAbstractTableModel).

Antes se usaba QTableWidget, que crea un QTableWidgetItem por celda (35.000
objetos para 5000 partidas) y bloqueaba la interfaz al refrescar. Con un
modelo bajo demanda, solo se consultan las filas visibles: el refresco es
prácticamente instantáneo incluso con decenas de miles de partidas.
"""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

COLUMNS = ["#", "Blancas", "Negras", "Resultado", "Fecha", "Evento", "ECO"]


class GameListModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list = []

    def set_rows(self, rows: list) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = index.column()
        if role == Qt.DisplayRole:
            return (row.id, row.white, row.black, row.result, row.date, row.event, row.eco)[column]
        if role == Qt.UserRole:
            return row.id
        if role == Qt.TextAlignmentRole and column == 0:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    def sort(self, column: int, order=Qt.AscendingOrder) -> None:
        keys = (
            lambda r: r.id,
            lambda r: r.white.lower(),
            lambda r: r.black.lower(),
            lambda r: r.result,
            lambda r: r.date,
            lambda r: r.event.lower(),
            lambda r: r.eco.lower(),
        )
        if not 0 <= column < len(keys):
            return
        self.layoutAboutToBeChanged.emit()
        self._rows.sort(key=keys[column], reverse=(order == Qt.DescendingOrder))
        self.layoutChanged.emit()

    def game_id(self, row: int) -> int:
        return self._rows[row].id


class GameListWidget(QTableView):
    gameActivated = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = GameListModel(self)
        self.setModel(self._model)
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setWordWrap(False)
        self.verticalHeader().setDefaultSectionSize(22)
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.doubleClicked.connect(self._on_double_click)

    def set_rows(self, rows) -> None:
        self._model.set_rows(rows)

    def selected_ids(self) -> list[int]:
        ids = []
        for model_index in self.selectionModel().selectedRows():
            ids.append(int(self._model.game_id(model_index.row())))
        return ids

    def _on_double_click(self, index) -> None:
        if index.isValid():
            self.gameActivated.emit(int(self._model.game_id(index.row())))
