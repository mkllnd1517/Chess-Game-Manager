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
-- Las fuentes permiten que un repertorio retire todas las partidas que
-- llegaron en un PGN concreto sin tocar los demás archivos importados.
CREATE TABLE IF NOT EXISTS pgn_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    -- Las fuentes de repertorio indexan todas sus variantes; las partidas y
    -- preparaciones conservan el índice de línea principal habitual.
    include_variations INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS pgn_source_games (
    source_id INTEGER NOT NULL REFERENCES pgn_sources(id) ON DELETE CASCADE,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    PRIMARY KEY (source_id, game_id)
);
CREATE INDEX IF NOT EXISTS idx_games_white ON games(white);
CREATE INDEX IF NOT EXISTS idx_games_black ON games(black);
CREATE INDEX IF NOT EXISTS idx_games_event ON games(event);
CREATE INDEX IF NOT EXISTS idx_games_date ON games(date);
CREATE INDEX IF NOT EXISTS idx_games_eco ON games(eco);
CREATE INDEX IF NOT EXISTS idx_pos_poskey ON pos_index(poskey);
-- Cubre la consulta más frecuente del explorador: posición + siguiente
-- movimiento, sin obligar a SQLite a recorrer todas las partidas de la base.
CREATE INDEX IF NOT EXISTS idx_pos_lookup ON pos_index(poskey, next_san, result, game_id);
CREATE INDEX IF NOT EXISTS idx_pgn_source_games_source ON pgn_source_games(source_id, game_id);
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


