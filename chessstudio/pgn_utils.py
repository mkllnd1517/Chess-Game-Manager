"""Utilidades PGN: flechas (%cal), casillas marcadas (%csl) y comentarios.

Los índices de color coinciden con las paletas de BoardWidget:
    ARROW_COLORS = [rojo, verde, azul, amarillo]
    MARK_COLORS  = [naranja, verde, rojo, azul]

Se reconocen las etiquetas estándar ``[%cal Ge2e4,Gd2d4]`` y ``[%csl Rc4]``
en cualquier capitalización, con varios tags por comentario, y también la
variante sin corchetes que usan algunos exportadores.
"""
from __future__ import annotations

import re

import chess

ARROW_COLOR_INDEX = {"R": 0, "G": 1, "B": 2, "Y": 3}
MARK_COLOR_INDEX = {"Y": 0, "G": 1, "R": 2, "B": 3}
ARROW_INDEX_COLOR = {v: k for k, v in ARROW_COLOR_INDEX.items()}
MARK_INDEX_COLOR = {v: k for k, v in MARK_COLOR_INDEX.items()}

_TAG_RE = re.compile(r"\[%[^\]]*\]")
_DRAWING_TAG_RE = re.compile(r"\[%\s*(?:cal|csl)\s+[^\]]*\]", re.IGNORECASE)
_ARROW_RE = re.compile(r"([RGBY]?)([a-h][1-8])([a-h][1-8])", re.IGNORECASE)
_MARK_RE = re.compile(r"([RGBY]?)([a-h][1-8])", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")
_EVAL_RE = re.compile(r"\[%\s*eval\s+([^\]]+)\]", re.IGNORECASE)
_CLK_RE = re.compile(r"\[%\s*clk\s+([^\]]+)\]", re.IGNORECASE)


def _tag_payloads(comment: str, name: str) -> list[str]:
    """Devuelve el contenido de todos los tags ``[%name ...]`` del comentario.

    Si no hay ninguno con corchetes, acepta la forma suelta ``name ...``.
    """
    bracketed = re.compile(r"\[%\s*" + name + r"\s+([^\]]*)\]", re.IGNORECASE)
    found = bracketed.findall(comment)
    if found:
        return found
    bare = re.compile(r"\b" + name + r"\s+([^\]\n]+)", re.IGNORECASE)
    return bare.findall(comment)


def parse_drawings(comment: str) -> tuple[dict[str, int], dict[str, int]]:
    """Extrae flechas y marcas de un comentario PGN.

    Devuelve ``(arrows, marks)`` donde:
      * ``arrows`` mapea ``"casilla_origen,casilla_destino"`` -> índice de color.
      * ``marks`` mapea ``"casilla"`` -> índice de color.
    """
    arrows: dict[str, int] = {}
    marks: dict[str, int] = {}
    if not comment:
        return arrows, marks

    for payload in _tag_payloads(comment, "cal"):
        for color, src, dst in _ARROW_RE.findall(payload):
            if src == dst:
                continue
            try:
                a = chess.parse_square(src.lower())
                b = chess.parse_square(dst.lower())
            except ValueError:
                continue
            letter = (color or "G").upper()
            arrows[f"{a},{b}"] = ARROW_COLOR_INDEX.get(letter, 1)

    for payload in _tag_payloads(comment, "csl"):
        for color, square in _MARK_RE.findall(payload):
            try:
                sq = chess.parse_square(square.lower())
            except ValueError:
                continue
            letter = (color or "G").upper()
            marks[str(sq)] = MARK_COLOR_INDEX.get(letter, 1)

    return arrows, marks


def drawings_to_tags(drawings: dict) -> str:
    """Serializa un dict de dibujos a etiquetas PGN ``[%cal ...] [%csl ...]``."""
    parts: list[str] = []

    arrows = drawings.get("arrows") or {}
    arrow_tokens: list[str] = []
    for key, idx in arrows.items():
        try:
            src, dst = key.split(",")
            a = chess.square_name(int(src))
            b = chess.square_name(int(dst))
        except (ValueError, TypeError):
            continue
        if a == b:
            continue
        letter = ARROW_INDEX_COLOR.get(int(idx) % len(ARROW_INDEX_COLOR), "G")
        arrow_tokens.append(f"{letter}{a}{b}")
    if arrow_tokens:
        parts.append("[%cal " + ",".join(arrow_tokens) + "]")

    marks = drawings.get("marks") or {}
    mark_tokens: list[str] = []
    for key, idx in marks.items():
        try:
            square = chess.square_name(int(key))
        except (ValueError, TypeError):
            continue
        letter = MARK_INDEX_COLOR.get(int(idx) % len(MARK_INDEX_COLOR), "G")
        mark_tokens.append(f"{letter}{square}")
    if mark_tokens:
        parts.append("[%csl " + ",".join(mark_tokens) + "]")

    return " ".join(parts)


def strip_tags(comment: str) -> str:
    """Elimina todas las etiquetas ``[%...]`` y normaliza espacios."""
    if not comment:
        return ""
    return _WS_RE.sub(" ", _TAG_RE.sub("", comment)).strip()


def display_comment(comment: str) -> str:
    """Texto de comentario listo para mostrar (sin tags de dibujo/reloj/eval)."""
    return strip_tags(comment)


def _format_eval(raw: str) -> str:
    """Convierte el valor de [%eval] a texto legible (+0.34, M3, ...)."""
    raw = raw.split(",")[0].strip()
    if raw.startswith("#"):
        return "M" + raw[1:]
    try:
        return f"{float(raw):+.2f}"
    except ValueError:
        return raw


def parse_comment(comment: str) -> dict:
    """Descompone un comentario PGN para mostrarlo con formato enriquecido.

    Devuelve ``{"text", "eval", "clk"}``: el texto limpio (sin etiquetas),
    la evaluación legible (si existe) y el tiempo de reloj (si existe).
    Las flechas/marcas (%cal/%csl) se muestran en el tablero, no aquí.
    """
    if not comment:
        return {"text": "", "eval": None, "clk": None}
    eval_str = None
    clk_str = None
    match = _EVAL_RE.search(comment)
    if match:
        eval_str = _format_eval(match.group(1))
    match = _CLK_RE.search(comment)
    if match:
        clk_str = match.group(1).strip()
    return {"text": strip_tags(comment), "eval": eval_str, "clk": clk_str}


def has_drawing_tags(comment: str) -> bool:
    return bool(comment and _DRAWING_TAG_RE.search(comment))


def replace_drawing_tags(comment: str, drawings: dict) -> str:
    """Sustituye SOLO los tags [%cal]/[%csl] por los del dict dado.

    Conserva el resto de etiquetas (``[%eval]``, ``[%clk]``, etc.) y el texto
    del comentario. Si ``drawings`` está vacío, elimina los tags de dibujo.
    """
    cleaned = _WS_RE.sub(" ", _DRAWING_TAG_RE.sub("", comment or "")).strip()
    tags = drawings_to_tags(drawings)
    if cleaned and tags:
        return f"{cleaned} {tags}"
    return cleaned or tags


def merge_comment(comment: str, drawings: dict) -> str:
    """Reemplaza los tags de dibujo del comentario por los del dict dado."""
    return replace_drawing_tags(comment, drawings)


def walk_game(game: chess.pgn.Game):
    """Recorre todos los nodos del árbol rindiendo ``(nodo, tablero_tras_jugada)``.

    El tablero del nodo raíz es la posición inicial (respeta cabeceras FEN/SetUp).
    Es iterativo para soportar partidas muy largas sin límite de recursión.
    """
    stack: list[tuple[chess.pgn.GameNode, chess.Board]] = [(game, game.board())]
    while stack:
        node, board = stack.pop()
        yield node, board
        for child in reversed(node.variations):
            if child.move is None:
                continue
            # copy(stack=False): no necesitamos el historial de jugadas para
            # calcular la posición. Copiarlo hacía el recorrido O(n²) y
            # bloqueaba la apertura de partidas largas (miles de jugadas).
            child_board = board.copy(stack=False)
            child_board.push(child.move)
            stack.append((child, child_board))
