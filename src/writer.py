"""
writer — Write Markdown notes to the Obsidian vault for a given notebook.

Responsabilité unique : écrire les fichiers .md dans le vault Obsidian.
Résout les placeholders {{ATTACHMENT:hash}}, gère les collisions de slug,
écrit atomiquement via .md.tmp + os.replace (iCloud-safe), anti-traversal.

Ne fait pas :
  - Parsing ENEX (enex_parser)
  - Extraction métadonnées (metadata_extractor)
  - Conversion XHTML→Markdown (content_converter)
  - Décodage pièces jointes (attachment_handler)
  - Logging direct (WriteResult retourné à l'orchestrateur/reporter)
"""

from __future__ import annotations

import os
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from src.filename_normalizer import slug_for_note, is_path_under_base
from src.metadata_extractor import NoteMetadata, to_yaml_frontmatter
from src.attachment_handler import AttachmentResult

# Strict MD5 hex format — non-hex characters are not treated as placeholders
_PLACEHOLDER_RE = re.compile(r'\{\{ATTACHMENT:([a-f0-9]+)\}\}')

# Types MIME rendus en embed wikilink ![[attachments/...]] (images + PDFs, V1.8)
_EMBED_MIMES = {
    "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp",
    "image/heic", "image/heif", "image/tiff", "image/svg+xml",
    "application/pdf",
}

WriteStatus = Literal[
    "ok",
    "skipped_existing",
    "write_error",
    "traversal_blocked",
]


@dataclass
class WriteResult:
    """Résultat de l'écriture d'une note dans le vault."""
    status: WriteStatus
    final_path: Path | None
    slug: str
    collided: bool
    final_filename: str | None
    error_detail: str | None
    unresolved_placeholders: list[str] = field(default_factory=list)


class Writer:
    """Écriture des fichiers .md dans le vault pour un carnet donné.

    Instanciation : une fois par carnet, avant la boucle sur les notes.
    Maintient l'état des noms de fichiers .md déjà écrits pour gérer les
    collisions de slug à l'échelle du carnet.

    Limitations connues (V1) :
    - Pas de fsync après l'écriture du .tmp : flush() garantit la sortie du
      buffer Python, mais l'écriture disque physique peut être différée.
      Impact uniquement en cas de crash matériel pendant la migration.
    - Race condition entre check d'existence et write : un autre processus
      pourrait créer/supprimer le .md cible entre les deux. V1 mono-process,
      acceptable.
    - Idempotence intra-session par evernote_guid non implémentée : deux
      appels write() pour la même note (même GUID) dans la même session
      produisent un suffixe -2 au lieu d'être détectés comme redondants.
      L'orchestrateur V1 itère sur des notes uniques, donc ce cas ne se
      présente pas en pratique.
    - URL encoding : un nom de fichier contenant déjà %XX sera double-encodé
      (%2520 au lieu de %20). Cas pathologique improbable sur un corpus
      Evernote standard.
    """

    def __init__(self, notebook_dir: Path, force_overwrite: bool = False) -> None:
        """
        Args:
            notebook_dir: dossier de destination des .md du carnet.
                         Créé s'il n'existe pas (parents inclus).
            force_overwrite: si True, écrase un .md cible existant.
        """
        self._notebook_dir = Path(notebook_dir)
        self._notebook_dir.mkdir(parents=True, exist_ok=True)
        self._force_overwrite = force_overwrite
        self._written_filenames: set[str] = set()

    def write(
        self,
        metadata: NoteMetadata,
        markdown_content: str,
        attachment_map: dict[str, AttachmentResult],
    ) -> WriteResult:
        """Écrit une note dans le vault.

        Ne lève jamais d'exception : toute erreur disque est capturée dans WriteResult.
        """
        # Étape 1 — Génération du slug (constitution règle 4 : pas de fallback inventé)
        try:
            slug = slug_for_note(metadata.title, metadata.evernote_guid)
            slug = unicodedata.normalize("NFC", slug)  # défense en profondeur (V1.8)
        except ValueError as exc:
            return WriteResult(
                status="write_error",
                final_path=None,
                slug="",
                collided=False,
                final_filename=None,
                error_detail=f"cannot generate slug: {exc}",
            )

        # Étape 2 — Anti-traversal sur le slug initial
        initial_filename = f"{slug}.md"
        initial_candidate = (self._notebook_dir / initial_filename).resolve()
        if not is_path_under_base(str(self._notebook_dir), str(initial_candidate)):
            return WriteResult(
                status="traversal_blocked",
                final_path=None,
                slug=slug,
                collided=False,
                final_filename=None,
                error_detail=f"Slug '{slug}' resolves outside notebook_dir",
            )

        # Étape 3 — Gestion collision / skip
        final_filename = initial_filename
        collided = False
        notebook_dir = self._notebook_dir

        disk_exists = (notebook_dir / final_filename).exists()
        in_session = final_filename in self._written_filenames

        if disk_exists or in_session:
            if self._force_overwrite:
                pass  # écrasement inter- ou intra-session (correction 4)
            elif not in_session:
                # Conflit disque uniquement, force=False.
                # Vérifie si l'espace de suffixes est épuisé (correction 2).
                all_taken = True
                for suffix in range(2, 1000):
                    cand = f"{slug}-{suffix}.md"
                    if cand not in self._written_filenames and not (notebook_dir / cand).exists():
                        all_taken = False
                        break
                if all_taken:
                    return WriteResult(
                        status="write_error",
                        final_path=None,
                        slug=slug,
                        collided=False,
                        final_filename=None,
                        error_detail=f"collision counter exhausted (>1000 conflicts for slug '{slug}')",
                    )
                # Suffixe libre disponible → note déjà traitée lors d'un run précédent
                return WriteResult(
                    status="skipped_existing",
                    final_path=notebook_dir / final_filename,
                    slug=slug,
                    collided=False,
                    final_filename=final_filename,
                    error_detail=None,
                )
            else:
                # Conflit intra-session : trouver un suffixe libre (correction 2)
                found = False
                for suffix in range(2, 1000):
                    cand = f"{slug}-{suffix}.md"
                    if cand not in self._written_filenames and not (notebook_dir / cand).exists():
                        final_filename = cand
                        collided = True
                        found = True
                        break
                if not found:
                    return WriteResult(
                        status="write_error",
                        final_path=None,
                        slug=slug,
                        collided=False,
                        final_filename=None,
                        error_detail=f"collision counter exhausted (>1000 conflicts for slug '{slug}')",
                    )

        final_path = notebook_dir / final_filename

        # Étape 4 — Résolution des placeholders
        resolved_content, unresolved = _resolve_placeholders(markdown_content, attachment_map)

        # Étape 5 — Assemblage
        frontmatter = to_yaml_frontmatter(metadata)
        final_content = frontmatter + "\n" + resolved_content

        # Étape 6 — Écriture atomique avec protection symlink (correction 1)
        tmp_path = final_path.parent / (final_path.name + ".tmp")

        # Cleanup défensif d'un .tmp préexistant (orphelin ou symlink malicieux)
        if tmp_path.exists() or tmp_path.is_symlink():
            try:
                tmp_path.unlink()
            except Exception as exc:
                return WriteResult(
                    status="write_error",
                    final_path=None,
                    slug=slug,
                    collided=collided,
                    final_filename=None,
                    error_detail=f"cannot remove existing .tmp: {exc}",
                )

        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                f.write(final_content)
                f.flush()

            # Vérification anti-traversal sur le .tmp APRÈS écriture, AVANT os.replace
            if not is_path_under_base(str(self._notebook_dir), str(tmp_path.resolve())):
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
                return WriteResult(
                    status="traversal_blocked",
                    final_path=None,
                    slug=slug,
                    collided=collided,
                    final_filename=None,
                    error_detail=".tmp path resolves outside notebook_dir",
                )

            os.replace(tmp_path, final_path)

        except Exception as exc:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            return WriteResult(
                status="write_error",
                final_path=None,
                slug=slug,
                collided=collided,
                final_filename=final_filename,
                error_detail=str(exc)[:400],
            )

        self._written_filenames.add(final_filename)

        return WriteResult(
            status="ok",
            final_path=final_path,
            slug=slug,
            collided=collided,
            final_filename=final_filename,
            error_detail=None,
            unresolved_placeholders=unresolved,
        )


