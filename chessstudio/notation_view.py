"""Vista de notación con variantes, comentarios y símbolos NAG.

Optimizaciones clave para partidas grandes:
  * Renderizado TOTALMENTE ITERATIVO (pila explícita): las variantes muy
    anidadas ya no provocan RecursionError ni abortan el proceso.
  * Presupuesto de renderizado: en partidas enormes se pintan las primeras
    jugadas y la vista se amplía automáticamente al navegar (o con un enlace
    «mostrar toda la partida»), evitando HTML de varios MB de golpe.
  * El HTML solo se reconstruye cuando cambia la ESTRUCTURA. Al navegar se
    mueve el resaltado mediante un mapa de anclas construido una sola vez
    tras cada reconstrucción: cada paso es O(1), no O(tamaño del documento).
"""
from __future__ import annotations

import html as html_mod

import chess
import chess.pgn
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QFont, QTextCursor
from PySide6.QtWidgets import QInputDialog, QMenu, QTextBrowser, QTextEdit, QWidget

from chessstudio.game_model import NAG_SYMBOLS
from chessstudio.pgn_utils import parse_comment

VARIATION_STYLE = "color:#9c1c1c;"
COMMENT_STYLE = "color:#2e7d32; font-style:italic;"
COMMENT_BOX_STYLE = "background-color:#eef6ee;"
EVAL_STYLE = "color:#1565c0; font-weight:bold; font-style:normal;"
CLK_STYLE = "color:#8a8a8a; font-style:normal;"
CURRENT_BG = "#ffeba8"
NAG_STYLE = "color:#b45309; font-weight:bold;"
TRUNC_STYLE = "color:#888; font-style:italic;"

MOVE_NAG_MENU = [1, 2, 3, 4, 5, 6, 7]
POSITION_NAG_MENU = [10, 13, 14, 15, 16, 17, 18, 19, 21, 22]

# Nº de jugadas (nodos) que se pintan inicialmente en partidas enormes.
INITIAL_BUDGET = 4000
EXTEND_MARGIN = 2000
SHOW_ALL_ANCHOR = "__show_all__"


