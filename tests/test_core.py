"""Pruebas del núcleo: PGN, dibujos, base de datos y modelo de partida."""
from __future__ import annotations

import io
import time
from pathlib import Path

import chess
import chess.pgn
import pytest

from chessstudio.database import ChessDatabase, import_game, poskey
from chessstudio.game_model import GameDoc
from chessstudio.pgn_utils import (
    display_comment,
    drawings_to_tags,
    merge_comment,
    parse_drawings,
    strip_tags,
)

SAMPLE = Path(__file__).parent / "sample_arrows.pgn"


def test_app_documents_directory_migrates_legacy_data(monkeypatch, tmp_path):
    from chessstudio import APP_NAME
    from chessstudio import app_paths

    legacy = tmp_path / "ChessStudio"
    legacy.mkdir()
    (legacy / "default.csdb").write_text("datos", encoding="utf-8")
    monkeypatch.setattr(app_paths, "documents_directory", lambda: tmp_path)

    target = app_paths.app_documents_directory()
    assert target == tmp_path / APP_NAME
    assert (target / "default.csdb").read_text(encoding="utf-8") == "datos"
    assert not legacy.exists()


def read_sample() -> chess.pgn.Game:
    with open(SAMPLE, encoding="utf-8") as handle:
        return chess.pgn.read_game(handle)


# --------------------------------------------------------------------- #
# pgn_utils
# --------------------------------------------------------------------- #
def test_parse_lowercase_cal_csl():
    arrows, marks = parse_drawings("[%cal Ge2e4,Gd2d4] [%csl Rc4,Yf5]")
    assert arrows == {"12,28": 1, "11,27": 1}
    assert marks == {"26": 2, "37": 0}


def test_parse_uppercase_and_colors():
    arrows, marks = parse_drawings("[%CAL Re2e4,Be7e5,Yd2d4] [%CSL Gc4,Bf5]")
    assert arrows["12,28"] == 0  # roja
    assert arrows["52,36"] == 2  # azul
    assert arrows["11,27"] == 3  # amarilla
    assert marks["26"] == 1 and marks["37"] == 3


def test_parse_multiple_tags_and_text():
    comment = "Buena jugada [%cal Ge2e4] y también [%cal Gd2d4] [%csl Rc4]"
    arrows, marks = parse_drawings(comment)
    assert set(arrows) == {"12,28", "11,27"}
    assert marks == {"26": 2}


def test_strip_and_display():
    assert strip_tags("Hola [%cal Ge2e4] mundo [%clk 0:01:00]") == "Hola mundo"
    assert display_comment("[%eval 0.34]") == ""
    assert display_comment("  Texto   con   espacios ") == "Texto con espacios"


def test_drawings_roundtrip():
    drawings = {"arrows": {"12,28": 1, "52,36": 0}, "marks": {"26": 2}}
    tags = drawings_to_tags(drawings)
    arrows, marks = parse_drawings(tags)
    assert arrows == drawings["arrows"]
    assert marks == drawings["marks"]


def test_merge_comment_replaces_tags():
    merged = merge_comment("Idea [%cal Gd2d4]", {"arrows": {"12,28": 1}, "marks": {}})
    assert "Ge2e4" in merged and "Gd2d4" not in merged and merged.startswith("Idea")


# --------------------------------------------------------------------- #
# GameDoc: dibujos
# --------------------------------------------------------------------- #
def test_drawings_extracted_on_init():
    doc = GameDoc(read_sample())
    doc.goto_next()  # 1. e4
    drawings = doc.current_drawings()
    assert "12,28" in drawings["arrows"] and "11,27" in drawings["arrows"]
    assert drawings["marks"] == {"26": 2, "37": 0}
    doc.goto_next()  # 1... e5
    assert doc.current_drawings()["arrows"] == {"52,36": 0}


def test_drawings_survive_navigation():
    doc = GameDoc(read_sample())
    doc.goto_next()
    assert doc.current_drawings()["arrows"]
    doc.goto_previous()
    assert doc.current_drawings()["arrows"] == {}
    doc.goto_next()
    assert "12,28" in doc.current_drawings()["arrows"]


