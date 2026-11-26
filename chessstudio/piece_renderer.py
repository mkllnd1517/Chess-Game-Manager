"""Renderizado de piezas con el set SVG «cburnett» (ver pieces/LICENSE.txt).

Las piezas se rasterizan una sola vez por tamaño y se cachean, de modo que
el repintado del tablero (arrastre, animaciones) es muy rápido. Si los SVG
no estuvieran disponibles, se usa un fallback de glifos Unicode.
"""
from __future__ import annotations

from pathlib import Path

import chess
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PIECES_DIR = Path(__file__).parent / "pieces"

_PIECE_FILES = {
    (chess.WHITE, chess.KING): "wK",
    (chess.WHITE, chess.QUEEN): "wQ",
    (chess.WHITE, chess.ROOK): "wR",
    (chess.WHITE, chess.BISHOP): "wB",
    (chess.WHITE, chess.KNIGHT): "wN",
    (chess.WHITE, chess.PAWN): "wP",
    (chess.BLACK, chess.KING): "bK",
    (chess.BLACK, chess.QUEEN): "bQ",
    (chess.BLACK, chess.ROOK): "bR",
    (chess.BLACK, chess.BISHOP): "bB",
    (chess.BLACK, chess.KNIGHT): "bN",
    (chess.BLACK, chess.PAWN): "bP",
}

_GLYPHS = {
    chess.PAWN: "\u265f", chess.KNIGHT: "\u265e", chess.BISHOP: "\u265d",
    chess.ROOK: "\u265c", chess.QUEEN: "\u265b", chess.KING: "\u265a",
}


class PieceRenderer:
    """Caché de piezas rasterizadas a partir de SVG vectoriales."""

    def __init__(self):
        self._renderers: dict[str, QSvgRenderer] = {}
        self._cache: dict[tuple[str, int, float], QPixmap] = {}
        self._available = False
        self._load()

    def _load(self) -> None:
        for key, name in _PIECE_FILES.items():
            path = PIECES_DIR / f"{name}.svg"
            try:
                data = path.read_bytes()
            except OSError:
                continue
            renderer = QSvgRenderer(QByteArray(data))
            if renderer.isValid():
                self._renderers[name] = renderer
        self._available = len(self._renderers) == len(_PIECE_FILES)

    @property
    def available(self) -> bool:
        return self._available

    def clear_cache(self) -> None:
        self._cache.clear()

    def pixmap(self, piece: chess.Piece, size: int, device_ratio: float = 1.0) -> QPixmap:
        name = _PIECE_FILES[(piece.color, piece.piece_type)]
        key = (name, size, round(device_ratio, 2))
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        if len(self._cache) > 200:
            self._cache.clear()

        renderer = self._renderers.get(name)
        if renderer is not None:
            pixmap = self._render_svg(renderer, size, device_ratio)
        else:
            pixmap = self._render_glyph(piece, size, device_ratio)
        self._cache[key] = pixmap
        return pixmap

    @staticmethod
    def _render_svg(renderer: QSvgRenderer, size: int, device_ratio: float) -> QPixmap:
        pixel_size = max(1, round(size * device_ratio))
        pixmap = QPixmap(pixel_size, pixel_size)
        pixmap.fill(Qt.transparent)
        # Pintamos primero en píxeles físicos. Si se establece el DPR antes de
        # crear el QPainter, Qt convierte sus coordenadas a píxeles lógicos y
        # ``pixel_size`` se aplica una segunda vez con escalado fraccional.
        # Ese doble escalado hacía crecer el contenido de las piezas en 125 %
        # y 150 %. El DPR se asigna después, solo como metadato de visualización.
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        # Margen del 4 % para que la pieza no toque los bordes de la casilla.
        margin = pixel_size * 0.04
        renderer.render(painter, QRectF(margin, margin, pixel_size - 2 * margin, pixel_size - 2 * margin))
        painter.end()
        pixmap.setDevicePixelRatio(device_ratio)
        return pixmap

    @staticmethod
    def _render_glyph(piece: chess.Piece, size: int, device_ratio: float) -> QPixmap:
        pixel_size = max(1, round(size * device_ratio))
        pixmap = QPixmap(pixel_size, pixel_size)
        pixmap.fill(Qt.transparent)
        # Véase _render_svg: las fuentes también deben pintarse en coordenadas
        # físicas antes de etiquetar el pixmap con su DPR.
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.TextAntialiasing)
        font = QFont()
        font.setFamilies(["Segoe UI Symbol", "Noto Sans Symbols 2", "DejaVu Sans", "FreeSerif"])
        font.setPixelSize(int(pixel_size * 0.8))
        painter.setFont(font)
        glyph = _GLYPHS[piece.piece_type]
        rect = QRectF(0, -pixel_size * 0.06, pixel_size, pixel_size)
        if piece.color == chess.WHITE:
            fill, rim = QColor(250, 248, 243), QColor(18, 18, 18)
        else:
            fill, rim = QColor(24, 24, 24), QColor(214, 210, 202)
        outline = max(1, pixel_size // 25)
        painter.setPen(rim)
        for dx, dy in [(outline, 0), (-outline, 0), (0, outline), (0, -outline)]:
            painter.drawText(rect.translated(dx, dy), Qt.AlignCenter, glyph)
        painter.setPen(fill)
        painter.drawText(rect, Qt.AlignCenter, glyph)
        painter.end()
        pixmap.setDevicePixelRatio(device_ratio)
        return pixmap


# Instancia compartida (los SVG se cargan una sola vez en toda la app).
_renderer: PieceRenderer | None = None


def get_renderer() -> PieceRenderer:
    global _renderer
    if _renderer is None:
        _renderer = PieceRenderer()
    return _renderer
