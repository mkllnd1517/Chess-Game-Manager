"""Pruebas de las mejoras de la segunda ronda: seguridad, formato de
comentarios, modo rival del explorador, lista modelo/vista, piezas SVG,
fijado del motor y rendimiento con partidas largas.
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

import chess
import chess.pgn
import pytest
from PySide6.QtCore import QUrl, Qt
from PySide6.QtNetwork import QNetworkRequest
from PySide6.QtWidgets import QApplication

from chessstudio.database import ChessDatabase, GameRow
from chessstudio.engine_panel import EnginePanel
from chessstudio.game_list import GameListWidget
from chessstudio.game_model import GameDoc
from chessstudio.lichess_explorer import LichessExplorer, _is_lichess_host
from chessstudio.notation_view import NotationView
from chessstudio.opening_tree import OpeningTreeWidget
from chessstudio.piece_renderer import get_renderer
from chessstudio.pgn_utils import parse_comment, walk_game


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def wait_for(app, predicate, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


# --------------------------------------------------------------------- #
# Formato de comentarios
# --------------------------------------------------------------------- #
def test_parse_comment_text_eval_clk():
    parsed = parse_comment("Buena jugada [%eval 0.34] [%clk 1:23:45] [%cal Ge2e4]")
    assert parsed["text"] == "Buena jugada"
    assert parsed["eval"] == "+0.34"
    assert parsed["clk"] == "1:23:45"


def test_parse_comment_mate_and_negative():
    assert parse_comment("[%eval #-3]")["eval"] == "M-3"
    assert parse_comment("[%eval -1.5]")["eval"] == "-1.50"
    assert parse_comment("solo texto")["eval"] is None


def test_notation_shows_eval_badge(qapp):
    pgn = '[White "A"]\n[Black "B"]\n[Result "*"]\n\n1. e4 {idea [%eval 0.3]} e5 *'
    doc = GameDoc(chess.pgn.read_game(io.StringIO(pgn)))
    view = NotationView()
    view.set_document(doc)
    html = view.toHtml()
    assert "+0.30" in html
    assert "idea" in html
    assert "[%eval" not in html  # el tag crudo no debe verse


# --------------------------------------------------------------------- #
# Seguridad: token y red
# --------------------------------------------------------------------- #
def test_lichess_host_check():
    assert _is_lichess_host(QUrl("https://lichess.org/api"))
    assert _is_lichess_host(QUrl("https://explorer.lichess.ovh/masters"))
    assert not _is_lichess_host(QUrl("https://evil.com/steal"))
    assert not _is_lichess_host(QUrl("https://lichess.org.evil.com/x"))
    # _is_lichess_host solo comprueba el dominio; el esquema HTTPS se valida
    # por separado en _prepare_request (ver test_token_only_to_lichess).
    assert _is_lichess_host(QUrl("http://lichess.org/api"))


def test_token_only_to_lichess(qapp):
    explorer = LichessExplorer()
    explorer.set_token("SECRET_TOKEN")
    req_ok = explorer._prepare_request(QUrl("https://explorer.lichess.ovh/masters"))
    assert bytes(req_ok.rawHeader("Authorization")) == b"Bearer SECRET_TOKEN"
    req_bad = explorer._prepare_request(QUrl("https://evil.com/steal"))
    assert bytes(req_bad.rawHeader("Authorization")) == b""
    req_http = explorer._prepare_request(QUrl("http://lichess.org/api"))
    assert bytes(req_http.rawHeader("Authorization")) == b""  # nunca por HTTP


def test_no_redirect_followed(qapp):
    explorer = LichessExplorer()
    req = explorer._prepare_request(QUrl("https://lichess.org/api"))
    policy = req.attribute(QNetworkRequest.RedirectPolicyAttribute)
    assert policy == QNetworkRequest.ManualRedirectPolicy


def test_secure_store_roundtrip():
    from chessstudio import secure_store
    original = secure_store.get_token()
    try:
        secure_store.set_token("test-token-123")
        assert secure_store.get_token() == "test-token-123"
        secure_store.set_token("")
        assert secure_store.get_token() == ""
    finally:
        secure_store.set_token(original)


# --------------------------------------------------------------------- #
# Explorador: modo rival como base de datos
# --------------------------------------------------------------------- #
def _fill_db(db, player, opening, n=10):
    for i in range(n):
        game = chess.pgn.Game()
        game.headers["White"] = player if i % 2 == 0 else f"Other{i}"
        game.headers["Black"] = player if i % 2 == 1 else f"Foe{i}"
        game.headers["Result"] = "1-0"
        game.headers["Date"] = "2026.01.01"
        node = game
        for san in opening:
            node = node.add_variation(chess.Board().parse_san(san) if node is game else node.board().parse_san(san))
        db.add_game(game)


def test_explorer_rival_mode(qapp, tmp_path):
    main = ChessDatabase(tmp_path / "main.csdb")
    rival = ChessDatabase(tmp_path / "rival.csdb")
    _fill_db(main, "Me", ["e4", "e5"], 6)
    _fill_db(rival, "RivalX", ["d4", "d5"], 8)

    tree = OpeningTreeWidget()
    tree.set_database(main)
    tree.set_reference_database(rival, player="RivalX", color="both")
    # Al activar la preparación, el modo debe ser "rival" (su base es la activa)
    assert tree._scope == "rival"
    tree.set_position(chess.STARTING_FEN)
    moves = [tree.table.item(r, 0).text() for r in range(tree.table.rowCount())]
    assert "d4" in moves  # las jugadas del rival, no las de la base principal
    assert "Base del rival" in tree.info.text()
    # Cambiar a modo comparación muestra ambas
    tree.scope_combo.setCurrentIndex(tree.scope_combo.findData("compare"))
    assert tree._scope == "compare"
    main.close()
    rival.close()


# --------------------------------------------------------------------- #
# Lista modelo/vista
# --------------------------------------------------------------------- #
def test_game_list_model(qapp):
    rows = [
        GameRow(id=i, white=f"W{i}", black=f"B{i}", event="E", site="S",
                date=f"2026.01.{i:02d}", round="1", result="1-0", eco="B00")
        for i in range(1, 11)
    ]
    widget = GameListWidget()
    widget.set_rows(rows)
    assert widget._model.rowCount() == 10
    # ordenación numérica por id (desc)
    widget._model.sort(0, Qt.DescendingOrder)
    assert widget._model.game_id(0) == 10
    widget.selectRow(0)
    assert widget.selected_ids() == [10]


def test_game_list_many_rows_fast(qapp):
    rows = [
        GameRow(id=i, white="A", black="B", event="E", site="S",
                date="2026.01.01", round="1", result="*", eco="")
        for i in range(20000)
    ]
    widget = GameListWidget()
    t0 = time.perf_counter()
    widget.set_rows(rows)
    elapsed = time.perf_counter() - t0
    assert widget._model.rowCount() == 20000
    assert elapsed < 1.0, f"Refresco de lista demasiado lento: {elapsed:.2f}s"


# --------------------------------------------------------------------- #
# Piezas SVG
# --------------------------------------------------------------------- #
def test_svg_pieces_available(qapp):
    renderer = get_renderer()
    assert renderer.available
    pixmap = renderer.pixmap(chess.Piece(chess.QUEEN, chess.WHITE), 60)
    assert not pixmap.isNull()
    assert pixmap.width() >= 60


# --------------------------------------------------------------------- #
# Motor: fijar posición y mostrar variantes
# --------------------------------------------------------------------- #
def test_engine_pv_includes_move_numbers():
    from chessstudio.engine_panel import format_pv

    board = chess.Board()
    moves = [board.parse_san("e4")]
    board.push(moves[0])
    moves.append(board.parse_san("e5"))
    assert format_pv(chess.Board(), moves) == "1. e4 e5"

    after_e4 = chess.Board()
    after_e4.push_san("e4")
    assert format_pv(after_e4, [after_e4.parse_san("e5")]) == "1... e5"


def test_engine_lock_state(qapp):
    panel = EnginePanel()
    board = chess.Board()
    board.push_san("e4")
    panel.set_position(board)
    panel._toggle_lock(True)
    assert panel._locked_fen == board.fen()
    # Navegar a otra posición no cambia la posición fijada
    other = chess.Board()
    other.push_san("d4")
    panel.set_position(other)
    assert panel._locked_fen == board.fen()
    assert panel._analysis_board().fen() == board.fen()
    # Soltar
    panel._toggle_lock(False)
    assert panel._locked_fen is None
    assert panel._analysis_board().fen() == other.fen()


# --------------------------------------------------------------------- #
# Rendimiento con partidas largas
# --------------------------------------------------------------------- #
def _long_game(n_moves=1200):
    moves = ["Nf3", "Nf6", "Nc3", "Nc6", "Nb1", "Nb8", "Ng1", "Ng8"] * (n_moves // 8)
    game = chess.pgn.Game()
    node = game
    board = chess.Board()
    for san in moves:
        move = board.parse_san(san)
        node = node.add_variation(move)
        node.comment = "[%cal Gg1f3]"
        board.push(move)
    return game


def test_long_game_open_fast(qapp):
    game = _long_game(1600)
    t0 = time.perf_counter()
    doc = GameDoc(game)
    view = NotationView()
    view.set_document(doc)
    elapsed = time.perf_counter() - t0
    assert elapsed < 2.0, f"Apertura de partida larga demasiado lenta: {elapsed:.2f}s"
    # navegación al final y al inicio
    doc.goto_end()
    doc.goto_start()
    assert doc.board.fen() == chess.STARTING_FEN


def test_walk_game_no_history_copy():
    game = _long_game(800)
    t0 = time.perf_counter()
    count = sum(1 for _ in walk_game(game))
    elapsed = time.perf_counter() - t0
    assert count == 801  # raíz + 800 jugadas
    assert elapsed < 0.5


# --------------------------------------------------------------------- #
# Regresión: crashes con PGN grandes (ronda 3)
# --------------------------------------------------------------------- #
def _nested_game(levels=600):
    """Anidamiento real: cada nodo tiene línea principal + variante y se
    desciende por la variante (profundidad de árbol = levels)."""
    game = chess.pgn.Game()
    current = game
    board = chess.Board()
    for _ in range(levels):
        moves = list(board.legal_moves)
        current.add_variation(moves[0])
        current = current.add_variation(moves[1])
        board.push(moves[1])
    return game


def test_deep_variations_no_recursion_crash(qapp):
    # Antes: RecursionError en el renderizado -> abortaba el proceso.
    game = _nested_game(600)
    doc = GameDoc(game)
    view = NotationView()
    view.set_document(doc)  # no debe lanzar RecursionError
    assert view.toPlainText().strip()
    # Navegar por la variante anidada hasta el final no debe fallar.
    doc.goto_end()
    view.select_node(doc.node)
    doc.goto_start()
    view.select_node(doc.node)


def test_long_game_navigation_is_fast(qapp):
    # Antes: cada paso escaneaba todo el documento (~200 ms/paso).
    game = _long_game(6000)
    doc = GameDoc(game)
    view = NotationView()
    view.set_document(doc)
    t0 = time.perf_counter()
    for _ in range(300):
        doc.goto_next()
        view.select_node(doc.node)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"Navegación demasiado lenta: {elapsed:.2f}s para 300 pasos"


def test_notation_budget_extends_on_jump(qapp):
    # Partida más larga que el presupuesto inicial: al saltar al final la
    # vista debe ampliarse y resaltar la última jugada.
    game = _long_game(9000)
    doc = GameDoc(game)
    view = NotationView()
    view.set_document(doc)
    assert view._truncated  # render inicial parcial
    doc.goto_end()
    view.select_node(doc.node)
    assert not view._truncated or str(id(doc.node)) in view._anchor_map
    assert str(id(doc.node)) in view._anchor_map


def test_show_all_anchor(qapp):
    game = _long_game(9000)
    doc = GameDoc(game)
    view = NotationView()
    view.set_document(doc)
    assert view._truncated
    from PySide6.QtCore import QUrl
    view._on_anchor(QUrl("__show_all__"))
    assert not view._truncated


def test_db_open_large_game_background(qapp, tmp_path):
    # Abrir una partida grande guardada en la base no debe bloquear la UI.
    from chessstudio.main_window import MainWindow
    window = MainWindow()
    window.open_database(tmp_path / "big.csdb", quiet=True)
    game = _long_game(6000)
    game.headers["White"] = "Grande"
    game.headers["Black"] = "Partida"
    gid = window.db.add_game(game)
    window._open_game_by_id(gid)
    # Debe haber lanzado el parseo en segundo plano.
    assert window._open_thread is not None
    ok = wait_for(qapp, lambda: window._open_thread is None, timeout=15)
    assert ok, "La apertura en segundo plano no terminó"
    gw = window.current_game_window()
    assert gw is not None and gw.db_id == gid
    window.close()


def test_open_large_pgn_file_end_to_end(qapp, tmp_path):
    # Escenario exacto del usuario: abrir un PGN grande no debe petar ni
    # congelar la ventana. Se parsea en segundo plano y la pestaña se crea en
    # el hilo de la UI (no en el worker).
    from chessstudio.main_window import MainWindow
    pgn = tmp_path / "grande.pgn"
    pgn.write_text(str(_long_game(8000)), encoding="utf-8")
    window = MainWindow()
    window.start_open_pgn(str(pgn))
    assert window._open_thread is not None  # parseo en segundo plano
    ok = wait_for(qapp, lambda: window._open_thread is None, timeout=20)
    assert ok, "La apertura del PGN grande no terminó"
    gw = window.current_game_window()
    assert gw is not None, "No se creó la pestaña de la partida"
    # La navegación debe funcionar y ser rápida.
    t0 = time.perf_counter()
    for _ in range(100):
        gw.doc.goto_next()
    assert time.perf_counter() - t0 < 1.0
    window.close()


def test_open_deep_variations_file_end_to_end(qapp, tmp_path):
    # Antes: las variantes muy anidadas provocaban RecursionError y el proceso
    # abortaba. Ahora el renderizado es iterativo y debe abrir sin crash.
    from chessstudio.main_window import MainWindow
    pgn = tmp_path / "anidadas.pgn"
    pgn.write_text(str(_nested_game(800)), encoding="utf-8")
    window = MainWindow()
    window.start_open_pgn(str(pgn))
    ok = wait_for(qapp, lambda: window._open_thread is None, timeout=20)
    assert ok, "La apertura de variantes anidadas no terminó"
    gw = window.current_game_window()
    assert gw is not None, "No se creó la pestaña (posible crash por recursión)"
    gw.doc.goto_end()
    gw.doc.goto_start()
    assert gw.doc.board.fen() == chess.STARTING_FEN
    window.close()
