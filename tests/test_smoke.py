"""
test_smoke — Integration smoke test running the full pipeline on a real .enex file.

Requires the ENEX_REFERENCE_FILE environment variable pointing to an existing .enex file.
Skipped automatically if the variable is not set or the file does not exist.

Run with:
    export ENEX_REFERENCE_FILE=~/Migration-Evernote/exports-enex/Bail-test.enex
    pytest tests/test_smoke.py
"""

import os
import pytest


def test_smoke():
    """
    Full pipeline smoke test on the ENEX_REFERENCE_FILE carnet.

    Setup: creates a temporary vault directory and log directory.
    Execution: runs enex2obsidian on the reference .enex file.

    Verifies:
        - At least 1 .md file produced in [tmp_vault]/[notebook_slug]/
        - attachments/ subdirectory present if the carnet has attachments
        - Log file and CSV files present and non-empty in log directory
        - No files written outside the temporary vault directory
        - .md count + CSV error rows at "note" level == total note count in .enex

    Does NOT validate content correctness — that is covered by CT tests and human review.

    Skips if ENEX_REFERENCE_FILE is not defined or the pointed file does not exist.
    """
    enex_path = os.environ.get("ENEX_REFERENCE_FILE")
    if not enex_path or not os.path.exists(os.path.expanduser(enex_path)):
        pytest.skip("ENEX_REFERENCE_FILE non défini ou fichier introuvable")

    pytest.skip("Étape 12 de la séquence")