def _resolve_placeholders(
    content: str,
    attachment_map: dict[str, AttachmentResult],
) -> tuple[str, list[str]]:
    """Résout les placeholders {{ATTACHMENT:hash}} dans le contenu Markdown.

    Format de sortie (V1.8) :
    - Images et PDFs : ![[attachments/fichier.ext]] (embed wikilink, chemin relatif explicite)
    - Autres types   : [fichier.ext](attachments/fichier-encoded.ext) (lien Markdown classique)
    - Non disponible : [pièce jointe non disponible : status]
    - Non résolu     : [pièce jointe non résolue : hash[:8]...]

    Tous les noms de fichiers sont normalisés en NFC (constitution règle 10, V1.8).

    Returns:
        (contenu résolu, liste des hashes non trouvés dans attachment_map)
    """
    unresolved: list[str] = []

    def _replace(m: re.Match) -> str:
        hash_val = m.group(1)
        att = attachment_map.get(hash_val)
        if att is None:
            # SPECS Bloc 4 : PJ corrompue stockée sous hash="" par attachment_handler
            corrupted = attachment_map.get("")
            if corrupted and corrupted.status in ("corrupted_base64", "missing_hash"):
                return "[pièce jointe corrompue, voir log]"
            unresolved.append(hash_val)
            return f"[pièce jointe non résolue : {hash_val[:8]}...]"
        if att.status == "ok" and att.final_filename:
            # Défense en profondeur NFC (constitution règle 10, V1.8)
            filename = unicodedata.normalize("NFC", att.final_filename)
            if att.mime in _EMBED_MIMES:
                return f"![[attachments/{filename}]]"
            else:
                encoded = urllib.parse.quote(filename, safe="")
                return f"[{filename}](attachments/{encoded})"
        if att.status == "skipped_size":  # SPECS Bloc 4 : [pièce jointe ignorée : taille > N Mo, voir log]
            limit = att.size_limit_mb if att.size_limit_mb is not None else "?"
            return f"[pièce jointe ignorée : taille > {limit} Mo, voir log]"
        return f"[pièce jointe non disponible : {att.status}]"

    resolved = _PLACEHOLDER_RE.sub(_replace, content)
    return resolved, unresolved
