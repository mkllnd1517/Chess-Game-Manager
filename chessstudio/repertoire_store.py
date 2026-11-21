"""Almacenamiento persistente de repertorios personales.

Un repertorio es un perfil con nombre —por ejemplo, «e4» o «Agresivo»— y dos
bases SQLite independientes: una para líneas con blancas y otra para líneas
con negras. El índice solo guarda nombres y fechas; las rutas originales de
los PGN no se conservan para no filtrar información local innecesaria.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from chessstudio.app_paths import repertoire_directory

_INDEX_FILENAME = "repertoires.json"
_SAFE_IDENTIFIER = re.compile(r"[0-9a-f]{32}\Z")
_VALID_COLORS = {"white", "black"}


class RepertoireError(ValueError):
    """Un nombre o índice de repertorios no es válido."""


@dataclass(frozen=True)
class Repertoire:
    identifier: str
    name: str
    created_at: str


class RepertoireLibrary:
    """Gestiona perfiles de repertorio sin mezclar sus datos con la base principal."""

    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root is not None else repertoire_directory()
        self.index_path = self.root / _INDEX_FILENAME

    @staticmethod
    def clean_name(name: str) -> str:
        """Normaliza un nombre visible y rechaza entradas ambiguas o vacías."""
        clean = " ".join(str(name).replace("\x00", " ").split())
        if not clean:
            raise RepertoireError("Escribe un nombre para el repertorio.")
        if len(clean) > 80:
            raise RepertoireError("El nombre del repertorio puede tener como máximo 80 caracteres.")
        return clean

    def list(self) -> list[Repertoire]:
        return sorted(self._load(), key=lambda item: item.name.casefold())

    def create(self, name: str) -> Repertoire:
        name = self.clean_name(name)
        profiles = self._load()
        if any(profile.name.casefold() == name.casefold() for profile in profiles):
            raise RepertoireError("Ya existe un repertorio con ese nombre.")
        profile = Repertoire(
            identifier=uuid.uuid4().hex,
            name=name,
            created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self._profile_directory(profile).mkdir(parents=False, exist_ok=False)
        try:
            self._save([*profiles, profile])
        except Exception:
            shutil.rmtree(self._profile_directory(profile), ignore_errors=True)
            raise
        return profile

    def rename(self, identifier: str, name: str) -> Repertoire:
        name = self.clean_name(name)
        profiles = self._load()
        target = self._get_from(profiles, identifier)
        if any(
            profile.identifier != target.identifier and profile.name.casefold() == name.casefold()
            for profile in profiles
        ):
            raise RepertoireError("Ya existe un repertorio con ese nombre.")
        renamed = Repertoire(identifier=target.identifier, name=name, created_at=target.created_at)
        self._save([renamed if profile.identifier == identifier else profile for profile in profiles])
        return renamed

    def delete(self, identifier: str) -> None:
        profiles = self._load()
        target = self._get_from(profiles, identifier)
        # Primero se actualiza el índice de forma atómica. Si el sistema se
        # interrumpe durante la limpieza, puede quedar una carpeta huérfana,
        # pero nunca un perfil visible con datos a medias.
        self._save([profile for profile in profiles if profile.identifier != identifier])
        shutil.rmtree(self._profile_directory(target), ignore_errors=True)

    def database_path(self, repertoire: Repertoire, color: str) -> Path:
        if color not in _VALID_COLORS:
            raise RepertoireError("El color del repertorio debe ser 'white' o 'black'.")
        return self._profile_directory(repertoire) / f"{color}.csdb"

    def _load(self) -> list[Repertoire]:
        if not self.index_path.exists():
            return []
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RepertoireError(
                "No se pudo leer el índice de repertorios. Restaura una copia de "
                "repertoires.json antes de modificarlo."
            ) from exc
        if not isinstance(raw, list):
            raise RepertoireError("El índice de repertorios tiene un formato no válido.")
        profiles: list[Repertoire] = []
        for item in raw:
            try:
                identifier = str(item["identifier"])
                name = self.clean_name(str(item["name"]))
                created_at = str(item["created_at"])
            except (KeyError, TypeError, RepertoireError) as exc:
                raise RepertoireError("El índice de repertorios contiene una entrada no válida.") from exc
            if not _SAFE_IDENTIFIER.fullmatch(identifier):
                raise RepertoireError("El índice de repertorios contiene un identificador no válido.")
            profiles.append(Repertoire(identifier=identifier, name=name, created_at=created_at))
        return profiles

    def _save(self, profiles: list[Repertoire]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([asdict(profile) for profile in profiles], ensure_ascii=False, indent=2) + "\n"
        temporary = self.index_path.with_name(self.index_path.name + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.index_path)

    @staticmethod
    def _get_from(profiles: list[Repertoire], identifier: str) -> Repertoire:
        for profile in profiles:
            if profile.identifier == identifier:
                return profile
        raise RepertoireError("El repertorio seleccionado ya no existe.")

    def _profile_directory(self, repertoire: Repertoire) -> Path:
        if not _SAFE_IDENTIFIER.fullmatch(repertoire.identifier):
            raise RepertoireError("Identificador de repertorio no válido.")
        return self.root / repertoire.identifier
