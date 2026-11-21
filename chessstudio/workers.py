"""Tareas en segundo plano (QThread) para no bloquear la interfaz.

El worker de importación abre su PROPIA conexión SQLite (las conexiones no
se comparten entre hilos); gracias al modo WAL la interfaz puede seguir
leyendo la base mientras se importa.
"""
from __future__ import annotations

import collections
import threading

import chess.pgn
from PySide6.QtCore import QObject, QThread, Signal

from chessstudio.database import ChessDatabase


class GameParseWorker(QObject):
    """Parsea la primera partida de un PGN en segundo plano (archivos grandes)."""

    ready = Signal(object, bool)  # chess.pgn.Game|None, ¿hay más partidas?
    finished = Signal()
    failed = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    def run(self) -> None:
        try:
            with open(self._path, "r", encoding="utf-8-sig", errors="replace") as handle:
                game = chess.pgn.read_game(handle)
                second = chess.pgn.read_game(handle) if game is not None else None
            self.ready.emit(game, second is not None)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class GameTextParseWorker(QObject):
    """Parsea el movetext de una partida de la base en segundo plano.

    Se usa para partidas muy grandes guardadas en la base, de modo que
    abrirlas con doble clic no congele la interfaz mientras se parsean.
    """

    ready = Signal(object)  # chess.pgn.Game|None
    finished = Signal()
    failed = Signal(str)

    def __init__(self, movetext: str, headers: dict):
        super().__init__()
        self._movetext = movetext
        self._headers = dict(headers)

    def run(self) -> None:
        try:
            from chessstudio.database import parse_stored_game
            game = parse_stored_game(self._movetext, self._headers)
            self.ready.emit(game)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class PgnSourceRemovalWorker(QObject):
    """Quita fuentes PGN de una base sin bloquear la interfaz gráfica."""

    progress = Signal(int, int)  # porcentaje, partidas eliminadas
    finished = Signal(int)       # partidas eliminadas
    failed = Signal(str)

    def __init__(self, db_path: str, source_ids: list[int]):
        super().__init__()
        self._db_path = db_path
        self._source_ids = [int(source_id) for source_id in source_ids]
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        db: ChessDatabase | None = None
        try:
            db = ChessDatabase(self._db_path)
            removed = 0
            total = max(1, len(self._source_ids))
            for index, source_id in enumerate(self._source_ids, start=1):
                if self._cancel.is_set():
                    break
                removed += db.remove_source(source_id)
                self.progress.emit(int(index * 100 / total), removed)
            db.close()
            db = None
            self.finished.emit(removed)
        except Exception as exc:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass
            self.failed.emit(str(exc))


class PgnImportWorker(QObject):
    progress = Signal(int, int)   # porcentaje, partidas importadas
    finished = Signal(dict)       # resumen
    failed = Signal(str)

    def __init__(
        self,
        db_path: str,
        pgn_paths: list[str],
        detect_players: bool = False,
        fresh: bool = False,
        source_labels: list[str] | None = None,
        include_variations: bool = False,
    ):
        super().__init__()
        self._db_path = db_path
        self._pgn_paths = list(pgn_paths)
        # Cuando se importa a un repertorio, cada fichero queda registrado por
        # separado para poder quitarlo más tarde sin afectar a los demás.
        self._source_labels = list(source_labels) if source_labels is not None else None
        if self._source_labels is not None and len(self._source_labels) != len(self._pgn_paths):
            raise ValueError("source_labels debe tener una etiqueta por cada PGN")
        self._detect_players = detect_players
        self._fresh = fresh
        self._include_variations = include_variations
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        db: ChessDatabase | None = None
        try:
            db = ChessDatabase(self._db_path)
            if self._fresh:
                db.clear()
            players: collections.Counter | None = (
                collections.Counter() if self._detect_players else None
            )
            imported = 0
            skipped = 0
            total_files = max(1, len(self._pgn_paths))
            for index, path in enumerate(self._pgn_paths):
                base = imported

                def report(percent: int, count: int, base=base, index=index) -> None:
                    overall = int((index * 100 + percent) / total_files)
                    self.progress.emit(overall, base + count)

                source_label = self._source_labels[index] if self._source_labels is not None else None
                done, miss = db.import_pgn(
                    path,
                    progress=report,
                    cancel=self._cancel,
                    player_counts=players,
                    source_label=source_label,
                    include_variations=self._include_variations,
                )
                imported += done
                skipped += miss
                if self._cancel.is_set():
                    break
            db.close()
            db = None
            self.finished.emit(
                {
                    "imported": imported,
                    "skipped": skipped,
                    "players": players,
                    "cancelled": self._cancel.is_set(),
                    "db_path": self._db_path,
                }
            )
        except Exception as exc:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass
            self.failed.emit(str(exc))


def run_in_thread(worker: QObject, parent: QObject | None = None) -> QThread:
    """Prepara un QThread para ``worker`` (con ``run`` como slot).

    El llamador debe conservar la referencia al hilo y llamar a ``start()``
    después de conectar sus propias señales a ``finished``/``failed``.
    """
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    return thread
