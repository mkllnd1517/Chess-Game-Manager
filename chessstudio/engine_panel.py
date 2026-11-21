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

from chessstudio import APP_NAME

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


def format_pv(board: chess.Board, moves: list[chess.Move], limit: int = 18) -> str:
    """Convierte una variante principal UCI en SAN con números de jugada.

    Los números aportan contexto al analizar una posición intermedia: una PV
    que empieza con negras se muestra como ``12... Ac5`` y no como una lista
    ambigua de SAN. La copia local evita modificar el tablero que sigue la UI.
    """
    temp = board.copy()
    tokens: list[str] = []
    for index, move in enumerate(moves[:limit]):
        try:
            if temp.turn == chess.WHITE:
                tokens.append(f"{temp.fullmove_number}.")
            elif index == 0:
                tokens.append(f"{temp.fullmove_number}...")
            tokens.append(temp.san(move))
            temp.push(move)
        except Exception:
            break
    return " ".join(tokens) or "(sin línea)"


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
        # SimpleEngine mantiene su propio bucle asyncio. Guardar una referencia
        # permite cerrarlo desde stop() y esperar el hilo antes de que Qt/Python
        # empiecen su finalización (evita procesos UCI huérfanos).
        self._engine_lock = threading.Lock()
        self._engine: chess.engine.SimpleEngine | None = None
        self._stop = threading.Event()
        self._board = chess.Board()
        self._generation = 0
        self._multipv = 3
        self._run_id = 0

    def start(self, engine_path: str, board: chess.Board, multipv: int) -> None:
        self.stop()
        if self._thread is not None and self._thread.is_alive():
            self.failed.emit(self._run_id, "El motor anterior todavía se está cerrando.")
            return
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
        """Detiene el análisis y cierra el transporte UCI de forma determinista."""
        self._stop.set()
        # close() es seguro entre hilos en python-chess: programa el cierre en
        # su propio event loop y desbloquea inmediatamente analysis().
        with self._engine_lock:
            engine = self._engine
        if engine is not None:
            try:
                engine.close()
            except Exception:
                pass
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
        # Nunca se reutiliza el evento de parada hasta que el hilo actual ha
        # terminado. Así un arranque nuevo no puede reanimar una ejecución UCI
        # anterior que estuviera saliendo.
        if thread is None or not thread.is_alive():
            self._thread = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ #
    def _run(self, engine_path: str, run_id: int) -> None:
        engine = None
        try:
            engine = chess.engine.SimpleEngine.popen_uci(engine_path, timeout=10)
            with self._engine_lock:
                self._engine = engine
            if self._stop.is_set():
                engine.close()
                return
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
                    # Un close() solicitado por stop() es una salida normal,
                    # no un fallo que deba dejar señales/futuros pendientes.
                    if not self._stop.is_set():
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
                with self._engine_lock:
                    if self._engine is engine:
                        self._engine = None
                try:
                    if self._stop.is_set():
                        engine.close()
                    else:
                        engine.quit()
                except Exception:
                    # El transporte puede haber sido cerrado desde stop(). En
                    # ese caso no queda nada que esperar en el event loop UCI.
                    pass

    def _emit_lines(self, board: chess.Board, lines_by_rank: dict[int, dict]) -> None:
        lines = []
        max_depth = 0
        max_seldepth = 0
        for rank in sorted(lines_by_rank):
            info = lines_by_rank[rank]
            pv = info.get("pv") or []
            pv_text = format_pv(board, pv)
            score = info.get("score")
            score_str = format_score(score) if score is not None else "?"
            depth = int(info.get("depth", 0))
            seldepth = int(info.get("seldepth", 0))
            max_depth = max(max_depth, depth)
            max_seldepth = max(max_seldepth, seldepth)
            lines.append({
                "rank": rank, "score": score_str, "depth": depth,
                "seldepth": seldepth, "pv": pv_text,
            })
            if rank == 1:
                self.scoreUpdate.emit(score_str)
        if lines:
            self.depthUpdate.emit(max_depth, max_seldepth)
            self.linesReady.emit(lines)


class EnginePanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = QSettings(APP_NAME, APP_NAME)
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
        self.output.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.output.setPlaceholderText(
            "Las recomendaciones del motor aparecerán aquí, separadas por variante."
        )
        self.output.setToolTip(
            "Cada bloque es una recomendación distinta. La variante principal incluye números de jugada."
        )

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
        blocks = []
        for line in lines:
            depth_str = f"Prof. {line['depth']}"
            if line.get("seldepth"):
                depth_str += f" / Sel. {line['seldepth']}"
            # Bloques separados en vez de una tabla compacta: se distinguen
            # mejor las alternativas MultiPV y se leen bien en paneles estrechos.
            blocks.append(
                f"┌─ Recomendación {line['rank']}   Eval. {line['score']}   {depth_str}\n"
                f"└─ {line['pv']}"
            )
        self.output.setPlainText("\n\n".join(blocks))

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
