"""Regresión de importación/exportación de PGN (ronda 4).

Cubre el crash crítico de importación GUI (reentrada de QProgressDialog),
la preservación de FEN y flechas en el ciclo importar->exportar->reimportar,
la escritura atómica y la exportación en segundo plano.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path
from unittest.mock import patch

import chess
import chess.pgn
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from chessstudio.database import ChessDatabase, parse_stored_game
from chessstudio.game_model import GameDoc


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def wait_for(app, predicate, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _make_pgn(path, n, arrows=True):
    chunks = []
    for i in range(n):
        c = " {[%cal Ge2e4] [%eval 0.3]}" if arrows else ""
        chunks.append(
            f'[Event "E{i}"]\n[White "W{i}"]\n[Black "B{i}"]\n[Result "1-0"]\n\n'
            f"1. e4{c} e5 2. Nf3 Nc6 1-0\n"
        )
    path.write_text("\n".join(chunks), encoding="utf-8")
    return path


def _fen_game():
    fen = "8/8/8/4k3/8/8/4P3/4K3 w - - 0 1"
    board = chess.Board(fen)
    game = chess.pgn.Game()
    game.headers["FEN"] = fen
    game.headers["SetUp"] = "1"
    game.headers["White"] = "A"
    game.headers["Black"] = "B"
    game.headers["Result"] = "*"
    node = game.add_variation(board.parse_san("e4"))
    node.comment = "[%cal Ge2e4]"
    board.push_san("e4")
    node.add_variation(board.parse_san("Kd6"))
    return game, fen


# --------------------------------------------------------------------- #
# Crash crítico de importación GUI (reentrada del diálogo de progreso)
# --------------------------------------------------------------------- #
def test_import_gui_large_no_crash(qapp, tmp_path):
    from chessstudio.main_window import MainWindow
    pgn = _make_pgn(tmp_path / "big.pgn", 450)
    window = MainWindow()
    window.open_database(tmp_path / "gui.csdb", quiet=True)
    with patch.object(QFileDialog, "getOpenFileNames", return_value=([str(pgn)], "")), \
         patch.object(QMessageBox, "information", return_value=QMessageBox.Ok), \
         patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok):
        window.import_pgn()
        ok = wait_for(qapp, lambda: window._import_thread is None)
    assert ok, "La importación GUI no terminó"
    assert window.db.game_count() == 450
    window.close()


# --------------------------------------------------------------------- #
# FEN y flechas: importar -> reabrir
# --------------------------------------------------------------------- #
def test_fen_roundtrip_import_reopen(tmp_path):
    game, fen = _fen_game()
    pgn = tmp_path / "fen.pgn"
    pgn.write_text(str(game), encoding="utf-8")
    db = ChessDatabase(tmp_path / "fen.csdb")
    done, _ = db.import_pgn(str(pgn))
    assert done == 1
    row = db.search(limit=1)[0]
    reopened = parse_stored_game(row.movetext, row.headers)
    doc = GameDoc(reopened)
    assert doc.board.fen().split()[0] == fen.split()[0]  # posición inicial correcta
    doc.goto_next()
    assert len(doc.current_drawings()["arrows"]) == 1  # flecha preservada
    db.close()


def test_arrows_roundtrip_import_export_reimport(tmp_path):
    game, fen = _fen_game()
    pgn = tmp_path / "fen.pgn"
    pgn.write_text(str(game), encoding="utf-8")
    db = ChessDatabase(tmp_path / "a.csdb")
    db.import_pgn(str(pgn))
    out = tmp_path / "out.pgn"
    count = db.export_pgn(str(out))
    assert count == 1
    text = out.read_text(encoding="utf-8")
    assert "[FEN " in text and '[SetUp "1"]' in text
    g2 = chess.pgn.read_game(io.StringIO(text))
    assert len(list(g2.mainline_moves())) == 2
    doc = GameDoc(g2)
    doc.goto_next()
    assert len(doc.current_drawings()["arrows"]) == 1
    # Reimportar el PGN exportado en una base nueva conserva las flechas.
    db2 = ChessDatabase(tmp_path / "b.csdb")
    done, _ = db2.import_pgn(str(out))
    assert done == 1
    row = db2.search(limit=1)[0]
    doc2 = GameDoc(parse_stored_game(row.movetext, row.headers))
    doc2.goto_next()
    assert len(doc2.current_drawings()["arrows"]) == 1
    db.close()
    db2.close()


# --------------------------------------------------------------------- #
# Exportación: atómica, cancelable, en segundo plano
# --------------------------------------------------------------------- #
def test_export_atomic_cancel_leaves_no_file(tmp_path):
    import threading
    db = ChessDatabase(tmp_path / "c.csdb")
    for i in range(50):
        g = chess.pgn.Game()
        g.headers["White"] = f"W{i}"
        g.add_variation(chess.Move.from_uci("e2e4"))
        db.add_game(g)
    out = tmp_path / "cancel.pgn"
    cancel = threading.Event()
    cancel.set()  # cancelar antes de empezar
    count = db.export_pgn(str(out), cancel=cancel)
    assert count == 0
    assert not out.exists()  # nunca se deja un archivo parcial
    assert not out.with_name(out.name + ".tmp").exists()
    db.close()


def test_export_direct_write_reimport_matches(tmp_path):
    pgn = _make_pgn(tmp_path / "src.pgn", 120)
    db = ChessDatabase(tmp_path / "d.csdb")
    db.import_pgn(str(pgn))
    out = tmp_path / "exp.pgn"
    count = db.export_pgn(str(out))
    assert count == 120
    db2 = ChessDatabase(tmp_path / "e.csdb")
    done, _ = db2.import_pgn(str(out))
    assert done == 120
    # Las flechas sobreviven al ciclo completo.
    row = db2.search(limit=1)[0]
    doc = GameDoc(parse_stored_game(row.movetext, row.headers))
    doc.goto_next()
    assert len(doc.current_drawings()["arrows"]) == 1
    db.close()
    db2.close()


def test_export_current_game_only(qapp, tmp_path):
    # La exportación saca ÚNICAMENTE la partida abierta, con sus flechas,
    # aunque la base contenga muchas más partidas.
    from chessstudio.main_window import MainWindow
    pgn = _make_pgn(tmp_path / "src.pgn", 25)
    window = MainWindow()
    window.open_database(tmp_path / "g.csdb", quiet=True)
    window.db.import_pgn(str(pgn))
    window.refresh_game_list()
    row = window.db.search(limit=1)[0]
    window._open_game_by_id(row.id)
    gw = window.current_game_window()
    assert gw is not None
    # Cambio sin guardar: un comentario nuevo debe salir en la exportación.
    gw.doc.goto_next()
    gw.doc.set_comment("comentario de prueba [%cal Gg1f3]")
    out = tmp_path / "una.pgn"
    with patch.object(QFileDialog, "getSaveFileName", return_value=(str(out), "")):
        window.export_pgn()
    text = out.read_text(encoding="utf-8")
    assert text.count("[Event ") == 1, "Debe exportarse solo la partida abierta"
    assert "comentario de prueba" in text
    assert "[%cal Gg1f3]" in text
    assert not out.with_name(out.name + ".tmp").exists()
    window.close()


def test_export_without_open_game_shows_notice(qapp, tmp_path):
    from chessstudio.main_window import MainWindow
    window = MainWindow()
    window.open_database(tmp_path / "h.csdb", quiet=True)
    with patch.object(QMessageBox, "information", return_value=QMessageBox.Ok) as info, \
         patch.object(QFileDialog, "getSaveFileName") as save_dialog:
        window.export_pgn()
    info.assert_called_once()
    save_dialog.assert_not_called()
    window.close()


# --------------------------------------------------------------------- #
# Eliminar partidas de la base
# --------------------------------------------------------------------- #
def _window_with_games(qapp, tmp_path, n=5):
    from chessstudio.main_window import MainWindow
    pgn = _make_pgn(tmp_path / "del.pgn", n)
    window = MainWindow()
    window.open_database(tmp_path / "del.csdb", quiet=True)
    window.db.import_pgn(str(pgn))
    window.refresh_game_list()
    return window


def test_delete_selected_games(qapp, tmp_path):
    window = _window_with_games(qapp, tmp_path, 5)
    from PySide6.QtCore import QItemSelectionModel
    window.game_list.selectRow(0)
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    window.game_list.selectionModel().select(window.game_list._model.index(1, 0), flags)
    ids = window.game_list.selected_ids()
    assert len(ids) == 2
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        window.delete_selected_games()
    assert window.db.game_count() == 3
    # El índice de posiciones se limpia en cascada (sin filas huérfanas).
    orphans = window.db.conn.execute(
        "SELECT COUNT(*) FROM pos_index WHERE game_id NOT IN (SELECT id FROM games)"
    ).fetchone()[0]
    assert orphans == 0
    assert window.game_list._model.rowCount() == 3
    window.close()


def test_delete_cancel_keeps_games(qapp, tmp_path):
    window = _window_with_games(qapp, tmp_path, 4)
    window.game_list.selectRow(0)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
        window.delete_selected_games()
    assert window.db.game_count() == 4
    window.close()


def test_delete_detaches_open_tab(qapp, tmp_path):
    window = _window_with_games(qapp, tmp_path, 3)
    row = window.db.search(limit=1)[0]
    window._open_game_by_id(row.id)
    gw = window.current_game_window()
    assert gw.db_id == row.id
    # Seleccionar esa partida en la lista y borrarla.
    for r in range(window.game_list._model.rowCount()):
        if window.game_list._model.game_id(r) == row.id:
            window.game_list.selectRow(r)
            break
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        window.delete_selected_games()
    assert gw.db_id is None  # la pestaña queda como copia sin vincular
    assert window.db.game_count() == 2
    window.close()
