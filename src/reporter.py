"""
reporter — Structured logging and CSV reporting for the migration pipeline.

Responsabilité unique : persister les événements d'exécution dans 3 fichiers
suffixés du timestamp de démarrage :
  - migration-YYYYMMDD-HHMMSS.log    (log texte timestampé, lisible humainement)
  - collisions-YYYYMMDD-HHMMSS.csv   (collisions de noms .md et pièces jointes)
  - errors-YYYYMMDD-HHMMSS.csv       (erreurs par niveau : notebook/note/attachment)

Ne fait pas :
  - Agrégation statistiques inter-fichiers (orchestrateur)
  - Envoi vers destinations externes (Slack, email, syslog)
  - Validation stricte des codes de cause (accepte toute chaîne)

Causes d'erreur supportées par convention (cf. SPECS.md V1.7 Bloc 4) :
  Niveau notebook : notebook_not_found, enex_unreadable
  Niveau note     : xhtml_malformed, metadata_extraction_failed,
                    md_exists_no_force, md_write_error
  Niveau attachment: corrupted_base64, missing_hash, size_exceeded,
                     mime_excluded, traversal_blocked, write_error
"""

from __future__ import annotations

import csv
from datetime import datetime
from enum import Enum
from pathlib import Path


class LogLevel(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ErrorLevel(str, Enum):
    """Granularité d'une erreur dans le pipeline."""
    NOTEBOOK = "notebook"
    NOTE = "note"
    ATTACHMENT = "attachment"


class CollisionType(str, Enum):
    """Type de collision de nom de fichier."""
    MD = "md"
    ATTACHMENT = "attachment"


_ERRORS_HEADER = ["timestamp", "level", "cause", "detail",
                  "notebook", "note_guid", "note_title", "attachment_filename"]

_COLLISIONS_HEADER = ["timestamp", "kind", "original_name", "final_name",
                      "notebook", "note_guid"]


def _sanitize_field(value: str | None) -> str:
    """Supprime les NULL bytes (\\x00) susceptibles de casser CSV et certains éditeurs."""
    if value is None:
        return ""
    return value.replace("\x00", "")


def _resolve_paths(log_dir: Path, ts: str) -> tuple[Path, Path, Path]:
    """Retourne un triplet (log, errors, collisions) dont aucun fichier n'existe.

    Si le triplet au timestamp brut existe déjà (au moins un des 3), ajoute
    un suffixe numérique croissant : -1, -2, ... jusqu'à trouver un triplet
    entièrement libre.
    """
    counter = 0
    while True:
        suffix = f"-{counter}" if counter > 0 else ""
        log_path = log_dir / f"migration-{ts}{suffix}.log"
        errors_path = log_dir / f"errors-{ts}{suffix}.csv"
        coll_path = log_dir / f"collisions-{ts}{suffix}.csv"
        if not log_path.exists() and not errors_path.exists() and not coll_path.exists():
            return log_path, errors_path, coll_path
        counter += 1


class Reporter:
    """Collecte et persiste les logs et reports d'une exécution de migration.

    Instanciation : une fois par exécution de batch, avant toute opération.
    Trois fichiers générés dans log_dir, suffixés du timestamp de démarrage :
      migration-YYYYMMDD-HHMMSS.log
      collisions-YYYYMMDD-HHMMSS.csv
      errors-YYYYMMDD-HHMMSS.csv

    Si deux instances sont créées dans la même seconde, la seconde utilise
    un suffixe numérique : migration-YYYYMMDD-HHMMSS-1.log, etc.

    Usage typique :
        with Reporter(log_dir=Path("logs")) as reporter:
            reporter.log(LogLevel.INFO, "Démarrage migration")
            reporter.record_error(level=ErrorLevel.ATTACHMENT, cause="mime_excluded", ...)

    Limitations connues (V1) :
    - Écriture séquentielle CSV puis log : divergence possible en cas de panne
      mid-method (CSV écrit mais ligne log absente, ou inverse). Acceptable V1.
    - Pas de fsync : flush() garantit la sortie du buffer Python, mais l'écriture
      disque physique peut être différée par le système. Acceptable V1 (impact
      uniquement en cas de crash matériel).
    - Erreurs disque non encapsulées : laissées remonter à l'appelant (constitution
      règle 2 — aucune perte silencieuse, le batch s'arrête sur erreur disque grave).
    - Usage après close() : lèvera une exception Python native (fichier fermé).
      Pas de message custom.
    """

    def __init__(self, log_dir: Path) -> None:
        """
        Args:
            log_dir: répertoire où écrire les 3 fichiers. Créé s'il n'existe pas.

        Les 3 fichiers sont ouverts en mode append à l'instanciation.
        Le timestamp de démarrage est fixé ici (YYYYMMDD-HHMMSS).
        En cas de collision de noms (même seconde), un suffixe -1, -2... est ajouté.
        Les CSV ont leur ligne d'en-tête écrite uniquement si le fichier est nouveau.
        """
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_path, errors_path, coll_path = _resolve_paths(self._log_dir, ts)

        self._closed = False
        opened_handles: list = []
        try:
            self._log_fh = log_path.open("a", encoding="utf-8")
            opened_handles.append(self._log_fh)

            errors_existed = errors_path.exists()
            self._errors_fh = errors_path.open("a", encoding="utf-8", newline="")
            opened_handles.append(self._errors_fh)
            self._errors_writer = csv.writer(self._errors_fh, quoting=csv.QUOTE_MINIMAL)
            if not errors_existed:
                self._errors_writer.writerow(_ERRORS_HEADER)
                self._errors_fh.flush()

            coll_existed = coll_path.exists()
            self._coll_fh = coll_path.open("a", encoding="utf-8", newline="")
            opened_handles.append(self._coll_fh)
            self._coll_writer = csv.writer(self._coll_fh, quoting=csv.QUOTE_MINIMAL)
            if not coll_existed:
                self._coll_writer.writerow(_COLLISIONS_HEADER)
                self._coll_fh.flush()

        except Exception:
            for fh in opened_handles:
                try:
                    fh.close()
                except Exception:
                    pass
            raise

    def log(self, level: LogLevel, message: str) -> None:
        """Écrit une ligne timestampée dans le log texte.

        Format : YYYY-MM-DDTHH:MM:SS [LEVEL] message
        Flush immédiat. NULL bytes supprimés.
        """
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self._log_fh.write(f"{ts} [{level.value}] {_sanitize_field(message)}\n")
        self._log_fh.flush()

    def record_error(
        self,
        level: ErrorLevel,
        cause: str,
        detail: str,
        notebook: str | None = None,
        note_guid: str | None = None,
        note_title: str | None = None,
        attachment_filename: str | None = None,
    ) -> None:
        """Écrit une ligne dans errors.csv et une ligne ERROR dans le log texte.

        Les champs None sont écrits comme chaîne vide dans le CSV.
        NULL bytes supprimés dans tous les champs.
        Flush immédiat sur les deux fichiers.
        """
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self._errors_writer.writerow([
            ts,
            level.value,
            _sanitize_field(cause),
            _sanitize_field(detail),
            _sanitize_field(notebook),
            _sanitize_field(note_guid),
            _sanitize_field(note_title),
            _sanitize_field(attachment_filename),
        ])
        self._errors_fh.flush()

        context = ""
        if notebook:
            context += f" notebook='{_sanitize_field(notebook)}'"
        if note_guid:
            context += f" guid={_sanitize_field(note_guid)}"
        if attachment_filename:
            context += f" file='{_sanitize_field(attachment_filename)}'"
        self.log(LogLevel.ERROR, f"{_sanitize_field(cause)}{context} — {_sanitize_field(detail)}")

    def record_collision(
        self,
        kind: CollisionType,
        original_name: str,
        final_name: str,
        notebook: str,
        note_guid: str | None = None,
    ) -> None:
        """Écrit une ligne dans collisions.csv et une ligne INFO dans le log texte.

        NULL bytes supprimés dans tous les champs. Flush immédiat.
        """
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self._coll_writer.writerow([
            ts,
            kind.value,
            _sanitize_field(original_name),
            _sanitize_field(final_name),
            _sanitize_field(notebook),
            _sanitize_field(note_guid),
        ])
        self._coll_fh.flush()

        self.log(
            LogLevel.INFO,
            f"Collision {kind.value} : '{_sanitize_field(original_name)}' → "
            f"'{_sanitize_field(final_name)}' dans '{_sanitize_field(notebook)}'",
        )

    def close(self) -> None:
        """Ferme proprement les 3 handles de fichier.

        Idempotent. Ferme les 3 indépendamment : si l'un lève, les autres
        sont quand même fermés. La première exception est re-raised à la fin.
        """
        if self._closed:
            return
        self._closed = True
        errors: list[Exception] = []
        for fh in [self._log_fh, self._errors_fh, self._coll_fh]:
            try:
                fh.close()
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise errors[0]

    def __enter__(self) -> "Reporter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
