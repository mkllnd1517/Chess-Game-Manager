"""Tablero interactivo con arrastre de piezas y anotaciones gráficas.

Mejoras:
  * Piezas pre-renderizadas en QPixmap con caché (el repintado durante el
    arrastre ya no dibuja 9 pasadas de texto por pieza y fotograma).
  * Colores de flechas/marcas con modificadores, como en Lichess:
    clic derecho = verde, Shift = rojo, Alt = azul, Shift+Alt = amarillo.
  * ``set_drawings`` ya no emite señales (evita bucles de sincronización y
    que se borren las flechas importadas al navegar a una posición).
"""
from __future__ import annotations

import math

import chess
from PySide6.QtCore import QPoint, QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QInputDialog, QWidget

from chessstudio.piece_renderer import get_renderer

LIGHT = QColor("#f0d9b5")
DARK = QColor("#b58863")
HIGHLIGHT = QColor(255, 230, 120, 110)
SELECT = QColor(40, 130, 220, 130)
DOT = QColor(30, 30, 30, 80)
CAPTURE_RING = QColor(180, 30, 30, 150)
FRAME = QColor("#3e2723")
FRAME_LIGHT = QColor("#6d4c41")
FRAME_EDGE = QColor("#2a1a12")
COORD_LIGHT = QColor(90, 55, 30, 220)
COORD_DARK = QColor(245, 225, 200, 220)
# Orden: rojo, verde, azul, amarillo (índices usados en %cal)
# Opacidad alta, pero no total: las flechas se distinguen con claridad sin
# ocultar las piezas que atraviesan (especialmente en PGN con muchas marcas).
ARROW_COLORS = [
    QColor(198, 40, 40, 214), QColor(46, 158, 68, 214),
    QColor(47, 111, 208, 214), QColor(224, 160, 32, 222),
]
# Orden: naranja, verde, rojo, azul (índices usados en %csl)
MARK_COLORS = [QColor(235, 160, 40, 110), QColor(60, 175, 80, 110), QColor(215, 60, 60, 110), QColor(70, 120, 220, 110)]

PROMO_CHOICES = [("Dama", chess.QUEEN), ("Torre", chess.ROOK), ("Alfil", chess.BISHOP), ("Caballo", chess.KNIGHT)]


def arrow_color_index(modifiers) -> int:
    shift = bool(modifiers & Qt.ShiftModifier)
    alt = bool(modifiers & Qt.AltModifier)
    if shift and alt:
        return 3
    if shift:
        return 0
    if alt:
        return 2
    return 1


def mark_color_index(modifiers) -> int:
    shift = bool(modifiers & Qt.ShiftModifier)
    alt = bool(modifiers & Qt.AltModifier)
    if shift and alt:
        return 0
    if shift:
        return 2
    if alt:
        return 3
    return 1


