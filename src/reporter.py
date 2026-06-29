"""
reporter — Structured logging and CSV reporting for the migration pipeline.

Creates and manages the three output files for each migration run:
  - migration-YYYY-MM-DD-HHMM.log  (human-readable execution log)
  - collisions-YYYY-MM-DD-HHMM.csv (attachment and .md name collisions)
  - erreurs-YYYY-MM-DD-HHMM.csv    (errors at notebook, note, and attachment level)

All file handles are opened at session creation and closed at summary.
Thread-unsafe by design (single-threaded pipeline).
"""

import csv
import os
from datetime import datetime
from typing import Optional


class Reporter:
    """
    Manages log and CSV output files for a single migration session.

    Instantiated once per run by enex2obsidian.py orchestrator.
    Passed by reference to all src/ modules that need to log events.
    """

    def __init__(self, log_dir: str, timestamp: str):
        """
        Initialize reporter and open output files.

        Args:
            log_dir (str): absolute path to log directory (must exist)
            timestamp (str): run timestamp string "YYYY-MM-DD-HHMM"
                Used as suffix for all output filenames.

        Raises:
            OSError: if output files cannot be created.
        """
        raise NotImplementedError("Étape 8 de la séquence")

    def log_info(self, message: str) -> None:
        """
        Write an informational line to the execution log.

        Format: "[YYYY-MM-DD HH:MM:SS] message"

        Args:
            message (str): log message (single line recommended)
        """
        raise NotImplementedError("Étape 8 de la séquence")

    def log_warning(self, message: str) -> None:
        """
        Write a warning line to the execution log.

        Format: "[YYYY-MM-DD HH:MM:SS] WARNING: message"

        Args:
            message (str): warning message
        """
        raise NotImplementedError("Étape 8 de la séquence")

    def log_error(self, message: str) -> None:
        """
        Write an error line to the execution log.

        Format: "[YYYY-MM-DD HH:MM:SS] ERROR: message"

        Args:
            message (str): error message
        """
        raise NotImplementedError("Étape 8 de la séquence")

    def log_collision(
        self,
        carnet: str,
        note_titre: str,
        note_guid: str,
        collision_type: str,
        nom_original: str,
        nom_final: str,
        note: str = "",
    ) -> None:
        """
        Record a filename collision in the collisions CSV.

        CSV columns: timestamp, carnet, note_titre, note_guid, type, nom_original, nom_final, note

        Args:
            carnet (str): notebook name
            note_titre (str): note title
            note_guid (str): note GUID
            collision_type (str): "attachment" or "md"
            nom_original (str): original filename before collision resolution
            nom_final (str): final filename after collision resolution
            note (str): optional annotation e.g. "sanitized"
        """
        raise NotImplementedError("Étape 8 de la séquence")

    def log_erreur(
        self,
        carnet: str,
        note_titre: str,
        note_guid: str,
        niveau: str,
        cause: str,
        detail: str,
    ) -> None:
        """
        Record a processing error in the erreurs CSV.

        CSV columns: timestamp, carnet, note_titre, note_guid, niveau, cause, detail

        Args:
            carnet (str): notebook name
            note_titre (str): note title (or "—" if unavailable)
            note_guid (str): note GUID (or "—" if unavailable)
            niveau (str): "notebook", "note", or "attachment"
            cause (str): short error code e.g. "xhtml_malformed", "size_exceeded"
            detail (str): detailed error message or exception text
        """
        raise NotImplementedError("Étape 8 de la séquence")

    def write_summary(self, stats: dict) -> None:
        """
        Write the migration summary to the log file and close all handles.

        Args:
            stats (dict): migration statistics with keys:
                - notebooks_total (int)
                - notebooks_processed (int)
                - notes_total (int)
                - notes_success (int)
                - notes_error_partial (int)
                - notes_error_total (int)
                - attachments_copied (int)
                - attachments_collisions (int)
                - attachments_ignored (int)
        """
        raise NotImplementedError("Étape 8 de la séquence")

    def close(self) -> None:
        """Close all open file handles. Safe to call multiple times."""
        raise NotImplementedError("Étape 8 de la séquence")


def make_timestamp() -> str:
    """
    Return the current datetime in "YYYY-MM-DD-HHMM" format for log filenames.

    Returns:
        str: timestamp string e.g. "2026-06-29-1430"
    """
    raise NotImplementedError("Étape 8 de la séquence")
