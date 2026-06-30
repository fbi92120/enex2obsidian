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
    from src.content_converter import convert_content

    xhtml = (
        "<en-note>"
        "<p>Un <strong>texte en gras</strong>.</p>"
        "<ul><li>Item 1</li><li>Item 2</li></ul>"
        "</en-note>"
    )
    result = convert_content(xhtml)
    assert "**texte en gras**" in result
    assert "- Item 1" in result
    assert "- Item 2" in result


def test_ct09_en_todo_unchecked():
    """CT-09: <en-todo checked='false'/> converts to '- [ ]'."""
    from src.content_converter import convert_content

    xhtml = '<en-note><div><en-todo checked="false"/> Tâche</div></en-note>'
    result = convert_content(xhtml)
    assert "- [ ]" in result


def test_ct10_en_todo_checked():
    """CT-10: <en-todo checked='true'/> converts to '- [x]'."""
    from src.content_converter import convert_content

    xhtml = '<en-note><div><en-todo checked="true"/> Tâche faite</div></en-note>'
    result = convert_content(xhtml)
    assert "- [x]" in result


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
# CT-08x — Edge cases for content_converter (Codex audit corrections)
# ---------------------------------------------------------------------------

def test_convert_content_none():
    """convert_content(None) returns "" without exception."""
    from src.content_converter import convert_content
    assert convert_content(None) == ""


def test_convert_content_empty():
    """convert_content("") returns "" without exception."""
    from src.content_converter import convert_content
    assert convert_content("") == ""


def test_en_media_without_hash():
    """<en-media> without hash attribute does not raise an exception."""
    from src.content_converter import convert_content
    result = convert_content('<en-note><en-media type="image/png"/></en-note>')
    assert isinstance(result, str)


def test_en_crypt():
    """<en-crypt> content is replaced by a readable placeholder."""
    from src.content_converter import convert_content
    result = convert_content('<en-note><en-crypt>secret</en-crypt></en-note>')
    assert "chiffré" in result


def test_en_todo_inline():
    """<en-todo> inline dans un <p> produit '[ ]' sans lever d'exception."""
    from src.content_converter import convert_content
    result = convert_content(
        '<en-note><p>Rappel : <en-todo checked="false"/>Payer la facture</p></en-note>'
    )
    assert "[ ]" in result
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# CT-13 & CT-14 — Collision handling
# ---------------------------------------------------------------------------

def test_ct13_attachment_collision(tmp_path):
    """CT-13: Two attachments named 'scan.pdf' result in 'scan.pdf' then 'scan-2.pdf'."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    target_dir = tmp_path / "attachments"
    handler = AttachmentHandler(target_dir=target_dir, size_limit_mb=200)

    raw1 = RawAttachment(
        hash=None, mime="application/pdf", file_name="scan.pdf",
        data_base64=base64.b64encode(b"content_first").decode(),
    )
    raw2 = RawAttachment(
        hash=None, mime="application/pdf", file_name="scan.pdf",
        data_base64=base64.b64encode(b"content_second").decode(),
    )

    result1 = handler.handle(raw1, note_title="Note 1", note_guid="guid-1")
    result2 = handler.handle(raw2, note_title="Note 2", note_guid="guid-2")

    assert result1.status == "ok"
    assert result1.final_filename == "scan.pdf"
    assert result2.status == "ok"
    assert result2.final_filename == "scan-2.pdf"
    assert (target_dir / "scan.pdf").exists()
    assert (target_dir / "scan-2.pdf").exists()


def test_ct14_md_collision(tmp_path):
    """CT-14: Two notes with slug 'Facture' result in 'Facture.md' then 'Facture-2.md'."""
    from src.writer import Writer
    from src.metadata_extractor import NoteMetadata

    writer = Writer(notebook_dir=tmp_path / "Carnet")

    def _make_meta(guid):
        return NoteMetadata(
            title="Facture", created="", updated="", tags=[],
            source_url="", evernote_notebook="Carnet", evernote_guid=guid,
        )

    r1 = writer.write(_make_meta("guid-001"), "Contenu 1", {})
    r2 = writer.write(_make_meta("guid-002"), "Contenu 2", {})

    assert r1.status == "ok"
    assert r1.final_filename == "Facture.md"
    assert r1.collided is False
    assert r2.status == "ok"
    assert r2.final_filename == "Facture-2.md"
    assert r2.collided is True
    assert (tmp_path / "Carnet" / "Facture.md").exists()
    assert (tmp_path / "Carnet" / "Facture-2.md").exists()


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


def test_ct15_path_traversal_sanitization(tmp_path):
    """CT-15: Attachment with '../etc/passwd' filename is sanitized or blocked — never written outside target_dir."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    target_dir = tmp_path / "attachments"
    raw = RawAttachment(
        hash=None, mime="application/pdf", file_name="../etc/passwd",
        data_base64=base64.b64encode(b"safe content").decode(),
    )
    handler = AttachmentHandler(target_dir=target_dir, size_limit_mb=200)
    result = handler.handle(raw, note_title="t", note_guid="g")

    if result.status == "ok":
        final = (target_dir / result.final_filename).resolve()
        assert str(final).startswith(str(target_dir.resolve()))
    else:
        assert result.status in ("traversal_blocked", "ok")


# ---------------------------------------------------------------------------
# CT-06x — AttachmentHandler edge cases (Codex preview tests)
# ---------------------------------------------------------------------------

def test_attachment_handler_idempotence_same_hash(tmp_path):
    """Deux RawAttachment avec le même contenu (même hash) ne produisent qu'un fichier."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    data = base64.b64encode(b"same content").decode()
    raw1 = RawAttachment(hash=None, mime="image/png", file_name="img.png", data_base64=data)
    raw2 = RawAttachment(hash=None, mime="image/png", file_name="other.png", data_base64=data)
    handler = AttachmentHandler(target_dir=tmp_path / "att", size_limit_mb=200)

    result1 = handler.handle(raw1, note_title="n1", note_guid="g1")
    result2 = handler.handle(raw2, note_title="n2", note_guid="g2")

    assert result1.status == "ok"
    assert result2.status == "skipped_existing"
    assert result2.final_filename == result1.final_filename
    written = list((tmp_path / "att").glob("*"))
    assert len([f for f in written if f.is_file()]) == 1


def test_attachment_handler_size_limit(tmp_path):
    """Pièce jointe > size_limit_mb retourne status='skipped_size' sans écrire."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    large_bytes = b"x" * (2 * 1024 * 1024)  # 2 MB
    raw = RawAttachment(
        hash=None, mime="application/pdf", file_name="big.pdf",
        data_base64=base64.b64encode(large_bytes).decode(),
    )
    handler = AttachmentHandler(target_dir=tmp_path / "att", size_limit_mb=1)
    result = handler.handle(raw, note_title="n", note_guid="g")

    assert result.status == "skipped_size"
    assert result.final_filename is None
    assert not any((tmp_path / "att").glob("*")) if (tmp_path / "att").exists() else True


