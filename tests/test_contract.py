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

CT01_ENEX_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
<en-export export-date="20240329T120000Z" application="Evernote" version="10.0">
<note>
<title>Facture EDF mars 2024</title>
<content><![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
<en-note><div>Facture reçue le 15 mars.</div></en-note>]]></content>
<created>20240315T092300Z</created>
<updated>20240315T092500Z</updated>
<tag>factures</tag>
<tag>EDF</tag>
<note-attributes><source-url></source-url></note-attributes>
</note>
<note>
<title>Réunion bilan Q1</title>
<content><![CDATA[<en-note><div>Notes de réunion.</div></en-note>]]></content>
<created>20240401T140000Z</created>
<updated>20240401T141500Z</updated>
<tag>réunions</tag>
</note>
<note>
<title>Note avec PJ</title>
<guid>abc-123-def-456</guid>
<content><![CDATA[<en-note><div>Voir document attaché.</div></en-note>]]></content>
<created>20240315T092300Z</created>
<updated>20240315T092500Z</updated>
<tag>test</tag>
<note-attributes>
  <source-url>https://example.com/doc</source-url>
</note-attributes>
<resource>
  <data encoding="base64">SGVsbG8gV29ybGQ=</data>
  <mime>application/pdf</mime>
  <resource-attributes>
    <file-name>document.pdf</file-name>
  </resource-attributes>
</resource>
</note>
</en-export>
"""


def test_ct01_parse_reference_enex(tmp_path):
    """CT-01: iter_notes() yields 3 RawNote with correct fields from an inline ENEX fixture.

    Vérifie : title, created, updated, tags, content_xhtml, guid, source_url,
    attachments (mime, file_name, data_base64, hash).
    """
    from src.enex_parser import iter_notes, RawNote
    from collections.abc import Iterator

    enex_file = tmp_path / "test.enex"
    enex_file.write_text(CT01_ENEX_XML, encoding="utf-8")

    result = iter_notes(enex_file)
    assert isinstance(result, Iterator)

    notes = list(result)
    assert len(notes) == 3

    # Note 1 — champs de base + source-url vide
    n1 = notes[0]
    assert isinstance(n1, RawNote)
    assert n1.title == "Facture EDF mars 2024"
    assert n1.created == "20240315T092300Z"
    assert n1.updated == "20240315T092500Z"
    assert n1.tags == ["factures", "EDF"]
    assert n1.content_xhtml is not None
    assert "Facture reçue le 15 mars." in n1.content_xhtml
    assert n1.source_url == ""        # balise présente mais vide → "" (correction 5)
    assert n1.parse_errors == []

    # Note 2 — sans note-attributes (source_url absent)
    n2 = notes[1]
    assert n2.title == "Réunion bilan Q1"
    assert n2.created == "20240401T140000Z"
    assert n2.updated == "20240401T141500Z"
    assert n2.tags == ["réunions"]
    assert n2.source_url is None      # balise absente → None (correction 5)
    assert n2.parse_errors == []

    # Note 3 — guid, source_url avec valeur, attachments
    n3 = notes[2]
    assert n3.title == "Note avec PJ"
    assert n3.guid == "abc-123-def-456"
    assert n3.source_url == "https://example.com/doc"
    assert len(n3.attachments) == 1
    att = n3.attachments[0]
    assert att.mime == "application/pdf"
    assert att.file_name == "document.pdf"
    assert att.data_base64 == "SGVsbG8gV29ybGQ="
    assert att.hash is None           # hash toujours None ici (correction 1)
    assert n3.parse_errors == []


def test_ct01a_attachment_hash_is_none(tmp_path):
    """CT-01a: RawAttachment.hash est toujours None après parsing — jamais fabriqué."""
    from src.enex_parser import iter_notes

    enex_file = tmp_path / "test.enex"
    enex_file.write_text(CT01_ENEX_XML, encoding="utf-8")

    notes = list(iter_notes(enex_file))
    n3 = notes[2]
    assert n3.attachments[0].hash is None


def test_ct01b_xxe_entity_ignored(tmp_path):
    """CT-01b: Entité XML externe dans le DOCTYPE ignorée — pas de lecture /etc/passwd."""
    from src.enex_parser import iter_notes

    xxe_xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<en-export>
<note>
<title>Test XXE</title>
<content><![CDATA[<en-note><div>contenu</div></en-note>]]></content>
<created>20240101T000000Z</created>
</note>
</en-export>
"""
    enex_file = tmp_path / "xxe.enex"
    enex_file.write_text(xxe_xml, encoding="utf-8")

    # Le parser ne doit pas crasher et doit retourner la note normalement
    notes = list(iter_notes(enex_file))
    assert len(notes) == 1
    assert notes[0].title == "Test XXE"


def test_ct01c_source_url_empty_vs_absent(tmp_path):
    """CT-01c: <source-url></source-url> → '' ; balise absente → None."""
    from src.enex_parser import iter_notes

    xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<en-export>
