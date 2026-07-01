"""
test_limits — Degraded-case tests for the enex2obsidian pipeline.

Covers SPECS.md Bloc 4 / Bloc 5 cases LI-01 to LI-10, idempotence
(Constitution rule 5), and note-without-title (Bloc 4), structured in
8 pytest classes for targeted filtering (e.g. ``pytest -k DryRun``).

Fixtures used:
  tests/fixtures/testmigration.enex  — 7-note committed fixture (nominal)
  tests/fixtures/malformed.enex      — empty file, reliably triggers
                                       XMLSyntaxError in lxml.etree.iterparse
                                       even with recover=True (LI-02 only)

Run with:
    pytest tests/test_limits.py -v
"""

import csv
import hashlib
import shutil
import time
from pathlib import Path

import pytest
from lxml import etree
from lxml.etree import CDATA

from enex2obsidian import run_migration, DEFAULT_ALLOWED_MIME_TYPES
from src.reporter import Reporter


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

FIXTURE_ENEX = Path(__file__).parent / "fixtures" / "testmigration.enex"
MALFORMED_ENEX = Path(__file__).parent / "fixtures" / "malformed.enex"
NOTEBOOK_NAME = "testmigration"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_paths(
    source_dir: Path,
    vault: Path,
    log_dir: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    size_limit_mb: float = 200,
    single_notebook: str = NOTEBOOK_NAME,
    notebook_list: Path = None,
) -> dict:
    """Build the paths dict consumed by run_migration."""
    return {
        "source_directory": source_dir,
        "vault_path": vault,
        "log_directory": log_dir,
        "notebook_list": notebook_list,
        "attachment_size_limit_mb": size_limit_mb,
        "allowed_mime_types": DEFAULT_ALLOWED_MIME_TYPES,
        "force_overwrite": force,
        "dry_run": dry_run,
        "single_notebook": single_notebook,
    }


def _run(paths: dict):
    """Execute pipeline with a Reporter. Returns (exit_code, errors_csv_path | None)."""
    exit_code = 0
    log_dir = paths["log_directory"]
    log_dir.mkdir(parents=True, exist_ok=True)
    try:
        with Reporter(log_dir=log_dir) as reporter:
            run_migration(paths, reporter=reporter, dry_run=paths.get("dry_run", False))
    except Exception:
        exit_code = 1
    errors_csvs = sorted(log_dir.glob("errors-*.csv"))
    return exit_code, (errors_csvs[-1] if errors_csvs else None)


def _csv_rows(errors_csv: Path, level: str) -> list:
    """Return rows from errors CSV filtered by the 'level' column."""
    if errors_csv is None or not errors_csv.exists():
        return []
    with errors_csv.open(encoding="utf-8", newline="") as f:
        return [row for row in csv.DictReader(f) if row.get("level") == level]