@dataclass(frozen=True)
class PgnSource:
    """Un archivo PGN importado en una colección administrada.

    Se guarda únicamente una etiqueta legible —normalmente el nombre del
    archivo—, no su ruta absoluta. Así la colección sigue siendo portable y no
    revela innecesariamente rutas locales en sus metadatos.
    """

    id: int
    label: str
    game_count: int
    include_variations: bool
    imported_at: str


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
        self._migrate_schema()
        self.conn.commit()

    def _migrate_schema(self) -> None:
        """Completa cambios aditivos del esquema en bases ya existentes."""
        source_columns = {
            str(row["name"]) for row in self.conn.execute("PRAGMA table_info(pgn_sources)").fetchall()
        }
        if "include_variations" not in source_columns:
            self.conn.execute(
                "ALTER TABLE pgn_sources ADD COLUMN include_variations INTEGER NOT NULL DEFAULT 0"
            )

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

    def _insert_game(self, game: chess.pgn.Game, include_variations: bool = False) -> int:
        """Inserta una partida y su índice de posiciones sin hacer commit.

        Las partidas jugadas usan únicamente la línea principal. Un repertorio
        de aperturas, en cambio, necesita que cada variante PGN sea navegable;
        por eso puede solicitar un índice de árbol completo.
        """
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
        self._index_game(game_id, game, include_variations=include_variations)
        return game_id

    def add_game(self, game: chess.pgn.Game) -> int:
        game_id = self._insert_game(game)
        self.conn.commit()
        return game_id

    def _index_game(
        self,
        game_id: int,
        game: chess.pgn.Game,
        include_variations: bool = False,
    ) -> None:
        """Indexa una partida para búsquedas y estadísticas de aperturas.

        La colección normal y la preparación de rival representan partidas
        reales: solo cuentan su línea principal. Los PGN de repertorio suelen
        ser árboles de análisis, por lo que ``include_variations`` registra
        todas las aristas del árbol de forma iterativa. Así el explorador puede
        mostrar, por ejemplo, todas las respuestas a ``1.e4`` sin confundirlas
        con una única partida principal.
        """
        result = game.headers.get("Result", "*")
        rows: list[tuple] = []
        if include_variations:
            # (nodo padre, tablero antes de sus continuaciones, profundidad).
            # Evitamos recursión para que árboles PGN profundos sigan siendo
            # importables y navegables sin agotar el límite de Python.
            stack: list[tuple[chess.pgn.GameNode, chess.Board, int]] = [
                (game, game.board(), 0)
            ]
            while stack:
                node, board, ply = stack.pop()
                for child in node.variations:
                    move = child.move
                    if move is None:
                        continue
                    key = poskey(board)
                    try:
                        san = board.san(move)
                    except Exception:
                        try:
                            san = board.uci(move)
                        except Exception:
                            continue
                    rows.append((game_id, ply, key, san, result))
                    next_board = board.copy(stack=False)
                    try:
                        next_board.push(move)
                    except Exception:
                        continue
                    stack.append((child, next_board, ply + 1))
        else:
            board = game.board()
            node: chess.pgn.GameNode = game
            ply = 0
            while node.variations:
                node = node.variations[0]
                move = node.move
                if move is None:
                    break
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
        self.conn.execute("DELETE FROM pgn_source_games")
        self.conn.execute("DELETE FROM pgn_sources")
        self.conn.execute("DELETE FROM games")
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # Fuentes PGN (usadas por los repertorios)
    # ------------------------------------------------------------------ #
    def create_source(self, label: str, include_variations: bool = False) -> int:
        """Registra una fuente PGN y devuelve su identificador.

        ``label`` es texto de interfaz; se acota para evitar que un nombre de
        archivo inesperadamente enorme termine en la base de datos o en la UI.
        Se permiten etiquetas repetidas: dos archivos con el mismo nombre en
        carpetas distintas siguen siendo fuentes independientes y eliminables.
        """
        clean_label = str(label).strip().replace("\x00", " ")[:255] or "PGN sin nombre"
        cursor = self.conn.execute(
            "INSERT INTO pgn_sources (label, include_variations) VALUES (?, ?)",
            (clean_label, int(include_variations)),
        )
        return int(cursor.lastrowid)

    def list_sources(self) -> list[PgnSource]:
        """Devuelve los PGN importados y su número de partidas, más recientes primero."""
        rows = self.conn.execute(
            "SELECT s.id, s.label, s.include_variations, s.imported_at, COUNT(m.game_id) AS game_count "
            "FROM pgn_sources s LEFT JOIN pgn_source_games m ON m.source_id = s.id "
            "GROUP BY s.id ORDER BY s.id DESC"
        ).fetchall()
        return [
            PgnSource(
                id=int(row["id"]),
                label=str(row["label"]),
                game_count=int(row["game_count"]),
                include_variations=bool(row["include_variations"]),
                imported_at=str(row["imported_at"]),
            )
            for row in rows
        ]

    def remove_source(self, source_id: int) -> int:
        """Elimina una fuente y exactamente las partidas que aportó.

        Las partidas añadidas desde otro PGN o creadas manualmente no están
        vinculadas a esta fuente, así que se conservan. La operación se hace en
        una única transacción para no dejar un repertorio a medio actualizar.
        """
        ids = [
            int(row[0])
            for row in self.conn.execute(
                "SELECT game_id FROM pgn_source_games WHERE source_id = ?", (source_id,)
            ).fetchall()
        ]
        if not ids:
            self.conn.execute("DELETE FROM pgn_sources WHERE id = ?", (source_id,))
            self.conn.commit()
            return 0
        self.conn.execute("DELETE FROM pgn_sources WHERE id = ?", (source_id,))
        placeholders = ",".join("?" for _ in ids)
        self.conn.execute(f"DELETE FROM games WHERE id IN ({placeholders})", ids)
        self.conn.commit()
        return len(ids)

    def enable_variation_index_for_sources(self) -> int:
        """Reindexa fuentes PGN antiguas como árboles de repertorio.

        Las primeras versiones del panel de repertorios usaban el índice de
        línea principal de las partidas. Esta migración es idempotente y se
        limita a fuentes marcadas como no indexadas por variantes; las bases
        normales, sin fuentes de repertorio, no se modifican.
        """
        rows = self.conn.execute(
            "SELECT DISTINCT g.id, g.movetext, g.headers "
            "FROM games g JOIN pgn_source_games m ON m.game_id = g.id "
            "JOIN pgn_sources s ON s.id = m.source_id "
            "WHERE s.include_variations = 0"
        ).fetchall()
        if not rows:
            return 0
        converted = 0
        for row in rows:
            game = parse_stored_game(str(row["movetext"]), json.loads(row["headers"]))
            if game is None:
                continue
            game_id = int(row["id"])
            self.conn.execute("DELETE FROM pos_index WHERE game_id = ?", (game_id,))
            self._index_game(game_id, game, include_variations=True)
            converted += 1
        self.conn.execute("UPDATE pgn_sources SET include_variations = 1 WHERE include_variations = 0")
        self.conn.commit()
        return converted

    def import_pgn(
        self,
        path: Path | str,
        progress=None,
        cancel=None,
        player_counts: collections.Counter | None = None,
        source_label: str | None = None,
        include_variations: bool = False,
    ) -> tuple[int, int]:
        """Importa un PGN por lotes.

        ``progress(percent, imported)`` se llama periódicamente.
        ``cancel`` es un ``threading.Event`` opcional para abortar.
        ``player_counts`` (Counter) acumula partidas por jugador si se pasa.
        Si se indica ``source_label``, cada partida queda vinculada al archivo
        importado y puede retirarse después mediante :meth:`remove_source`.
        ``include_variations`` indexa todas las ramas PGN y se reserva para
        repertorios de aperturas; las partidas normales siguen usando solo la
        línea principal.
        """
        path = Path(path)
        size = max(1, path.stat().st_size)
        imported = 0
        skipped = 0
        batch = 0
        consecutive_errors = 0
        source_id: int | None = None
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            if source_label is not None:
                source_id = self.create_source(source_label, include_variations=include_variations)
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
                    game_id = self._insert_game(game, include_variations=include_variations)
                    if source_id is not None:
                        self.conn.execute(
                            "INSERT INTO pgn_source_games (source_id, game_id) VALUES (?, ?)",
                            (source_id, game_id),
                        )
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
        # No mostramos fuentes vacías si el PGN no tenía ninguna partida válida.
        if source_id is not None and imported == 0:
            self.conn.execute("DELETE FROM pgn_sources WHERE id = ?", (source_id,))
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
