import chess
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

RESULTS = ["Cualquiera", "1-0", "0-1", "1/2-1/2", "*"]


class SearchDialog(QDialog):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Buscar partidas")
        self.setMinimumWidth(420)

        self.white_edit = QLineEdit()
        self.black_edit = QLineEdit()
        self.event_edit = QLineEdit()
        self.site_edit = QLineEdit()
        self.date_from_edit = QLineEdit()
        self.date_from_edit.setPlaceholderText("YYYY.MM.DD")
        self.date_to_edit = QLineEdit()
        self.date_to_edit.setPlaceholderText("YYYY.MM.DD")
        self.result_combo = QComboBox()
        self.result_combo.addItems(RESULTS)
        self.eco_edit = QLineEdit()

        form = QFormLayout()
        form.addRow("Blancas:", self.white_edit)
        form.addRow("Negras:", self.black_edit)
        form.addRow("Evento:", self.event_edit)
        form.addRow("Sitio:", self.site_edit)
        form.addRow("Fecha desde:", self.date_from_edit)
        form.addRow("Fecha hasta:", self.date_to_edit)
        form.addRow("Resultado:", self.result_combo)
        form.addRow("ECO:", self.eco_edit)

        self.position_check = QCheckBox("Buscar la posición del tablero actual")
        self.position_check.setEnabled(False)

        position_box = QGroupBox("Posición")
        position_layout = QVBoxLayout(position_box)
        position_layout.addWidget(self.position_check)
        self.position_label = QLineEdit()
        self.position_label.setReadOnly(True)
        position_layout.addWidget(self.position_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Buscar")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(position_box)
        layout.addWidget(buttons)

    def set_position(self, board: chess.Board | None) -> None:
        if board is None:
            self.position_check.setEnabled(False)
            self.position_label.clear()
            return
        self.position_check.setEnabled(True)
        self.position_label.setText(board.fen())

    def criteria(self) -> dict:
        result = self.result_combo.currentText()
        return {
            "white": self.white_edit.text().strip(),
            "black": self.black_edit.text().strip(),
            "event": self.event_edit.text().strip(),
            "site": self.site_edit.text().strip(),
            "date_from": self.date_from_edit.text().strip(),
            "date_to": self.date_to_edit.text().strip(),
            "result": "" if result == "Cualquiera" else result,
            "eco": self.eco_edit.text().strip(),
            "position": self.position_label.text() if self.position_check.isChecked() else "",
        }
