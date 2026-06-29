"""
writer — Write Markdown notes and create vault directory structure.

Handles .md file creation, collision resolution (suffix -2, -3, ...),
and Obsidian vault structure (notebook directories and attachments/ subdirectories).
Enforces skip-on-exist (default) and overwrite-on-force semantics per constitution rule 8.
All writes are verified against vault_path before execution (anti-traversal).
"""

import os


def ensure_notebook_structure(vault_path: str, notebook_slug: str) -> tuple:
    """
    Create the notebook directory and its attachments/ subdirectory in the vault.

    Idempotent: safe to call if directories already exist.

    Args:
        vault_path (str): absolute path to the Obsidian vault root
        notebook_slug (str): ASCII slug for the notebook (used as directory name)

    Returns:
        tuple: (notebook_dir: str, attachments_dir: str)
            Both are absolute paths guaranteed to exist after this call.

    Raises:
        OSError: if directories cannot be created (permissions, disk full, etc.)
    """
    raise NotImplementedError("Étape 10 de la séquence")


def resolve_md_path(notebook_dir: str, note_slug: str, existing_slugs: set) -> tuple:
    """
    Determine the final .md filepath, resolving name collisions with -N suffixes.

    If note_slug already exists in existing_slugs:
        try note_slug-2, note_slug-3, ... until unique.

    Args:
        notebook_dir (str): absolute path to the notebook directory
        note_slug (str): base slug for the note (without .md extension)
        existing_slugs (set[str]): slugs already used in this notebook this run

    Returns:
        tuple: (final_path: str, final_slug: str, is_collision: bool)
            final_path: absolute .md file path
            final_slug: slug actually used (may have -N suffix)
            is_collision: True if a -N suffix was added
    """
    raise NotImplementedError("Étape 10 de la séquence")


def write_note(md_path: str, frontmatter: str, content: str, force: bool = False) -> tuple:
    """
    Write a Markdown note to disk.

    Checks for existing file before writing:
        - exists and not force → skip, return ("skipped", None)
        - exists and force → overwrite
        - does not exist → write new file

    Args:
        md_path (str): absolute path to the target .md file
        frontmatter (str): YAML frontmatter block (with --- delimiters)
        content (str): Markdown body content
        force (bool): if True, overwrite existing files

    Returns:
        tuple: (status: str, error: str|None)
            status: "written", "skipped", or "error"
            error: None on success/skip, or error description string on failure
    """
    raise NotImplementedError("Étape 10 de la séquence")