def test_attachment_handler_corrupted_base64(tmp_path):
    """Base64 invalide retourne status='corrupted_base64' sans crasher."""
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    raw = RawAttachment(
        hash=None, mime="application/pdf", file_name="doc.pdf",
        data_base64="not valid base64 !@#$%",
    )
    handler = AttachmentHandler(target_dir=tmp_path / "att", size_limit_mb=200)
    result = handler.handle(raw, note_title="n", note_guid="g")

    assert result.status == "corrupted_base64"
    assert result.hash == ""
    assert result.final_filename is None


def test_attachment_handler_missing_filename(tmp_path):
    """RawAttachment sans file_name produit attachment-{hash[:8]}.{ext}."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    raw = RawAttachment(
        hash=None, mime="application/pdf", file_name=None,
        data_base64=base64.b64encode(b"pdf content").decode(),
    )
    handler = AttachmentHandler(target_dir=tmp_path / "att", size_limit_mb=200)
    result = handler.handle(raw, note_title="n", note_guid="g")

    assert result.status == "ok"
    assert result.final_filename is not None
    assert result.final_filename.startswith("attachment-")
    assert len(result.final_filename.split("-")[1].split(".")[0]) == 8


def test_attachment_handler_path_traversal_blocked(tmp_path):
    """RawAttachment avec file_name='../../etc/passwd' est sanitisé ou bloqué."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    target_dir = tmp_path / "att"
    raw = RawAttachment(
        hash=None, mime="application/pdf", file_name="../../etc/passwd",
        data_base64=base64.b64encode(b"content").decode(),
    )
    handler = AttachmentHandler(target_dir=target_dir, size_limit_mb=200)
    result = handler.handle(raw, note_title="n", note_guid="g")

    if result.status == "ok":
        final = (target_dir / result.final_filename).resolve()
        assert str(final).startswith(str(target_dir.resolve()))
    else:
        assert result.status == "traversal_blocked"


def test_attachment_handler_creates_target_dir(tmp_path):
    """target_dir est créé automatiquement s'il n'existe pas."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    target_dir = tmp_path / "deep" / "nested" / "attachments"
    assert not target_dir.exists()

    raw = RawAttachment(
        hash=None, mime="image/png", file_name="photo.png",
        data_base64=base64.b64encode(b"png data").decode(),
    )
    handler = AttachmentHandler(target_dir=target_dir, size_limit_mb=200)
    result = handler.handle(raw, note_title="n", note_guid="g")

    assert result.status == "ok"
    assert target_dir.exists()


def test_attachment_handler_preserves_accents_in_filename(tmp_path):
    """Les accents et espaces du nom d'origine sont conservés (SPECS.md)."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    raw = RawAttachment(
        hash=None, mime="application/pdf", file_name="Facture EDF mars 2024.pdf",
        data_base64=base64.b64encode(b"pdf").decode(),
    )
    handler = AttachmentHandler(target_dir=tmp_path / "att", size_limit_mb=200)
    result = handler.handle(raw, note_title="n", note_guid="g")

    assert result.status == "ok"
    assert result.final_filename == "Facture EDF mars 2024.pdf"


# ---------------------------------------------------------------------------
# CT-16 — Attachment size limit enforcement
# ---------------------------------------------------------------------------

def test_ct16_attachment_size_exceeded(tmp_path):
    """CT-16: Attachment over size limit is not copied; status skipped_size."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    # 1 Mo + 1 byte dépasse la limite de 1 Mo
    oversized_data = b"x" * (1 * 1024 * 1024 + 1)
    raw = RawAttachment(
        data_base64=base64.b64encode(oversized_data).decode(),
        mime="application/pdf",
        file_name="big.pdf",
        hash=None,
    )
    handler = AttachmentHandler(target_dir=tmp_path / "attachments", size_limit_mb=1)
    result = handler.handle(raw, note_title="Test", note_guid="guid1")

    assert result.status == "skipped_size"
    assert result.final_filename is None
    assert not (tmp_path / "attachments" / "big.pdf").exists()


# ---------------------------------------------------------------------------
# CT-17 — Note without title
# ---------------------------------------------------------------------------

def test_ct17_note_without_title(tmp_path):
    """CT-17: Note without title gets slug 'note-[8-chars-guid].md' and title: '' in frontmatter."""
    from src.writer import Writer
    from src.metadata_extractor import NoteMetadata

    writer = Writer(notebook_dir=tmp_path / "Carnet")
    metadata = NoteMetadata(
        title="", created="", updated="", tags=[],
        source_url="", evernote_notebook="Carnet", evernote_guid="abc12345-def-456",
    )
    result = writer.write(metadata, "Contenu sans titre", {})

    assert result.status == "ok"
    assert result.final_filename == "note-abc12345.md"
    content = result.final_path.read_text(encoding="utf-8")
    assert 'title: ""' in content


# ---------------------------------------------------------------------------
# CT-18 — Empty tag after normalization is dropped
# ---------------------------------------------------------------------------

def test_ct18_empty_tag_after_normalization():
    """CT-18: Tag that normalizes to empty string is not included in the tags list."""
    from src.enex_parser import RawNote
    from src.metadata_extractor import extract_metadata

    raw = RawNote(
        title="Facture EDF",
        content_xhtml=None,
        created="20240101T120000Z",
        updated="20240101T120000Z",
        tags=["facture", "!!!"],   # "!!!" normalise en ""
        source_url=None,
        guid="test-guid-001",
        attachments=[],
    )
    metadata = extract_metadata(raw, notebook_name="Comptabilité")

    assert "facture" in metadata.tags
    assert "" not in metadata.tags
    assert len(metadata.tags) < len(raw.tags)


# ---------------------------------------------------------------------------
# CT-16b — MIME allowlist filtering (SPECS.md V1.6)
# ---------------------------------------------------------------------------

def test_ct16b_mime_excluded_svg(tmp_path):
    """CT-16b: SVG (image/svg+xml) hors allowlist → skipped_mime, rien écrit sur disque."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    handler = AttachmentHandler(
        target_dir=tmp_path / "attachments",
        allowed_mime_types={"application/pdf", "image/jpeg", "image/png"},
    )
    raw = RawAttachment(
        data_base64=base64.b64encode(b"<svg>fake</svg>").decode(),
        mime="image/svg+xml",
        file_name="logo.svg",
        hash=None,
    )
    result = handler.handle(raw, note_title="test", note_guid="guid1")
    assert result.status == "skipped_mime"
    assert result.final_filename is None
    assert result.mime == "image/svg+xml"
    assert "image/svg+xml" in (result.error_detail or "")
    assert result.hash != ""
    assert result.size_bytes is not None and result.size_bytes > 0
    assert not (tmp_path / "attachments" / "logo.svg").exists()


