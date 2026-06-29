"""
notebook_selector — Parse carnets-a-migrer.txt and locate matching .enex files.

Reads the notebook list file, ignores comment lines (starting with #) and blank lines,
deduplicates notebook names (with warning via reporter), and finds the corresponding
.enex file in source_directory using Unicode-NFC-normalized matching.
"""

import os
from typing import Optional


def load_notebook_list(filepath: str) -> list:
    """
    Read carnets-a-migrer.txt and return the list of notebook names.

    Ignores lines starting with '#' (comments) and blank lines.
    Deduplicates names — caller is responsible for logging warnings on duplicates.

    Args:
        filepath (str): absolute path to carnets-a-migrer.txt

    Returns:
        list[str]: notebook names verbatim (accents and spaces preserved),
                   in file order, deduplicated.

    Raises:
        OSError: if filepath does not exist or is not readable.
    """
    raise NotImplementedError("Étape 7 de la séquence")


def find_enex_file(notebook_name: str, source_dir: str) -> Optional[str]:
    """
    Find the .enex file in source_dir that matches notebook_name.

    Matching strategy (in order):
        1. Exact match: "{notebook_name}.enex"
        2. NFC-normalized match: compare NFC forms of both name and filename

    Args:
        notebook_name (str): notebook name from carnets-a-migrer.txt
        source_dir (str): directory containing .enex files

    Returns:
        str: absolute path to the matching .enex file, or None if not found.
    """
    raise NotImplementedError("Étape 7 de la séquence")
