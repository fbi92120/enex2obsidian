"""
test_smoke — Integration smoke test for the full enex2obsidian pipeline.

Runs once on tests/fixtures/testmigration.enex (7 notes, committed fixture,
no personal data). Verifies 10 critical invariants on the produced vault,
including regressions introduced in V1.8 (NFC normalization, PDF embed format).

Scope: structural verification only — content correctness is human-reviewed.

Run with:
    pytest tests/test_smoke.py -v
"""

import csv
import re
import shutil
import unicodedata
from pathlib import Path

import pytest
import yaml
from lxml import etree

from enex2obsidian import run_migration, DEFAULT_ALLOWED_MIME_TYPES
from src.reporter import Reporter


_FIXTURE_ENEX = Path(__file__).parent / "fixtures" / "testmigration.enex"
_NOTEBOOK_NAME = "testmigration"

# Required frontmatter keys per SPECS.md Bloc 3
_REQUIRED_FRONTMATTER_KEYS = {
    "title", "created", "updated", "tags",
    "source_url", "evernote_notebook", "evernote_guid",
}

# Regex patterns shared across PDF embed and wikilink tests
_PDF_CLASSIC_LINK = re.compile(
    r"\[[^\]]*\.pdf\]\(attachments/[^)]+\.pdf\)", re.IGNORECASE
)
_PDF_WIKILINK = re.compile(r"!\[\[attachments/[^\]]+\.pdf\]\]", re.IGNORECASE)
_WIKILINK_TARGET = re.compile(r"!\[\[attachments/([^\]]+)\]\]")


# ---------------------------------------------------------------------------
# Shared fixture — pipeline runs once per test module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def migrated_vault(tmp_path_factory):
    """
    Builds an isolated environment and runs the full pipeline once on
    tests/fixtures/testmigration.enex.

    Returns a dict:
      vault:         Path  — root of the produced Obsidian vault
      log_dir:       Path  — directory containing migration logs and CSV files
      notebook_dir:  Path  — notebook subdirectory inside vault
      source_count:  int   — number of <note> elements in the source ENEX
      exit_code:     int   — 0 if pipeline completed without uncaught exception
      errors_csv:    Path  — path to the errors-*.csv produced by Reporter
    """
    vault = tmp_path_factory.mktemp("smoke-vault")
    log_dir = tmp_path_factory.mktemp("smoke-logs")
    source_dir = tmp_path_factory.mktemp("smoke-source")

    # Isolate the fixture so the pipeline never touches tests/fixtures/ directly
    shutil.copy2(_FIXTURE_ENEX, source_dir / _FIXTURE_ENEX.name)

    # Count notes before the run — used for conservation invariant
    tree = etree.parse(
        str(_FIXTURE_ENEX),
        parser=etree.XMLParser(recover=True, huge_tree=True),
    )
    source_count = len(tree.getroot().findall("note"))

    paths = {
        "source_directory": source_dir,
        "vault_path": vault,
        "log_directory": log_dir,
        "notebook_list": None,
        "attachment_size_limit_mb": 200,
        "allowed_mime_types": DEFAULT_ALLOWED_MIME_TYPES,
        "force_overwrite": False,
        "dry_run": False,
        "single_notebook": _NOTEBOOK_NAME,
    }

    exit_code = 0
    try:
        with Reporter(log_dir=log_dir) as reporter:
            run_migration(paths, reporter=reporter, dry_run=False)
    except Exception:
        exit_code = 1

    errors_csvs = list(log_dir.glob("errors-*.csv"))
    assert len(errors_csvs) == 1, (
        f"Expected exactly 1 errors-*.csv in log_dir, "
        f"found {len(errors_csvs)}: {[p.name for p in errors_csvs]}"
    )

    # The notebook directory is the single subdirectory created under vault
    notebook_dirs = [d for d in vault.iterdir() if d.is_dir()]
    assert len(notebook_dirs) == 1, (
        f"Expected exactly 1 notebook subdir under vault, "
        f"found {len(notebook_dirs)}: {[d.name for d in notebook_dirs]}"
    )

    return {
        "vault": vault,
        "log_dir": log_dir,
        "notebook_dir": notebook_dirs[0],
        "source_count": source_count,
        "exit_code": exit_code,
        "errors_csv": errors_csvs[0],
    }


