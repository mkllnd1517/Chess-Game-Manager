"""Pruebas de interfaz en modo offscreen (sin pantalla)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import chess
import pytest

from PySide6.QtWidgets import QApplication

from chessstudio.board_widget import BoardWidget
from chessstudio.database import ChessDatabase
from chessstudio.engine_panel import EngineWorker
from chessstudio.game_model import GameDoc
from chessstudio.main_window import MainWindow
from chessstudio.notation_view import NotationView
from chessstudio.opening_tree import OpeningTreeWidget

SAMPLE = Path(__file__).parent / "sample_arrows.pgn"
FAKE_ENGINE = Path(__file__).parent / "fake_engine.py"


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def wait_for(qapp, predicate, timeout=20.0):
    start = time.time()
    while time.time() - start < timeout:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def make_rival_pgn(path: Path, n: int = 40) -> None:
    lines = []
    for i in range(n):
        white = "Rival Target" if i % 2 == 0 else f"Other{i}"
        black = "Rival Target" if i % 2 == 1 else f"Foe{i}"
        lines.append(
            f'[Event "Rival game {i}"]\n[White "{white}"]\n[Black "{black}"]\n'
            f'[Result "1-0"]\n[Date "2026.02.01"]\n\n1. d4 d5 2. c4 e6 1-0\n'
        )
    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------- #
def test_main_window_opens(qapp):
    window = MainWindow()
    assert window.db is not None
    window.close()


def test_open_pgn_with_arrows_shows_on_board(qapp, tmp_path):
    window = MainWindow()
    # Base aislada para que el test no dependa de datos residuales.
    window.open_database(tmp_path / "test.csdb", quiet=True)
    # Importar la muestra a la base y abrirla por id (camino completo).
    window.db.import_pgn(SAMPLE)
    row = window.db.search(limit=1)[0]
    window._open_game_by_id(row.id)
    game_window = window.current_game_window()
    game_window.doc.goto_next()  # 1. e4
    qapp.processEvents()
    assert (12, 28) in game_window.board_widget.arrows
    assert 26 in game_window.board_widget.marks
    window.close()


def test_prep_flow(qapp, tmp_path):
    window = MainWindow()
    pgn = tmp_path / "rival.pgn"
    make_rival_pgn(pgn, 40)
    prep = window.opponent_prep
    prep._start_import(pgn)
    assert prep.progress.isVisible() or prep._thread is not None
    ok = wait_for(qapp, lambda: prep._prep_db is not None and prep._thread is None)
    assert ok, "La importación de preparación no terminó"
    assert prep._opponent == "Rival Target"
    assert window.opening_tree.reference_db is prep._prep_db
    assert window.opening_tree.ref_player == "Rival Target"
    assert prep.prep_list.count() == 40
    # Cambiar a solo blancas filtra a 20
    prep.color_combo.setCurrentText("Con blancas")
    qapp.processEvents()
    assert prep.prep_list.count() == 20
    assert window.opening_tree.ref_color == "white"
    window.opponent_prep.shutdown()
    window.close()


def test_opening_tree_local_stats(qapp, tmp_path):
    db = ChessDatabase(tmp_path / "tree.csdb")
    db.import_pgn(SAMPLE)
    tree = OpeningTreeWidget()
    tree.set_database(db)
    tree.set_position(chess.STARTING_FEN)
    assert tree.table.rowCount() >= 1
    assert tree.table.item(0, 0).text() == "e4"
    db.close()


LICHESS_PAYLOAD = {
    "white": 1000, "draws": 500, "black": 800,
    "opening": {"eco": "B00", "name": "King's Pawn"},
    "moves": [
        {"uci": "e2e4", "san": "e4", "white": 500, "draws": 250, "black": 400, "averageRating": 2400},
        {"uci": "d2d4", "san": "d4", "white": 300, "draws": 150, "black": 250, "averageRating": 2350},
    ],
    "topGames": [
        {"id": "abcd1234", "winner": "white", "year": 2024,
         "white": {"name": "Carlsen", "rating": 2830},
         "black": {"name": "Nakamura", "rating": 2780}},
    ],
}


def test_lichess_render(qapp):
    tree = OpeningTreeWidget()
    tree._lichess_key = "masters|test"
    tree._on_lichess_data("masters|test", LICHESS_PAYLOAD)
    assert tree.lichess_table.rowCount() == 2
    assert tree.lichess_table.item(0, 0).text() == "e4"
    assert tree.games_list.count() == 1
    assert "B00" in tree.lichess_status.text()
    # Una clave obsoleta se ignora
    tree._on_lichess_data("otra|clave", {"moves": []})
    assert tree.lichess_table.rowCount() == 2


def test_board_drawings_api(qapp):
    board = BoardWidget()
    board.set_drawings({"arrows": {"12,28": 1}, "marks": {"26": 2}})
    assert board.arrows == {(12, 28): 1}
    assert board.marks == {26: 2}
    data = board.get_drawings()
    assert data["arrows"] == {"12,28": 1}
    assert data["marks"] == {"26": 2}
    board.clear_drawings()
    assert not board.arrows and not board.marks


def test_notation_navigation(qapp):
    import chess.pgn
    with open(SAMPLE, encoding="utf-8") as handle:
        game = chess.pgn.read_game(handle)
    doc = GameDoc(game)
    view = NotationView()
    view.set_document(doc)
    doc.goto_next()
    view.select_node(doc.node)
    qapp.processEvents()
    doc.goto_end()
    view.select_node(doc.node)
    qapp.processEvents()
    # El resaltado debe existir para la jugada actual
    assert view._current_anchor == str(id(doc.node))


def test_engine_multipv(qapp, tmp_path):
    # EngineWorker lanza un ejecutable UCI; envolvemos python + script en un
    # pequeño lanzador para poder usar el motor falso de las pruebas.
    script = tmp_path / "fake_engine.sh"
    script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE_ENGINE}"\n', encoding="utf-8")
    script.chmod(0o755)

    worker = EngineWorker()
    received = []
    worker.linesReady.connect(lambda lines: received.append(lines))
    worker.start(str(script), chess.Board(), 3)
    ok = wait_for(qapp, lambda: any(len(lines) >= 3 for lines in received), timeout=15)
    worker.stop()
    assert ok, f"MultiPV no produjo 3 líneas: {received[-3:] if received else 'nada'}"
    best = max(received, key=len)
    assert [line["rank"] for line in best] == [1, 2, 3]
    assert all(line["pv"] for line in best)
