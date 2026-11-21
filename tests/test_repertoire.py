"""Pruebas de repertorios personales y comparación en el explorador."""
from __future__ import annotations

import sys
from pathlib import Path

import chess
import chess.pgn
import pytest
from PySide6.QtWidgets import QApplication

from chessstudio.database import ChessDatabase
from chessstudio.opening_tree import OpeningTreeWidget, PRIMARY_ONLY_BG, REF_BG
from chessstudio.repertoire_store import RepertoireError, RepertoireLibrary


@pytest.fixture(scope="session")
def qapp():
    """Una QApplication reutilizable para el test del explorador."""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _write_pgn(path: Path, moves: list[str]) -> None:
    game = chess.pgn.Game()
    game.headers["White"] = "Jugador"
    game.headers["Black"] = "Rival"
    game.headers["Date"] = "2026.11.08"
    game.headers["Result"] = "1-0"
    board = game.board()
    node = game
    for san in moves:
        move = board.parse_san(san)
        node = node.add_variation(move)
        board.push(move)
    path.write_text(str(game), encoding="utf-8")


def test_named_repertoires_keep_colors_and_sources_separate(tmp_path):
    library = RepertoireLibrary(tmp_path / "repertoires")
    e4 = library.create("Repertorio e4")
    d4 = library.create("Repertorio d4")
    assert [profile.name for profile in library.list()] == ["Repertorio d4", "Repertorio e4"]

    with pytest.raises(RepertoireError):
        library.create("  repertorio E4 ")

    source = tmp_path / "italiana.pgn"
    _write_pgn(source, ["e4", "e5", "Nf3", "Nc6"])
    white = ChessDatabase(library.database_path(e4, "white"))
    black = ChessDatabase(library.database_path(e4, "black"))
    try:
        # Una partida manual no pertenece a ningún archivo y no debe borrarse
        # al retirar una fuente PGN.
        manual = chess.pgn.Game()
        manual.headers["White"] = "Manual"
        manual.headers["Black"] = "Manual"
        manual.headers["Result"] = "*"
        white.add_game(manual)

        imported, skipped = white.import_pgn(
            source, source_label=source.name, include_variations=True
        )
        assert (imported, skipped) == (1, 0)
        source_row = white.list_sources()[0]
        assert source_row.label == "italiana.pgn"
        assert source_row.game_count == 1
        assert source_row.include_variations
        assert white.game_count() == 2
        assert [stat.san for stat in white.opening_stats(chess.STARTING_FEN)] == ["e4"]

        # Blancas y negras se almacenan en bases distintas del mismo perfil.
        assert black.game_count() == 0
        assert white.remove_source(source_row.id) == 1
        assert white.game_count() == 1
        assert white.list_sources() == []
    finally:
        white.close()
        black.close()

    renamed = library.rename(e4.identifier, "Ataque italiano")
    assert renamed.name == "Ataque italiano"
    library.delete(d4.identifier)
    assert [profile.name for profile in library.list()] == ["Ataque italiano"]


def test_repertoire_indexes_every_pgn_variation(tmp_path):
    """Un PGN de estudio debe ofrecer todas sus ramas, no solo la principal."""
    game = chess.pgn.Game()
    game.headers["Result"] = "*"
    board = game.board()
    e4 = game.add_variation(board.parse_san("e4"))
    d4 = game.add_variation(board.parse_san("d4"))
    board.push(e4.move)
    e4.add_variation(board.parse_san("e5"))
    e4.add_variation(board.parse_san("c5"))
    # Una rama más profunda también debe ser indexada.
    c5_board = game.board()
    c5_board.push(e4.move)
    c5 = e4.variations[1]
    c5_board.push(c5.move)
    c5.add_variation(c5_board.parse_san("Nf3"))

    pgn = tmp_path / "arbol.pgn"
    pgn.write_text(str(game), encoding="utf-8")
    db = ChessDatabase(tmp_path / "repertorio.csdb")
    try:
        # Simula un repertorio de una versión anterior, que solo indexaba su
        # línea principal. Al abrirlo hoy debe migrar a árbol completo.
        assert db.import_pgn(pgn, source_label=pgn.name) == (1, 0)
        assert {stat.san for stat in db.opening_stats(chess.STARTING_FEN)} == {"e4"}
        assert db.enable_variation_index_for_sources() == 1
        root_moves = {stat.san for stat in db.opening_stats(chess.STARTING_FEN)}
        assert root_moves == {"e4", "d4"}
        after_e4 = chess.Board()
        after_e4.push_san("e4")
        replies = {stat.san for stat in db.opening_stats(after_e4.fen())}
        assert replies == {"e5", "c5"}
        after_c5 = after_e4.copy()
        after_c5.push_san("c5")
        assert {stat.san for stat in db.opening_stats(after_c5.fen())} == {"Nf3"}
    finally:
        db.close()


def _add_game(db: ChessDatabase, moves: list[str], white: str, black: str) -> None:
    game = chess.pgn.Game()
    game.headers.update({"White": white, "Black": black, "Date": "2026.11.08", "Result": "1-0"})
    board = game.board()
    node = game
    for san in moves:
        node = node.add_variation(board.parse_san(san))
        board.push(node.move)
    db.add_game(game)


def test_explorer_compares_repertoire_with_rival(qapp, tmp_path):
    repertoire = ChessDatabase(tmp_path / "repertoire.csdb")
    rival = ChessDatabase(tmp_path / "rival.csdb")
    try:
        _add_game(repertoire, ["e4", "e5", "Nf3", "Nc6"], "Yo", "Otro")
        _add_game(rival, ["e4", "c5", "Nf3", "d6"], "Rival", "Otro")

        tree = OpeningTreeWidget()
        tree.set_repertoire_database(repertoire, "e4", "white")
        assert tree._scope == "repertoire"
        tree.set_reference_database(rival, "Rival", "white")
        assert tree.show_repertoire_comparison()
        assert tree._scope == "repertoire_compare"
        assert "continuación" in tree.info.text()
        moves = [tree.table.item(row, 0).text() for row in range(tree.table.rowCount())]
        assert moves == ["e4"]
        assert tree.table.item(0, 0).toolTip()
        assert tree.table.item(0, 8).text() == "Repertorio y rival"

        # Tras 1.e4 cada fuente aporta una respuesta distinta. La columna y
        # el color de la jugada deben dejar inequívoca su procedencia.
        after_e4 = chess.Board()
        after_e4.push_san("e4")
        tree.set_position(after_e4.fen())
        presence_by_move = {
            tree.table.item(row, 0).text(): tree.table.item(row, 8).text()
            for row in range(tree.table.rowCount())
        }
        assert presence_by_move == {"e5": "Solo repertorio", "c5": "Solo rival"}
        colors_by_move = {
            tree.table.item(row, 0).text(): tree.table.item(row, 0).background().color()
            for row in range(tree.table.rowCount())
        }
        assert colors_by_move == {"e5": PRIMARY_ONLY_BG, "c5": REF_BG}
    finally:
        repertoire.close()
        rival.close()
