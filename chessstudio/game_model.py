"""Modelo de documento de partida (árbol de variantes, navegación y dibujos).

Cambios clave:
  * Las flechas/marcas ``[%cal]``/``[%csl]`` se extraen SIEMPRE al construir
    el documento y se guardan por nodo, no solo por posición. Así dos
    variantes que llegan a la misma posición conservan sus anotaciones
    propias al abrir PGN de otros programas.
  * Al exportar/guardar, los dibujos se reinyectan como tags PGN estándar,
    de modo que el ida y vuelta con otros programas funciona.
  * Navegación O(1) en el caso habitual (avanzar/retroceder una jugada).
  * Los NAG se guardan en ``node.nags`` (el estándar de python-chess), no en
    un atributo inventado que no se exportaba.
"""
from __future__ import annotations

import io

import chess
import chess.pgn
from PySide6.QtCore import QObject, Signal

from chessstudio.database import DEFAULT_HEADERS, import_game
from chessstudio.pgn_utils import has_drawing_tags, parse_drawings, replace_drawing_tags, walk_game

# Símbolos NAG estándar
NAG_SYMBOLS = {
    0: "",
    1: "!", 2: "?", 3: "!!", 4: "??", 5: "!?", 6: "?!", 7: "□",
    10: "=", 11: "=", 12: "=", 13: "∞",
    14: "+/=", 15: "=/+", 16: "+/-", 17: "-/+", 18: "+-", 19: "-+",
    20: "+--", 21: "⊙", 22: "○", 23: "⌛", 24: "↑", 25: "→",
    26: "⯮", 27: "⇄", 32: "↻", 36: "↑", 40: "→", 44: "=∞",
    132: "↑", 133: "↑", 134: "⇑", 135: "⇓", 136: "○", 138: "⊕",
    140: "∆", 142: "⌓", 146: "N",
}

MOVE_EVAL_NAGS = {1, 2, 3, 4, 5, 6, 7}
POSITION_EVAL_NAGS = {10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22}