# ---------------------------------------------------------------------------
# Invariant 1 — Pipeline exit code
# ---------------------------------------------------------------------------

def test_smoke_pipeline_exit_code_zero(migrated_vault):
    """Pipeline must complete without an uncaught exception (exit code 0)."""
    assert migrated_vault["exit_code"] == 0, (
        "run_migration raised an uncaught exception — check log_dir for details"
    )


# ---------------------------------------------------------------------------
# Invariant 2 — At least one .md produced
# ---------------------------------------------------------------------------

def test_smoke_at_least_one_md_produced(migrated_vault):
    """At least one .md file must exist anywhere under vault/."""
    vault = migrated_vault["vault"]
    md_files = list(vault.rglob("*.md"))
    assert len(md_files) >= 1, (
        f"No .md files found under vault ({vault}) — pipeline produced no output"
    )


# ---------------------------------------------------------------------------
# Invariant 3 — attachments/ directory present
# ---------------------------------------------------------------------------

def test_smoke_attachments_folder_exists(migrated_vault):
    """The attachments/ subdirectory must exist inside the notebook directory."""
    notebook_dir = migrated_vault["notebook_dir"]
    attachments_dir = notebook_dir / "attachments"
    assert attachments_dir.is_dir(), (
        f"No attachments/ directory under notebook dir {notebook_dir} — "
        "the fixture contains attachments so this directory must be created"
    )


# ---------------------------------------------------------------------------
# Invariant 4 — No zero-byte attachments  (regression: bug 11b)
# ---------------------------------------------------------------------------

def test_smoke_no_zero_byte_attachments(migrated_vault):
    """Every file under attachments/ must be non-empty (regression: bug 11b)."""
    notebook_dir = migrated_vault["notebook_dir"]
    attachments_dir = notebook_dir / "attachments"
    if not attachments_dir.is_dir():
        pytest.skip("attachments/ not present — covered by test_smoke_attachments_folder_exists")

    zero_byte = [
        f.name for f in attachments_dir.iterdir()
        if f.is_file() and f.stat().st_size == 0
    ]
    assert not zero_byte, (
        f"Found {len(zero_byte)} zero-byte file(s) in attachments/: {zero_byte}"
    )


# ---------------------------------------------------------------------------
# Invariant 5 — All filenames in vault are NFC  (regression: V1.8)
# ---------------------------------------------------------------------------

def test_smoke_all_filenames_nfc(migrated_vault):
    """Every filename (file and directory) under vault/ must be in NFC Unicode form.

    Regression guard for the NFD/NFC mismatch bug found in step 11 (Obsidian
    broken links for accented PDF filenames).
    """
    vault = migrated_vault["vault"]
    nfd_names = [
        str(entry.relative_to(vault))
        for entry in vault.rglob("*")
        if not unicodedata.is_normalized("NFC", entry.name)
    ]
    assert not nfd_names, (
        f"Found {len(nfd_names)} filename(s) NOT in NFC form (NFD detected): {nfd_names}"
    )


# ---------------------------------------------------------------------------
# Invariant 6 — PDFs rendered as embed wikilinks  (regression: V1.8)
# ---------------------------------------------------------------------------