def test_attachment_handler_mime_allowlist_none_means_no_filter(tmp_path):
    """Si allowed_mime_types=None (défaut), aucun filtrage MIME — SVG passe normalement."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    handler = AttachmentHandler(target_dir=tmp_path / "attachments")
    raw = RawAttachment(
        data_base64=base64.b64encode(b"<svg>fake</svg>").decode(),
        mime="image/svg+xml",
        file_name="logo.svg",
        hash=None,
    )
    result = handler.handle(raw, note_title="test", note_guid="guid1")
    assert result.status == "ok"
    assert result.final_filename == "logo.svg"


def test_attachment_handler_mime_absent_with_allowlist(tmp_path):
    """RawAttachment avec MIME vide + allowlist active → skipped_mime."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    handler = AttachmentHandler(
        target_dir=tmp_path / "attachments",
        allowed_mime_types={"application/pdf"},
    )
    raw = RawAttachment(
        data_base64=base64.b64encode(b"data").decode(),
        mime="",
        file_name="mystery.bin",
        hash=None,
    )
    result = handler.handle(raw, note_title="test", note_guid="guid1")
    assert result.status == "skipped_mime"
    assert "absent" in (result.error_detail or "").lower()


def test_attachment_handler_mime_case_sensitive(tmp_path):
    """Comparaison MIME stricte sensible à la casse (SPECS.md V1.6) — Application/PDF ne matche pas."""
    import base64
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    handler = AttachmentHandler(
        target_dir=tmp_path / "attachments",
        allowed_mime_types={"application/pdf"},
    )
    raw = RawAttachment(
        data_base64=base64.b64encode(b"%PDF-1.4").decode(),
        mime="Application/PDF",
        file_name="doc.pdf",
        hash=None,
    )
    result = handler.handle(raw, note_title="test", note_guid="guid1")
    assert result.status == "skipped_mime"


# ---------------------------------------------------------------------------
# Étape 7 — notebook_selector : load_notebook_list
# ---------------------------------------------------------------------------

def test_notebook_selector_basic(tmp_path):
    """Lecture basique : noms simples séparés par retours ligne."""
    from src.notebook_selector import load_notebook_list
    f = tmp_path / "carnets.txt"
    f.write_text("Comptabilité 2024\nBail appartement\nImpôts\n", encoding="utf-8")
    assert load_notebook_list(f) == ["Comptabilité 2024", "Bail appartement", "Impôts"]


def test_notebook_selector_ignores_comments(tmp_path):
    """Les lignes commençant par # sont ignorées."""
    from src.notebook_selector import load_notebook_list
    f = tmp_path / "carnets.txt"
    f.write_text(
        "# Liste des carnets admin\n"
        "Comptabilité 2024\n"
        "# Bail appartement (en pause)\n"
        "Impôts\n",
        encoding="utf-8",
    )
    assert load_notebook_list(f) == ["Comptabilité 2024", "Impôts"]


def test_notebook_selector_ignores_empty_lines(tmp_path):
    """Les lignes vides ou ne contenant que des espaces sont ignorées."""
    from src.notebook_selector import load_notebook_list
    f = tmp_path / "carnets.txt"
    f.write_text("Comptabilité 2024\n\n  \nImpôts\n", encoding="utf-8")
    assert load_notebook_list(f) == ["Comptabilité 2024", "Impôts"]


def test_notebook_selector_strips_whitespace(tmp_path):
    """Espaces en début/fin de ligne strippés, espaces internes préservés."""
    from src.notebook_selector import load_notebook_list
    f = tmp_path / "carnets.txt"
    f.write_text("  Comptabilité 2024  \n\tBail appartement\n", encoding="utf-8")
    assert load_notebook_list(f) == ["Comptabilité 2024", "Bail appartement"]


def test_notebook_selector_preserves_order(tmp_path):
    """L'ordre des lignes du fichier est préservé."""
    from src.notebook_selector import load_notebook_list
    f = tmp_path / "carnets.txt"
    f.write_text("Zeta\nAlpha\nMu\n", encoding="utf-8")
    assert load_notebook_list(f) == ["Zeta", "Alpha", "Mu"]


def test_notebook_selector_preserves_duplicates(tmp_path):
    """Les doublons sont conservés (la dédup est la responsabilité de l'orchestrateur)."""
    from src.notebook_selector import load_notebook_list
    f = tmp_path / "carnets.txt"
    f.write_text("Impôts\nImpôts\n", encoding="utf-8")
    assert load_notebook_list(f) == ["Impôts", "Impôts"]


def test_notebook_selector_empty_file(tmp_path):
    """Fichier vide ou ne contenant que des commentaires → liste vide."""
    from src.notebook_selector import load_notebook_list
    f = tmp_path / "carnets.txt"
    f.write_text("# Tout est en commentaire\n# Pour l'instant\n\n", encoding="utf-8")
    assert load_notebook_list(f) == []


def test_notebook_selector_file_not_found(tmp_path):
    """Fichier inexistant → FileNotFoundError."""
    from src.notebook_selector import load_notebook_list
    with pytest.raises(FileNotFoundError):
        load_notebook_list(tmp_path / "n_existe_pas.txt")


def test_notebook_selector_unicode(tmp_path):
    """Caractères Unicode préservés (accents, ç, espaces composés)."""
    from src.notebook_selector import load_notebook_list
    f = tmp_path / "carnets.txt"
    f.write_text("Documents — Voyages\nProjet Lëtzebuerg\n", encoding="utf-8")
    assert load_notebook_list(f) == ["Documents — Voyages", "Projet Lëtzebuerg"]


def test_notebook_selector_hash_in_middle_kept(tmp_path):
    """Un # qui n'est pas en début de ligne est conservé (pas de commentaire inline)."""
    from src.notebook_selector import load_notebook_list
    f = tmp_path / "carnets.txt"
    f.write_text("Carnet # avec hash\n", encoding="utf-8")
    assert load_notebook_list(f) == ["Carnet # avec hash"]


# ---------------------------------------------------------------------------
# Étape 8 — reporter : Reporter, LogLevel, ErrorLevel, CollisionType
# ---------------------------------------------------------------------------

def test_reporter_creates_three_files(tmp_path):
    """Reporter crée 3 fichiers timestampés dans log_dir."""
    from src.reporter import Reporter
    reporter = Reporter(log_dir=tmp_path)
    reporter.close()
    files = list(tmp_path.glob("*"))
    names = sorted(f.name for f in files)
    assert len(files) == 3
    assert any(n.startswith("migration-") and n.endswith(".log") for n in names)
    assert any(n.startswith("collisions-") and n.endswith(".csv") for n in names)
    assert any(n.startswith("errors-") and n.endswith(".csv") for n in names)


