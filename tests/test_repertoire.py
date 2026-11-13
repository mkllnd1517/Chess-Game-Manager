"""Pruebas de repertorios personales y comparación en el explorador."""
from __future__ import annotations

from pathlib import Path

import chess
import chess.pgn
import pytest

from chessstudio.database import ChessDatabase
from chessstudio.opening_tree import OpeningTreeWidget
from chessstudio.repertoire_store import RepertoireError, RepertoireLibrary


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

        imported, skipped = white.import_pgn(source, source_label=source.name)
        assert (imported, skipped) == (1, 0)
        source_row = white.list_sources()[0]
        assert source_row.label == "italiana.pgn"
        assert source_row.game_count == 1
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
    finally:
        repertoire.close()
        rival.close()
