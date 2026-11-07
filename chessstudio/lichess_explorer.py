"""Cliente del Explorador de Aperturas de Lichess (explorer.lichess.ovh).

Fuentes:
  * ``masters``: base de partidas de maestros (OTB).
  * ``lichess``: base de partidas online de Lichess, filtrable por ritmo y Elo.

Nota (2026): el explorador requiere un token personal gratuito de Lichess
(https://lichess.org/account/oauth/token, sin permisos especiales). El token
se guarda en QSettings y solo se envía a hosts de Lichess.

Se usa QNetworkAccessManager (asíncrono, integrado en Qt): la interfaz nunca
se bloquea esperando la red. Incluye caché LRU, cancelación de peticiones
obsoletas, timeout y mensajes claros para 401/429/errores de red.
"""
from __future__ import annotations

import io
import json
from collections import OrderedDict

import chess.pgn
from PySide6.QtCore import QObject, QTimer, QUrl, QUrlQuery, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from chessstudio import APP_NAME, __version__

EXPLORER_BASE = "https://explorer.lichess.ovh"
GAME_EXPORT_BASE = "https://lichess.org/game/export"
TOKEN_URL = "https://lichess.org/account/oauth/token"

# El token de autorización SOLO se envía a estos dominios (defensa en
# profundidad: aunque una URL cambiara, el token nunca saldría hacia otro
# servidor). Además no se siguen redirecciones.
LICHESS_HOSTS = ("lichess.org", "lichess.ovh")


def _is_lichess_host(url: QUrl) -> bool:
    host = url.host().lower()
    return any(host == h or host.endswith("." + h) for h in LICHESS_HOSTS)

RATING_PRESETS: dict[str, list[str]] = {
    "Todos los Elo": ["1000", "1200", "1400", "1600", "1800", "2000", "2200", "2500"],
    "1000 - 1600": ["1000", "1200", "1400", "1600"],
    "1600 - 2000": ["1600", "1800", "2000"],
    "2000 o más": ["2000", "2200", "2500"],
}
ALL_SPEEDS = ["bullet", "blitz", "rapid", "classical"]
SPEED_LABELS = {"bullet": "Bullet", "blitz": "Blitz", "rapid": "Rapid", "classical": "Clásico"}


