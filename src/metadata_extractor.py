"""
metadata_extractor — Normalize RawNote metadata into Obsidian frontmatter.

Responsabilité unique : transformer une RawNote (produite par enex_parser)
en métadonnées normalisées et en bloc frontmatter YAML prêt à écrire.

Ne fait pas :
  - parsing ENEX (enex_parser.py)
  - conversion XHTML → Markdown (content_converter.py)
  - décodage base64 (attachment_handler.py)
  - écriture sur disque (writer.py)

Constitution règle 4 : aucune métadonnée inventée. Champ absent → "" ou [].
"""

from __future__ import annotations

from dataclasses import dataclass
from dateutil import parser as dateutil_parser

from src.enex_parser import RawNote
from src.filename_normalizer import normalize_tag as fn_normalize_tag


@dataclass
class NoteMetadata:
    """Métadonnées normalisées d'une note, prêtes pour frontmatter YAML."""

    title: str
    created: str
    updated: str
    tags: list[str]
    source_url: str
    evernote_notebook: str
    evernote_guid: str


def extract_metadata(raw_note: RawNote, notebook_name: str) -> NoteMetadata:
    """Transforme une RawNote en NoteMetadata normalisée pour frontmatter YAML.

    Args:
        raw_note: note brute extraite par enex_parser
        notebook_name: nom du carnet Evernote source (verbatim, accents conservés)

    Returns:
        NoteMetadata avec tous les champs renseignés ("" si absent du source)
    """
    title = raw_note.title if raw_note.title is not None else ""
    created = _normalize_date(raw_note.created)
    updated = _normalize_date(raw_note.updated)
    tags = _normalize_tags(raw_note.tags)
    source_url = raw_note.source_url if raw_note.source_url is not None else ""
    evernote_guid = raw_note.guid if raw_note.guid is not None else ""

    return NoteMetadata(
        title=title,
        created=created,
        updated=updated,
        tags=tags,
        source_url=source_url,
        evernote_notebook=notebook_name,
        evernote_guid=evernote_guid,
    )


def to_yaml_frontmatter(metadata: NoteMetadata) -> str:
    """Génère le bloc frontmatter YAML complet (entre --- et ---).

    Args:
        metadata: NoteMetadata à sérialiser

    Returns:
        Chaîne contenant le frontmatter complet, terminée par \\n.
        Format conforme à SPECS.md Bloc 3 "Frontmatter YAML".
    """
    lines = ["---"]

    lines.append(f'title: "{_escape_yaml_string(metadata.title)}"')

    if metadata.created:
        lines.append(f"created: {metadata.created}")
    else:
        lines.append('created: ""')

    if metadata.updated:
        lines.append(f"updated: {metadata.updated}")
    else:
        lines.append('updated: ""')

    if metadata.tags:
        lines.append("tags:")
        for tag in metadata.tags:
            lines.append(f"  - {tag}")
    else:
        lines.append("tags: []")

    lines.append(f'source_url: "{_escape_yaml_string(metadata.source_url)}"')
    lines.append(f'evernote_notebook: "{_escape_yaml_string(metadata.evernote_notebook)}"')
    lines.append(f'evernote_guid: "{_escape_yaml_string(metadata.evernote_guid)}"')

    lines.append("---")
    return "\n".join(lines) + "\n"


def _normalize_date(date_str: str | None) -> str:
    """Parse une date Evernote (YYYYMMDDTHHMMSSz) en ISO 8601 sans timezone.

    Args:
        date_str: chaîne brute depuis ENEX, ou None

    Returns:
        "YYYY-MM-DDTHH:MM:SS" ou "" si absent/mal formé.
    """
    if not date_str:
        return ""
    try:
        dt = dateutil_parser.parse(date_str)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except (ValueError, OverflowError):
        return ""


def _normalize_tags(tags: list[str]) -> list[str]:
    """Normalise une liste de tags via filename_normalizer.normalize_tag.

    Filtre les tags qui deviennent vides après normalisation.
    Préserve l'ordre d'origine.

    Args:
        tags: liste brute depuis RawNote

    Returns:
        liste de tags normalisés non vides.
    """
    result = []
    for tag in tags:
        normalized = fn_normalize_tag(tag)
        if normalized:
            result.append(normalized)
    return result


def _escape_yaml_string(s: str) -> str:
    """Échappe une chaîne pour inclusion dans un YAML quoted-string.

    Échappements appliqués :
    - Retours ligne et tabulations : remplacés par un espace
      (garantit la validité du YAML inline, conforme à la pratique d'Obsidian)
    - Guillemets doubles : " → \\"
    """
    if s is None:
        return ""
    s = s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = s.replace('"', '\\"')
    return s
