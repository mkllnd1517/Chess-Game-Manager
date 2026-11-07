"""Base de datos de partidas en SQLite con índice de posiciones.

Optimizaciones frente a la versión original:
  * Importación PGN por lotes (una transacción cada N partidas) en lugar de
    un COMMIT por partida, que era lo que bloqueaba la interfaz.
  * Modo WAL + synchronous NORMAL para escrituras rápidas y lecturas
    concurrentes (el hilo de importación escribe mientras la UI lee).
  * Callbacks de progreso y cancelación para importar en segundo plano.
  * Filtros por jugador/color en búsquedas y estadísticas de aperturas.
"""
from __future__ import annotations

import collections
import io
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import chess
import chess.pgn

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    white TEXT NOT NULL DEFAULT '',
    black TEXT NOT NULL DEFAULT '',
    event TEXT NOT NULL DEFAULT '',
    site TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL DEFAULT '',
    round TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '*',
    eco TEXT NOT NULL DEFAULT '',
    movetext TEXT NOT NULL DEFAULT '',
    headers TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS pos_index (
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply INTEGER NOT NULL,
    poskey TEXT NOT NULL,
    next_san TEXT NOT NULL DEFAULT '',
    result TEXT NOT NULL DEFAULT '*'
);
CREATE INDEX IF NOT EXISTS idx_games_white ON games(white);
CREATE INDEX IF NOT EXISTS idx_games_black ON games(black);
CREATE INDEX IF NOT EXISTS idx_games_event ON games(event);
CREATE INDEX IF NOT EXISTS idx_games_date ON games(date);
CREATE INDEX IF NOT EXISTS idx_games_eco ON games(eco);
CREATE INDEX IF NOT EXISTS idx_pos_poskey ON pos_index(poskey);
"""

DEFAULT_HEADERS = ["Event", "Site", "Date", "Round", "White", "Black", "Result", "ECO"]

IMPORT_BATCH = 200


def poskey(board: chess.Board) -> str:
    """Clave de posición: piezas, turno, enroques y en passant (sin contadores)."""
    return " ".join(board.fen().split(" ")[:4])


def export_movetext(game: chess.pgn.Game) -> str:
    exporter = chess.pgn.StringExporter(headers=False, variations=True, comments=True)
    return game.accept(exporter).strip()


def import_game(movetext: str) -> chess.pgn.Game | None:
    if not movetext.strip():
        return None
    try:
        return chess.pgn.read_game(io.StringIO(movetext))
    except Exception:
        return None


def parse_stored_game(movetext: str, headers: dict) -> chess.pgn.Game | None:
    """Reconstruye una partida guardada (movetext + cabeceras).

    Las cabeceras FEN/SetUp deben anteponerse ANTES de parsear para que las
    jugadas se interpreten desde la posición inicial correcta (si no, una
    partida que empieza de una posición personalizada se corrompe).
    """
    fen = headers.get("FEN")
    if fen:
        movetext = f'[FEN "{fen}"]\n[SetUp "1"]\n\n{movetext}'
    game = import_game(movetext)
    if game is None:
        return None
    for key, value in headers.items():
        game.headers[key] = value
    return game


# Orden estándar PGN (Seven Tag Roster) para exportar cabeceras.
_STR_ORDER = ["Event", "Site", "Date", "Round", "White", "Black", "Result"]


def format_pgn_headers(headers: dict) -> str:
    """Formatea cabeceras PGN con el escape correcto (sin reparsear la partida)."""
    keys = [k for k in _STR_ORDER if k in headers]
    keys += sorted(k for k in headers if k not in _STR_ORDER)
    lines = []
    for key in keys:
        value = str(headers[key]).replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'[{key} "{value}"]')
    return "\n".join(lines)


@dataclass
class GameRow:
    id: int
    white: str
    black: str
    event: str
    site: str
    date: str
    round: str
    result: str
    eco: str
    movetext: str = field(default="", repr=False)
    headers: dict = field(default_factory=dict, repr=False)


@dataclass
class MoveStat:
    san: str
    games: int
    white_wins: int
    draws: int
    black_wins: int
    last_game_year: int | None = None

    @property
    def white_score(self) -> float:
        if not self.games:
            return 0.0
        return (self.white_wins + self.draws / 2) / self.games * 100.0


class ChessDatabase:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA temp_store = MEMORY")
        self.conn.execute("PRAGMA cache_size = -16000")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.commit()
        except sqlite3.Error:
            pass
        self.conn.close()

    # ------------------------------------------------------------------ #
    # Escritura
    # ------------------------------------------------------------------ #
    def game_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]

    def _insert_game(self, game: chess.pgn.Game) -> int:
        """Inserta partida + índice de posiciones SIN hacer commit."""
        headers = {k: str(v) for k, v in dict(game.headers).items()}
        cur = self.conn.execute(
            "INSERT INTO games (white, black, event, site, date, round, result, eco, movetext, headers)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                headers.get("White", ""),
                headers.get("Black", ""),
                headers.get("Event", ""),
                headers.get("Site", ""),
                headers.get("Date", ""),
                headers.get("Round", ""),
                headers.get("Result", "*"),
                headers.get("ECO", ""),
                export_movetext(game),
                json.dumps(headers, ensure_ascii=False),
            ),
        )
        game_id = int(cur.lastrowid)
        self._index_game(game_id, game)
        return game_id

    def add_game(self, game: chess.pgn.Game) -> int:
        game_id = self._insert_game(game)
        self.conn.commit()
        return game_id

    def _index_game(self, game_id: int, game: chess.pgn.Game) -> None:
        """Indexa la línea principal (las variantes de análisis no cuentan
        como partidas jugadas y no deben inflar las estadísticas)."""
        board = game.board()
        node: chess.pgn.GameNode = game
        ply = 0
        result = game.headers.get("Result", "*")
        rows: list[tuple] = []
        while node.variations:
            node = node.variations[0]
            move = node.move
            key = poskey(board)
            try:
                san = board.san(move)
            except Exception:
                san = board.uci(move)
            rows.append((game_id, ply, key, san, result))
            board.push(move)
            ply += 1
        if rows:
            self.conn.executemany(
                "INSERT INTO pos_index (game_id, ply, poskey, next_san, result) VALUES (?,?,?,?,?)",
                rows,
            )

    def update_game(self, game_id: int, game: chess.pgn.Game) -> None:
        headers = {k: str(v) for k, v in dict(game.headers).items()}
        self.conn.execute(
            "UPDATE games SET white=?, black=?, event=?, site=?, date=?, round=?, result=?, eco=?, movetext=?, headers=?"
            " WHERE id=?",
            (
                headers.get("White", ""),
                headers.get("Black", ""),
                headers.get("Event", ""),
                headers.get("Site", ""),
                headers.get("Date", ""),
                headers.get("Round", ""),
                headers.get("Result", "*"),
                headers.get("ECO", ""),
                export_movetext(game),
                json.dumps(headers, ensure_ascii=False),
                game_id,
            ),
        )
        self.conn.execute("DELETE FROM pos_index WHERE game_id = ?", (game_id,))
        self._index_game(game_id, game)
        self.conn.commit()

    def delete_games(self, ids: list[int]) -> None:
        self.conn.executemany("DELETE FROM games WHERE id = ?", [(i,) for i in ids])
        self.conn.commit()

    def clear(self) -> None:
        self.conn.execute("DELETE FROM pos_index")
        self.conn.execute("DELETE FROM games")
        self.conn.commit()

    def import_pgn(
        self,
        path: Path | str,
        progress=None,
        cancel=None,
        player_counts: collections.Counter | None = None,
    ) -> tuple[int, int]:
        """Importa un PGN por lotes.

        ``progress(percent, imported)`` se llama periódicamente.
        ``cancel`` es un ``threading.Event`` opcional para abortar.
        ``player_counts`` (Counter) acumula partidas por jugador si se pasa.
        """
        path = Path(path)
        size = max(1, path.stat().st_size)
        imported = 0
        skipped = 0
        batch = 0
        consecutive_errors = 0
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            while True:
                if cancel is not None and cancel.is_set():
                    break
                try:
                    game = chess.pgn.read_game(handle)
                except Exception:
                    skipped += 1
                    consecutive_errors += 1
                    # Asegurar avance para no quedar en bucle con un PGN corrupto.
                    if not handle.readline():
                        break
                    if consecutive_errors > 200:
                        break
                    continue
                if game is None:
                    break
                consecutive_errors = 0

                if player_counts is not None:
                    white = game.headers.get("White", "").strip()
                    black = game.headers.get("Black", "").strip()
                    if white and white != "?":
                        player_counts[white] += 1
                    if black and black != "?":
                        player_counts[black] += 1

                if not game.variations:
                    skipped += 1
                    continue
                try:
                    self._insert_game(game)
                    imported += 1
                    batch += 1
                except Exception:
                    skipped += 1

                if batch >= IMPORT_BATCH:
                    self.conn.commit()
                    batch = 0
                    if progress is not None:
                        percent = min(99, int(handle.buffer.tell() * 100 / size))
                        progress(percent, imported)
            self.conn.commit()
        if progress is not None:
            progress(100, imported)
        return imported, skipped

    # ------------------------------------------------------------------ #
    # Lectura
    # ------------------------------------------------------------------ #
    def get_game(self, game_id: int) -> GameRow | None:
        row = self.conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        return _row_to_game(row) if row is not None else None

    def export_pgn(
        self,
        path: Path | str,
        ids: list[int] | None = None,
        progress=None,
        cancel=None,
    ) -> int:
        """Exporta partidas a PGN.

        Escritura DIRECTA de cabeceras + movetext almacenados (sin reparsear
        cada partida, mucho más rápido en bases grandes). Escritura ATÓMICA:
        se escribe a un temporal y se renombra al terminar, de modo que un
        fallo o cancelación nunca deja un PGN parcial en el destino.
        """
        path = Path(path)
        if ids:
            placeholders = ",".join("?" for _ in ids)
            cursor = self.conn.execute(
                f"SELECT headers, movetext FROM games WHERE id IN ({placeholders}) ORDER BY id",
                ids,
            )
        else:
            cursor = self.conn.execute("SELECT headers, movetext FROM games ORDER BY id")
        tmp_path = path.with_name(path.name + ".tmp")
        count = 0
        cancelled = False
        try:
            with open(tmp_path, "w", encoding="utf-8", newline="\n") as handle:
                for row in cursor:
                    if cancel is not None and cancel.is_set():
                        cancelled = True
                        break
                    headers = json.loads(row["headers"])
                    handle.write(format_pgn_headers(headers))
                    handle.write("\n\n")
                    handle.write(row["movetext"].strip())
                    handle.write("\n\n")
                    count += 1
                    if progress is not None and count % 200 == 0:
                        progress(count)
            if cancelled:
                tmp_path.unlink(missing_ok=True)
            else:
                tmp_path.replace(path)  # atómico en el mismo sistema de archivos
                if progress is not None:
                    progress(count)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
        return count

    def search(
        self,
        white: str = "",
        black: str = "",
        event: str = "",
        site: str = "",
        date_from: str = "",
        date_to: str = "",
        result: str = "",
        eco: str = "",
        position: str = "",
        player: str = "",
        player_color: str = "both",
        limit: int = 1000,
    ) -> list[GameRow]:
        clauses: list[str] = []
        params: list = []
        for column, value in (
            ("white", white),
            ("black", black),
            ("event", event),
            ("site", site),
            ("eco", eco),
        ):
            if value:
                clauses.append(f"g.{column} LIKE ?")
                params.append(f"%{value}%")
        if date_from:
            clauses.append("g.date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("g.date <= ?")
            params.append(date_to)
        if result:
            clauses.append("g.result = ?")
            params.append(result)
        if player:
            if player_color == "white":
                clauses.append("g.white = ?")
                params.append(player)
            elif player_color == "black":
                clauses.append("g.black = ?")
                params.append(player)
            else:
                clauses.append("(g.white = ? OR g.black = ?)")
                params.extend([player, player])

        join = ""
        if position:
            join = "JOIN pos_index p ON p.game_id = g.id"
            clauses.append("p.poskey = ?")
            params.append(_clean_fen(position))

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT DISTINCT g.* FROM games g {join} {where} ORDER BY g.date DESC, g.id DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [_row_to_game(r) for r in rows]

    def opening_stats(self, fen: str, player: str = "", player_color: str = "both") -> list[MoveStat]:
        key = _clean_fen(fen)
        sql = (
            "SELECT p.next_san, p.result, COUNT(*) AS n, MAX(substr(g.date, 1, 4)) AS last_year "
            "FROM pos_index p JOIN games g ON g.id = p.game_id WHERE p.poskey = ?"
        )
        params: list = [key]
        if player:
            if player_color == "white":
                sql += " AND g.white = ?"
                params.append(player)
            elif player_color == "black":
                sql += " AND g.black = ?"
                params.append(player)
            else:
                sql += " AND (g.white = ? OR g.black = ?)"
                params.extend([player, player])
        sql += " GROUP BY p.next_san, p.result"
        rows = self.conn.execute(sql, params).fetchall()

        stats: dict[str, MoveStat] = {}
        for row in rows:
            san = row["next_san"]
            stat = stats.setdefault(san, MoveStat(san, 0, 0, 0, 0))
            stat.games += row["n"]
            if row["last_year"] and row["last_year"].isdigit():
                year = int(row["last_year"])
                if stat.last_game_year is None or year > stat.last_game_year:
                    stat.last_game_year = year
            if row["result"] == "1-0":
                stat.white_wins += row["n"]
            elif row["result"] == "0-1":
                stat.black_wins += row["n"]
            elif row["result"] == "1/2-1/2":
                stat.draws += row["n"]
        return sorted(stats.values(), key=lambda s: s.games, reverse=True)

    def games_with_position(self, fen: str, limit: int = 1000) -> list[GameRow]:
        key = _clean_fen(fen)
        rows = self.conn.execute(
            "SELECT DISTINCT g.* FROM games g JOIN pos_index p ON p.game_id = g.id "
            "WHERE p.poskey = ? ORDER BY g.id LIMIT ?",
            (key, limit),
        ).fetchall()
        return [_row_to_game(r) for r in rows]

    def player_counts(self) -> collections.Counter:
        """Partidas por jugador (como blancas o negras) en toda la base."""
        counts: collections.Counter = collections.Counter()
        rows = self.conn.execute(
            "SELECT white AS name, COUNT(*) AS n FROM games GROUP BY white "
            "UNION ALL SELECT black, COUNT(*) FROM games GROUP BY black"
        ).fetchall()
        for row in rows:
            name = (row["name"] or "").strip()
            if name and name != "?":
                counts[name] += row["n"]
        return counts

    def player_color_counts(self, player: str) -> tuple[int, int]:
        white = self.conn.execute("SELECT COUNT(*) FROM games WHERE white = ?", (player,)).fetchone()[0]
        black = self.conn.execute("SELECT COUNT(*) FROM games WHERE black = ?", (player,)).fetchone()[0]
        return int(white), int(black)


def _clean_fen(fen: str) -> str:
    return " ".join(fen.split(" ")[:4])


def _row_to_game(row: sqlite3.Row) -> GameRow:
    return GameRow(
        id=row["id"],
        white=row["white"],
        black=row["black"],
        event=row["event"],
        site=row["site"],
        date=row["date"],
        round=row["round"],
        result=row["result"],
        eco=row["eco"],
        movetext=row["movetext"],
        headers=json.loads(row["headers"]),
    )
