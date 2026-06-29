"""
attachment_handler — Decode, hash, sanitize and write note attachments.

Responsabilité : prendre une RawAttachment (enex_parser), décoder le base64,
calculer le hash MD5, déterminer le nom de fichier final (sanitization +
gestion des collisions), vérifier la limite de taille, écrire sur disque et
retourner un AttachmentResult structuré pour l'orchestrateur.

Ne fait pas :
  - Résolution des placeholders {{ATTACHMENT:hash}} dans le Markdown (orchestrateur)
  - Logging (reporter.py consomme AttachmentResult)
  - Écriture du .md (writer.py)

Constitution règle 1 : ne lève jamais d'exception vers l'appelant.
Constitution règle 5 : idempotence — même hash MD5 → même fichier, pas de réécriture.
Constitution règle 9 : anti-traversal vérifié avant toute écriture.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.filename_normalizer import sanitize_attachment_name, is_path_under_base


AttachmentStatus = Literal[
    "ok",               # décodage et écriture réussis
    "skipped_size",     # > size_limit_mb, fichier non écrit
    "skipped_existing", # même hash MD5 déjà traité dans cette session (idempotence)
    "corrupted_base64", # base64 invalide, fichier non écrit
    "missing_hash",     # hash MD5 non calculable (data_base64 absent)
    "traversal_blocked", # chemin résolu hors target_dir, fichier non écrit
    "write_error",      # erreur disque
]


@dataclass
class AttachmentResult:
    """Résultat du traitement d'une pièce jointe.

    Le hash MD5 sert de clé pour résoudre les placeholders {{ATTACHMENT:hash}}
    dans le Markdown généré par content_converter.
    """

    hash: str                     # MD5 hexdigest des bytes décodés, "" si calcul impossible
    status: AttachmentStatus
    final_filename: str | None    # nom final écrit dans target_dir, None si non écrit
    mime: str                     # type MIME (ex. "application/pdf")
    original_filename: str | None # nom d'origine avant sanitization/collision
    size_bytes: int | None        # taille décodée en bytes, None si non décodée
    error_detail: str | None      # message d'erreur pour le reporter, None si ok
    note_title: str               # contexte pour le reporter
    note_guid: str                # contexte pour le reporter


class AttachmentHandler:
    """Gestionnaire de pièces jointes pour un carnet.

    Instancié une fois par carnet par l'orchestrateur, avant la boucle sur les notes.
    Maintient l'état des hashes traités pour assurer l'idempotence intra-session
    (même contenu → même fichier, pas de réécriture, pas de collision).
    """

    def __init__(self, target_dir: Path, size_limit_mb: int = 200) -> None:
        """
        Args:
            target_dir: dossier de destination (typiquement [vault]/[carnet]/attachments/).
                        Créé automatiquement lors du premier handle() si absent.
            size_limit_mb: plafond de taille par pièce jointe en Mo (défaut 200).
        """
        self._target_dir = Path(target_dir)
        self._size_limit_bytes = size_limit_mb * 1024 * 1024
        # hash MD5 hexdigest → nom de fichier final écrit (idempotence intra-session)
        self._hash_to_filename: dict[str, str] = {}

    def handle(
        self,
        raw_attachment,
        note_title: str,
        note_guid: str,
    ) -> AttachmentResult:
        """Traite une pièce jointe : décode, hash, sanitization, écriture.

        Ne lève jamais d'exception : toute erreur est capturée et retournée
        dans AttachmentResult.status + error_detail (constitution règle 1).

        Args:
            raw_attachment: RawAttachment produite par enex_parser.
            note_title: titre de la note source (contexte pour reporter).
            note_guid: GUID de la note source (contexte pour reporter).

        Returns:
            AttachmentResult avec status, hash, final_filename et infos reporter.
        """
        mime = raw_attachment.mime or ""
        original_filename = raw_attachment.file_name

        # Étape 1 : Décodage base64
        if not raw_attachment.data_base64:
            return self._error(
                hash_val="",
                status="corrupted_base64",
                mime=mime,
                original_filename=original_filename,
                size_bytes=None,
                error_detail="data_base64 is None or empty",
                note_title=note_title,
                note_guid=note_guid,
            )

        try:
            # ENEX base64 contient souvent des retours à la ligne (76 chars par ligne)
            cleaned = (
                raw_attachment.data_base64
                .replace("\n", "")
                .replace("\r", "")
                .replace(" ", "")
            )
            decoded_bytes = base64.b64decode(cleaned, validate=True)
        except (binascii.Error, ValueError, Exception) as exc:
            return self._error(
                hash_val="",
                status="corrupted_base64",
                mime=mime,
                original_filename=original_filename,
                size_bytes=None,
                error_detail=str(exc)[:200],
                note_title=note_title,
                note_guid=note_guid,
            )

        # Étape 2 : Calcul MD5 sur les bytes décodés
        md5_hash = hashlib.md5(decoded_bytes).hexdigest()
        size_bytes = len(decoded_bytes)

        # Étape 3 : Vérification taille
        if size_bytes > self._size_limit_bytes:
            return self._error(
                hash_val=md5_hash,
                status="skipped_size",
                mime=mime,
                original_filename=original_filename,
                size_bytes=size_bytes,
                error_detail=(
                    f"Size {size_bytes} bytes exceeds limit {self._size_limit_bytes} bytes"
                ),
                note_title=note_title,
                note_guid=note_guid,
            )

        # Étape 4 : Idempotence intra-session (même contenu → même fichier)
        if md5_hash in self._hash_to_filename:
            return AttachmentResult(
                hash=md5_hash,
                status="skipped_existing",
                final_filename=self._hash_to_filename[md5_hash],
                mime=mime,
                original_filename=original_filename,
                size_bytes=size_bytes,
                error_detail=None,
                note_title=note_title,
                note_guid=note_guid,
            )

        # Étape 5 : Détermination du nom de fichier
        final_name = self._resolve_filename(original_filename, md5_hash, mime)

        # Étape 6 : Anti-traversal — vérification realpath des deux côtés
        candidate_path = self._target_dir / final_name
        if not is_path_under_base(str(self._target_dir), str(candidate_path)):
            return self._error(
                hash_val=md5_hash,
                status="traversal_blocked",
                mime=mime,
                original_filename=original_filename,
                size_bytes=size_bytes,
                error_detail=f"Path {final_name!r} resolves outside target_dir",
                note_title=note_title,
                note_guid=note_guid,
            )

        # Étape 7 : Gestion des collisions (suffixes -2, -3, ...)
        final_name = self._resolve_collision(final_name)
        final_path = self._target_dir / final_name

        # Étape 8 : Écriture sur disque
        try:
            self._target_dir.mkdir(parents=True, exist_ok=True)
            final_path.write_bytes(decoded_bytes)
        except OSError as exc:
            return self._error(
                hash_val=md5_hash,
                status="write_error",
                mime=mime,
                original_filename=original_filename,
                size_bytes=size_bytes,
                error_detail=str(exc)[:200],
                note_title=note_title,
                note_guid=note_guid,
            )

        # Étape 9 : Mémorisation et retour
        self._hash_to_filename[md5_hash] = final_name

        return AttachmentResult(
            hash=md5_hash,
            status="ok",
            final_filename=final_name,
            mime=mime,
            original_filename=original_filename,
            size_bytes=size_bytes,
            error_detail=None,
            note_title=note_title,
            note_guid=note_guid,
        )

    # ------------------------------------------------------------------
    # Méthodes internes
    # ------------------------------------------------------------------

    def _resolve_filename(
        self, original_filename: str | None, md5_hash: str, mime: str
    ) -> str:
        """Détermine le nom de fichier final (sanitization, fallback sur hash+mime).

        Priorité :
          1. original_filename sanitisé (accents et espaces conservés per SPECS.md)
          2. attachment-{hash[:8]}.{ext} si nom absent ou vide après sanitization
        """
        if original_filename:
            sanitized, _ = sanitize_attachment_name(original_filename)
            if sanitized:
                return sanitized
        ext = self._guess_extension(mime)
        return f"attachment-{md5_hash[:8]}{ext}"

    def _guess_extension(self, mime: str) -> str:
        """Devine l'extension depuis le MIME type via mimetypes stdlib.

        Retourne ".bin" si MIME inconnu ou absent.
        """
        if not mime:
            return ".bin"
        ext = mimetypes.guess_extension(mime)
        return ext if ext else ".bin"

    def _resolve_collision(self, name: str) -> str:
        """Gère les collisions sur disque avec suffixes -2, -3, ...

        Vérifie l'existence sur disque (inclut les fichiers d'autres sessions).
        La boucle incrémente le suffixe jusqu'à trouver un nom libre.
        """
        if not (self._target_dir / name).exists():
            return name

        # Séparer base et extension
        dot_idx = name.rfind(".")
        if dot_idx > 0:
            stem = name[:dot_idx]
            ext = name[dot_idx:]
        else:
            stem = name
            ext = ""

        counter = 2
        while True:
            candidate = f"{stem}-{counter}{ext}"
            if not (self._target_dir / candidate).exists():
                return candidate
            counter += 1

    @staticmethod
    def _error(
        hash_val: str,
        status: AttachmentStatus,
        mime: str,
        original_filename: str | None,
        size_bytes: int | None,
        error_detail: str | None,
        note_title: str,
        note_guid: str,
    ) -> AttachmentResult:
        """Construit un AttachmentResult d'erreur (final_filename=None)."""
        return AttachmentResult(
            hash=hash_val,
            status=status,
            final_filename=None,
            mime=mime,
            original_filename=original_filename,
            size_bytes=size_bytes,
            error_detail=error_detail,
            note_title=note_title,
            note_guid=note_guid,
        )