def test_smoke_pdf_uses_wikilink_embed(migrated_vault):
    """PDFs must use ![[attachments/…pdf]] embed wikilinks, never [text](attachments/…pdf).

    Two-part assertion (V1.8 regression guard):
    1. No .md contains a classic Markdown PDF link — even a single one means a regression.
    2. At least one .md contains a PDF embed wikilink (fixture has PDF attachments).
    """
    vault = migrated_vault["vault"]
    classic_offenders = []
    wikilink_count = 0

    for md_file in vault.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        for m in _PDF_CLASSIC_LINK.finditer(content):
            classic_offenders.append((md_file.name, m.group(0)))
        if _PDF_WIKILINK.search(content):
            wikilink_count += 1

    assert not classic_offenders, (
        f"PDFs rendered as Markdown links instead of wikilink embeds "
        f"(V1.8 regression): {classic_offenders}"
    )
    assert wikilink_count > 0, (
        f"No PDF wikilink embed found across {len(list(vault.rglob('*.md')))} .md files "
        f"— fixture expected to contain at least one PDF (check _EMBED_MIMES in writer.py)"
    )


# ---------------------------------------------------------------------------
# Invariant 7 — Images rendered as embed wikilinks
# ---------------------------------------------------------------------------

def test_smoke_image_uses_wikilink_embed(migrated_vault):
    """At least one .md must contain an image embed wikilink ![[attachments/…(png|jpg|…)]]."""
    vault = migrated_vault["vault"]
    img_embed_re = re.compile(
        r'!\[\[attachments/[^\]]+\.(png|jpg|jpeg|heic|heif|tiff|gif|webp)\]\]',
        re.IGNORECASE,
    )
    matching = [
        md.name for md in vault.rglob("*.md")
        if img_embed_re.search(md.read_text(encoding="utf-8"))
    ]
    assert matching, (
        "No .md file contains an image embed wikilink ![[attachments/…png/jpg/…]]. "
        "The fixture has image attachments — check _EMBED_MIMES in writer.py."
    )


# ---------------------------------------------------------------------------
# Invariant 8 — No files written outside vault  (constitution rule 9)
# ---------------------------------------------------------------------------

def test_smoke_no_file_outside_vault(migrated_vault):
    """No .md files must appear in log_dir or source_dir (constitution rule 9: no traversal)."""
    log_dir = migrated_vault["log_dir"]
    # The fixture is in source_dir; we check that no .md was created there
    # Recover source_dir from the only .enex copy present
    enex_copies = list(log_dir.parent.rglob("testmigration.enex"))
    # source_dir is the parent of the copied .enex
    source_dirs = {p.parent for p in enex_copies}

    md_in_log = list(log_dir.rglob("*.md"))
    assert not md_in_log, (
        f"Found .md file(s) in log_dir: {[p.name for p in md_in_log]}"
    )

    for src_dir in source_dirs:
        md_in_source = list(src_dir.rglob("*.md"))
        assert not md_in_source, (
            f"Found .md file(s) in source_dir ({src_dir}): "
            f"{[p.name for p in md_in_source]}"
        )


# ---------------------------------------------------------------------------
# Invariant 9 — All frontmatter is valid YAML with required keys
# ---------------------------------------------------------------------------

def test_smoke_all_frontmatter_yaml_parsable(migrated_vault):
    """Every .md must have parsable YAML frontmatter containing all required keys."""
    vault = migrated_vault["vault"]
    md_files = list(vault.rglob("*.md"))
    assert md_files, f"No .md files found under vault {vault}"

    for md_path in md_files:
        content = md_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        if not lines or lines[0].strip() != "---":
            first = repr(lines[0]) if lines else "'empty file'"
            pytest.fail(
                f"{md_path.name}: does not start with '---' (first line: {first})"
            )

        try:
            closing_idx = lines.index("---", 1)
        except ValueError:
            pytest.fail(f"{md_path.name}: no closing '---' found for frontmatter block")

        fm_text = "\n".join(lines[1:closing_idx])
        try:
            fm = yaml.safe_load(fm_text)
        except yaml.YAMLError as exc:
            pytest.fail(f"{md_path.name}: YAML parse error in frontmatter: {exc}")

        assert isinstance(fm, dict), (
            f"{md_path.name}: frontmatter parsed as {type(fm).__name__}, expected dict"
        )
        missing = _REQUIRED_FRONTMATTER_KEYS - set(fm.keys())
        assert not missing, (
            f"{md_path.name}: missing required frontmatter keys: {missing}"
        )


