"""
filename_normalizer — ASCII slug generation, filename sanitization, and path traversal prevention.

Central module for all filename and path normalization. Used by writer.py,
attachment_handler.py, and metadata_extractor.py (for tags).
No side effects: all functions are pure transformations.
"""

import os


def to_slug(text: str) -> str:
    """
    Convert a text string to an ASCII slug for use as filename or directory name.

    Rules: accents removed (NFD → ASCII), spaces → hyphens,
    characters not in [a-zA-Z0-9-] removed, consecutive hyphens collapsed,
    leading/trailing hyphens stripped.

    Examples:
        "Comptabilité 2024" → "Comptabilite-2024"
        "Réunion: bilan Q1/2024" → "Reunion-bilan-Q1-2024"

    Args:
        text (str): input text (may contain accents, spaces, punctuation)

    Returns:
        str: ASCII slug. Empty string if input is empty or produces no slug chars.
    """
    raise NotImplementedError("Étape 2 de la séquence")


def sanitize_filename(name: str) -> tuple:
    """
    Remove characters forbidden on macOS/Linux/Windows filesystems.

    Removes: < > : " / \\ | ? * and path traversal sequences (.. / \\).
    Collapses resulting multiple spaces/hyphens.

    Args:
        name (str): raw filename (basename only, not a path)

    Returns:
        tuple: (sanitized_name: str, was_modified: bool)
            sanitized_name: cleaned filename
            was_modified: True if any characters were removed or replaced
    """
    raise NotImplementedError("Étape 2 de la séquence")


def is_safe_path(base_path: str, target_path: str) -> bool:
    """
    Check that target_path resolves to a location strictly under base_path.

    Uses os.path.realpath to resolve symlinks and ".." components before
    comparing. Prevents path traversal attacks from malicious filenames.

    Args:
        base_path (str): the allowed root directory (e.g. vault_path)
        target_path (str): the candidate path to write to

    Returns:
        bool: True if target_path is strictly under base_path, False otherwise.
            Returns False if target_path == base_path (must be strictly under).
    """
    raise NotImplementedError("Étape 2 de la séquence")


def slug_for_note(title: str, guid: str) -> str:
    """
    Produce a slug for a note filename, with fallback for empty titles.

    If title produces a non-empty slug: use it.
    If title is absent or produces an empty slug:
        use "note-" + first 8 characters of guid.

    Args:
        title (str|None): note title from Evernote
        guid (str|None): Evernote note GUID

    Returns:
        str: slug suitable for use as .md basename (without extension).
    """
    raise NotImplementedError("Étape 2 de la séquence")