def test_export_reinjects_drawings():
    doc = GameDoc(read_sample())
    text = doc.movetext()
    assert "[%cal" in text and "[%csl" in text
    reimported = import_game(text)
    assert reimported is not None
    doc2 = GameDoc(reimported)
    doc2.goto_next()
    assert "12,28" in doc2.current_drawings()["arrows"]


def test_user_drawings_persisted_on_export():
    doc = GameDoc()
    doc.set_current_drawings({"arrows": {"12,28": 1}, "marks": {"26": 2}})
    text = doc.movetext()
    assert "Ge2e4" in text and "[%csl" in text
    doc2 = GameDoc(import_game(text))
    assert doc2.current_drawings()["arrows"] == {"12,28": 1}


def test_clearing_drawings_removes_tags():
    doc = GameDoc(read_sample())
    doc.goto_next()  # 1. e4
    doc.set_current_drawings({"arrows": {}, "marks": {}})
    text = doc.movetext()
    # La flecha e2e4 solo estaba en el comentario de 1.e4: debe desaparecer.
    assert "Ge2e4" not in text
    # Pero las flechas de las demás jugadas se conservan.
    assert "Re7e5" in text


def test_drawings_stay_with_their_pgn_node_after_transposition():
    """Dos variantes pueden llegar al mismo tablero con dibujos distintos."""
    game = chess.pgn.Game()
    board = game.board()

    main = game.add_variation(board.parse_san("Nf3"))
    board.push(main.move)
    black = main.add_variation(board.parse_san("d5"))
    board.push(black.move)
    main_end = black.add_variation(board.parse_san("g3"))
    main_end.comment = "[%cal Gg1f3]"

    board = game.board()
    branch = game.add_variation(board.parse_san("g3"))
    board.push(branch.move)
    black = branch.add_variation(board.parse_san("d5"))
    board.push(black.move)
    branch_end = black.add_variation(board.parse_san("Nf3"))
    branch_end.comment = "[%cal Gg2g3]"

    doc = GameDoc(game)
    doc.go_to(main_end)
    assert doc.current_drawings()["arrows"] == {"6,21": 1}
    doc.go_to(branch_end)
    assert doc.current_drawings()["arrows"] == {"14,22": 1}


# --------------------------------------------------------------------- #
# GameDoc: navegación y variantes
# --------------------------------------------------------------------- #
def test_navigation_fast_paths():
    doc = GameDoc(read_sample())
    doc.goto_end()
    end_board = doc.board.fen()
    doc.goto_start()
    assert doc.board.fen() == chess.STARTING_FEN
    doc.goto_end()
    assert doc.board.fen() == end_board
    # variante
    doc.goto_start()
    for _ in range(5):
        doc.goto_next()
    node = doc.node  # 3. Bb5
    branch = node.parent.variations[1]
    doc.go_to(branch)
    assert doc.node.move == chess.Move.from_uci("f1c4")
    assert doc.board.piece_at(chess.C4) == chess.Piece(chess.BISHOP, chess.WHITE)


def test_play_move_and_variation():
    doc = GameDoc()
    assert doc.play_san("e4")
    assert doc.play_san("e5")
    doc.goto_previous()
    assert doc.play_san("c5")  # variante
    assert len(doc.game.variations[0].variations) == 2
    assert doc.dirty


def test_delete_variation():
    doc = GameDoc(read_sample())
    doc.goto_start()
    for _ in range(5):
        doc.goto_next()
    branch = doc.node.parent.variations[1]
    doc.go_to(branch)
    doc.delete_variation(branch)
    assert len(doc.node.variations) == 1


def test_custom_fen_roundtrip():
    pgn = (
        '[SetUp "1"]\n'
        '[FEN "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"]\n'
        '[White "A"]\n[Black "B"]\n[Result "*"]\n\n2. Nf3 Nc6 *'
    )
    game = import_game(pgn)
    doc = GameDoc(game)
    exported = doc.export_game()
    assert exported.headers.get("FEN")
    moves = list(exported.mainline_moves())
    assert moves == [chess.Move.from_uci("g1f3"), chess.Move.from_uci("b8c6")]


def test_nags_standard():
    doc = GameDoc(read_sample())
    doc.goto_next()
    doc.goto_next()
    doc.goto_next()  # 2. Nf3 $1
    assert 1 in doc.node.nags
    doc.set_move_nag(3)
    assert 3 in doc.node.nags and 1 not in doc.node.nags
    doc.set_position_nag(14)
    assert 14 in doc.node.nags
    text = doc.movetext()
    assert "$3" in text and "$14" in text