# ---------------------------------------------------------------------------
# Invariant 10 — Conservation: no silent loss  (constitution rule 2)
# ---------------------------------------------------------------------------

def test_smoke_conservation_count(migrated_vault):
    """
    count(.md produced) + count(note-level rows in errors CSV) == source_count.

    Constitution rule 2: every note must produce either a .md or an explicit
    error row. No silent loss allowed.
    """
    vault = migrated_vault["vault"]
    errors_csv = migrated_vault["errors_csv"]
    source_count = migrated_vault["source_count"]

    md_count = len(list(vault.rglob("*.md")))

    with errors_csv.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        note_error_count = sum(1 for row in reader if row["level"] == "note")

    total = md_count + note_error_count
    assert total == source_count, (
        f"Conservation invariant failed: "
        f"{md_count} .md files + {note_error_count} note-level CSV errors = {total}, "
        f"expected source_count={source_count}. "
        f"Silent loss detected: {source_count - total} note(s) unaccounted for."
    )


# ---------------------------------------------------------------------------
# Invariant 11 — Wikilink targets are NFC and point to existing files (V1.8)
# ---------------------------------------------------------------------------

def test_smoke_wikilinks_nfc_and_resolvable(migrated_vault):
    """Every ![[attachments/CIBLE]] in .md files must be NFC and resolve to a real file.

    Covers the V1.8 bug from the 'internal links' angle: a wikilink written in
    NFD form breaks Obsidian's link resolution even when the file on disk is NFC,
    and even when test_smoke_all_filenames_nfc passes.
    """
    vault = migrated_vault["vault"]
    attachments_dir = migrated_vault["notebook_dir"] / "attachments"

    nfd_links = []
    broken_links = []

    for md_file in vault.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        for target in _WIKILINK_TARGET.findall(content):
            if not unicodedata.is_normalized("NFC", target):
                nfd_links.append((md_file.name, target))
            if not (attachments_dir / target).exists():
                broken_links.append((md_file.name, target))

    assert not nfd_links, (
        f"Wikilink targets NOT in NFC form (V1.8 regression — Obsidian resolves in NFC): "
        f"{nfd_links}"
    )
    assert not broken_links, (
        f"Wikilinks point to non-existent files in attachments/: {broken_links}"
    )


# ---------------------------------------------------------------------------
# Invariant 12 — Log files present and non-empty (SPECS Bloc 5)
# ---------------------------------------------------------------------------

def test_smoke_logs_present_and_non_empty(migrated_vault):
    """SPECS Bloc 5 — the 3 reporter files must exist, be unique, and be non-empty.

    Filenames per reporter.py: migration-*.log, errors-*.csv, collisions-*.csv.
    The log must be non-empty. The CSV files must contain at least their header line.
    """
    log_dir = migrated_vault["log_dir"]

    migration_logs = list(log_dir.glob("migration-*.log"))
    errors_csvs = list(log_dir.glob("errors-*.csv"))
    collisions_csvs = list(log_dir.glob("collisions-*.csv"))

    assert len(migration_logs) == 1, (
        f"Expected exactly 1 migration-*.log, got {len(migration_logs)}: "
        f"{[p.name for p in migration_logs]}"
    )
    assert len(errors_csvs) == 1, (
        f"Expected exactly 1 errors-*.csv, got {len(errors_csvs)}: "
        f"{[p.name for p in errors_csvs]}"
    )
    assert len(collisions_csvs) == 1, (
        f"Expected exactly 1 collisions-*.csv, got {len(collisions_csvs)}: "
        f"{[p.name for p in collisions_csvs]}"
    )

    assert migration_logs[0].stat().st_size > 0, (
        f"Migration log is empty: {migration_logs[0].name}"
    )

    for csv_path in errors_csvs + collisions_csvs:
        text = csv_path.read_text(encoding="utf-8")
        first_line = text.split("\n", 1)[0] if text else ""
        assert first_line.strip(), (
            f"CSV file has no header line: {csv_path.name}"
        )
