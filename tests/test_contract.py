"""
test_contract — Contract tests for enex2obsidian modules (CT-01 to CT-18).

Validates that each module respects its spec contract as defined in SPECS.md Bloc 5.
Uses inline XML fixtures only — no external .enex file required.
All tests are skipped until the corresponding module is implemented.
"""

import pytest


# ---------------------------------------------------------------------------
# Inline fixture: minimal 3-note ENEX XML for CT-01
# ---------------------------------------------------------------------------

REFERENCE_ENEX_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
<en-export>
  <note>
    <title>Note complète</title>
    <content><![CDATA[<?xml version="1.0"?><en-note><div>Contenu 1</div></en-note>]]></content>
    <created>20240315T092300Z</created>
    <updated>20240315T092500Z</updated>
    <tag>facture</tag>
    <tag>edf</tag>
    <note-attributes><source-url>https://example.com</source-url></note-attributes>
    <resource>
      <data encoding="base64">AAAA</data>
      <mime>application/pdf</mime>
      <resource-attributes><file-name>doc.pdf</file-name></resource-attributes>
    </resource>
  </note>
  <note>
    <title>Note sans tags</title>
    <content><![CDATA[<?xml version="1.0"?><en-note><div>Contenu 2</div></en-note>]]></content>
    <created>20240316T100000Z</created>
  </note>
  <note>
    <title>Note avec image</title>
    <content><![CDATA[<?xml version="1.0"?><en-note><div>Image:</div><en-media hash="abc123" type="image/png"/></en-note>]]></content>
    <resource>
      <data encoding="base64">iVBORw</data>
      <mime>image/png</mime>
      <resource-attributes><file-name>photo.png</file-name></resource-attributes>
    </resource>
  </note>
