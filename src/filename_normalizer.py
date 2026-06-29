"""
filename_normalizer — ASCII slug generation, tag normalization, filename sanitization,
and path traversal prevention.

Implémentation stdlib uniquement (unicodedata + re + os.path) : le contrôle fin
des règles de casse (slug conserve les majuscules, tag force les minuscules) et
la lisibilité des transformations justifient de ne pas déléguer à python-slugify.

Fonctions publiques :
  to_ascii_slug()            — slug pour dossiers et noms de fichiers .md
  normalize_tag()            — normalisation tag Obsidian
  sanitize_attachment_name() — nettoyage nom pièce jointe (accents et espaces conservés)
  is_path_under_base()       — vérification anti path-traversal avant écriture
  slug_for_note()            — slug d'une note avec fallback sur guid
"""

import os
import re
import unicodedata


def to_ascii_slug(text: str) -> str:
    """
    Convert a text string to an ASCII slug for use as folder or .md filename.

    Rules (per SPECS.md Bloc 3):
      - Diacritical marks removed via NFD decomposition + Mn-category filter
      - Spaces and FS-forbidden chars (< > : " / \\ | ? *) replaced by hyphens
      - Non-ASCII and non-alphanumeric chars (except hyphens) removed
      - Consecutive hyphens collapsed to one
      - Leading/trailing hyphens stripped
      - Case preserved (majuscules restent majuscules)

    Args:
        text (str): raw input (may contain accents, spaces, punctuation)

    Returns:
        str: ASCII slug, or "" if input produces no slug characters.
    """
    decomposed = unicodedata.normalize('NFD', text)
    ascii_only = ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')
    slug = re.sub(r'[<>:"/\\|?*\s]', '-', ascii_only)
    slug = re.sub(r'[^a-zA-Z0-9-]', '', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def normalize_tag(tag: str) -> str:
    """
    Normalize an Evernote tag for Obsidian frontmatter.

    Rules (per SPECS.md Bloc 3):
      - Strip surrounding whitespace
      - Diacritical marks removed via NFD decomposition + Mn-category filter
      - Spaces replaced by hyphens
      - Forced lowercase
      - Non-[a-z0-9-] characters removed
      - Consecutive hyphens collapsed, leading/trailing stripped

    Args:
        tag (str): raw Evernote tag

    Returns:
        str: normalized tag, or "" if the tag becomes empty after normalization.
    """
    tag = tag.strip()
    decomposed = unicodedata.normalize('NFD', tag)
    ascii_only = ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')
    slug = re.sub(r'\s+', '-', ascii_only)
    slug = slug.lower()
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def sanitize_attachment_name(name: str) -> tuple:
    """
    Remove dangerous characters from an attachment filename.

    Accents and spaces are preserved (attachment names are kept verbatim per SPECS.md).
    Only path-traversal sequences and FS-forbidden chars are removed.

    Rules:
      - '..' sequences removed (path traversal)
      - '/' and '\\' replaced by '-' (path separators turned readable separator)
      - FS-forbidden chars removed: < > : " | ? *
      - Consecutive hyphens collapsed, leading/trailing stripped

    Args:
        name (str): raw attachment filename (basename only)

    Returns:
        tuple: (sanitized_name: str, was_modified: bool)
            was_modified is True if any character was removed or replaced.
    """
    original = name
    cleaned = name.replace('..', '')
    cleaned = cleaned.replace('/', '-').replace('\\', '-')
    cleaned = re.sub(r'[<>:"|?*]', '', cleaned)
    cleaned = re.sub(r'-+', '-', cleaned).strip('-')
    return cleaned, cleaned != original


def is_path_under_base(base_path: str, target_path: str) -> bool:
    """
    Check that target_path resolves strictly under base_path.

    Uses os.path.realpath to resolve symlinks before comparison, making this
    safe on macOS where /var → /private/var and similar symlinked locations exist.

    Args:
        base_path (str): allowed root directory (e.g. vault_path)
        target_path (str): candidate write path

    Returns:
        bool: True if target_path is strictly under base_path.
            False if equal to base_path or outside it.
    """
    real_base = os.path.realpath(os.path.abspath(base_path))
    real_target = os.path.realpath(os.path.abspath(target_path))
    if real_target == real_base:
        return False
    return real_target.startswith(real_base + os.sep)


def slug_for_note(title, guid) -> str:
    """
    Produce a slug for a note filename, with GUID-based fallback for empty titles.

    Args:
        title (str|None): note title from Evernote (may be None or empty)
        guid (str|None): Evernote note GUID

    Returns:
        str: slug for use as .md basename (without extension).
            Falls back to "note-[first 8 chars of guid]" if title yields no slug.
    """
    if title:
        slug = to_ascii_slug(title)
        if slug:
            return slug
    if guid:
        return f"note-{guid[:8]}"
    return "note-unknown"
