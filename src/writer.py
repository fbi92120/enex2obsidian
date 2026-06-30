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
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from src.filename_normalizer import slug_for_note, is_path_under_base
from src.metadata_extractor import NoteMetadata, to_yaml_frontmatter
from src.attachment_handler import AttachmentResult

# Regex des placeholders — permissive sur le hash pour couvrir MD5 hex et les tests
_PLACEHOLDER_RE = re.compile(r'\{\{ATTACHMENT:([^\}]+)\}\}')

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
        # Noms de fichiers .md finaux déjà écrits dans cette session (intra-session)
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
        # Étape 1 — Génération du slug
        try:
            slug = slug_for_note(metadata.title, metadata.evernote_guid)
        except ValueError:
            slug = "note-unknown"

        # Étape 2 — Nom de fichier initial
        initial_filename = f"{slug}.md"

        # Étape 3 — Anti-traversal
        candidate_path = (self._notebook_dir / initial_filename).resolve()
        if not is_path_under_base(str(self._notebook_dir), str(candidate_path)):
            return WriteResult(
                status="traversal_blocked",
                final_path=None,
                slug=slug,
                collided=False,
                final_filename=None,
                error_detail=f"Slug '{slug}' resolves outside notebook_dir",
            )

        # Étape 4 — Gestion collision / skip existant
        # Vérifier si le fichier initial existe sur disque ou en mémoire de session
        final_filename = initial_filename
        final_path = self._notebook_dir / final_filename
        collided = False

        if final_path.exists() or final_filename in self._written_filenames:
            if not self._force_overwrite:
                # On cherche si c'est un vrai conflit inter-session (disque seul)
                # ou intra-session → dans les deux cas sans force : skipped ou collision
                if not (final_filename in self._written_filenames):
                    # Fichier existe sur disque, pas encore en session → skip
                    return WriteResult(
                        status="skipped_existing",
                        final_path=final_path,
                        slug=slug,
                        collided=False,
                        final_filename=final_filename,
                        error_detail=None,
                    )
                # Déjà dans la session → résoudre la collision avec suffixe
            if self._force_overwrite and final_filename not in self._written_filenames:
                # Écraser le fichier disque existant (force mode, pas encore écrit dans cette session)
                pass
            else:
                # Chercher un nom libre avec suffixe -2, -3, ...
                for counter in range(2, 10000):
                    candidate_filename = f"{slug}-{counter}.md"
                    candidate_path2 = self._notebook_dir / candidate_filename
                    if not candidate_path2.exists() and candidate_filename not in self._written_filenames:
                        final_filename = candidate_filename
                        final_path = candidate_path2
                        collided = True
                        break

        # Vérifier anti-traversal sur le nom final (au cas où le suffixe modifie)
        if not is_path_under_base(str(self._notebook_dir), str(final_path.resolve())):
            return WriteResult(
                status="traversal_blocked",
                final_path=None,
                slug=slug,
                collided=collided,
                final_filename=None,
                error_detail=f"Resolved path for '{final_filename}' outside notebook_dir",
            )

        # Étape 5 — Résolution des placeholders
        resolved_content, unresolved = _resolve_placeholders(markdown_content, attachment_map)

        # Étape 6 — Assemblage
        frontmatter = to_yaml_frontmatter(metadata)
        final_content = frontmatter + "\n" + resolved_content

        # Étape 7 — Écriture atomique
        tmp_path = final_path.parent / (final_path.name + ".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as f:
                f.write(final_content)
                f.flush()
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

        # Mémoriser le nom final pour les collisions intra-session
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

    Returns:
        (contenu résolu, liste des hashes non trouvés dans attachment_map)
    """
    unresolved: list[str] = []

    def _replace(m: re.Match) -> str:
        hash_val = m.group(1)
        att = attachment_map.get(hash_val)
        if att is None:
            unresolved.append(hash_val)
            return f"[pièce jointe non résolue : {hash_val[:8]}...]"
        if att.status == "ok" and att.final_filename:
            if _is_image_mime(att.mime):
                return f"![[{att.final_filename}]]"
            else:
                encoded = urllib.parse.quote(att.final_filename, safe="")
                return f"[{att.final_filename}](attachments/{encoded})"
        # Pièce jointe skippée (mime_excluded, size_exceeded, etc.)
        return f"[pièce jointe non disponible : {att.status}]"

    resolved = _PLACEHOLDER_RE.sub(_replace, content)
    return resolved, unresolved


def _is_image_mime(mime: str) -> bool:
    return bool(mime) and mime.startswith("image/")