<note>
<title>Avec source-url vide</title>
<content><![CDATA[<en-note/>]]></content>
<created>20240101T000000Z</created>
<note-attributes><source-url></source-url></note-attributes>
</note>
<note>
<title>Sans source-url</title>
<content><![CDATA[<en-note/>]]></content>
<created>20240101T000000Z</created>
</note>
</en-export>
"""
    enex_file = tmp_path / "test.enex"
    enex_file.write_text(xml, encoding="utf-8")

    notes = list(iter_notes(enex_file))
    assert notes[0].source_url == ""    # présente mais vide
    assert notes[1].source_url is None  # absente


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
    from src.enex_parser import RawNote
    from src.metadata_extractor import extract_metadata, to_yaml_frontmatter

    raw = RawNote(
        title="Facture EDF mars 2024",
        content_xhtml="<en-note><div>Contenu</div></en-note>",
        created="20240315T092300Z",
        updated="20240315T092500Z",
        tags=["Facture EDF", "énergie"],
        source_url="https://example.com",
        guid="a1b2c3d4-1234-5678-abcd-ef0123456789",
    )

    meta = extract_metadata(raw, notebook_name="Comptabilité 2024")

    assert meta.title == "Facture EDF mars 2024"
    assert meta.created == "2024-03-15T09:23:00"
    assert meta.updated == "2024-03-15T09:25:00"
    assert meta.tags == ["facture-edf", "energie"]
    assert meta.source_url == "https://example.com"
    assert meta.evernote_notebook == "Comptabilité 2024"
    assert meta.evernote_guid == "a1b2c3d4-1234-5678-abcd-ef0123456789"

    yaml_block = to_yaml_frontmatter(meta)
    assert yaml_block.startswith("---\n")
    assert yaml_block.strip().endswith("---")
    assert 'title: "Facture EDF mars 2024"' in yaml_block
    assert "created: 2024-03-15T09:23:00" in yaml_block
    assert "updated: 2024-03-15T09:25:00" in yaml_block
    assert "  - facture-edf" in yaml_block
    assert "  - energie" in yaml_block
    assert 'source_url: "https://example.com"' in yaml_block
    assert 'evernote_notebook: "Comptabilité 2024"' in yaml_block
    assert 'evernote_guid: "a1b2c3d4-1234-5678-abcd-ef0123456789"' in yaml_block


def test_ct07_frontmatter_missing_updated():
    """CT-07: Frontmatter for note without 'updated' has updated: '' (empty string, field present)."""
    from src.enex_parser import RawNote
    from src.metadata_extractor import extract_metadata, to_yaml_frontmatter

    raw = RawNote(
        title="Note sans updated",
        content_xhtml="<en-note><div>Contenu</div></en-note>",
        created="20240316T100000Z",
        updated=None,
        tags=[],
        source_url=None,
        guid=None,
    )

    meta = extract_metadata(raw, notebook_name="Inbox")

    assert meta.updated == ""
    assert meta.tags == []
    assert meta.source_url == ""
    assert meta.evernote_guid == ""

    yaml_block = to_yaml_frontmatter(meta)
    assert 'updated: ""' in yaml_block
    assert "tags: []" in yaml_block
    assert 'source_url: ""' in yaml_block
    assert 'evernote_guid: ""' in yaml_block


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
    """CT-11: en-media with image/png produces {{ATTACHMENT:hash}} placeholder."""
    from src.content_converter import convert_content

    xhtml = '<en-note><en-media hash="abc123" type="image/png"/></en-note>'
    result = convert_content(xhtml)
    assert "{{ATTACHMENT:abc123}}" in result


def test_ct12_pdf_link():
    """CT-12: en-media with application/pdf produces {{ATTACHMENT:hash}} placeholder."""
    from src.content_converter import convert_content

    xhtml = '<en-note><en-media hash="def456" type="application/pdf"/></en-note>'
    result = convert_content(xhtml)
    assert "{{ATTACHMENT:def456}}" in result


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


def test_ct15c_sanitize_control_chars():
    """CT-15c: sanitize_attachment_name strips ASCII control chars (0x00-0x1F) and DEL (0x7F)."""
    from src.filename_normalizer import sanitize_attachment_name
    name, modified = sanitize_attachment_name('file\x00name\x07.pdf')
    assert modified is True
    assert '\x00' not in name
    assert '\x07' not in name
    assert name == 'filename.pdf'


def test_ct15d_sanitize_dotdot_segment_wise():
    """CT-15d: segment-wise '..' check — internal '..' in a basename is preserved."""
    from src.filename_normalizer import sanitize_attachment_name
    # Legitimate filename: '..' is internal, not a segment — must be preserved
    name, modified = sanitize_attachment_name('report..backup.pdf')
    assert modified is False
    assert name == 'report..backup.pdf'
    # Path traversal: '..' is a complete segment — must be blocked
    name2, modified2 = sanitize_attachment_name('../etc/passwd')
    assert modified2 is True
    assert '..' not in name2
    # Multi-level traversal
    name3, modified3 = sanitize_attachment_name('subfolder/../file.pdf')
    assert modified3 is True
    assert '..' not in name3


def test_ct15e_sanitize_empty_result():
    """CT-15e: sanitize_attachment_name returns '' (not None) when everything is stripped."""
    from src.filename_normalizer import sanitize_attachment_name
    name, modified = sanitize_attachment_name('..')
    assert name == ''
    assert modified is True


def test_ct17a_slug_for_note_no_title_no_guid():
    """CT-17a: slug_for_note raises ValueError when both title and guid are missing."""
    from src.filename_normalizer import slug_for_note
    with pytest.raises(ValueError, match="Cannot generate slug"):
        slug_for_note(None, None)


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