class NotationView(QTextBrowser):
    nodeSelected = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenLinks(False)
        self.setLineWrapMode(QTextBrowser.WidgetWidth)
        self.setFont(QFont("Segoe UI", 10))
        self.setStyleSheet("QTextBrowser { background: #fffdf6; color: #161616; }")
        self._doc = None
        self._current_anchor: str = ""
        self._anchor_map: dict[str, tuple[int, int]] = {}
        self._rendered_ids: set[int] = set()
        self._budget: int = INITIAL_BUDGET
        self._truncated: bool = False
        self.anchorClicked.connect(self._on_anchor)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def set_document(self, doc) -> None:
        self._doc = doc
        self._budget = INITIAL_BUDGET
        self.rebuild()

    def loadResource(self, resource_type, url):
        # Defensa en profundidad: aunque el contenido va escapado, impedir
        # que el visor cargue recursos externos o locales (imágenes, etc.).
        if url.scheme() in ("http", "https", "file", "data", "ftp"):
            return None
        return super().loadResource(resource_type, url)

    # ------------------------------------------------------------------ #
    # Renderizado
    # ------------------------------------------------------------------ #
    def rebuild(self) -> None:
        self._current_anchor = ""
        self._anchor_map = {}
        self._rendered_ids = set()
        self._truncated = False
        self.clear()
        if self._doc is None:
            return
        blocks: list[str] = []
        root_comment = self._comment_html(parse_comment(self._doc.game.comment))
        if root_comment:
            blocks.append(root_comment)
        body = self._render_tree(self._doc.game, self._doc.game.board())
        if body:
            blocks.append(body)
        result = self._doc.game.headers.get("Result", "")
        if result and result != "*" and not self._truncated:
            blocks.append(f'<span style="color:#666;">{html_mod.escape(result)}</span>')
        if self._truncated:
            blocks.append(
                f'<span style="{TRUNC_STYLE}">… partida muy larga; se muestran las '
                f'primeras jugadas. La navegación amplía la vista automáticamente. '
                f'<a href="{SHOW_ALL_ANCHOR}">Mostrar toda la partida</a></span>'
            )
        joined = " ".join(blocks)
        self.setHtml(f'<div style="font-family:\'Segoe UI\'; font-size:10.5pt;">{joined}</div>')
        self._build_anchor_map()
        self._highlight_current()

    def _render_tree(self, root: chess.pgn.GameNode, board: chess.Board) -> str:
        """Recorre el árbol en orden de notación con una pila explícita.

        Cada tarea es una de:
          ("visit", node, board, force_number)  -> línea principal
          ("var", branch, board)                -> abrir variante
          ("closevar",)                         -> cerrar variante
        Se respeta el formato PGN estándar con variantes en línea y el
        número de jugada re-mostrado tras cada variante.
        """
        out: list[str] = []
        rendered = self._rendered_ids
        budget = self._budget
        count = 0
        open_vars = 0
        stack: list[tuple] = [("visit", root, board.copy(stack=False), True)]
        while stack:
            task = stack.pop()
            kind = task[0]
            if kind == "closevar":
                if out:
                    out[-1] += ")</span>"
                open_vars -= 1
                continue
            if kind == "var":
                _, branch, b = task
                if branch.move is None:
                    continue
                out.append(
                    f'<span style="{VARIATION_STYLE}">('
                    + self._render_move(branch, b, is_branch=True, force_number=True)
                )
                rendered.add(id(branch))
                count += 1
                open_vars += 1
                if count >= budget:
                    self._truncated = True
                    break
                b2 = b.copy(stack=False)
                b2.push(branch.move)
                stack.append(("closevar",))
                stack.append(("visit", branch, b2, True))
                continue
            # kind == "visit"
            _, node, b, force_number = task
            if not node.variations:
                continue
            main = node.variations[0]
            if main.move is None:
                continue
            out.append(self._render_move(main, b, is_branch=False, force_number=force_number))
            rendered.add(id(main))
            count += 1
            if count >= budget:
                self._truncated = True
                break
            b2 = b.copy(stack=False)
            b2.push(main.move)
            branches = [br for br in node.variations[1:] if br.move is not None]
            # La continuación de la línea principal se procesa DESPUÉS de las
            # variantes (que van encima en la pila). Tras una variante hay que
            # re-mostrar el número de jugada.
            stack.append(("visit", main, b2, bool(branches)))
            for br in reversed(branches):
                stack.append(("var", br, b))
        if self._truncated:
            # Cerrar las variantes que quedaron abiertas al cortar.
            if out:
                out[-1] += ")</span>" * open_vars
        return " ".join(out)

    def _render_move(self, child: chess.pgn.GameNode, board: chess.Board,
                     is_branch: bool, force_number: bool) -> str:
        try:
            san = board.san(child.move)
        except Exception:
            san = board.uci(child.move)
        if board.turn == chess.WHITE:
            prefix = f"{board.fullmove_number}. "
        elif is_branch or force_number:
            prefix = f"{board.fullmove_number}... "
        else:
            prefix = ""
        nid = id(child)
        label = f"{prefix}{html_mod.escape(san)}"
        link = (
            f'<a name="{nid}" href="{nid}" style="color:inherit; text-decoration:none;">'
            f"<b>{label}</b></a>{self._nags_html(child)}"
        )
        pieces = [link]
        comment = self._comment_html(parse_comment(child.comment))
        if comment:
            pieces.append(comment)
        return " ".join(pieces)

    @staticmethod
    def _nags_html(node: chess.pgn.GameNode) -> str:
        symbols = []
        for nag in sorted(node.nags):
            symbol = NAG_SYMBOLS.get(nag) or f"${nag}"
            symbols.append(html_mod.escape(symbol))
        if not symbols:
            return ""
        return f' <span style="{NAG_STYLE}">{" ".join(symbols)}</span>'

    @staticmethod
    def _comment_html(parsed: dict) -> str:
        parts: list[str] = []
        text = parsed.get("text", "")
        if text:
            parts.append(f'<span style="{COMMENT_STYLE}">{html_mod.escape(text)}</span>')
        if parsed.get("eval"):
            parts.append(f'<span style="{EVAL_STYLE}">{html_mod.escape(parsed["eval"])}</span>')
        if parsed.get("clk"):
            # ◷ (U+25F7) como icono de reloj: compatible con fuentes estándar.
            parts.append(f'<span style="{CLK_STYLE}">&#9719; {html_mod.escape(parsed["clk"])}</span>')
        if not parts:
            return ""
        inner = " &nbsp; ".join(parts)
        return f'<span style="{COMMENT_BOX_STYLE}">&nbsp;{{ {inner} }}&nbsp;</span>'

    # ------------------------------------------------------------------ #
    # Mapa de anclas (una sola pasada tras reconstruir) -> resaltado O(1)
    # ------------------------------------------------------------------ #
    def _build_anchor_map(self) -> None:
        self._anchor_map = {}
        document = self.document()
        block = document.firstBlock()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    href = fragment.charFormat().anchorHref()
                    if href and href != SHOW_ALL_ANCHOR:
                        self._anchor_map[href] = (fragment.position(), fragment.length())
                iterator += 1
            block = block.next()

    def select_node(self, node: chess.pgn.GameNode) -> None:
        self._highlight_current()

    def _render_order_index(self, target_id: int) -> int | None:
        """Índice (en orden de notación) del nodo, para ampliar el presupuesto."""
        count = 0
        stack: list[tuple] = [("visit", self._doc.game)]
        while stack:
            task = stack.pop()
            if task[0] == "closevar":
                continue
            if task[0] == "var":
                branch = task[1]
                if branch.move is None:
                    continue
                count += 1
                if id(branch) == target_id:
                    return count
                stack.append(("closevar",))
                stack.append(("visit", branch))
                continue
            node = task[1]
            if not node.variations:
                continue
            main = node.variations[0]
            if main.move is None:
                continue
            count += 1
            if id(main) == target_id:
                return count
            branches = [br for br in node.variations[1:] if br.move is not None]
            stack.append(("visit", main))
            for br in reversed(branches):
                stack.append(("var", br))
        return None

    def _highlight_current(self) -> None:
        if self._doc is None:
            self.setExtraSelections([])
            return
        target = str(id(self._doc.node))
        if target == self._current_anchor:
            return
        # Si la jugada actual quedó fuera del presupuesto, ampliar y reconstruir.
        if self._truncated and id(self._doc.node) not in self._rendered_ids \
                and self._doc.node is not self._doc.game:
            index = self._render_order_index(id(self._doc.node))
            if index is not None:
                self._budget = index + EXTEND_MARGIN
                self.rebuild()
                return
        self._current_anchor = target
        span = self._anchor_map.get(target)
        if span is None:
            self.setExtraSelections([])
            return
        position, length = span
        document = self.document()
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(CURRENT_BG))
        cursor = QTextCursor(document)
        cursor.setPosition(position)
        cursor.setPosition(position + length, QTextCursor.KeepAnchor)
        selection.cursor = cursor
        self.setExtraSelections([selection])
        nav = QTextCursor(document)
        nav.setPosition(position)
        self.setTextCursor(nav)
        self.ensureCursorVisible()

    # ------------------------------------------------------------------ #
    # Interacción
    # ------------------------------------------------------------------ #
    def _node_by_id(self, node_id: str | None):
        if node_id is None or self._doc is None:
            return None
        try:
            return self._doc.find_node(int(node_id))
        except (TypeError, ValueError):
            return None

    def _on_anchor(self, url: QUrl) -> None:
        text = url.toString()
        if text == SHOW_ALL_ANCHOR:
            self._budget = 10 ** 9
            self.rebuild()
            return
        node = self._node_by_id(text)
        if node is not None:
            self.nodeSelected.emit(node)

    def _on_context_menu(self, pos) -> None:
        if self._doc is None:
            return
        node = self._node_by_id(self.anchorAt(pos))
        if node is None:
            return
        menu = QMenu(self)
        act_comment = menu.addAction("Editar comentario...")
        menu.addSeparator()

        actions: dict = {}
        nag_menu = menu.addMenu("Evaluación de jugada")
        for nag in MOVE_NAG_MENU:
            symbol = NAG_SYMBOLS.get(nag, "")
            act = nag_menu.addAction(f"{symbol}  (${nag})")
            actions[act] = ("move", nag)
        nag_menu.addSeparator()
        act = nag_menu.addAction("Quitar evaluación")
        actions[act] = ("move", 0)

        pos_menu = menu.addMenu("Evaluación de posición")
        for nag in POSITION_NAG_MENU:
            symbol = NAG_SYMBOLS.get(nag, "")
            act = pos_menu.addAction(f"{symbol}  (${nag})")
            actions[act] = ("position", nag)
        pos_menu.addSeparator()
        act = pos_menu.addAction("Quitar evaluación")
        actions[act] = ("position", 0)

        menu.addSeparator()
        act_delete = None
        act_promote = None
        if node.parent is not None:
            act_delete = menu.addAction("Eliminar variante")
            if node.parent.variations and node.parent.variations[0] is not node:
                act_promote = menu.addAction("Promover a línea principal")

        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen == act_comment:
            text, ok = QInputDialog.getMultiLineText(self, "Comentario", "Texto:", node.comment)
            if ok:
                self._doc.set_comment(text, node)
        elif act_delete is not None and chosen == act_delete:
            self._doc.delete_variation(node)
        elif act_promote is not None and chosen == act_promote:
            self._doc.promote_variation(node)
        elif chosen in actions:
            kind, nag = actions[act]
            if kind == "move":
                self._doc.set_move_nag(nag, node)
            else:
                self._doc.set_position_nag(nag, node)