</en-export>
"""


# ---------------------------------------------------------------------------
# CT-01 — Parsing: 3 notes extracted with complete metadata
# ---------------------------------------------------------------------------

def test_ct01_parse_reference_enex():
    """CT-01: Parsing REFERENCE_ENEX_XML produces 3 notes with complete metadata fields."""
    pytest.skip("Étape 3 de la séquence")


# ---------------------------------------------------------------------------
# CT-02 & CT-03 — Slug generation
# ---------------------------------------------------------------------------

def test_ct02_slug_comptabilite():
    """CT-02: to_ascii_slug('Comptabilité 2024') returns 'Comptabilite-2024'."""
    from src.filename_normalizer import to_ascii_slug
    assert to_ascii_slug('Comptabilité 2024') == 'Comptabilite-2024'


def test_ct03_slug_reunion():
    """CT-03: to_ascii_slug('Réunion: bilan Q1/2024') returns 'Reunion-bilan-Q1-2024'."""
    from src.filename_normalizer import to_ascii_slug
    assert to_ascii_slug('Réunion: bilan Q1/2024') == 'Reunion-bilan-Q1-2024'


# ---------------------------------------------------------------------------
# CT-04 & CT-05 — Tag normalization
# ---------------------------------------------------------------------------

def test_ct04_tag_facture_edf():
    """CT-04: normalize_tag('Facture EDF') returns 'facture-edf'."""
    from src.filename_normalizer import normalize_tag
    assert normalize_tag('Facture EDF') == 'facture-edf'


def test_ct05_tag_eleve_evaluation():
    """CT-05: normalize_tag('Élève évaluation') returns 'eleve-evaluation'."""
    from src.filename_normalizer import normalize_tag
    assert normalize_tag('Élève évaluation') == 'eleve-evaluation'


# ---------------------------------------------------------------------------
# CT-06 & CT-07 — Frontmatter construction
# ---------------------------------------------------------------------------

def test_ct06_frontmatter_complete():
    """CT-06: Frontmatter for a complete note has all required fields with ISO 8601 dates."""
    pytest.skip("Étape 4 de la séquence")


def test_ct07_frontmatter_missing_updated():
    """CT-07: Frontmatter for note without 'updated' has updated: '' (empty string, field present)."""
    pytest.skip("Étape 4 de la séquence")


# ---------------------------------------------------------------------------
# CT-08 to CT-10 — XHTML → Markdown conversion
# ---------------------------------------------------------------------------

def test_ct08_xhtml_basic_conversion():
    """CT-08: <p>, <ul>, <li>, <strong> tags are correctly converted to Markdown equivalents."""
    pytest.skip("Étape 5 de la séquence")


def test_ct09_en_todo_unchecked():
    """CT-09: <en-todo checked='false'/> converts to '- [ ]'."""
    pytest.skip("Étape 5 de la séquence")


def test_ct10_en_todo_checked():
    """CT-10: <en-todo checked='true'/> converts to '- [x]'."""
    pytest.skip("Étape 5 de la séquence")


# ---------------------------------------------------------------------------
# CT-11 & CT-12 — Attachment substitution in Markdown
# ---------------------------------------------------------------------------

def test_ct11_image_embed():
    """CT-11: en-media with image/png produces Obsidian embed ![[image.png]]."""
    pytest.skip("Étape 5 de la séquence")


def test_ct12_pdf_link():
    """CT-12: en-media with application/pdf produces [document.pdf](attachments/document.pdf)."""
    pytest.skip("Étape 5 de la séquence")


# ---------------------------------------------------------------------------
# CT-13 & CT-14 — Collision handling
# ---------------------------------------------------------------------------

def test_ct13_attachment_collision():
    """CT-13: Two attachments named 'scan.pdf' result in 'scan.pdf' then 'scan-2.pdf'."""
    pytest.skip("Étape 6 de la séquence")


def test_ct14_md_collision():
    """CT-14: Two notes with slug 'Facture' result in 'Facture.md' then 'Facture-2.md'."""
    pytest.skip("Étape 10 de la séquence")


# ---------------------------------------------------------------------------
# CT-15a — sanitize_attachment_name (filename_normalizer unit)
# CT-15b — is_path_under_base (filename_normalizer unit)
# CT-15  — full path-traversal end-to-end (skipped: depends on attachment_handler)
# ---------------------------------------------------------------------------

def test_ct15a_sanitize_attachment_path_traversal():
    """CT-15a: sanitize_attachment_name removes '..' and path separators; signals modification."""
    from src.filename_normalizer import sanitize_attachment_name
    name, modified = sanitize_attachment_name('../etc/passwd')
    assert modified is True
    assert '..' not in name
    assert '/' not in name
    assert '\\' not in name


def test_ct15b_is_path_under_base():
    """CT-15b: is_path_under_base rejects equal and outer paths; accepts strict children."""
    import os
    import tempfile
    from src.filename_normalizer import is_path_under_base
    with tempfile.TemporaryDirectory() as base:
        assert is_path_under_base(base, base) is False
        child = os.path.join(base, 'notebook', 'note.md')
        assert is_path_under_base(base, child) is True
        parent = os.path.dirname(base)
        assert is_path_under_base(base, parent) is False


def test_ct15_path_traversal_sanitization():
    """CT-15: Attachment named '../etc/passwd' is sanitized to a safe name; logged with 'sanitized'."""
    pytest.skip("Dépend de attachment_handler — étape 6 de la séquence")


# ---------------------------------------------------------------------------
# CT-16 — Attachment size limit enforcement
# ---------------------------------------------------------------------------

def test_ct16_attachment_size_exceeded():
    """CT-16: Attachment over size limit is not copied; error logged; .md contains notice."""
    pytest.skip("Étape 6 de la séquence")


# ---------------------------------------------------------------------------
# CT-17 — Note without title
# ---------------------------------------------------------------------------

def test_ct17_note_without_title():
    """CT-17: Note without title gets slug 'note-[8-chars-guid].md' and title: '' in frontmatter."""
    pytest.skip("Étape 2 de la séquence")


# ---------------------------------------------------------------------------
# CT-18 — Empty tag after normalization is dropped
# ---------------------------------------------------------------------------

def test_ct18_empty_tag_after_normalization():
    """CT-18: Tag that normalizes to empty string is not included in the tags list."""
    pytest.skip("Étape 4 de la séquence")