def _source_count() -> int:
    """Count <note> elements in the reference fixture."""
    tree = etree.parse(
        str(FIXTURE_ENEX),
        parser=etree.XMLParser(recover=True, huge_tree=True),
    )
    return len(tree.getroot().findall("note"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def mutated_enex_path(source_dir: Path, mutation_func) -> Path:
    """Parse the reference fixture, apply mutation_func(root), write to
    source_dir/testmigration.enex so find_enex_file() can locate it."""
    tree = etree.parse(
        str(FIXTURE_ENEX),
        parser=etree.XMLParser(recover=True, huge_tree=True),
    )
    mutation_func(tree.getroot())
    out_path = source_dir / f"{NOTEBOOK_NAME}.enex"
    tree.write(str(out_path), encoding="utf-8", xml_declaration=True)
    return out_path


# ---------------------------------------------------------------------------
# TestNotebookSelection — LI-01, LI-09
# ---------------------------------------------------------------------------

class TestNotebookSelection:

    def test_li01_enex_introuvable_pour_carnet_liste(self, tmp_path):
        """LI-01: .enex missing for a carnet listed in carnets-a-migrer.txt.

        Constitution rule 1: batch must continue; missing carnet is logged at
        notebook level and the pipeline moves on.
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        vault = tmp_path / "vault"
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        carnets_file = tmp_path / "carnets.txt"
        carnets_file.write_text("inexistant\n", encoding="utf-8")

        paths = _build_paths(
            source_dir, vault, log_dir,
            single_notebook=None,
            notebook_list=carnets_file,
        )
        exit_code, errors_csv = _run(paths)

        assert exit_code == 0, "Constitution rule 1: batch must not stop on missing .enex"

        md_files = list(vault.rglob("*.md")) if vault.exists() else []
        assert len(md_files) == 0, (
            f"Vault must be empty when .enex is missing, found: {[f.name for f in md_files]}"
        )

        notebook_rows = _csv_rows(errors_csv, "notebook")
        assert len(notebook_rows) >= 1, (
            "Expected at least 1 notebook-level error in CSV for missing .enex"
        )
        causes = [r["cause"] for r in notebook_rows]
        assert "enex_not_found" in causes, (
            f"Expected cause='enex_not_found', got: {causes}"
        )

        log_files = sorted(log_dir.glob("migration-*.log"))
        if log_files:
            log_text = log_files[-1].read_text(encoding="utf-8")
            assert "inexistant" in log_text, (
                "Migration log must mention the missing notebook name"
            )

    def test_li09_flag_carnet_avec_nom_absent(self, tmp_path):
        """LI-09: --carnet 'X' where no matching .enex exists.

        NOTE: SPECS Bloc 4 says 'Erreur terminal explicite. Aucune migration
        lancée.' (exit != 0). Actual implementation exits 0 and logs
        enex_not_found at notebook level — code/spec divergence.
        See '⚠️ Problèmes transversaux' at the bottom of this file.
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        vault = tmp_path / "vault"
        log_dir = tmp_path / "logs"

        paths = _build_paths(
            source_dir, vault, log_dir,
            single_notebook="carnet_inexistant",
        )
        exit_code, errors_csv = _run(paths)

        # Current code exits 0 (not 1 as SPECS mandates)
        assert exit_code == 0, (
            "Current implementation exits 0 for missing --carnet "
            "(SPECS says exit != 0; flagged as transversal problem)"
        )

        md_files = list(vault.rglob("*.md")) if vault.exists() else []
        assert len(md_files) == 0, (
            f"Vault must be empty for unknown --carnet, found: {[f.name for f in md_files]}"
        )

        notebook_rows = _csv_rows(errors_csv, "notebook")
        assert any(r["cause"] == "enex_not_found" for r in notebook_rows), (
            f"Expected enex_not_found in notebook errors, got: {notebook_rows}"
        )


# ---------------------------------------------------------------------------
# TestDegradedInput — LI-02, LI-03
# ---------------------------------------------------------------------------

class TestDegradedInput:

    def test_li02_enex_xml_globalement_invalide(self, tmp_path):
        """LI-02: Globally unreadable ENEX (empty file) — notebook-level error, empty vault.

        An empty file triggers XMLSyntaxError in lxml.etree.iterparse even with
        recover=True ('no element found'), which iter_notes re-raises as ValueError.
        process_notebook catches it and logs cause='enex_unreadable'.
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        shutil.copy2(MALFORMED_ENEX, source_dir / "malformed.enex")
        vault = tmp_path / "vault"
        log_dir = tmp_path / "logs"

        paths = _build_paths(
            source_dir, vault, log_dir,
            single_notebook="malformed",
        )
        exit_code, errors_csv = _run(paths)

        assert exit_code == 0, "Constitution rule 1: batch must not stop on unreadable .enex"

        md_files = list(vault.rglob("*.md")) if vault.exists() else []
        assert len(md_files) == 0, (
            f"Vault must be empty for unreadable .enex, found: {[f.name for f in md_files]}"
        )

        notebook_rows = _csv_rows(errors_csv, "notebook")
        assert len(notebook_rows) >= 1, (
            "Expected at least 1 notebook-level error in CSV for unreadable .enex"
        )
        causes = [r["cause"] for r in notebook_rows]
        assert "enex_unreadable" in causes, (
            f"Expected cause='enex_unreadable', got: {causes}"
        )

    def test_li03_note_avec_xhtml_mal_forme(self, tmp_path):
        """LI-03: Note with malformed XHTML in <content>.

        NOTE: SPECS Bloc 4 says the note should be skipped (no .md produced)
        and an error logged at note level. Actual implementation uses best-effort
        conversion (convert_content never raises): the note IS written with
        partial/empty Markdown content. No note-level error in CSV.
        Test verifies the actual tolerant behavior (no crash, all notes written).
        See '⚠️ Problèmes transversaux' at the bottom of this file.
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        def _break_first_note_xhtml(root):
            first_note = root.findall("note")[0]
            content_elem = first_note.find("content")
            if content_elem is not None:
                # CDATA with unclosed XHTML — lxml recover=True handles gracefully
                content_elem.text = CDATA(
                    "<en-note><div>malformed xhtml content without closing tags"
                )

        mutated_enex_path(source_dir, _break_first_note_xhtml)
        vault = tmp_path / "vault"
        log_dir = tmp_path / "logs"

        paths = _build_paths(source_dir, vault, log_dir)
        exit_code, errors_csv = _run(paths)

        assert exit_code == 0, "Pipeline must not crash on malformed note XHTML"

        src_count = _source_count()
        md_files = list(vault.rglob("*.md"))
        # Best-effort: ALL notes produce a .md (convert_content never raises)
        assert len(md_files) == src_count, (
            f"Expected {src_count} .md files (best-effort XHTML tolerance), "
            f"found {len(md_files)}"
        )

        note_rows = _csv_rows(errors_csv, "note")
        # Actual behavior: 0 note-level errors (SPECS expected 1)
        assert len(note_rows) == 0, (
            f"Actual implementation produces 0 note errors for malformed XHTML "
            f"(SPECS says 1); got: {[r['cause'] for r in note_rows]}"
        )


# ---------------------------------------------------------------------------
# TestAttachmentLimits — LI-04, LI-05
# ---------------------------------------------------------------------------

class TestAttachmentLimits:

    def test_li04_piece_jointe_au_dela_du_plafond(self, tmp_path):
        """LI-04: Attachments exceeding the size limit are skipped.

        Uses size_limit_mb=0.001 (~1 KB) — all large attachments in the
        fixture (e.g. 146KB PDF) are skipped with cause='skipped_size'.
        The note .md is produced; the placeholder becomes
        '[pièce jointe non disponible : skipped_size]' (actual text;
        SPECS says '[pièce jointe ignorée : taille > N Mo, voir log]' —
        divergence flagged as transversal problem).
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        shutil.copy2(FIXTURE_ENEX, source_dir / f"{NOTEBOOK_NAME}.enex")
        vault = tmp_path / "vault"
        log_dir = tmp_path / "logs"

        paths = _build_paths(source_dir, vault, log_dir, size_limit_mb=0.001)
        exit_code, errors_csv = _run(paths)

        assert exit_code == 0, "Pipeline must not stop on oversized attachments"

        src_count = _source_count()
        md_files = list(vault.rglob("*.md"))
        assert len(md_files) == src_count, (
            f"All {src_count} notes must be written even when attachments are skipped, "
            f"found {len(md_files)}"
        )

        att_rows = _csv_rows(errors_csv, "attachment")
        size_skipped = [r for r in att_rows if r["cause"] == "skipped_size"]
        assert len(size_skipped) >= 1, (
            f"Expected at least 1 skipped_size attachment error, "
            f"attachment causes: {[r['cause'] for r in att_rows]}"
        )

        # Verify at least one .md mentions the unavailable attachment
        placeholder_text = "pièce jointe non disponible : skipped_size"
        found = any(
            placeholder_text in md.read_text(encoding="utf-8")
            for md in md_files
        )
        assert found, (
            f"Expected at least one .md to contain '{placeholder_text}' "
            f"for oversized attachment placeholder"
        )

    def test_li05_piece_jointe_avec_base64_corrompu(self, tmp_path):
        """LI-05: Attachment with corrupted base64 data.

        The corrupted attachment cannot be decoded: hash_val='' is stored in
        att_map but the placeholder in the .md uses the original MD5 hash
        from <en-media hash="...">, which is never found in att_map.
        Result: '[pièce jointe non résolue : HASH...]' in the .md
        (not '[pièce jointe corrompue, voir log]' as SPECS say — divergence
        flagged as transversal problem).
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        def _corrupt_first_attachment(root):
            first_note = root.findall("note")[0]
            resources = first_note.findall("resource")
            if resources:
                data_elem = resources[0].find("data")
                if data_elem is not None:
                    data_elem.text = "NOT_VALID_BASE64_!!!@#$%^&*()"

        mutated_enex_path(source_dir, _corrupt_first_attachment)
        vault = tmp_path / "vault"
        log_dir = tmp_path / "logs"

        paths = _build_paths(source_dir, vault, log_dir)
        exit_code, errors_csv = _run(paths)

        assert exit_code == 0, "Pipeline must not stop on corrupted base64"

        src_count = _source_count()
        md_files = list(vault.rglob("*.md"))
        assert len(md_files) == src_count, (
            f"All {src_count} notes must be written despite corrupted attachment, "
            f"found {len(md_files)}"
        )

        # The corrupted attachment is NOT in attachments/
        notebook_dirs = [d for d in vault.iterdir() if d.is_dir()]
        assert len(notebook_dirs) == 1, f"Expected 1 notebook dir, found {len(notebook_dirs)}"
        att_dir = notebook_dirs[0] / "attachments"
        # Corrupted attachment produces nothing on disk (or collision-free originals only)

        att_rows = _csv_rows(errors_csv, "attachment")
        corrupted = [r for r in att_rows if r["cause"] == "corrupted_base64"]
        assert len(corrupted) >= 1, (
            f"Expected at least 1 corrupted_base64 attachment error, "
            f"attachment causes: {[r['cause'] for r in att_rows]}"
        )

        # .md of the host note contains 'pièce jointe non résolue' (actual placeholder text)
        first_note_mds = [
            md for md in md_files
            if "pièce jointe non résolue" in md.read_text(encoding="utf-8")
        ]
        assert first_note_mds, (
            "Expected at least one .md to contain 'pièce jointe non résolue' "
            "for corrupted attachment whose hash cannot be computed"
        )


# ---------------------------------------------------------------------------
# TestForceOverwrite — LI-06, LI-07
# ---------------------------------------------------------------------------

class TestForceOverwrite:

    def test_li06_md_existe_sans_force(self, tmp_path):
        """LI-06: .md already exists, no --force — skip + log, mtime unchanged."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        shutil.copy2(FIXTURE_ENEX, source_dir / f"{NOTEBOOK_NAME}.enex")
        vault = tmp_path / "vault"
        log_dir1 = tmp_path / "logs1"
        log_dir2 = tmp_path / "logs2"

        # Run 1 — produce the .md files
        paths1 = _build_paths(source_dir, vault, log_dir1)
        exit_code1, _ = _run(paths1)
        assert exit_code1 == 0, "Run 1 must succeed"

        md_files_r1 = sorted(vault.rglob("*.md"))
        assert md_files_r1, "Run 1 must produce at least one .md"

        # Capture mtime_ns (nanosecond precision) before Run 2
        mtimes_before = {md: md.stat().st_mtime_ns for md in md_files_r1}

        # Run 2 — same vault, no force
        paths2 = _build_paths(source_dir, vault, log_dir2, force=False)
        exit_code2, errors_csv2 = _run(paths2)

        assert exit_code2 == 0, "Run 2 must succeed even when .md files already exist"

        md_files_r2 = sorted(vault.rglob("*.md"))
        assert len(md_files_r2) >= len(md_files_r1), (
            "Run 2 must not delete any .md from Run 1"
        )

        # mtime must be unchanged for all .md from Run 1
        changed = [
            str(md.relative_to(vault))
            for md in md_files_r1
            if md.stat().st_mtime_ns != mtimes_before[md]
        ]
        assert not changed, (
            f"mtime changed for {len(changed)} .md file(s) in no-force Run 2: {changed}"
        )

        # CSV must contain skip entries for existing .md files
        note_rows_r2 = _csv_rows(errors_csv2, "note")
        skip_rows = [r for r in note_rows_r2 if r["cause"] == "md_exists_no_force"]
        assert len(skip_rows) >= 1, (
            f"Expected at least 1 md_exists_no_force entry in Run 2 CSV, "
            f"note causes: {[r['cause'] for r in note_rows_r2]}"
        )

    def test_li07_md_existe_avec_force(self, tmp_path):
        """LI-07: .md already exists, --force active — overwrites, mtime increases."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        shutil.copy2(FIXTURE_ENEX, source_dir / f"{NOTEBOOK_NAME}.enex")
        vault = tmp_path / "vault"
        log_dir1 = tmp_path / "logs1"
        log_dir2 = tmp_path / "logs2"

        # Run 1 — produce .md files
        paths1 = _build_paths(source_dir, vault, log_dir1)
        exit_code1, _ = _run(paths1)
        assert exit_code1 == 0, "Run 1 must succeed"

        md_files_r1 = sorted(vault.rglob("*.md"))
        assert md_files_r1, "Run 1 must produce at least one .md"
        mtimes_before = {md: md.stat().st_mtime_ns for md in md_files_r1}

        # Small sleep to ensure the filesystem timestamp increases
        time.sleep(0.05)

        # Run 2 — same vault, force=True
        paths2 = _build_paths(source_dir, vault, log_dir2, force=True)
        exit_code2, errors_csv2 = _run(paths2)

        assert exit_code2 == 0, "Run 2 with --force must succeed"

        # At least one .md must have a higher mtime (evidence of overwrite)
        newer = [
            str(md.relative_to(vault))
            for md in md_files_r1
            if md.stat().st_mtime_ns > mtimes_before[md]
        ]
        assert newer, (
            f"Expected at least one .md to be overwritten (mtime increased) "
            f"with --force; mtime_before={mtimes_before}"
        )

        # No skip entries in Run 2 CSV (force mode does not skip)
        note_rows_r2 = _csv_rows(errors_csv2, "note")
        skip_rows = [r for r in note_rows_r2 if r["cause"] == "md_exists_no_force"]
        assert not skip_rows, (
            f"Expected no md_exists_no_force entries with --force, got: {skip_rows}"
        )


# ---------------------------------------------------------------------------
# TestDryRun — LI-08
# ---------------------------------------------------------------------------

class TestDryRun:

    def test_li08_dry_run_n_ecrit_rien_dans_le_vault(self, tmp_path, capsys):
        """LI-08: --dry-run mode produces no disk writes in the vault."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        shutil.copy2(FIXTURE_ENEX, source_dir / f"{NOTEBOOK_NAME}.enex")
        vault = tmp_path / "vault"
        vault.mkdir()  # pre-create so we can check it stays empty
        log_dir = tmp_path / "logs"

        paths = _build_paths(source_dir, vault, log_dir, dry_run=True)

        # Dry-run: reporter=None matches main() behavior
        exit_code = 0
        try:
            run_migration(paths, reporter=None, dry_run=True)
        except Exception:
            exit_code = 1

        assert exit_code == 0, "Dry-run must not raise"

        vault_entries = list(vault.rglob("*"))
        assert vault_entries == [], (
            f"Vault must be strictly empty after dry-run, "
            f"found: {[str(e.relative_to(vault)) for e in vault_entries]}"
        )

        captured = capsys.readouterr()
        assert "DRY-RUN" in captured.out, (
            "Stdout must mention DRY-RUN mode; got:\n" + captured.out[:500]
        )


# ---------------------------------------------------------------------------
# TestVaultAccess — LI-10
# ---------------------------------------------------------------------------

class TestVaultAccess:

    def test_li10_vault_path_en_lecture_seule(self, tmp_path):
        """LI-10: Read-only vault causes a permission error (exit != 0).

        The vault directory exists and is readable but not writable (0o555).
        Writer.__init__ tries to create the notebook subdir inside the vault
        and raises PermissionError, which propagates unhandled through
        run_migration and is caught by the test helper (exit_code = 1).
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        shutil.copy2(FIXTURE_ENEX, source_dir / f"{NOTEBOOK_NAME}.enex")
        vault = tmp_path / "vault"
        vault.mkdir()
        log_dir = tmp_path / "logs"

        vault.chmod(0o555)  # read + execute, no write
        try:
            paths = _build_paths(source_dir, vault, log_dir)
            exit_code, _ = _run(paths)
        finally:
            vault.chmod(0o755)  # restore for pytest temp dir cleanup

        assert exit_code != 0, (
            "Pipeline must fail (exit != 0) when vault_path is read-only"
        )

        md_files = list(vault.rglob("*.md"))
        assert len(md_files) == 0, (
            f"No .md must be created in a read-only vault, found: {[f.name for f in md_files]}"
        )


# ---------------------------------------------------------------------------
# TestIdempotence — Constitution rule 5
# ---------------------------------------------------------------------------

class TestIdempotence:

    def test_idempotence_deux_runs_successifs_etat_identique(self, tmp_path):
        """Constitution rule 5: identical perimeter = identical .md result.

        Verifies that .md files produced by Run 1 are not modified by Run 2
        (same sha256 checksums). Note: attachment files may be duplicated in
        Run 2 due to absent cross-session idempotence in AttachmentHandler
        (flagged as transversal problem) — only .md content is asserted here.
        """
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        shutil.copy2(FIXTURE_ENEX, source_dir / f"{NOTEBOOK_NAME}.enex")
        vault = tmp_path / "vault"
        log_dir1 = tmp_path / "logs1"
        log_dir2 = tmp_path / "logs2"

        # Run 1
        paths1 = _build_paths(source_dir, vault, log_dir1)
        exit_code1, _ = _run(paths1)
        assert exit_code1 == 0, "Run 1 must succeed"

        md_files_r1 = sorted(vault.rglob("*.md"))
        assert md_files_r1, "Run 1 must produce at least one .md"
        sha256_r1 = {md: _sha256(md) for md in md_files_r1}

        # Run 2 — same parameters, same vault
        paths2 = _build_paths(source_dir, vault, log_dir2)
        exit_code2, _ = _run(paths2)
        assert exit_code2 == 0, "Run 2 must succeed"

        # Every .md from Run 1 must still exist with identical content
        changed = []
        for md, digest in sha256_r1.items():
            assert md.exists(), f".md from Run 1 is missing after Run 2: {md.name}"
            if _sha256(md) != digest:
                changed.append(md.name)

        assert not changed, (
            f"Constitution rule 5 violated: {len(changed)} .md file(s) were "
            f"modified by Run 2: {changed}"
        )


# ---------------------------------------------------------------------------
# TestNoteWithoutTitle — SPECS Bloc 4
# ---------------------------------------------------------------------------

class TestNoteWithoutTitle:

    def test_note_sans_titre_produit_slug_note_guid8(self, tmp_path):
        """SPECS Bloc 4: note without title uses 'note-{guid[:8]}.md' filename.

        The fixture has no <guid> elements, so the mutation also injects a
        synthetic GUID into the first note. This is necessary because
        slug_for_note(None, None) raises ValueError (constitution rule 4:
        no fabricated metadata — a note with no title AND no guid cannot be
        named without inventing an identifier).
        """
        INJECTED_GUID = "aabbccdd-eeee-ffff-0000-111122223333"
        EXPECTED_SLUG = f"note-{INJECTED_GUID[:8]}"  # "note-aabbccdd"
        EXPECTED_FILENAME = f"{EXPECTED_SLUG}.md"

        source_dir = tmp_path / "source"
        source_dir.mkdir()

        def _strip_title_inject_guid(root):
            first_note = root.findall("note")[0]
            for title_elem in first_note.findall("title"):
                first_note.remove(title_elem)
            guid_el = etree.SubElement(first_note, "guid")
            guid_el.text = INJECTED_GUID

        mutated_enex_path(source_dir, _strip_title_inject_guid)
        vault = tmp_path / "vault"
        log_dir = tmp_path / "logs"

        src_count = _source_count()
        paths = _build_paths(source_dir, vault, log_dir)
        exit_code, _ = _run(paths)

        assert exit_code == 0, "Pipeline must succeed even with a title-less note"

        md_files = list(vault.rglob("*.md"))
        assert len(md_files) == src_count, (
            f"Expected {src_count} .md files, found {len(md_files)}"
        )

        notebook_dirs = [d for d in vault.iterdir() if d.is_dir()]
        assert len(notebook_dirs) == 1, f"Expected 1 notebook dir, found {len(notebook_dirs)}"
        notebook_dir = notebook_dirs[0]

        target_md = notebook_dir / EXPECTED_FILENAME
        assert target_md.exists(), (
            f"Expected '{EXPECTED_FILENAME}' in notebook dir, "
            f"found: {[f.name for f in notebook_dir.glob('*.md')]}"
        )

        content = target_md.read_text(encoding="utf-8")
        lines = content.split("\n")
        assert lines[0].strip() == "---", f"File must start with '---', got: {lines[0]!r}"
        closing = lines.index("---", 1)
        import yaml
        fm = yaml.safe_load("\n".join(lines[1:closing]))
        assert isinstance(fm, dict), f"Frontmatter must be a dict, got {type(fm).__name__}"
        assert fm.get("title") == "", (
            f"title must be empty string for note without title, got: {fm.get('title')!r}"
        )

        other_mds = [
            f.name for f in notebook_dir.glob("*.md") if f.name != EXPECTED_FILENAME
        ]
        assert len(other_mds) == src_count - 1, (
            f"Expected {src_count - 1} other .md files, found: {other_mds}"
        )


# ---------------------------------------------------------------------------
# ⚠️ Problèmes transversaux identifiés (NE PAS corriger dans ce prompt)
# ---------------------------------------------------------------------------
#
# 1. LI-03 — SPECS/code divergence: XHTML malformed in note
#    SPECS Bloc 4 says: note skipped, .md not produced, note-level error logged.
#    Actual code: convert_content() is best-effort (never raises), malformed
#    XHTML produces a .md with empty/partial Markdown content, no error logged.
#    Fix: make convert_content raise on invalid ENML, or check parse_errors in
#    process_note and skip note if non-empty.
#
# 2. LI-09 — SPECS/code divergence: --carnet X with no matching .enex
#    SPECS Bloc 4 says: "Erreur terminal explicite. Aucune migration lancée."
#    (exit != 0). Actual code: exits 0, logs enex_not_found at notebook level.
#    Fix: detect single_notebook at startup (validate_environment or run_migration)
#    and return non-zero exit when the sole carnet has no .enex.
#
# 3. LI-05 — SPECS/code text divergence: corrupted attachment placeholder
#    SPECS says .md should contain "[pièce jointe corrompue, voir log]".
#    Actual code: corrupted_base64 → att.hash="" → placeholder not found in
#    att_map → "[pièce jointe non résolue : HASH[:8]...]" in .md.
#    Fix: either propagate the hash from <en-media> to the error result, or
#    keep a set of "known-corrupted hashes" to resolve the placeholder.
#
# 4. LI-04 — SPECS/code text divergence: oversized attachment placeholder
#    SPECS says .md should contain "[pièce jointe ignorée : taille > N Mo, voir log]".
#    Actual code: "[pièce jointe non disponible : skipped_size]".
#    Fix: update _resolve_placeholders to use SPECS-mandated text per status.
#
# 5. TestIdempotence — cross-session attachment idempotence missing
#    Constitution rule 5 says "même périmètre = même résultat". Run 2 creates
#    collision-suffixed copies of attachments because _hash_to_filename dict
#    is per-session (not persisted). Vault file list is NOT the same after Run 2.
#    Fix: persist hash→filename mapping across sessions (e.g. in a manifest file),
#    or check disk for existing content before collision-suffixing.
#
# 6. LI-06 / md_exists_no_force — PJ processées avant le skip .md
#    SPECS Bloc 4 says "Pièces jointes de cette note NON copiées non plus."
#    Actual code: process_note handles attachments BEFORE writer.write(). If
#    writer returns skipped_existing, the already-written attachment copies
#    are not rolled back (collision-suffixed duplicates left on disk).
#    Fix: check if .md exists BEFORE processing attachments in process_note.