class LichessExplorer(QObject):
    dataReady = Signal(str, dict)     # clave de petición, JSON
    failed = Signal(str, str)         # clave de petición, mensaje
    gameReady = Signal(object)        # chess.pgn.Game descargado
    gameFailed = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._pending: dict[str, QNetworkReply] = {}
        self._token = ""

    def set_token(self, token: str) -> None:
        token = token.strip()
        if token != self._token:
            self._token = token
            self._cache.clear()

    def has_token(self) -> bool:
        return bool(self._token)

    def _prepare_request(self, url: QUrl, user_agent_suffix: str = "") -> QNetworkRequest:
        """Crea una petición endurecida: HTTPS, sin redirecciones, timeout y
        Authorization únicamente si el destino es un dominio de Lichess."""
        request = QNetworkRequest(url)
        ua = f"{APP_NAME}/{__version__}" + (f" {user_agent_suffix}" if user_agent_suffix else "")
        request.setHeader(QNetworkRequest.UserAgentHeader, ua)
        request.setTransferTimeout(15000)
        # No seguir redirecciones: evita que un 3xx reenvíe el token a otro host.
        request.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.ManualRedirectPolicy)
        request.setAttribute(QNetworkRequest.CacheLoadControlAttribute, QNetworkRequest.AlwaysNetwork)
        if self._token and url.scheme() == "https" and _is_lichess_host(url):
            request.setRawHeader(b"Authorization", f"Bearer {self._token}".encode("utf-8"))
        return request

    # ------------------------------------------------------------------ #
    # Explorador
    # ------------------------------------------------------------------ #
    def request(self, fen: str, source: str, speeds: list[str], ratings: list[str]) -> str:
        key = f"{source}|{fen}|{','.join(sorted(speeds))}|{','.join(sorted(ratings))}"
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            QTimer.singleShot(0, lambda: self.dataReady.emit(key, cached))
            return key
        if key in self._pending:
            return key

        # Cancelar consultas obsoletas: solo importa la posición actual.
        for old_key, reply in list(self._pending.items()):
            if old_key != key:
                reply.abort()
                self._pending.pop(old_key, None)

        url = QUrl(f"{EXPLORER_BASE}/{source}")
        query = QUrlQuery()
        query.addQueryItem("fen", fen)
        query.addQueryItem("moves", "12")
        if source == "masters":
            query.addQueryItem("topGames", "5")
            query.addQueryItem("recentGames", "0")
        else:
            query.addQueryItem("variant", "standard")
            query.addQueryItem("speeds", ",".join(speeds) or "blitz,rapid,classical")
            query.addQueryItem("ratings", ",".join(ratings) or ",".join(RATING_PRESETS["Todos los Elo"]))
            query.addQueryItem("recentGames", "5")
            query.addQueryItem("topGames", "0")
        url.setQuery(query)

        request = self._prepare_request(url, "(opening explorer)")
        reply = self._nam.get(request)
        self._pending[key] = reply
        reply.finished.connect(lambda r=reply, k=key: self._on_reply(k, r))
        return key

    def _on_reply(self, key: str, reply: QNetworkReply) -> None:
        if self._pending.get(key) is reply:
            self._pending.pop(key, None)
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        payload = bytes(reply.readAll())
        error = reply.error()
        error_text = reply.errorString()
        reply.deleteLater()

        if error == QNetworkReply.OperationCanceledError:
            return
        if status and 300 <= int(status) < 400:
            self.failed.emit(key, "El servidor redirigió la petición (no se sigue por seguridad).")
            return
        if error != QNetworkReply.NoError:
            if status == 401:
                message = (
                    "Lichess requiere un token gratuito para el explorador. "
                    "Créalo en lichess.org/account/oauth/token (sin marcar permisos) "
                    "y pégalo en el campo Token."
                )
            elif status == 429:
                message = "Límite de peticiones de Lichess alcanzado. Espera un minuto e inténtalo de nuevo."
            elif status == 404:
                self.dataReady.emit(key, {"white": 0, "draws": 0, "black": 0, "moves": []})
                return
            else:
                message = f"Error de red: {error_text}" + (f" (HTTP {status})" if status else "")
            self.failed.emit(key, message)
            return
        try:
            data = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.failed.emit(key, "Respuesta no válida del explorador de Lichess.")
            return
        self._cache[key] = data
        self._cache.move_to_end(key)
        while len(self._cache) > 300:
            self._cache.popitem(last=False)
        self.dataReady.emit(key, data)

    # ------------------------------------------------------------------ #
    # Descarga de partidas destacadas
    # ------------------------------------------------------------------ #
    def fetch_game(self, game_id: str) -> None:
        if not game_id or not game_id.isalnum():
            self.gameFailed.emit("Identificador de partida no válido.")
            return
        url = QUrl(f"{GAME_EXPORT_BASE}/{game_id}")
        query = QUrlQuery()
        query.addQueryItem("moves", "true")
        query.addQueryItem("tags", "true")
        query.addQueryItem("clocks", "false")
        query.addQueryItem("evals", "false")
        url.setQuery(query)
        request = self._prepare_request(url)
        request.setRawHeader(b"Accept", b"application/x-chess-pgn")
        reply = self._nam.get(request)
        reply.finished.connect(lambda r=reply: self._on_game_reply(r))

    def _on_game_reply(self, reply: QNetworkReply) -> None:
        payload = bytes(reply.readAll())
        error = reply.error()
        error_text = reply.errorString()
        reply.deleteLater()
        if error != QNetworkReply.NoError:
            self.gameFailed.emit(f"No se pudo descargar la partida: {error_text}")
            return
        try:
            game = chess.pgn.read_game(io.StringIO(payload.decode("utf-8", errors="replace")))
        except Exception:
            game = None
        if game is None or not game.variations:
            self.gameFailed.emit("La partida descargada no contiene jugadas.")
            return
        self.gameReady.emit(game)
