"""
enex2obsidian — CLI entry point for Evernote → Obsidian migration.

Passive orchestrator: parses CLI arguments, loads configuration, then delegates
to src/ modules for all business logic. Contains no conversion or writing logic.
"""

import argparse
import sys


def parse_args():
    """
    Parse CLI arguments for enex2obsidian.

    Returns:
        argparse.Namespace: parsed arguments with attributes:
            - carnets (str|None): path to notebook list file
            - source (str|None): source directory containing .enex files
            - vault (str|None): destination Obsidian vault path
            - carnet (str|None): single notebook name (overrides --carnets)
            - force (bool): overwrite existing .md files
            - dry_run (bool): plan only, no writes
            - log_dir (str|None): log output directory

    Raises:
        SystemExit: on --help or invalid arguments (argparse default).
    """
    raise NotImplementedError("Étape 11 de la séquence")


def load_config(config_path):
    """
    Load and parse config.yml.

    Args:
        config_path (str): path to config.yml file

    Returns:
        dict: configuration values with keys:
            source_directory, vault_path, log_directory,
            notebook_list, attachment_size_limit_mb, force_overwrite

    Raises:
        SystemExit: if config file is missing or invalid YAML.
    """
    raise NotImplementedError("Étape 11 de la séquence")


def resolve_paths(args, config):
    """
    Resolve final paths: CLI flags take priority over config.yml values.

    Args:
        args (argparse.Namespace): parsed CLI arguments
        config (dict): loaded configuration

    Returns:
        dict: resolved paths with keys:
            source_dir, vault_path, log_dir, notebook_list, carnet_name, force, dry_run
    """
    raise NotImplementedError("Étape 11 de la séquence")


def validate_paths(source_dir, vault_path, log_dir):
    """
    Validate that required directories exist and are accessible.

    Args:
        source_dir (str): source directory for .enex files
        vault_path (str): Obsidian vault destination path
        log_dir (str): log output directory (created automatically if absent)

    Raises:
        SystemExit: if source_dir or vault_path are missing or inaccessible.
    """
    raise NotImplementedError("Étape 11 de la séquence")


def main():
    """
    Main entry point — orchestrates the full migration pipeline.

    Delegates to src/ modules in order:
        1. parse_args + load_config + resolve_paths + validate_paths
        2. notebook_selector.load_notebook_list
        3. reporter.create_log_session
        4. For each notebook: enex_parser → metadata_extractor →
           content_converter → attachment_handler → writer
        5. reporter.write_summary

    No business logic lives here. All decisions are in src/ modules.
    """
    raise NotImplementedError("Étape 11 de la séquence")


if __name__ == "__main__":
    main()