class BoardWidget(QWidget):
    moveMade = Signal(chess.Move)
    drawingsChanged = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.board = chess.Board()
        self.orientation = chess.WHITE
        self.last_move: chess.Move | None = None
        self.selected: int | None = None
        self._targets: list[chess.Move] = []
        self._drag_from: int | None = None
        self._drag_pos: QPoint | None = None
        self.arrows: dict[tuple[int, int], int] = {}
        self.marks: dict[int, int] = {}
        self._right_from: int | None = None
        self._right_dragging = False
        self._right_pos: QPoint | None = None
        self._right_color = 1
        self.setMinimumSize(280, 280)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setToolTip(
            "Arrastra o haz clic para mover.\n"
            "Clic derecho: marcar casilla · Arrastrar con botón derecho: flecha.\n"
            "Colores: normal=verde, Shift=rojo, Alt=azul, Shift+Alt=amarillo.\n"
            "Repite el trazo para borrar la anotación."
        )

    # ------------------------------------------------------------------ #
    # API
    # ------------------------------------------------------------------ #
    def sizeHint(self) -> QSize:
        return QSize(480, 480)

    def set_board(self, board: chess.Board, last_move: chess.Move | None = None) -> None:
        self.board = board.copy()
        self.last_move = last_move
        self.selected = None
        self._targets = []
        self._drag_from = None
        self._drag_pos = None
        self.update()

    def flip(self) -> None:
        self.orientation = not self.orientation
        self.update()

    def clear_drawings(self) -> None:
        """Borra las anotaciones de la posición actual (acción del usuario)."""
        if not self.arrows and not self.marks:
            return
        self.arrows.clear()
        self.marks.clear()
        self._right_from = None
        self._right_dragging = False
        self.update()
        self.drawingsChanged.emit()

    def get_drawings(self) -> dict:
        return {
            "arrows": {f"{a},{b}": idx for (a, b), idx in self.arrows.items()},
            "marks": {str(sq): idx for sq, idx in self.marks.items()},
        }

    def set_drawings(self, data: dict) -> None:
        """Carga anotaciones de forma programática (sin emitir señales)."""
        new_arrows: dict[tuple[int, int], int] = {}
        new_marks: dict[int, int] = {}
        for key, idx in (data.get("arrows") or {}).items():
            try:
                a, b = map(int, str(key).split(","))
                new_arrows[(a, b)] = int(idx)
            except (ValueError, TypeError):
                continue
        for key, idx in (data.get("marks") or {}).items():
            try:
                new_marks[int(key)] = int(idx)
            except (ValueError, TypeError):
                continue
        if self.arrows == new_arrows and self.marks == new_marks:
            return
        self.arrows = new_arrows
        self.marks = new_marks
        self.update()

    # ------------------------------------------------------------------ #
    # Geometría
    # ------------------------------------------------------------------ #
    def _square_size(self) -> int:
        return max(1, (min(self.width(), self.height()) - 28) // 8)

    def _square_rect(self, square: int) -> QRect:
        size = self._square_size()
        file = chess.square_file(square)
        rank = chess.square_rank(square)
        if self.orientation == chess.WHITE:
            x, y = file, 7 - rank
        else:
            x, y = 7 - file, rank
        offset_x = (self.width() - size * 8) // 2
        offset_y = (self.height() - size * 8) // 2
        return QRect(offset_x + x * size, offset_y + y * size, size, size)

    def _square_at(self, pos: QPoint) -> int | None:
        size = self._square_size()
        offset_x = (self.width() - size * 8) // 2
        offset_y = (self.height() - size * 8) // 2
        col = (pos.x() - offset_x) // size
        row = (pos.y() - offset_y) // size
        if not (0 <= col < 8 and 0 <= row < 8):
            return None
        if self.orientation == chess.WHITE:
            return chess.square(col, 7 - row)
        return chess.square(7 - col, row)

    def _board_area(self) -> QRect:
        size = self._square_size()
        offset_x = (self.width() - size * 8) // 2
        offset_y = (self.height() - size * 8) // 2
        return QRect(offset_x, offset_y, size * 8, size * 8)

    # ------------------------------------------------------------------ #
    # Pintado
    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        size = self._square_size()
        board_area = self._board_area()

        painter.fillRect(self.rect(), FRAME)
        painter.setPen(QPen(FRAME_LIGHT, 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(board_area.adjusted(-10, -10, 10, 10), 6, 6)
        painter.setPen(QPen(FRAME_EDGE, 2))
        painter.drawRect(board_area.adjusted(-2, -2, 2, 2))

        for square in chess.SQUARES:
            rect = self._square_rect(square)
            light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
            painter.fillRect(rect, LIGHT if light else DARK)

        for square, idx in self.marks.items():
            painter.fillRect(self._square_rect(square), MARK_COLORS[idx % len(MARK_COLORS)])

        if self.last_move is not None:
            painter.fillRect(self._square_rect(self.last_move.from_square), HIGHLIGHT)
            painter.fillRect(self._square_rect(self.last_move.to_square), HIGHLIGHT)

        if self.selected is not None:
            painter.fillRect(self._square_rect(self.selected), SELECT)

        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece is None:
                continue
            if self._drag_from == square and self._drag_pos is not None:
                continue
            painter.drawPixmap(self._square_rect(square).topLeft(), self._piece_pixmap(piece, size))

        for move in self._targets:
            rect = self._square_rect(move.to_square)
            if self.board.is_capture(move):
                painter.setPen(QPen(CAPTURE_RING, 3))
                painter.setBrush(Qt.NoBrush)
                margin = max(3, size // 12)
                painter.drawEllipse(rect.adjusted(margin, margin, -margin, -margin))
            else:
                painter.setBrush(DOT)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(rect.center(), max(3, size // 9), max(3, size // 9))

        if self._drag_from is not None and self._drag_pos is not None:
            piece = self.board.piece_at(self._drag_from)
            if piece is not None:
                pixmap = self._piece_pixmap(piece, size)
                painter.drawPixmap(self._drag_pos - QPoint(size // 2, size // 2), pixmap)

        for (a, b), idx in self.arrows.items():
            self._draw_arrow(painter, a, b, ARROW_COLORS[idx % len(ARROW_COLORS)])
        if self._right_dragging and self._right_from is not None and self._right_pos is not None:
            preview_to = self._square_at(self._right_pos)
            if preview_to is not None and preview_to != self._right_from:
                color = QColor(ARROW_COLORS[self._right_color % len(ARROW_COLORS)])
                color.setAlpha(140)
                self._draw_arrow(painter, self._right_from, preview_to, color)

        self._draw_coordinates(painter, size)

    def _piece_pixmap(self, piece: chess.Piece, size: int):
        return get_renderer().pixmap(piece, size, self.devicePixelRatioF())

    def _draw_arrow(self, painter: QPainter, from_sq: int, to_sq: int, color: QColor) -> None:
        if from_sq == to_sq:
            return
        size = self._square_size()
        a = QPointF(self._square_rect(from_sq).center())
        b = QPointF(self._square_rect(to_sq).center())
        dx, dy = b.x() - a.x(), b.y() - a.y()
        dist = math.hypot(dx, dy)
        if dist < 1e-6:
            return
        ux, uy = dx / dist, dy / dist
        px, py = -uy, ux
        # Un trazo algo más ancho y un borde muy discreto hacen legibles las
        # flechas importadas tanto en tableros pequeños como sobre piezas.
        thickness = max(5.0, size * 0.16)
        head_len = thickness * 2.45
        head_half = thickness * 1.28
        base = QPointF(b.x() - ux * head_len, b.y() - uy * head_len)
        tip = QPointF(b.x() - ux * thickness * 0.15, b.y() - uy * thickness * 0.15)
        left = QPointF(base.x() + px * head_half, base.y() + py * head_half)
        right = QPointF(base.x() - px * head_half, base.y() - py * head_half)
        outline = QColor(25, 25, 25, min(72, color.alpha() // 3))
        painter.save()
        start = QPointF(a.x() + ux * thickness * 0.4, a.y() + uy * thickness * 0.4)
        painter.setPen(QPen(outline, thickness + 2.0, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(start, base)
        painter.setPen(QPen(color, thickness, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(start, base)
        painter.setPen(Qt.NoPen)
        painter.setBrush(outline)
        painter.drawPolygon(QPolygonF([tip, left, right]))
        # Cabeza ligeramente más pequeña encima del borde, para que siga
        # siendo nítida incluso con colores similares a la casilla.
        inner_base = QPointF(b.x() - ux * (head_len - 1.4), b.y() - uy * (head_len - 1.4))
        inner_left = QPointF(inner_base.x() + px * max(2.0, head_half - 1.1),
                             inner_base.y() + py * max(2.0, head_half - 1.1))
        inner_right = QPointF(inner_base.x() - px * max(2.0, head_half - 1.1),
                              inner_base.y() - py * max(2.0, head_half - 1.1))
        painter.setBrush(color)
        painter.drawPolygon(QPolygonF([tip, inner_left, inner_right]))
        painter.drawEllipse(a, thickness * 0.45, thickness * 0.45)
        painter.restore()

    def _coord_color(self, square: int) -> QColor:
        light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
        return COORD_LIGHT if light else COORD_DARK

    def _draw_coordinates(self, painter: QPainter, size: int) -> None:
        font = QFont("Segoe UI", weight=QFont.DemiBold)
        font.setPixelSize(max(9, size // 5))
        painter.setFont(font)
        bottom_rank = 0 if self.orientation == chess.WHITE else 7
        left_file = 0 if self.orientation == chess.WHITE else 7
        for i in range(8):
            file_char = "abcdefgh"[i if self.orientation == chess.WHITE else 7 - i]
            rank_char = str(8 - i if self.orientation == chess.WHITE else i + 1)
            file_square = chess.square(i, bottom_rank)
            rank_square = chess.square(left_file, 7 - i)
            painter.setPen(self._coord_color(file_square))
            rect = self._square_rect(file_square)
            painter.drawText(rect.adjusted(1, rect.height() - size // 4, -2, -1),
                             Qt.AlignRight | Qt.AlignBottom, file_char)
            painter.setPen(self._coord_color(rank_square))
            rect = self._square_rect(rank_square)
            painter.drawText(rect.adjusted(2, 1, 0, 0), Qt.AlignLeft | Qt.AlignTop, rank_char)

    # ------------------------------------------------------------------ #
    # Interacción
    # ------------------------------------------------------------------ #
    def _select(self, square: int | None) -> None:
        self.selected = square
        if square is None:
            self._targets = []
        else:
            self._targets = [m for m in self.board.legal_moves if m.from_square == square]

    def _emit_move(self, from_square: int, to_square: int) -> None:
        promotions = [m for m in self.board.legal_moves
                      if m.from_square == from_square and m.to_square == to_square and m.promotion]
        if promotions:
            options = [name for name, _ in PROMO_CHOICES]
            choice, ok = QInputDialog.getItem(self, "Promoción", "Elegir pieza:", options, 0, False)
            if not ok:
                return
            piece_type = dict(PROMO_CHOICES)[choice]
            move = chess.Move(from_square, to_square, promotion=piece_type)
            if move in self.board.legal_moves:
                self.moveMade.emit(move)
            return
        move = chess.Move(from_square, to_square)
        if move in self.board.legal_moves:
            self.moveMade.emit(move)
        else:
            self._select(None)
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            self._right_from = self._square_at(event.position().toPoint())
            self._right_dragging = False
            self._right_pos = event.position().toPoint()
            self._right_color = arrow_color_index(event.modifiers())
            return
        if event.button() != Qt.LeftButton:
            return
        square = self._square_at(event.position().toPoint())
        if square is None:
            return
        piece = self.board.piece_at(square)
        if piece is not None and piece.color == self.board.turn:
            self._select(square)
            self._drag_from = square
            self._drag_pos = event.position().toPoint()
            self.update()
            return
        if self.selected is not None and self.selected != square:
            source = self.selected
            self._drag_from = None
            self._drag_pos = None
            self._emit_move(source, square)
            return
        if piece is None:
            self.clear_drawings()
        self._select(None)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._right_from is not None:
            self._right_pos = event.position().toPoint()
            target = self._square_at(self._right_pos)
            if target is not None and target != self._right_from:
                self._right_dragging = True
            self.update()
            return
        if self._drag_from is not None:
            self._drag_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.RightButton:
            from_square = self._right_from
            was_drag = self._right_dragging
            self._right_from = None
            self._right_dragging = False
            self._right_pos = None
            target = self._square_at(event.position().toPoint())
            if target is not None and was_drag and from_square is not None and target != from_square:
                key = (from_square, target)
                color = arrow_color_index(event.modifiers())
                if self.arrows.get(key) == color:
                    del self.arrows[key]
                else:
                    self.arrows[key] = color
            elif target is not None:
                color = mark_color_index(event.modifiers())
                if self.marks.get(target) == color:
                    del self.marks[target]
                else:
                    self.marks[target] = color
            self.update()
            self.drawingsChanged.emit()
            return
        if event.button() != Qt.LeftButton or self._drag_from is None:
            return
        target = self._square_at(event.position().toPoint())
        source = self._drag_from
        self._drag_from = None
        self._drag_pos = None
        if target is not None and target != source:
            self._emit_move(source, target)
        else:
            self.update()