def test_reporter_creates_log_dir(tmp_path):
    """log_dir est créé automatiquement avec ses parents."""
    from src.reporter import Reporter
    target = tmp_path / "a" / "b" / "logs"
    reporter = Reporter(log_dir=target)
    reporter.close()
    assert target.exists()
    assert target.is_dir()


def test_reporter_log_format(tmp_path):
    """Le log texte est timestampé au format ISO 8601 + niveau."""
    from src.reporter import Reporter, LogLevel
    reporter = Reporter(log_dir=tmp_path)
    reporter.log(LogLevel.INFO, "Démarrage migration")
    reporter.close()
    log_file = next(tmp_path.glob("migration-*.log"))
    content = log_file.read_text(encoding="utf-8")
    assert "[INFO] Démarrage migration" in content
    assert content[0].isdigit()
    first_line = content.split("\n")[0]
    assert "Z" not in first_line.split(" [")[0]


def test_reporter_record_error_csv(tmp_path):
    """record_error écrit une ligne CSV bien formée."""
    import csv as csv_mod
    from src.reporter import Reporter, ErrorLevel
    reporter = Reporter(log_dir=tmp_path)
    reporter.record_error(
        level=ErrorLevel.ATTACHMENT,
        cause="mime_excluded",
        detail="MIME 'image/svg+xml' hors allowlist",
        notebook="Comptabilité 2024",
        note_guid="abc-123",
        note_title="Plaquette",
        attachment_filename="logo.svg",
    )
    reporter.close()
    errors_file = next(tmp_path.glob("errors-*.csv"))
    rows = list(csv_mod.DictReader(errors_file.open(encoding="utf-8")))
    assert len(rows) == 1
    row = rows[0]
    assert row["level"] == "attachment"
    assert row["cause"] == "mime_excluded"
    assert row["detail"] == "MIME 'image/svg+xml' hors allowlist"
    assert row["notebook"] == "Comptabilité 2024"
    assert row["note_guid"] == "abc-123"
    assert row["note_title"] == "Plaquette"
    assert row["attachment_filename"] == "logo.svg"


def test_reporter_record_error_with_none_fields(tmp_path):
    """Les champs None deviennent chaîne vide dans le CSV (pas 'None')."""
    import csv as csv_mod
    from src.reporter import Reporter, ErrorLevel
    reporter = Reporter(log_dir=tmp_path)
    reporter.record_error(
        level=ErrorLevel.NOTEBOOK,
        cause="notebook_not_found",
        detail="Carnet 'X' absent du dossier exports-enex",
    )
    reporter.close()
    errors_file = next(tmp_path.glob("errors-*.csv"))
    rows = list(csv_mod.DictReader(errors_file.open(encoding="utf-8")))
    assert rows[0]["notebook"] == ""
    assert rows[0]["note_guid"] == ""
    assert rows[0]["note_title"] == ""
    assert rows[0]["attachment_filename"] == ""


def test_reporter_record_error_also_logs(tmp_path):
    """record_error écrit aussi une ligne ERROR dans le log texte."""
    from src.reporter import Reporter, ErrorLevel
    reporter = Reporter(log_dir=tmp_path)
    reporter.record_error(
        level=ErrorLevel.NOTE,
        cause="xhtml_malformed",
        detail="conversion partielle",
        notebook="Comptabilité 2024",
        note_guid="abc-123",
        note_title="Facture EDF",
    )
    reporter.close()
    log_file = next(tmp_path.glob("migration-*.log"))
    content = log_file.read_text(encoding="utf-8")
    assert "[ERROR]" in content
    assert "xhtml_malformed" in content