# --------------------------------------------------------------------- #
# Base de datos
# --------------------------------------------------------------------- #
def make_pgn(path: Path, n: int = 60) -> None:
    lines = []
    for i in range(n):
        white = "Rival Target" if i % 2 == 0 else f"Player{i}"
        black = "Rival Target" if i % 2 == 1 else f"Opponent{i}"
        result = ["1-0", "0-1", "1/2-1/2"][i % 3]
        lines.append(
            f'[Event "Test {i}"]\n[White "{white}"]\n[Black "{black}"]\n'
            f'[Result "{result}"]\n[Date "2026.01.{(i % 28) + 1:02d}"]\n\n'
            f"1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 {result}\n"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def test_import_and_stats(tmp_path):
    pgn = tmp_path / "games.pgn"
    make_pgn(pgn, 60)
    db = ChessDatabase(tmp_path / "test.csdb")
    imported, skipped = db.import_pgn(pgn)
    assert imported == 60 and skipped == 0
    assert db.game_count() == 60
    stats = db.opening_stats(chess.STARTING_FEN)
    assert stats and stats[0].san == "e4" and stats[0].games == 60
    # filtro por rival
    rival_stats = db.opening_stats(chess.STARTING_FEN, player="Rival Target")
    assert sum(s.games for s in rival_stats) == 60
    # solo blancas del rival (30)
    white_stats = db.opening_stats(chess.STARTING_FEN, player="Rival Target", player_color="white")
    assert sum(s.games for s in white_stats) == 30
    rows = db.search(player="Rival Target", player_color="black")
    assert len(rows) == 30
    db.close()


def test_import_progress_and_cancel(tmp_path):
    pgn = tmp_path / "games.pgn"
    make_pgn(pgn, 500)
    db = ChessDatabase(tmp_path / "test.csdb")
    calls = []
    imported, _ = db.import_pgn(pgn, progress=lambda p, c: calls.append((p, c)))
    assert imported == 500
    assert calls and calls[-1][0] == 100

    import threading
    cancel = threading.Event()
    cancel.set()
    db2 = ChessDatabase(tmp_path / "test2.csdb")
    imported2, _ = db2.import_pgn(pgn, cancel=cancel)
    assert imported2 == 0
    db.close()
    db2.close()


def test_import_speed(tmp_path):
    pgn = tmp_path / "big.pgn"
    make_pgn(pgn, 1000)
    db = ChessDatabase(tmp_path / "speed.csdb")
    start = time.perf_counter()
    imported, _ = db.import_pgn(pgn)
    elapsed = time.perf_counter() - start
    assert imported == 1000
    # Con commits por partida esto tardaba varios segundos; por lotes debe
    # ser mucho más rápido. Margen amplio para máquinas lentas.
    assert elapsed < 15.0, f"Importación demasiado lenta: {elapsed:.1f}s"
    db.close()


def test_search_position(tmp_path):
    pgn = tmp_path / "games.pgn"
    make_pgn(pgn, 10)
    db = ChessDatabase(tmp_path / "s.csdb")
    db.import_pgn(pgn)
    board = chess.Board()
    for move in ["e4", "e5", "Nf3"]:
        board.push_san(move)
    rows = db.search(position=board.fen())
    assert len(rows) == 10
    db.close()


def test_export_pgn(tmp_path):
    pgn = tmp_path / "games.pgn"
    make_pgn(pgn, 5)
    db = ChessDatabase(tmp_path / "e.csdb")
    db.import_pgn(pgn)
    out = tmp_path / "out.pgn"
    count = db.export_pgn(out)
    assert count == 5
    text = out.read_text(encoding="utf-8")
    assert text.count("[Event ") == 5
    db.close()


def test_player_counts(tmp_path):
    pgn = tmp_path / "games.pgn"
    make_pgn(pgn, 20)
    db = ChessDatabase(tmp_path / "p.csdb")
    db.import_pgn(pgn)
    counts = db.player_counts()
    assert counts["Rival Target"] == 20
    white, black = db.player_color_counts("Rival Target")
    assert (white, black) == (10, 10)
    db.close()
