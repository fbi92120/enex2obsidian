"""
test_limits — Limit-behavior tests for enex2obsidian (LI-01 to LI-10).

Verifies that edge cases and failure modes defined in SPECS.md Bloc 4 are handled
correctly: missing files, malformed XML, oversized attachments, --force flag,
--dry-run mode, and startup validation failures.

All tests use inline fixtures — no external .enex file required.
All tests are skipped until the corresponding module is implemented.
"""

import pytest


# ---------------------------------------------------------------------------
# LI-01 — Missing .enex for listed notebook
# ---------------------------------------------------------------------------

def test_li01_enex_missing():
    """LI-01: Missing .enex for a listed notebook logs error at notebook level; next notebook processed."""
    pytest.skip("Étape 11 de la séquence")


# ---------------------------------------------------------------------------
# LI-02 — Globally malformed ENEX XML
# ---------------------------------------------------------------------------

def test_li02_enex_xml_invalid_global():
    """LI-02: .enex with globally invalid XML logs error at notebook level; next notebook processed."""
    pytest.skip("Étape 3 de la séquence")


# ---------------------------------------------------------------------------
# LI-03 — Note with malformed XHTML content
# ---------------------------------------------------------------------------

def test_li03_note_xhtml_malformed():
    """LI-03: Note with malformed XHTML logs error at note level; next note in carnet is processed."""
    pytest.skip("Étape 5 de la séquence")


# ---------------------------------------------------------------------------
# LI-04 — Attachment exceeding size limit
# ---------------------------------------------------------------------------

def test_li04_attachment_size_exceeded():
    """LI-04: Oversized attachment not copied; error logged; note .md produced with size notice."""
    pytest.skip("Étape 6 de la séquence")


# ---------------------------------------------------------------------------
# LI-05 — Corrupted base64 attachment data
# ---------------------------------------------------------------------------

def test_li05_attachment_base64_corrupt():
    """LI-05: Corrupted base64 attachment logs error; note .md produced with corruption notice."""
    pytest.skip("Étape 6 de la séquence")


# ---------------------------------------------------------------------------
# LI-06 — .md target exists, no --force
# ---------------------------------------------------------------------------

def test_li06_md_exists_no_force():
    """LI-06: Existing .md target without --force results in skip + log; next note processed."""
    pytest.skip("Étape 10 de la séquence")


# ---------------------------------------------------------------------------
# LI-07 — .md target exists, --force active
# ---------------------------------------------------------------------------

def test_li07_md_exists_with_force():
    """LI-07: Existing .md target with --force is overwritten; action logged at info level."""
    pytest.skip("Étape 10 de la séquence")


# ---------------------------------------------------------------------------
# LI-08 — --dry-run produces no disk writes
# ---------------------------------------------------------------------------

def test_li08_dry_run_no_writes():
    """LI-08: --dry-run produces no disk writes; migration plan displayed on stdout."""
    pytest.skip("Étape 11 de la séquence")


# ---------------------------------------------------------------------------
# LI-09 — --carnet with unknown notebook name
# ---------------------------------------------------------------------------

def test_li09_carnet_unknown():
    """LI-09: --carnet 'X' where X has no matching .enex exits with terminal error; no migration started."""
    pytest.skip("Étape 11 de la séquence")


# ---------------------------------------------------------------------------
# LI-10 — vault_path in read-only mode
# ---------------------------------------------------------------------------

def test_li10_vault_readonly():
    """LI-10: Read-only vault_path causes terminal error at startup; no migration is started."""
    pytest.skip("Étape 11 de la séquence")