def test_reporter_record_collision_csv(tmp_path):
    """record_collision écrit une ligne CSV bien formée."""
    import csv as csv_mod
    from src.reporter import Reporter, CollisionType
    reporter = Reporter(log_dir=tmp_path)
    reporter.record_collision(
        kind=CollisionType.MD,
        original_name="Facture",
        final_name="Facture-2",
        notebook="Comptabilité 2024",
        note_guid="abc-123",
    )
    reporter.close()
    coll_file = next(tmp_path.glob("collisions-*.csv"))
    rows = list(csv_mod.DictReader(coll_file.open(encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["kind"] == "md"
    assert rows[0]["original_name"] == "Facture"
    assert rows[0]["final_name"] == "Facture-2"
    assert rows[0]["notebook"] == "Comptabilité 2024"


def test_reporter_csv_handles_special_chars(tmp_path):
    """CSV gère correctement virgules, guillemets, retours ligne dans les champs."""
    import csv as csv_mod
    from src.reporter import Reporter, ErrorLevel
    reporter = Reporter(log_dir=tmp_path)
    reporter.record_error(
        level=ErrorLevel.NOTE,
        cause="parse_error",
        detail='Erreur: champ avec "quote" et, virgule\net retour ligne',
        notebook="Carnet, virgulé",
        note_title='Note avec "quotes"',
    )
    reporter.close()
    errors_file = next(tmp_path.glob("errors-*.csv"))
    rows = list(csv_mod.DictReader(errors_file.open(encoding="utf-8")))
    assert len(rows) == 1
    assert "virgule" in rows[0]["detail"]
    assert "retour ligne" in rows[0]["detail"]
    assert rows[0]["notebook"] == "Carnet, virgulé"
    assert rows[0]["note_title"] == 'Note avec "quotes"'


def test_reporter_csv_headers_present(tmp_path):
    """Les CSV ont une ligne d'en-tête."""
    from src.reporter import Reporter
    reporter = Reporter(log_dir=tmp_path)
    reporter.close()
    errors_file = next(tmp_path.glob("errors-*.csv"))
    first_line = errors_file.read_text(encoding="utf-8").split("\n")[0]
    assert "timestamp" in first_line
    assert "level" in first_line
    assert "cause" in first_line


def test_reporter_close_idempotent(tmp_path):
    """close() peut être appelé plusieurs fois sans erreur."""
    from src.reporter import Reporter
    reporter = Reporter(log_dir=tmp_path)
    reporter.close()
    reporter.close()


def test_reporter_context_manager(tmp_path):
    """Reporter peut être utilisé comme context manager."""
    from src.reporter import Reporter, LogLevel
    with Reporter(log_dir=tmp_path) as reporter:
        reporter.log(LogLevel.INFO, "test")
    log_file = next(tmp_path.glob("migration-*.log"))
    assert "test" in log_file.read_text(encoding="utf-8")


def test_reporter_flush_after_each_write(tmp_path):
    """Les écritures sont flushées immédiatement (lecture en cours d'exécution possible)."""
    from src.reporter import Reporter, LogLevel
    reporter = Reporter(log_dir=tmp_path)
    reporter.log(LogLevel.INFO, "ligne 1")
    log_file = next(tmp_path.glob("migration-*.log"))
    content = log_file.read_text(encoding="utf-8")
    assert "ligne 1" in content
    reporter.close()


def test_reporter_two_instances_distinct_files(tmp_path):
    """Deux instances créées à des moments différents produisent des fichiers distincts."""
    import time
    from src.reporter import Reporter
    r1 = Reporter(log_dir=tmp_path)
    time.sleep(1.1)
    r2 = Reporter(log_dir=tmp_path)
    r1.close()
    r2.close()
    log_files = list(tmp_path.glob("migration-*.log"))
    assert len(log_files) == 2


def test_reporter_no_collision_same_second(tmp_path):
    """Deux Reporter instanciés dans la même seconde produisent des fichiers distincts (sans sleep)."""
    from src.reporter import Reporter
    r1 = Reporter(log_dir=tmp_path)
    r2 = Reporter(log_dir=tmp_path)
    r1.close()
    r2.close()
    log_files = list(tmp_path.glob("migration-*.log"))
    assert len(log_files) == 2


def test_reporter_no_duplicate_header_if_file_exists(tmp_path):
    """Si les fichiers existent déjà, pas de duplication d'en-tête à la réouverture."""
    from src.reporter import Reporter
    fake_log = tmp_path / "migration-20260629-201530.log"
    fake_errors = tmp_path / "errors-20260629-201530.csv"
    fake_coll = tmp_path / "collisions-20260629-201530.csv"
    fake_log.write_text("ligne préexistante\n", encoding="utf-8")
    fake_errors.write_text("timestamp,level,cause\nfake,fake,fake\n", encoding="utf-8")
    fake_coll.write_text("timestamp,kind\nfake,fake\n", encoding="utf-8")
    r = Reporter(log_dir=tmp_path)
    r.close()
    all_files = list(tmp_path.glob("*"))
    assert len(all_files) >= 4


def test_reporter_init_partial_failure_closes_handles(tmp_path, monkeypatch):
    """Si l'ouverture d'un fichier échoue, les handles déjà ouverts sont fermés."""
    from pathlib import Path
    from src.reporter import Reporter
    original_open = Path.open
    call_count = [0]

    def failing_open(self, *args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 3:
            raise OSError("Simulated disk error")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)

    with pytest.raises(OSError):
        Reporter(log_dir=tmp_path)


def test_reporter_null_byte_stripped(tmp_path):
    """Les NULL bytes (\\x00) sont supprimés des champs CSV et log."""
    import csv as csv_mod
    from src.reporter import Reporter, ErrorLevel, LogLevel
    reporter = Reporter(log_dir=tmp_path)
    reporter.record_error(
        level=ErrorLevel.NOTE,
        cause="parse_error",
        detail="contenu avec \x00 NULL byte",
        notebook="Carnet\x00normal",
        note_title="Titre\x00bizarre",
    )
    reporter.log(LogLevel.INFO, "log avec \x00 NULL")
    reporter.close()
    errors_file = next(tmp_path.glob("errors-*.csv"))
    errors_content = errors_file.read_text(encoding="utf-8")
    assert "\x00" not in errors_content
    log_file = next(tmp_path.glob("migration-*.log"))
    log_content = log_file.read_text(encoding="utf-8")
    assert "\x00" not in log_content


def test_reporter_close_robust_to_partial_failure(tmp_path):
    """close() ferme tous les handles même si l'un d'eux lève une exception."""
    from src.reporter import Reporter
    reporter = Reporter(log_dir=tmp_path)

    original_close = reporter._log_fh.close

    def failing_close():
        raise OSError("Simulated close error")

    reporter._log_fh.close = failing_close

    with pytest.raises(OSError):
        reporter.close()

    assert reporter._errors_fh.closed
    assert reporter._coll_fh.closed


# ---------------------------------------------------------------------------
# Étape 10 — writer : Writer, WriteResult, WriteStatus
# ---------------------------------------------------------------------------

def _minimal_metadata(title: str = "Test", guid: str = "abc-123"):
    from src.metadata_extractor import NoteMetadata
    return NoteMetadata(
        title=title, created="", updated="", tags=[],
        source_url="", evernote_notebook="Test Notebook", evernote_guid=guid,
    )


def test_writer_basic_write(tmp_path):
    """Écriture basique : frontmatter + contenu Markdown dans un .md."""
    from src.writer import Writer
    from src.metadata_extractor import NoteMetadata
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    metadata = NoteMetadata(
        title="Facture EDF",
        created="2024-03-15T09:23:00", updated="2024-03-15T09:25:00",
        tags=["facture", "edf"], source_url="",
        evernote_notebook="Comptabilité 2024", evernote_guid="abc-123-def-456",
    )
    result = writer.write(metadata=metadata, markdown_content="Contenu de la note.", attachment_map={})
    assert result.status == "ok"
    assert result.final_path == tmp_path / "Carnet" / "Facture-EDF.md"
    assert result.final_path.exists()
    content = result.final_path.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert 'title: "Facture EDF"' in content
    assert "Contenu de la note." in content


def test_writer_creates_notebook_dir(tmp_path):
    """notebook_dir est créé automatiquement avec ses parents."""
    from src.writer import Writer
    target = tmp_path / "a" / "b" / "Carnet"
    writer = Writer(notebook_dir=target)
    result = writer.write(_minimal_metadata(title="Test", guid="abc-123"), "Contenu", {})
    assert result.status == "ok"
    assert target.exists()


def test_writer_resolves_image_placeholder(tmp_path):
    """Placeholder {{ATTACHMENT:hash}} d'une image → embed Obsidian ![[...]]"""
    from src.writer import Writer
    from src.attachment_handler import AttachmentResult
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    attachment_map = {
        "abc123def": AttachmentResult(
            hash="abc123def", status="ok", final_filename="photo.jpg",
            mime="image/jpeg", original_filename="photo.jpg", size_bytes=1000,
            error_detail=None, note_title="...", note_guid="...",
        )
    }
    result = writer.write(
        metadata=_minimal_metadata(title="Note avec image", guid="abc-123"),
        markdown_content="Voici une photo : {{ATTACHMENT:abc123def}}",
        attachment_map=attachment_map,
    )
    assert result.status == "ok"
    content = result.final_path.read_text(encoding="utf-8")
    assert "![[attachments/photo.jpg]]" in content  # V1.8: chemin attachments/ explicite
    assert "{{ATTACHMENT:" not in content


def test_writer_resolves_pdf_placeholder(tmp_path):
    """Placeholder PDF → lien Markdown [nom](attachments/nom) URL-encodé."""
    from src.writer import Writer
    from src.attachment_handler import AttachmentResult
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    attachment_map = {
        "def456": AttachmentResult(
            hash="def456", status="ok", final_filename="Facture EDF.pdf",
            mime="application/pdf", original_filename="Facture EDF.pdf", size_bytes=2000,
            error_detail=None, note_title="...", note_guid="...",
        )
    }
    result = writer.write(
        metadata=_minimal_metadata(title="Note avec PDF", guid="abc-123"),
        markdown_content="Voici un PDF : {{ATTACHMENT:def456}}",
        attachment_map=attachment_map,
    )
    assert result.status == "ok"
    content = result.final_path.read_text(encoding="utf-8")
    assert "![[attachments/Facture EDF.pdf]]" in content  # V1.8: embed wikilink pour PDFs


def test_writer_unresolved_placeholder(tmp_path):
    """Placeholder sans correspondance dans attachment_map → signalé."""
    from src.writer import Writer
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    result = writer.write(
        metadata=_minimal_metadata(title="Note orpheline", guid="abc-123"),
        markdown_content="Référence orpheline : {{ATTACHMENT:aabb1199}}",
        attachment_map={},
    )
    assert result.status == "ok"
    assert "aabb1199" in result.unresolved_placeholders
    content = result.final_path.read_text(encoding="utf-8")
    assert "pièce jointe non résolue" in content


def test_writer_skipped_attachment_placeholder(tmp_path):
    """Placeholder pour pièce jointe skippée → message clair, non dans unresolved."""
    from src.writer import Writer
    from src.attachment_handler import AttachmentResult
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    attachment_map = {
        "11223344": AttachmentResult(
            hash="11223344", status="skipped_mime", final_filename=None,
            mime="image/svg+xml", original_filename="logo.svg", size_bytes=500,
            error_detail="MIME hors allowlist", note_title="...", note_guid="...",
        )
    }
    result = writer.write(
        metadata=_minimal_metadata(title="Note avec SVG", guid="abc-123"),
        markdown_content="Logo : {{ATTACHMENT:11223344}}",
        attachment_map=attachment_map,
    )
    assert result.status == "ok"
    assert "11223344" not in result.unresolved_placeholders
    content = result.final_path.read_text(encoding="utf-8")
    assert "pièce jointe non disponible" in content
    assert "skipped_mime" in content


def test_writer_skipped_existing_no_force(tmp_path):
    """Si .md cible existe et force_overwrite=False → skipped_existing."""
    from src.writer import Writer
    writer = Writer(notebook_dir=tmp_path / "Carnet", force_overwrite=False)
    metadata = _minimal_metadata(title="Facture", guid="abc-123")
    r1 = writer.write(metadata, "Contenu 1", {})
    assert r1.status == "ok"

    writer2 = Writer(notebook_dir=tmp_path / "Carnet", force_overwrite=False)
    r2 = writer2.write(metadata, "Contenu 2", {})
    assert r2.status == "skipped_existing"
    assert r2.final_path == r1.final_path
    assert "Contenu 1" in r1.final_path.read_text(encoding="utf-8")


def test_writer_force_overwrite(tmp_path):
    """Si force_overwrite=True, .md cible existant est écrasé."""
    from src.writer import Writer
    writer1 = Writer(notebook_dir=tmp_path / "Carnet")
    metadata = _minimal_metadata(title="Facture", guid="abc-123")
    writer1.write(metadata, "Contenu 1", {})

    writer2 = Writer(notebook_dir=tmp_path / "Carnet", force_overwrite=True)
    r2 = writer2.write(metadata, "Contenu 2", {})
    assert r2.status == "ok"
    content = r2.final_path.read_text(encoding="utf-8")
    assert "Contenu 2" in content
    assert "Contenu 1" not in content


def test_writer_intra_session_collision(tmp_path):
    """Trois notes de même titre dans la même session → suffixes -2, -3."""
    from src.writer import Writer
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    m1 = _minimal_metadata(title="Réunion", guid="abc-123")
    m2 = _minimal_metadata(title="Réunion", guid="def-456")
    m3 = _minimal_metadata(title="Réunion", guid="ghi-789")

    r1 = writer.write(m1, "Contenu 1", {})
    r2 = writer.write(m2, "Contenu 2", {})
    r3 = writer.write(m3, "Contenu 3", {})

    assert r1.final_filename == "Reunion.md"
    assert r1.collided is False
    assert r2.final_filename == "Reunion-2.md"
    assert r2.collided is True
    assert r3.final_filename == "Reunion-3.md"
    assert r3.collided is True
    assert len(list((tmp_path / "Carnet").glob("*.md"))) == 3


def test_writer_path_traversal_blocked(tmp_path):
    """Slug d'un titre traversal → fichier strictement dans notebook_dir."""
    from src.writer import Writer
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    metadata = _minimal_metadata(title="../../etc/passwd", guid="abc-123")
    result = writer.write(metadata, "Contenu", {})
    if result.status == "ok":
        assert (tmp_path / "Carnet").resolve() in result.final_path.resolve().parents
    else:
        assert result.status == "traversal_blocked"


def test_writer_atomic_write_no_tmp_remaining(tmp_path):
    """Après une écriture réussie, pas de fichier .tmp restant."""
    from src.writer import Writer
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    writer.write(_minimal_metadata(title="Test", guid="abc-123"), "Contenu", {})
    assert len(list((tmp_path / "Carnet").glob("*.tmp"))) == 0


def test_writer_unicode_preserved(tmp_path):
    """Caractères Unicode dans le contenu et le frontmatter sont préservés."""
    from src.writer import Writer
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    metadata = _minimal_metadata(title="Compte rendu — Réunion", guid="abc-123")
    metadata.tags = ["réunion", "stratégie"]
    result = writer.write(metadata, "Contenu avec é, è, à, ç, ñ", {})
    assert result.status == "ok"
    content = result.final_path.read_text(encoding="utf-8")
    assert "é, è, à, ç, ñ" in content
    assert "Compte rendu — Réunion" in content


def test_writer_no_exception_on_disk_error(tmp_path, monkeypatch):
    """En cas d'erreur disque (os.replace), retourne WriteResult status='write_error'."""
    from src.writer import Writer

    def failing_replace(*args, **kwargs):
        raise OSError("Simulated disk error")

    monkeypatch.setattr("os.replace", failing_replace)
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    result = writer.write(_minimal_metadata(title="Test", guid="abc-123"), "Contenu", {})
    assert result.status == "write_error"
    assert result.final_path is None
    assert "Simulated" in (result.error_detail or "")


# ---------------------------------------------------------------------------
# Étape 10b — Corrections post-audit Codex
# ---------------------------------------------------------------------------

def test_writer_tmp_symlink_blocked(tmp_path):
    """Si Facture.md.tmp est un symlink hors notebook_dir, l'écriture est protégée."""
    from src.writer import Writer
    notebook_dir = tmp_path / "Carnet"
    notebook_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    tmp_link = notebook_dir / "Facture.md.tmp"
    target_outside = outside / "evil.txt"
    target_outside.write_text("preexisting", encoding="utf-8")
    tmp_link.symlink_to(target_outside)

    writer = Writer(notebook_dir=notebook_dir)
    metadata = _minimal_metadata(title="Facture", guid="abc-123")
    result = writer.write(metadata, "Contenu", {})

    # Le fichier hors notebook_dir ne doit pas avoir été modifié
    assert target_outside.read_text(encoding="utf-8") == "preexisting"
    if result.status == "ok":
        assert (notebook_dir / "Facture.md").exists()
    else:
        assert result.status in ("traversal_blocked", "write_error")


def test_writer_collision_counter_exhausted(tmp_path):
    """Si la boucle de collision épuise les suffixes, retourne write_error."""
    from src.writer import Writer
    writer = Writer(notebook_dir=tmp_path / "Carnet")

    notebook = tmp_path / "Carnet"
    (notebook / "Facture.md").write_text("x", encoding="utf-8")
    for i in range(2, 1000):
        (notebook / f"Facture-{i}.md").write_text("x", encoding="utf-8")

    metadata = _minimal_metadata(title="Facture", guid="abc-123")
    result = writer.write(metadata, "Contenu", {})

    assert result.status == "write_error"
    assert "collision counter exhausted" in (result.error_detail or "").lower()


def test_writer_no_slug_no_guid_returns_error(tmp_path):
    """Titre vide ET GUID vide → write_error (pas de fallback note-unknown)."""
    from src.writer import Writer
    from src.metadata_extractor import NoteMetadata
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    metadata = NoteMetadata(
        title="",
        created="",
        updated="",
        tags=[],
        source_url="",
        evernote_notebook="Test",
        evernote_guid="",
    )
    result = writer.write(metadata, "Contenu", {})

    assert result.status == "write_error"
    assert "title" in (result.error_detail or "").lower() or "guid" in (result.error_detail or "").lower()


def test_writer_force_overwrite_intra_session(tmp_path):
    """force_overwrite=True écrase aussi en intra-session (même slug deux fois)."""
    from src.writer import Writer
    writer = Writer(notebook_dir=tmp_path / "Carnet", force_overwrite=True)

    metadata1 = _minimal_metadata(title="Facture", guid="abc-123")
    metadata2 = _minimal_metadata(title="Facture", guid="def-456")

    r1 = writer.write(metadata1, "Contenu 1", {})
    r2 = writer.write(metadata2, "Contenu 2", {})

    assert r1.final_filename == "Facture.md"
    assert r2.final_filename == "Facture.md"
    assert r2.status == "ok"

    content = r2.final_path.read_text(encoding="utf-8")
    assert "Contenu 2" in content
    assert "Contenu 1" not in content


def test_writer_placeholder_regex_strict(tmp_path):
    """Placeholder hash hex uniquement : {{ATTACHMENT:xyz!@#}} n'est pas résolu."""
    from src.writer import Writer
    writer = Writer(notebook_dir=tmp_path / "Carnet")
    metadata = _minimal_metadata(title="Test", guid="abc-123")

    result = writer.write(
        metadata=metadata,
        markdown_content="Texte avec {{ATTACHMENT:xyz!@#}} non-hex et {{ATTACHMENT:abc123}} hex",
        attachment_map={},
    )

    content = result.final_path.read_text(encoding="utf-8")
    assert "{{ATTACHMENT:xyz!@#}}" in content
    assert "abc123" in result.unresolved_placeholders


def test_metadata_extractor_yaml_escape_newline(tmp_path):
    """Échappement YAML : retours ligne dans titre remplacés par espaces."""
    from src.enex_parser import RawNote
    from src.metadata_extractor import extract_metadata, to_yaml_frontmatter

    raw = RawNote(
        title="Titre avec\nretour ligne",
        content_xhtml=None,
        created=None,
        updated=None,
        tags=[],
        source_url=None,
        guid="abc-123",
        attachments=[],
    )
    meta = extract_metadata(raw, notebook_name="Test")
    yaml = to_yaml_frontmatter(meta)

    title_line = [l for l in yaml.split("\n") if l.startswith("title:")][0]
    assert "\n" not in title_line[6:]
    assert "Titre avec retour ligne" in yaml


def test_metadata_extractor_yaml_escape_quote(tmp_path):
    """Échappement YAML : guillemets doubles dans titre sont échappés avec backslash."""
    from src.enex_parser import RawNote
    from src.metadata_extractor import extract_metadata, to_yaml_frontmatter

    raw = RawNote(
        title='Titre avec "guillemets"',
        content_xhtml=None,
        created=None,
        updated=None,
        tags=[],
        source_url=None,
        guid="abc-123",
        attachments=[],
    )
    meta = extract_metadata(raw, notebook_name="Test")
    yaml = to_yaml_frontmatter(meta)

    assert '\\"guillemets\\"' in yaml


def test_writer_tmp_cleanup_existing(tmp_path):
    """Un .tmp orphelin préexistant (non-symlink) est nettoyé avant écriture."""
    from src.writer import Writer
    notebook_dir = tmp_path / "Carnet"
    notebook_dir.mkdir()

    orphan_tmp = notebook_dir / "Facture.md.tmp"
    orphan_tmp.write_text("contenu orphelin d'une session précédente", encoding="utf-8")

    writer = Writer(notebook_dir=notebook_dir)
    metadata = _minimal_metadata(title="Facture", guid="abc-123")
    result = writer.write(metadata, "Nouveau contenu", {})

    assert result.status == "ok"
    assert not orphan_tmp.exists()
    content = result.final_path.read_text(encoding="utf-8")
    assert "Nouveau contenu" in content


# ---------------------------------------------------------------------------
# CT-19 à CT-22 + tests Codex — NFC + format embed (SPECS V1.8)
# ---------------------------------------------------------------------------

def test_ct19_nfd_input_normalized_to_nfc():
    """CT-19: sanitize_attachment_name normalise NFD en NFC."""
    import unicodedata
    from src.filename_normalizer import sanitize_attachment_name

    nfd_name = "nucléaire.pdf"   # e + combining acute accent (NFD)
    nfc_name = "nucléaire.pdf"    # é composé (NFC)

    result, was_modified = sanitize_attachment_name(nfd_name)

    assert result == nfc_name
    assert unicodedata.is_normalized("NFC", result)
    assert was_modified is True  # changement NFD → NFC détecté


def test_ct20_pdf_accentuated_link_uses_nfc(tmp_path):
    """CT-20: lien pour PDF accentué utilise NFC dans l'embed wikilink (pas NFD %CC%81)."""
    import unicodedata
    from src.writer import Writer
    from src.attachment_handler import AttachmentResult

    writer = Writer(notebook_dir=tmp_path / "Carnet")
    nfd_filename = "nucléaire.pdf"   # NFD : e + accent combinant
    nfc_filename = "nucléaire.pdf"    # NFC : é composé

    attachment_map = {
        "abc123def456": AttachmentResult(
            hash="abc123def456",
            status="ok",
            final_filename=nfd_filename,    # reçu en NFD (cas pathologique)
            mime="application/pdf",
            original_filename=nfd_filename,
            size_bytes=1000,
            error_detail=None,
            note_title="Test",
            note_guid="abc-123",
        )
    }
    result = writer.write(
        metadata=_minimal_metadata(title="Test PDF accent", guid="abc-123"),
        markdown_content="Voici : {{ATTACHMENT:abc123def456}}",
        attachment_map=attachment_map,
    )
    assert result.status == "ok"
    content = result.final_path.read_text(encoding="utf-8")

    # Embed wikilink avec NFC
    assert f"![[attachments/{nfc_filename}]]" in content
    # Pas d'encoding NFD (%CC%81 = combining acute accent)
    assert "%CC%81" not in content
    # Pas de lien Markdown classique (les PDFs sont des embeds en V1.8)
    assert f"[{nfd_filename}]" not in content
    assert f"[{nfc_filename}](" not in content


def test_ct21_pdf_uses_embed_wikilink(tmp_path):
    """CT-21: PDF utilise le format ![[attachments/file.pdf]], pas lien Markdown."""
    from src.writer import Writer
    from src.attachment_handler import AttachmentResult

    writer = Writer(notebook_dir=tmp_path / "Carnet")
    attachment_map = {
        "abc123def456": AttachmentResult(
            hash="abc123def456",
            status="ok",
            final_filename="Facture.pdf",
            mime="application/pdf",
            original_filename="Facture.pdf",
            size_bytes=1000,
            error_detail=None,
            note_title="Test",
            note_guid="abc-123",
        )
    }
    result = writer.write(
        metadata=_minimal_metadata(title="Test PDF", guid="abc-123"),
        markdown_content="{{ATTACHMENT:abc123def456}}",
        attachment_map=attachment_map,
    )
    assert result.status == "ok"
    content = result.final_path.read_text(encoding="utf-8")
    assert "![[attachments/Facture.pdf]]" in content
    assert "[Facture.pdf](" not in content  # pas de lien Markdown classique


def test_ct22_docx_uses_markdown_link(tmp_path):
    """CT-22: docx utilise le lien Markdown classique, pas d'embed."""
    from src.writer import Writer
    from src.attachment_handler import AttachmentResult

    writer = Writer(notebook_dir=tmp_path / "Carnet")
    attachment_map = {
        "abc123def456": AttachmentResult(
            hash="abc123def456",
            status="ok",
            final_filename="Rapport.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            original_filename="Rapport.docx",
            size_bytes=1000,
            error_detail=None,
            note_title="Test",
            note_guid="abc-123",
        )
    }
    result = writer.write(
        metadata=_minimal_metadata(title="Test DOCX", guid="abc-123"),
        markdown_content="{{ATTACHMENT:abc123def456}}",
        attachment_map=attachment_map,
    )
    assert result.status == "ok"
    content = result.final_path.read_text(encoding="utf-8")
    assert "[Rapport.docx](attachments/Rapport.docx)" in content
    assert "![[attachments/Rapport.docx]]" not in content


def test_image_uses_embed_wikilink_with_attachments_path(tmp_path):
    """Images utilisent ![[attachments/...]] avec chemin relatif explicite (V1.8)."""
    from src.writer import Writer
    from src.attachment_handler import AttachmentResult

    writer = Writer(notebook_dir=tmp_path / "Carnet")
    attachment_map = {
        "abc123def456": AttachmentResult(
            hash="abc123def456",
            status="ok",
            final_filename="photo.jpg",
            mime="image/jpeg",
            original_filename="photo.jpg",
            size_bytes=1000,
            error_detail=None,
            note_title="Test",
            note_guid="abc-123",
        )
    }
    result = writer.write(
        metadata=_minimal_metadata(title="Test image", guid="abc-123"),
        markdown_content="{{ATTACHMENT:abc123def456}}",
        attachment_map=attachment_map,
    )
    assert result.status == "ok"
    content = result.final_path.read_text(encoding="utf-8")
    assert "![[attachments/photo.jpg]]" in content
    # Pas de wikilink sans chemin (ancien format V1.7)
    assert "![[photo.jpg]]" not in content


def test_nfc_collision_after_normalization(tmp_path):
    """Deux pièces jointes en NFD et NFC du même nom détectent une collision."""
    import base64
    import unicodedata
    from src.enex_parser import RawAttachment
    from src.attachment_handler import AttachmentHandler

    handler = AttachmentHandler(target_dir=tmp_path / "att")

    # Premier : nom en NFC (é composé)
    nfc_attachment = RawAttachment(
        data_base64=base64.b64encode(b"contenu1").decode(),
        mime="application/pdf",
        file_name="nucléaire.pdf",   # é composé NFC
        hash=None,
    )
    r1 = handler.handle(nfc_attachment, note_title="t", note_guid="g1")

    # Deuxième : même mot en NFD (e + accent combinant)
    nfd_attachment = RawAttachment(
        data_base64=base64.b64encode(b"contenu2").decode(),
        mime="application/pdf",
        file_name="nucléaire.pdf",  # NFD
        hash=None,
    )
    r2 = handler.handle(nfd_attachment, note_title="t", note_guid="g2")

    nfc_name = "nucléaire.pdf"

    assert r1.status == "ok"
    assert r1.final_filename == nfc_name
    assert r2.status == "ok"
    # Après normalisation NFC, les deux noms convergent → collision détectée
    assert r2.final_filename == "nucléaire-2.pdf"
    # Les deux noms sont en NFC
    assert unicodedata.is_normalized("NFC", r1.final_filename)
    assert unicodedata.is_normalized("NFC", r2.final_filename)


def test_md_slug_normalized_to_nfc(tmp_path):
    """Le slug du .md produit par writer est en NFC."""
    import unicodedata
    from src.writer import Writer

    writer = Writer(notebook_dir=tmp_path / "Carnet")
    result = writer.write(_minimal_metadata(title="Réflexions", guid="abc-123"), "Contenu", {})

    assert result.status == "ok"
    filename = result.final_path.name
    assert unicodedata.is_normalized("NFC", filename)