class GameDoc(QObject):
    positionChanged = Signal(chess.Board)
    structureChanged = Signal()
    headersChanged = Signal()
    moveAdded = Signal()
    drawingsChanged = Signal()

    def __init__(self, game: chess.pgn.Game | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self.game = game if game is not None else chess.pgn.Game()
        if game is None:
            for header in DEFAULT_HEADERS:
                if header not in self.game.headers:
                    self.game.headers[header] = ""
            self.game.headers["Result"] = "*"
        self.node: chess.pgn.GameNode = self.game
        self.board: chess.Board = self.game.board()
        self._board_node: chess.pgn.GameNode | None = self.game
        self._dirty = False
        # Los dibujos pertenecen al comentario de un nodo PGN. Indexarlos por
        # identidad del nodo evita mezclar flechas de variantes/transposiciones
        # que terminan en el mismo FEN.
        self._drawings_by_node: dict[int, dict] = {}
        self._extract_drawings()

    # ------------------------------------------------------------------ #
    # Estado
    # ------------------------------------------------------------------ #
    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_saved(self) -> None:
        self._dirty = False

    def title(self) -> str:
        white = self.game.headers.get("White", "?") or "?"
        black = self.game.headers.get("Black", "?") or "?"
        return f"{white} - {black}"

    def load_pgn(self, movetext: str) -> bool:
        game = import_game(movetext)
        if game is None:
            return False
        self.game = game
        self.node = self.game
        self.board = self.game.board()
        self._board_node = self.game
        self._drawings_by_node.clear()
        self._extract_drawings()
        self._dirty = False
        self.headersChanged.emit()
        self.structureChanged.emit()
        self.positionChanged.emit(self.board)
        self.drawingsChanged.emit()
        return True

    @staticmethod
    def load_pgn_bytes(data: bytes) -> chess.pgn.Game | None:
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                game = chess.pgn.read_game(io.StringIO(data.decode(encoding)))
            except Exception:
                continue
            if game is not None:
                return game
        return None

    def apply_headers(self, headers: dict) -> None:
        for key, value in headers.items():
            self.game.headers[key] = value
        self._dirty = True
        self.headersChanged.emit()

    # ------------------------------------------------------------------ #
    # Dibujos (flechas y casillas)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalize_drawings(drawings: dict) -> dict:
        """Normaliza datos recibidos de la interfaz antes de persistirlos."""
        return {
            "arrows": {str(key): int(value) for key, value in (drawings.get("arrows") or {}).items()},
            "marks": {str(key): int(value) for key, value in (drawings.get("marks") or {}).items()},
        }

    def _extract_drawings(self) -> None:
        """Extrae ``[%cal]``/``[%csl]`` de todos los comentarios PGN.

        Un comentario posterior a una jugada describe su posición resultante,
        pero la anotación sigue perteneciendo al *nodo* que contiene ese
        comentario. No se combina por FEN: una transposición o dos variantes
        pueden compartir tablero y tener flechas diferentes.
        """
        for node, _board in walk_game(self.game):
            if not node.comment:
                continue
            arrows, marks = parse_drawings(node.comment)
            if arrows or marks:
                self._drawings_by_node[id(node)] = {"arrows": arrows, "marks": marks}

    def current_drawings(self) -> dict:
        return self._drawings_by_node.get(id(self.node), {"arrows": {}, "marks": {}})

    def set_current_drawings(self, drawings: dict) -> None:
        key = id(self.node)
        normalized = self._normalize_drawings(drawings)
        current = self._drawings_by_node.get(key)
        if current == normalized:
            return
        if not normalized["arrows"] and not normalized["marks"]:
            self._drawings_by_node.pop(key, None)
        else:
            self._drawings_by_node[key] = normalized
        self._dirty = True
        self.drawingsChanged.emit()

    # ------------------------------------------------------------------ #
    # Navegación
    # ------------------------------------------------------------------ #
    @staticmethod
    def _node_path(node: chess.pgn.GameNode) -> list[chess.Move]:
        moves: list[chess.Move] = []
        current = node
        while current.parent is not None and current.move is not None:
            moves.append(current.move)
            current = current.parent
        moves.reverse()
        return moves

    def _refresh_board(self) -> None:
        node = self.node
        previous = self._board_node
        fast = False
        if previous is node:
            fast = True
        elif previous is not None and node.parent is previous and node.move is not None:
            self.board.push(node.move)
            fast = True
        elif previous is not None and previous.parent is node:
            self.board.pop()
            fast = True
        if not fast:
            self.board = self.game.board()
            for move in self._node_path(node):
                self.board.push(move)
        self._board_node = node
        self.positionChanged.emit(self.board)
        self.drawingsChanged.emit()

    def go_to(self, node: chess.pgn.GameNode) -> None:
        self.node = node
        self._refresh_board()

    def goto_start(self) -> None:
        self.go_to(self.game)

    def goto_end(self) -> None:
        while self.node.variations:
            self.node = self.node.variations[0]
        self._refresh_board()

    def goto_next(self) -> None:
        if self.node.variations:
            self.go_to(self.node.variations[0])

    def goto_previous(self) -> None:
        if self.node.parent is not None:
            self.go_to(self.node.parent)

    def find_node(self, node_id: int) -> chess.pgn.GameNode | None:
        stack: list[chess.pgn.GameNode] = [self.game]
        while stack:
            node = stack.pop()
            if id(node) == node_id:
                return node
            stack.extend(node.variations)
        return None

    # ------------------------------------------------------------------ #
    # Edición
    # ------------------------------------------------------------------ #
    def play_move(self, move: chess.Move) -> bool:
        if move not in self.board.legal_moves:
            return False
        for child in self.node.variations:
            if child.move == move:
                self.go_to(child)
                return True
        new_node = self.node.add_variation(move)
        self._dirty = True
        self.node = new_node
        self._refresh_board()
        self.structureChanged.emit()
        self.moveAdded.emit()
        return True

    def play_san(self, san: str) -> bool:
        try:
            move = self.board.parse_san(san)
        except ValueError:
            return False
        return self.play_move(move)

    def set_comment(self, text: str, node: chess.pgn.GameNode | None = None) -> None:
        target = node if node is not None else self.node
        target.comment = text
        # Mantener sincronizados los dibujos extraídos de ese comentario. Si
        # se han quitado los tags, también se elimina el estado antiguo.
        arrows, marks = parse_drawings(text)
        key = id(target)
        if arrows or marks:
            self._drawings_by_node[key] = {"arrows": arrows, "marks": marks}
        else:
            self._drawings_by_node.pop(key, None)
        self._dirty = True
        self.structureChanged.emit()
        self.drawingsChanged.emit()

    def delete_variation(self, node: chess.pgn.GameNode) -> None:
        parent = node.parent
        if parent is None:
            return
        was_current = False
        cursor: chess.pgn.GameNode | None = self.node
        while cursor is not None:
            if cursor is node:
                was_current = True
                break
            cursor = cursor.parent
        parent.remove_variation(node)
        self._dirty = True
        if was_current:
            self.node = parent
        self._board_node = None  # forzar reconstrucción del tablero
        self._refresh_board()
        self.structureChanged.emit()

    def promote_variation(self, node: chess.pgn.GameNode) -> None:
        parent = node.parent
        if parent is None:
            return
        parent.promote_variation(node)
        self._dirty = True
        self.structureChanged.emit()

    def _export_with_drawings(self, headers: bool) -> str:
        """Exporta el juego con los dibujos actuales reinyectados como tags.

        Se procesan tanto las posiciones con dibujos actuales como las que
        tenían tags al importar (para que borrar los dibujos de una posición
        también elimine sus tags). El resto de etiquetas (%eval, %clk...) se
        conserva intacto. Los comentarios originales se restauran al final.
        """
        saved: list[tuple[chess.pgn.GameNode, str]] = []
        empty = {"arrows": {}, "marks": {}}
        for node, _board in walk_game(self.game):
            current = self._drawings_by_node.get(id(node))
            if current is not None or has_drawing_tags(node.comment):
                saved.append((node, node.comment))
                node.comment = replace_drawing_tags(node.comment, current if current is not None else empty)
        try:
            exporter = chess.pgn.StringExporter(headers=headers, variations=True, comments=True)
            return self.game.accept(exporter).strip()
        finally:
            for node, comment in saved:
                node.comment = comment

    def movetext(self) -> str:
        return self._export_with_drawings(headers=False)

    def export_game(self) -> chess.pgn.Game:
        """Copia del juego con cabeceras, comentarios y dibujos listos para
        guardar/exportar. Se exporta el PGN completo (incluida la cabecera
        FEN si la posición inicial es personalizada) y se vuelve a parsear,
        de modo que nada se pierde en el ida y vuelta."""
        game = import_game(self._export_with_drawings(headers=True))
        if game is None:
            game = chess.pgn.Game()
            for key, value in self.game.headers.items():
                game.headers[key] = value
        return game

    # ------------------------------------------------------------------ #
    # NAG (símbolos de evaluación)
    # ------------------------------------------------------------------ #
    def set_move_nag(self, nag: int, node: chess.pgn.GameNode | None = None) -> None:
        target = node if node is not None else self.node
        target.nags.difference_update(MOVE_EVAL_NAGS)
        if nag:
            target.nags.add(nag)
        self._dirty = True
        self.structureChanged.emit()

    def set_position_nag(self, nag: int, node: chess.pgn.GameNode | None = None) -> None:
        target = node if node is not None else self.node
        target.nags.difference_update(POSITION_EVAL_NAGS)
        if nag:
            target.nags.add(nag)
        self._dirty = True
        self.structureChanged.emit()

    def get_move_nag(self, node: chess.pgn.GameNode | None = None) -> int:
        target = node if node is not None else self.node
        values = target.nags & MOVE_EVAL_NAGS
        return min(values) if values else 0

    def get_position_nag(self, node: chess.pgn.GameNode | None = None) -> int:
        target = node if node is not None else self.node
        values = target.nags & POSITION_EVAL_NAGS
        return min(values) if values else 0
