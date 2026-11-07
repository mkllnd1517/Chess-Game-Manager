"""Almacenamiento seguro del token de Lichess.

Prioriza el llavero del sistema operativo (biblioteca ``keyring``):
  * Windows  -> Windows Credential Locker
  * macOS    -> Keychain
  * Linux    -> Secret Service / KWallet

Si no hay un llavero disponible (p. ej. un Linux sin escritorio), cae a
QSettings. Conviene recordar que un token de Lichess SIN permisos solo puede
leer datos públicos, así que incluso en ese fallback el riesgo es bajo; aun
así, siempre que se puede, el token se guarda cifrado en el llavero y se
elimina cualquier copia en texto plano.

El token nunca se escribe en registros ni se envía a hosts que no sean de
Lichess (ver lichess_explorer.py).
"""
from __future__ import annotations

from PySide6.QtCore import QSettings

SERVICE = "ChessStudio"
ACCOUNT = "lichess_token"
_SETTINGS_KEY = "lichess/token"

try:
    import keyring
    _HAS_KEYRING = True
except ImportError:  # pragma: no cover - depende del entorno
    keyring = None
    _HAS_KEYRING = False

_keyring_ok: bool | None = None


def _keyring_works() -> bool:
    """Comprueba una sola vez que hay un backend de llavero utilizable."""
    global _keyring_ok
    if _keyring_ok is not None:
        return _keyring_ok
    if not _HAS_KEYRING:
        _keyring_ok = False
        return False
    try:
        # Un backend "fail" o un entorno sin escritorio lanzan aquí.
        keyring.get_password(SERVICE, "__probe__")
        _keyring_ok = True
    except Exception:
        _keyring_ok = False
    return _keyring_ok


def get_token() -> str:
    settings = QSettings(SERVICE, SERVICE)
    legacy = settings.value(_SETTINGS_KEY, "", str) or ""
    if _keyring_works():
        try:
            token = keyring.get_password(SERVICE, ACCOUNT)
            if token:
                return token
            if legacy:
                # Migración: mover el token en texto plano al llavero.
                keyring.set_password(SERVICE, ACCOUNT, legacy)
                settings.remove(_SETTINGS_KEY)
                return legacy
            return ""
        except Exception:
            pass
    return legacy


def set_token(token: str) -> None:
    settings = QSettings(SERVICE, SERVICE)
    token = token.strip()
    if _keyring_works():
        try:
            if token:
                keyring.set_password(SERVICE, ACCOUNT, token)
            else:
                try:
                    keyring.delete_password(SERVICE, ACCOUNT)
                except Exception:
                    pass
            settings.remove(_SETTINGS_KEY)  # nunca dejar copia en texto plano
            return
        except Exception:
            pass
    if token:
        settings.setValue(_SETTINGS_KEY, token)
    else:
        settings.remove(_SETTINGS_KEY)


def storage_description() -> str:
    """Texto legible de dónde se guarda el token (para mostrar en la UI)."""
    if _keyring_works():
        try:
            name = keyring.get_keyring().__class__.__name__
            return f"llavero del sistema ({name})"
        except Exception:
            return "llavero del sistema"
    return "configuración local (sin llavero del sistema disponible)"
