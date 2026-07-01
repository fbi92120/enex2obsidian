"""
enex2obsidian — CLI entry point for Evernote → Obsidian migration.

Passive orchestrator: parses CLI arguments, loads configuration, then delegates
to src/ modules for all business logic. Contains no conversion or writing logic.
"""

import argparse
import sys
import unicodedata
from pathlib import Path
from typing import Optional

import yaml

from src.enex_parser import iter_notes
from src.metadata_extractor import extract_metadata
from src.content_converter import convert_content, ContentConversionError
from src.attachment_handler import AttachmentHandler
from src.notebook_selector import load_notebook_list
from src.filename_normalizer import to_ascii_slug, slug_for_note
from src.writer import Writer
from src.reporter import Reporter, LogLevel, ErrorLevel, CollisionType


DEFAULT_ALLOWED_MIME_TYPES = {
    # Documents bureautiques
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    "application/rtf",
    "text/rtf",
    "text/plain",
    "text/csv",
    # Images (pas SVG/WebP/GIF)
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif",
    "image/tiff",
    # Email
    "message/rfc822",
    "application/vnd.ms-outlook",
    # Archives
    "application/zip",
    "application/x-7z-compressed",
    "application/x-rar-compressed",
    # Audio
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
}


def main(argv: Optional[list] = None) -> int:
    """Point d'entrée CLI. Retourne 0 (succès) ou 1 (erreur de démarrage).

    1. Parse argv via argparse
    2. Charge config.yml
    3. Résout les chemins finaux (CLI > config)
    4. Valide l'environnement → sys.exit(1) si erreur
    5. Lance run_migration (avec ou sans Reporter selon --dry-run)
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    config_path = Path(args.config).expanduser().resolve()
    config = load_config(config_path)

    paths = resolve_paths(args, config)

    errors = validate_environment(paths)
    if errors:
        for err in errors:
            print(f"[ERREUR] {err}", file=sys.stderr)
        return 1

    if paths["dry_run"]:
        rc = run_migration(paths, reporter=None, dry_run=True)
    else:
        paths["log_directory"].mkdir(parents=True, exist_ok=True)
        with Reporter(log_dir=paths["log_directory"]) as reporter:
            rc = run_migration(paths, reporter=reporter, dry_run=False)

    return rc


def _build_parser() -> argparse.ArgumentParser:
    """Construit le parser argparse de la CLI."""
    p = argparse.ArgumentParser(
        prog="enex2obsidian",
        description="Convertit des carnets Evernote (.enex) en notes Obsidian (.md).",
    )
    p.add_argument(
        "--config", default="config.yml", metavar="CONFIG",
        help="Chemin du fichier config.yml (défaut : ./config.yml)",
    )
    p.add_argument(
        "--carnets", default=None, metavar="CARNETS",
        help="Fichier liste des carnets à migrer (override config)",
    )
    p.add_argument(
        "--source", default=None, metavar="SOURCE",
        help="Dossier des .enex exportés (override config)",
    )
    p.add_argument(
        "--vault", default=None, metavar="VAULT",
        help="Vault Obsidian de destination (override config)",
    )
    p.add_argument(
        "--carnet", default=None, metavar="CARNET",
        help="Migre un seul carnet par nom (ignore --carnets)",
    )
    p.add_argument("--force", action="store_true", help="Écrase les .md cibles existants")
    p.add_argument("--dry-run", action="store_true",
                   help="Liste ce qui serait migré sans rien écrire")
    p.add_argument(
        "--log-dir", default=None, metavar="LOG_DIR",
        help="Dossier des logs et rapports CSV (override config)",
    )
    return p


def load_config(config_path: Path) -> dict:
    """Charge config.yml et retourne un dict.

    Retourne {} si le fichier est absent (les flags CLI doivent alors suffire).
    Affiche un WARNING pour les clés inconnues (pas de rejet strict).
    Quitte (sys.exit 1) si le YAML est invalide.
    """
    if not config_path.exists():
        return {}
    try:
        with config_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            return {}
        if not isinstance(data, dict):
            print("[ERREUR] config.yml invalide : le fichier doit contenir un dict YAML.",
                  file=sys.stderr)
            sys.exit(1)
        known = {
            "source_directory", "vault_path", "log_directory", "notebook_list",
            "attachment_size_limit_mb", "allowed_mime_types", "force_overwrite",
        }
        for key in data:
            if key not in known:
                print(f"[WARNING] config.yml : clé inconnue ignorée : '{key}'")
        return data
    except yaml.YAMLError as exc:
        print(f"[ERREUR] config.yml invalide (YAML) : {exc}", file=sys.stderr)
        sys.exit(1)


def resolve_paths(args, config: dict) -> dict:
    """Résout les chemins finaux selon priorité CLI > config.yml.

    Returns:
        dict avec clés : source_directory, vault_path, log_directory,
        notebook_list, attachment_size_limit_mb, allowed_mime_types,
        force_overwrite, dry_run, single_notebook.
        Les chemins None indiquent des valeurs non configurées (détectées par validate_environment).
    """
    def _p(cli_val, config_key, default=None):
        val = cli_val or config.get(config_key) or default
        if val is None:
            return None
        return Path(str(val)).expanduser().resolve()

    mime_raw = config.get("allowed_mime_types")
    allowed_mime = (
        set(mime_raw)
        if isinstance(mime_raw, list) and mime_raw
        else DEFAULT_ALLOWED_MIME_TYPES
    )

    return {
        "source_directory": _p(args.source, "source_directory"),
        "vault_path": _p(args.vault, "vault_path"),
        "log_directory": _p(args.log_dir, "log_directory", "logs"),
        "notebook_list": _p(args.carnets, "notebook_list"),
        "attachment_size_limit_mb": int(config.get("attachment_size_limit_mb", 200)),
        "allowed_mime_types": allowed_mime,
        "force_overwrite": args.force or bool(config.get("force_overwrite", False)),
        "dry_run": args.dry_run,
        "single_notebook": args.carnet,
    }


def validate_environment(paths: dict) -> list:
    """Valide que les chemins critiques sont accessibles avant de démarrer.

    Returns:
        Liste de messages d'erreur bloquants. Vide si tout est OK.
    """
    errors = []

    source = paths["source_directory"]
    if source is None:
        errors.append("source_directory non configuré (utiliser --source ou config.yml)")
    elif not source.exists():
        errors.append(f"source_directory introuvable : {source}")
    elif not source.is_dir():
        errors.append(f"source_directory n'est pas un dossier : {source}")

    vault = paths["vault_path"]
    if vault is None:
        errors.append("vault_path non configuré (utiliser --vault ou config.yml)")
    else:
        try:
            vault.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            errors.append(f"vault_path inaccessible en écriture : {vault} ({exc})")

    if paths["single_notebook"] is None:
        nb_list = paths["notebook_list"]
        if nb_list is None:
            errors.append(
                "notebook_list non configuré (utiliser --carnets, --carnet ou config.yml)"
            )
        elif not nb_list.exists():
            errors.append(f"notebook_list introuvable : {nb_list}")

    return errors


def find_enex_file(notebook_name: str, source_dir: Path) -> Optional[Path]:
    """Cherche le fichier .enex correspondant à un nom de carnet dans source_dir.

    Matching NFC-normalisé (insensible aux variantes Unicode d'un même caractère accentué).
    Tente d'abord un match exact, puis scan de tous les .enex du dossier.
    Si plusieurs candidats, retourne le premier par ordre alphabétique + avertissement stdout.

    Returns:
        Path du .enex trouvé, ou None si aucune correspondance.
    """
    nfc_name = unicodedata.normalize("NFC", notebook_name)

    exact = source_dir / f"{nfc_name}.enex"
    if exact.exists():
        return exact

    candidates = sorted(
        p for p in source_dir.glob("*.enex")
        if unicodedata.normalize("NFC", p.stem) == nfc_name
    )
    if not candidates:
        return None
    if len(candidates) > 1:
        print(
            f"[WARNING] {len(candidates)} fichiers .enex candidats pour '{notebook_name}'"
            f" — utilisation de : {candidates[0].name}"
        )
    return candidates[0]


def run_migration(paths: dict, reporter: Optional[Reporter], dry_run: bool) -> int:
    """Boucle principale sur les carnets.

    Résout chaque carnet → fichier .enex, délègue à process_notebook,
    affiche l'entête et le résumé final.

    Returns:
        0 si la migration s'est déroulée normalement (même avec des erreurs par note).
        1 si une erreur terminale empêche tout démarrage (ex. --carnet X introuvable).
    """
    single = paths["single_notebook"]
    notebooks = [single] if single else load_notebook_list(paths["notebook_list"])

    # SPECS Bloc 4 : --carnet "X" avec X absent → erreur terminal, aucune migration
    if single:
        _enex_check = find_enex_file(single, paths["source_directory"])
        if _enex_check is None:
            print(
                f"[ERREUR] Carnet '{single}' introuvable dans "
                f"{paths['source_directory']} (aucun fichier .enex correspondant).",
                file=sys.stderr,
            )
            return 1

    print("\n=== Migration Evernote → Obsidian ===")
    if dry_run:
        print("MODE : DRY-RUN (aucune écriture disque)")
    print(f"Source : {paths['source_directory']}")
    print(f"Vault  : {paths['vault_path']}")
    if not dry_run:
        print(f"Logs   : {paths['log_directory']}")
    print(f"\nCarnets sélectionnés ({len(notebooks)}) :")
    for i, name in enumerate(notebooks, 1):
        print(f"  {i}. {name}")
    print()

    if reporter:
        reporter.log(LogLevel.INFO, f"Démarrage — {len(notebooks)} carnet(s)")

    stats = {
        "notes_in": 0,
        "notes_ok": 0,
        "notes_partial": 0,
        "notes_skipped": 0,
        "notes_error": 0,
        "att_ok": 0,
        "att_skipped": 0,
        "att_error": 0,
    }

    for idx, notebook_name in enumerate(notebooks, 1):
        enex_path = find_enex_file(notebook_name, paths["source_directory"])
        if enex_path is None:
            msg = f"Fichier .enex introuvable pour '{notebook_name}'"
            print(f"[ERREUR] {msg}")
            if reporter:
                reporter.record_error(
                    level=ErrorLevel.NOTEBOOK,
                    cause="enex_not_found",
                    detail=msg,
                    notebook=notebook_name,
                )
            continue
        process_notebook(
            notebook_name=notebook_name,
            enex_path=enex_path,
            paths=paths,
            reporter=reporter,
            dry_run=dry_run,
            notebook_idx=idx,
            total_notebooks=len(notebooks),
            stats=stats,
        )

    log_summary(stats=stats, paths=paths, reporter=reporter, dry_run=dry_run)
    return 0


def process_notebook(
    notebook_name: str,
    enex_path: Path,
    paths: dict,
    reporter: Optional[Reporter],
    dry_run: bool,
    notebook_idx: int,
    total_notebooks: int,
    stats: dict,
) -> None:
    """Traite un carnet complet : charge les notes, instancie les modules, boucle.

    Charge toutes les notes en mémoire pour afficher le total avant de commencer.
    Instancie AttachmentHandler et Writer une fois par carnet (état collision partagé).
    """
    notebook_slug = to_ascii_slug(notebook_name)
    notebook_dir = paths["vault_path"] / notebook_slug

    try:
        notes = list(iter_notes(enex_path))
    except Exception as exc:
        msg = f"Lecture .enex échouée pour '{notebook_name}' : {exc}"
        print(f"[ERREUR] {msg}")
        if reporter:
            reporter.record_error(
                level=ErrorLevel.NOTEBOOK,
                cause="enex_unreadable",
                detail=msg,
                notebook=notebook_name,
            )
        return

    total_notes = len(notes)
    print(f"[Carnet {notebook_idx}/{total_notebooks}] {notebook_name} — {total_notes} notes")

    if total_notes == 0:
        if reporter:
            reporter.log(LogLevel.INFO, f"Carnet '{notebook_name}' : 0 notes détectées")
        return

    if dry_run:
        attachment_handler = None
        writer = None
    else:
        attachment_handler = AttachmentHandler(
            target_dir=notebook_dir / "attachments",
            size_limit_mb=paths["attachment_size_limit_mb"],
            allowed_mime_types=paths["allowed_mime_types"],
        )
        writer = Writer(
            notebook_dir=notebook_dir,
            force_overwrite=paths["force_overwrite"],
        )

    nb_stats = {"ok": 0, "partial": 0, "skipped": 0, "error": 0}

    for note_idx, raw_note in enumerate(notes, 1):
        stats["notes_in"] += 1
        try:
            result = process_note(
                raw_note=raw_note,
                notebook_name=notebook_name,
                notebook_dir=notebook_dir,
                attachment_handler=attachment_handler,
                writer=writer,
                reporter=reporter,
                dry_run=dry_run,
                note_idx=note_idx,
                total_notes=total_notes,
                notebook_idx=notebook_idx,
                total_notebooks=total_notebooks,
                stats=stats,
            )
        except Exception as exc:
            result = "error"
            guid = getattr(raw_note, "guid", "unknown")
            msg = f"Erreur inattendue note guid={guid} : {type(exc).__name__}: {exc}"
            print(f"  [ERREUR] {msg}")
            if reporter:
                reporter.record_error(
                    level=ErrorLevel.NOTE,
                    cause="orchestration_error",
                    detail=msg,
                    notebook=notebook_name,
                    note_guid=guid,
                )

        nb_stats[result] += 1
        stats[f"notes_{result}"] += 1

    print(
        f"  → {nb_stats['ok']} succès, "
        f"{nb_stats['partial']} err. partielles, "
        f"{nb_stats['skipped']} ignorées, "
        f"{nb_stats['error']} erreurs"
    )
    if reporter:
        reporter.log(
            LogLevel.INFO,
            f"Carnet '{notebook_name}' : {nb_stats['ok']} ok, "
            f"{nb_stats['error']} erreurs, {nb_stats['skipped']} ignorées",
        )


def process_note(
    raw_note,
    notebook_name: str,
    notebook_dir: Path,
    attachment_handler: Optional[AttachmentHandler],
    writer: Optional[Writer],
    reporter: Optional[Reporter],
    dry_run: bool,
    note_idx: int,
    total_notes: int,
    notebook_idx: int,
    total_notebooks: int,
    stats: dict,
) -> str:
    """Pipeline d'une note : métadonnées → contenu → pièces jointes → écriture.

    Returns:
        "ok"      — note écrite, toutes les pièces jointes traitées normalement
        "partial" — note écrite, au moins une pièce jointe en erreur inattendue
        "skipped" — note ignorée (fichier .md existant, sans --force)
        "error"   — note non écrite (erreur métadonnées ou écriture)
    """
    title = raw_note.title or "(sans titre)"
    print(f"  Note {note_idx}/{total_notes} : {title}")

    # Extraction métadonnées
    try:
        meta = extract_metadata(raw_note, notebook_name)
    except Exception as exc:
        if reporter:
            reporter.record_error(
                level=ErrorLevel.NOTE,
                cause="metadata_extraction_failed",
                detail=str(exc),
                notebook=notebook_name,
                note_guid=raw_note.guid,
                note_title=title,
            )
        return "error"

    # Conversion contenu — lève ContentConversionError si ENML structurellement cassé
    # SPECS Bloc 4 : note avec XHTML mal formé → log level=note + skip, aucun .md produit
    try:
        md_content = convert_content(raw_note.content_xhtml)
    except ContentConversionError as exc:
        if reporter:
            reporter.record_error(
                level=ErrorLevel.NOTE,
                cause="xhtml_malformed",
                detail=str(exc),
                notebook=notebook_name,
                note_guid=raw_note.guid,
                note_title=title,
            )
        return "error"

    # Dry-run : affichage plan et sortie anticipée
    if dry_run:
        try:
            slug = slug_for_note(meta.title, meta.evernote_guid)
        except ValueError:
            slug = "(slug non calculable)"
        print(f"    DRY-RUN : serait écrit dans {notebook_dir}/{slug}.md")
        return "ok"

    # Traitement pièces jointes
    att_map = {}
    has_att_error = False
    for raw_att in raw_note.attachments:
        att = attachment_handler.handle(raw_att, note_title=title, note_guid=raw_note.guid)
        att_map[att.hash] = att
        if att.status == "ok":
            stats["att_ok"] += 1
        elif att.status in ("skipped_mime", "skipped_size"):
            # Exclusions intentionnelles : tracées mais non considérées comme erreurs de note
            stats["att_skipped"] += 1
            if reporter:
                reporter.record_error(
                    level=ErrorLevel.ATTACHMENT,
                    cause=att.status,
                    detail=att.error_detail or "",
                    notebook=notebook_name,
                    note_guid=raw_note.guid,
                    note_title=title,
                    attachment_filename=att.original_filename,
                )
        else:
            stats["att_error"] += 1
            has_att_error = True
            if reporter:
                reporter.record_error(
                    level=ErrorLevel.ATTACHMENT,
                    cause=att.status,
                    detail=att.error_detail or "",
                    notebook=notebook_name,
                    note_guid=raw_note.guid,
                    note_title=title,
                    attachment_filename=att.original_filename,
                )

    # Écriture
    wr = writer.write(metadata=meta, markdown_content=md_content, attachment_map=att_map)

    if wr.status == "skipped_existing":
        if reporter:
            reporter.record_error(
                level=ErrorLevel.NOTE,
                cause="md_exists_no_force",
                detail=f"Fichier existant : {wr.final_filename}",
                notebook=notebook_name,
                note_guid=raw_note.guid,
                note_title=title,
            )
        return "skipped"

    if wr.status in ("write_error", "traversal_blocked"):
        if reporter:
            reporter.record_error(
                level=ErrorLevel.NOTE,
                cause=wr.status,
                detail=wr.error_detail or "",
                notebook=notebook_name,
                note_guid=raw_note.guid,
                note_title=title,
            )
        return "error"

    # Note écrite (status == "ok")
    if wr.collided and reporter:
        reporter.record_collision(
            kind=CollisionType.MD,
            original_name=f"{wr.slug}.md",
            final_name=wr.final_filename or "",
            notebook=notebook_name,
            note_guid=raw_note.guid,
        )

    for hash_val in wr.unresolved_placeholders:
        if reporter:
            reporter.log(
                LogLevel.WARNING,
                f"Placeholder non résolu {hash_val} dans note guid={raw_note.guid}",
            )

    return "partial" if has_att_error else "ok"


def log_summary(stats: dict, paths: dict, reporter: Optional[Reporter], dry_run: bool) -> None:
    """Affiche le résumé final sur stdout et dans le log (si reporter présent)."""
    print("\n=== Migration terminée ===")

    if dry_run:
        print(f"Notes analysées (DRY-RUN) : {stats['notes_in']}")
        return

    print(
        f"Notes   : {stats['notes_in']} en entrée, "
        f"{stats['notes_ok']} succès, "
        f"{stats['notes_partial']} err. partielles, "
        f"{stats['notes_skipped']} ignorées, "
        f"{stats['notes_error']} erreurs"
    )
    print(
        f"Pièces jointes : {stats['att_ok']} copiées, "
        f"{stats['att_skipped']} ignorées (taille/MIME), "
        f"{stats['att_error']} erreurs"
    )

    if reporter:
        reporter.log(
            LogLevel.INFO,
            f"Résumé — notes : {stats['notes_ok']} ok / {stats['notes_error']} erreurs ; "
            f"pièces jointes : {stats['att_ok']} copiées / {stats['att_error']} erreurs",
        )
        log_dir = paths["log_directory"]
        print(f"\nLogs : {log_dir}/migration-*.log")
        print(f"       {log_dir}/collisions-*.csv")
        print(f"       {log_dir}/errors-*.csv")


if __name__ == "__main__":
    sys.exit(main())
