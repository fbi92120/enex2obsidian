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


class Reporter:
    """Collecte et persiste les logs et reports d'une exécution de migration.

    Instanciation : une fois par exécution de batch, avant toute opération.
    Trois fichiers générés dans log_dir, suffixés du timestamp de démarrage :
      migration-YYYYMMDD-HHMMSS.log
      collisions-YYYYMMDD-HHMMSS.csv
      errors-YYYYMMDD-HHMMSS.csv

    Usage typique :
        with Reporter(log_dir=Path("logs")) as reporter:
            reporter.log(LogLevel.INFO, "Démarrage migration")
            reporter.record_error(level=ErrorLevel.ATTACHMENT, cause="mime_excluded", ...)
    """

    def __init__(self, log_dir: Path) -> None:
        """
        Args:
            log_dir: répertoire où écrire les 3 fichiers. Créé s'il n'existe pas.

        Les 3 fichiers sont ouverts en mode append à l'instanciation.
        Le timestamp de démarrage est fixé ici (YYYYMMDD-HHMMSS).
        Les CSV ont leur ligne d'en-tête écrite à l'ouverture.
        """
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        self._startup_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        self._closed = False

        # Log texte
        log_path = self._log_dir / f"migration-{self._startup_ts}.log"
        self._log_fh = log_path.open("a", encoding="utf-8")

        # errors.csv
        errors_path = self._log_dir / f"errors-{self._startup_ts}.csv"
        self._errors_fh = errors_path.open("a", encoding="utf-8", newline="")
        self._errors_writer = csv.writer(self._errors_fh, quoting=csv.QUOTE_MINIMAL)
        self._errors_writer.writerow(_ERRORS_HEADER)
        self._errors_fh.flush()

        # collisions.csv
        coll_path = self._log_dir / f"collisions-{self._startup_ts}.csv"
        self._coll_fh = coll_path.open("a", encoding="utf-8", newline="")
        self._coll_writer = csv.writer(self._coll_fh, quoting=csv.QUOTE_MINIMAL)
        self._coll_writer.writerow(_COLLISIONS_HEADER)
        self._coll_fh.flush()

    def log(self, level: LogLevel, message: str) -> None:
        """Écrit une ligne timestampée dans le log texte.

        Format : YYYY-MM-DDTHH:MM:SS [LEVEL] message
        Flush immédiat.
        """
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self._log_fh.write(f"{ts} [{level.value}] {message}\n")
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
        Flush immédiat sur les deux fichiers.
        """
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self._errors_writer.writerow([
            ts,
            level.value,
            cause,
            detail,
            notebook or "",
            note_guid or "",
            note_title or "",
            attachment_filename or "",
        ])
        self._errors_fh.flush()

        # Résumé dans le log texte
        context = ""
        if notebook:
            context += f" notebook='{notebook}'"
        if note_guid:
            context += f" guid={note_guid}"
        if attachment_filename:
            context += f" file='{attachment_filename}'"
        self.log(LogLevel.ERROR, f"{cause}{context} — {detail}")

    def record_collision(
        self,
        kind: CollisionType,
        original_name: str,
        final_name: str,
        notebook: str,
        note_guid: str | None = None,
    ) -> None:
        """Écrit une ligne dans collisions.csv et une ligne INFO dans le log texte.

        Flush immédiat.
        """
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        self._coll_writer.writerow([
            ts,
            kind.value,
            original_name,
            final_name,
            notebook,
            note_guid or "",
        ])
        self._coll_fh.flush()

        self.log(
            LogLevel.INFO,
            f"Collision {kind.value} : '{original_name}' → '{final_name}' dans '{notebook}'",
        )

    def close(self) -> None:
        """Ferme proprement les 3 handles de fichier. Idempotent."""
        if self._closed:
            return
        self._closed = True
        self._log_fh.close()
        self._errors_fh.close()
        self._coll_fh.close()

    def __enter__(self) -> "Reporter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
