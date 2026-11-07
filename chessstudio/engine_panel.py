"""Panel de motor UCI con análisis continuo y automático.

Funcionamiento:
  * El motor se inicia UNA vez y queda residente. A partir de ahí analiza
    automáticamente la posición que haya en el tablero (lo sigue al navegar).
  * Botón «Fijar posición»: congela el análisis en la posición actual para
    estudiarla en profundidad mientras se sigue navegando por la partida.
  * «Iniciar automáticamente»: arranca el motor al abrir la aplicación si
    hay una ruta de motor configurada.

El hilo del motor es el único dueño del proceso UCI; la parada es
cooperativa y las actualizaciones a la interfaz se limitan a ~8/s.
"""
from __future__ import annotations

import sys
import threading
import time

import chess
import chess.engine
from PySide6.QtCore import QObject, QSettings, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

MONO = QFont("Consolas", 9)
if sys.platform != "win32":
    MONO = QFont("Monospace", 9)
    MONO.setStyleHint(QFont.Monospace)


def format_score(score: chess.engine.PovScore) -> str:
    white = score.white()
    if white.is_mate():
        mate = white.mate()
        return f"M{mate}" if mate is not None else "M#"
    value = white.score()
    if value is None:
        return "?"
    return f"{value / 100:+.2f}"


class EngineWorker(QObject):
    linesReady = Signal(list)
    engineInfo = Signal(str)
    failed = Signal(int, str)
    depthUpdate = Signal(int, int)
    scoreUpdate = Signal(str)
    finished = Signal(int)

    EMIT_INTERVAL = 0.12

    def __init__(self):
        super().__init__()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._board = chess.Board()
        self._generation = 0
        self._multipv = 3
        self._run_id = 0

    def start(self, engine_path: str, board: chess.Board, multipv: int) -> None:
        self.stop()
        self._stop.clear()
        self._run_id += 1
        run_id = self._run_id
        with self._lock:
            self._board = board.copy()
            self._multipv = multipv
            self._generation += 1
        self._thread = threading.Thread(target=self._run, args=(engine_path, run_id), daemon=True)
        self._thread.start()

    def set_position(self, board: chess.Board) -> None:
        with self._lock:
            self._board = board.copy()
            self._generation += 1

    def set_multipv(self, multipv: int) -> None:
        with self._lock:
            self._multipv = multipv
            self._generation += 1

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.5)
        self._thread = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ #
    def _run(self, engine_path: str, run_id: int) -> None:
        engine = None
        try:
            engine = chess.engine.SimpleEngine.popen_uci(engine_path, timeout=10)
            self.engineInfo.emit(f"Motor activo: {engine.id.get('name', engine_path)}")
            while not self._stop.is_set():
                with self._lock:
                    board = self._board.copy()
                    generation = self._generation
                    multipv = self._multipv

                if board.is_game_over(claim_draw=True):
                    self.linesReady.emit([])
                    if self._stop.wait(0.4):
                        break
                    continue

                lines_by_rank: dict[int, dict] = {}
                last_emit = 0.0
                try:
                    with engine.analysis(board, limit=chess.engine.Limit(), multipv=multipv,
                                         info=chess.engine.INFO_ALL) as analysis:
                        for info in analysis:
                            if self._stop.is_set():
                                analysis.stop()
                                break
                            with self._lock:
                                if self._generation != generation:
                                    analysis.stop()
                                    break
                            if "score" not in info or "pv" not in info:
                                continue
                            rank = int(info.get("multipv", 1))
                            lines_by_rank[rank] = info
                            now = time.monotonic()
                            if now - last_emit >= self.EMIT_INTERVAL:
                                self._emit_lines(board, lines_by_rank)
                                last_emit = now
                    if lines_by_rank:
                        self._emit_lines(board, lines_by_rank)
                except chess.engine.EngineTerminatedError:
                    self.failed.emit(run_id, "El motor terminó inesperadamente.")
                    break
                except Exception as exc:
                    self.failed.emit(run_id, f"Error de análisis: {exc}")
                    break
                if self._stop.is_set():
                    break
            self.finished.emit(run_id)
        except Exception as exc:
            self.failed.emit(run_id, f"No se pudo iniciar el motor: {exc}")
        finally:
            if engine is not None:
                try:
                    engine.quit()
                except Exception:
                    pass

    def _emit_lines(self, board: chess.Board, lines_by_rank: dict[int, dict]) -> None:
        lines = []
        max_depth = 0
        max_seldepth = 0
        for rank in sorted(lines_by_rank):
            info = lines_by_rank[rank]
            pv = info.get("pv") or []
            san_moves = []
            temp = board.copy()
            for move in pv[:18]:
                try:
                    san_moves.append(temp.san(move))
                    temp.push(move)
                except Exception:
                    break
            score = info.get("score")
            score_str = format_score(score) if score is not None else "?"
            depth = int(info.get("depth", 0))
            seldepth = int(info.get("seldepth", 0))
            max_depth = max(max_depth, depth)
            max_seldepth = max(max_seldepth, seldepth)
            lines.append({
                "rank": rank, "score": score_str, "depth": depth,
                "seldepth": seldepth, "pv": " ".join(san_moves) or "(sin línea)",
            })
            if rank == 1:
                self.scoreUpdate.emit(score_str)
        if lines:
            self.depthUpdate.emit(max_depth, max_seldepth)
            self.linesReady.emit(lines)


class EnginePanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = QSettings("ChessStudio", "ChessStudio")
        self.worker = EngineWorker()
        self._engine_name = ""
        self.worker.linesReady.connect(self._on_lines)
        self.worker.engineInfo.connect(self._on_engine_info)
        self.worker.failed.connect(self._on_failed)
        self.worker.depthUpdate.connect(self._on_depth_update)
        self.worker.scoreUpdate.connect(self._on_score_update)
        self.worker.finished.connect(self._on_finished)
        self._current_board = chess.Board()
        self._locked_fen: str | None = None
        self._running = False
        self._active_run = 0

        self.engine_combo = QComboBox()
        self.engine_combo.setEditable(True)
        self.engine_combo.setMinimumWidth(180)
        saved = self._settings.value("engine/path", "", str)
        if saved:
            self.engine_combo.addItem(saved)
        browse = QPushButton("...")
        browse.setFixedWidth(30)
        browse.clicked.connect(self._browse)

        self.multipv_spin = QSpinBox()
        self.multipv_spin.setRange(1, 5)
        self.multipv_spin.setValue(int(self._settings.value("engine/multipv", 3, int)))
        self.multipv_spin.valueChanged.connect(self._on_multipv_changed)

        self.start_button = QPushButton("Iniciar motor")
        self.start_button.setCheckable(True)
        self.start_button.setStyleSheet("font-weight:bold; padding:6px;")
        self.start_button.clicked.connect(self._toggle)

        self.lock_button = QPushButton("Fijar posición actual")
        self.lock_button.setCheckable(True)
        self.lock_button.setEnabled(False)
        self.lock_button.setToolTip(
            "Congela el análisis en la posición actual para estudiarla en profundidad.\n"
            "Puedes seguir navegando por la partida sin perder el análisis."
        )
        self.lock_button.clicked.connect(self._toggle_lock)

        self.autostart_check = QCheckBox("Iniciar automáticamente al abrir")
        self.autostart_check.setChecked(self._settings.value("engine/autostart", True, bool))
        self.autostart_check.toggled.connect(lambda v: self._settings.setValue("engine/autostart", v))

        form = QFormLayout()
        form.addRow("Motor UCI:", self._combo_row(browse))
        form.addRow("Líneas (MultiPV):", self.multipv_spin)

        self.status_label = QLabel("Motor detenido.")
        self.status_label.setWordWrap(True)
        self.depth_label = QLabel("Profundidad: --  Seldepth: --")
        self.depth_label.setFont(MONO)
        self.eval_label = QLabel("Evaluación: ?")
        self.eval_label.setFont(QFont(MONO.family(), 10))
        self.eval_label.setStyleSheet("QLabel { background-color: #f5f5f5; padding: 4px; border: 1px solid #ddd; }")

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(MONO)
        self.output.setPlaceholderText("Las líneas de análisis del motor aparecerán aquí.")

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.start_button)
        layout.addWidget(self.lock_button)
        layout.addWidget(self.autostart_check)
        layout.addWidget(self.status_label)
        layout.addWidget(self.depth_label)
        layout.addWidget(self.eval_label)
        layout.addWidget(self.output, 1)

    def _combo_row(self, button: QPushButton) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.engine_combo, 1)
        layout.addWidget(button)
        return row

    # ------------------------------------------------------------------ #
    # Control del motor
    # ------------------------------------------------------------------ #
    def _browse(self) -> None:
        filter_str = "Ejecutables (*.exe);;Todos (*)" if sys.platform == "win32" else "Todos (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar motor UCI", "", filter_str)
        if path:
            self.engine_combo.setCurrentText(path)
            self._settings.setValue("engine/path", path)

    def _analysis_board(self) -> chess.Board:
        if self._locked_fen:
            try:
                return chess.Board(self._locked_fen)
            except ValueError:
                pass
        return self._current_board

    def _toggle(self, checked: bool) -> None:
        if checked:
            path = self.engine_combo.currentText().strip()
            if not path:
                self._on_info("Selecciona un motor UCI primero (por ejemplo Stockfish).")
                self.start_button.setChecked(False)
                return
            self._settings.setValue("engine/path", path)
            self._settings.setValue("engine/multipv", self.multipv_spin.value())
            self._running = True
            self.start_button.setText("Detener motor")
            self.lock_button.setEnabled(True)
            self.output.clear()
            self.depth_label.setText("Profundidad: --  Seldepth: --")
            self.eval_label.setText("Evaluación: ?")
            self.worker.start(path, self._analysis_board(), self.multipv_spin.value())
            self._active_run = self.worker._run_id
            self._update_status()
        else:
            self.worker.stop()
            self._running = False
            self._reset_controls()
            self._on_info("Motor detenido.")

    def _toggle_lock(self, checked: bool) -> None:
        if checked:
            self._locked_fen = self._current_board.fen()
            self.lock_button.setText("Posición fijada ✓ (soltar)")
            if self._running:
                self.worker.set_position(self._analysis_board())
        else:
            self._locked_fen = None
            self.lock_button.setText("Fijar posición actual")
            if self._running:
                self.worker.set_position(self._current_board)
                self.depth_label.setText("Profundidad: --  Seldepth: --")
                self.eval_label.setText("Evaluación: ?")
        self._update_status()

    def _on_multipv_changed(self, value: int) -> None:
        self._settings.setValue("engine/multipv", value)
        if self._running:
            self.worker.set_multipv(value)

    def _reset_controls(self) -> None:
        self.start_button.blockSignals(True)
        self.start_button.setChecked(False)
        self.start_button.blockSignals(False)
        self.start_button.setText("Iniciar motor")
        self.lock_button.setEnabled(False)
        self.lock_button.blockSignals(True)
        self.lock_button.setChecked(False)
        self.lock_button.blockSignals(False)
        self.lock_button.setText("Fijar posición actual")
        self._locked_fen = None
        self._update_status()

    def _update_status(self) -> None:
        if not self._running:
            self.status_label.setText("Motor detenido.")
            self.status_label.setStyleSheet("color:#777;")
        elif self._locked_fen:
            self.status_label.setText("Analizando posición FIJA en profundidad. Puedes navegar sin perder el análisis.")
            self.status_label.setStyleSheet("color:#b45309; font-weight:bold;")
        else:
            suffix = f" · {self._engine_name}" if self._engine_name else ""
            self.status_label.setText(f"Siguiendo el tablero automáticamente{suffix}.")
            self.status_label.setStyleSheet("color:#2e7d32;")

    def _on_engine_info(self, message: str) -> None:
        self._engine_name = message.replace("Motor activo:", "").strip()
        self._update_status()

    def maybe_autostart(self) -> None:
        """Arranca el motor al abrir la app si está configurado (llamado una vez)."""
        if self.autostart_check.isChecked() and self.engine_combo.currentText().strip():
            self.start_button.setChecked(True)
            self._toggle(True)

    # ------------------------------------------------------------------ #
    # Posición del tablero
    # ------------------------------------------------------------------ #
    def set_position(self, board: chess.Board) -> None:
        self._current_board = board.copy()
        if self._running and not self._locked_fen:
            self.depth_label.setText("Profundidad: --  Seldepth: --")
            self.eval_label.setText("Evaluación: ?")
            self.worker.set_position(self._current_board)

    # ------------------------------------------------------------------ #
    # Señales del worker
    # ------------------------------------------------------------------ #
    def _on_lines(self, lines: list) -> None:
        if not lines:
            self.output.setPlainText("(fin de partida o sin líneas)")
            return
        rows = []
        for line in lines:
            depth_str = f"d{line['depth']}"
            if line.get("seldepth"):
                depth_str += f"/{line['seldepth']}"
            rows.append(f"{line['rank']}. {line['score']:>7}  {depth_str:<8}  {line['pv']}")
        self.output.setPlainText("\n".join(rows))

    def _on_depth_update(self, depth: int, seldepth: int) -> None:
        self.depth_label.setText(f"Profundidad: {depth}  Seldepth: {seldepth}")

    def _on_score_update(self, score: str) -> None:
        self.eval_label.setText(f"Evaluación: {score}")

    def _on_info(self, message: str) -> None:
        self.status_label.setStyleSheet("")
        self.status_label.setText(message)

    def _on_failed(self, run_id: int, message: str) -> None:
        if run_id != self._active_run:
            return  # señal de una ejecución anterior (rearranque): ignorar
        self._running = False
        self.status_label.setStyleSheet("color:#c62828;")
        self.status_label.setText(message)
        self._reset_controls()

    def _on_finished(self, run_id: int) -> None:
        if run_id != self._active_run:
            return  # señal de una ejecución anterior (rearranque): ignorar
        self._running = False
        self._reset_controls()

    def shutdown(self) -> None:
        self.worker.stop()
