"""Entry point for shortcut and thumbnail generation tools."""
import argparse
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Any
from portprotonqt.cli import normalize_launch_path


def _download_ppdb_file(session: Any, ppdb_url: str, ppdb_path: str) -> bool:
    """Download PPDB file to the requested path."""
    from portprotonqt.logger import get_logger
    from requests import RequestException

    logger = get_logger(__name__)
    temp_path = f"{ppdb_path}.tmp"
    try:
        logger.info("Download new PPDB file from: %s", ppdb_url)
        ppdb_response = session.get(ppdb_url, timeout=30)
        ppdb_response.raise_for_status()
        Path(temp_path).write_bytes(ppdb_response.content)
        os.replace(temp_path, ppdb_path)
        return True
    except RequestException as error:
        logger.warning("Failed to download PPDB from URL %s: %s", ppdb_url, error)
    except OSError as error:
        logger.warning("Failed to save PPDB file %s: %s", ppdb_path, error)

    Path(temp_path).unlink(missing_ok=True)
    return False


def find_ext_ppdb(exe_path: str) -> bool:
    """Download PPDB file for executable when it is available."""
    from portprotonqt.downloader import get_requests_session
    from portprotonqt.logger import get_logger
    from requests import RequestException

    logger = get_logger(__name__)
    if not exe_path or not os.path.isfile(exe_path):
        logger.error("Broken arguments for PPDB lookup: %s", exe_path)
        return False

    ppdb_path = f"{exe_path}.ppdb"
    if os.path.isfile(ppdb_path):
        logger.info("PPDB file was found: %s", ppdb_path)
        return True

    exe_filename = os.path.basename(exe_path)
    api_url = "https://ppdb.linux-gaming.ru/api/lookup/exe/"
    api_url += urllib.parse.quote(exe_filename)
    session = get_requests_session()

    try:
        logger.info("Get metadata from %s", api_url)
        response = session.get(api_url, timeout=10)
        response.raise_for_status()
    except RequestException as error:
        logger.warning("Failed to fetch metadata %s: %s", api_url, error)
        return False

    if not response.text or "No game found" in response.text:
        logger.warning("Settings file not found for %s", exe_filename)
        return False

    try:
        ppdb_url = response.json().get("ppdb_url", "")
    except ValueError as error:
        logger.warning("Failed to parse metadata %s: %s", api_url, error)
        return False

    if not ppdb_url:
        logger.warning("PPDB URL not found in metadata for %s", exe_filename)
        return False

    return _download_ppdb_file(session, ppdb_url, ppdb_path)


def create_shortcut(exe_path: str, game_name: str | None = None) -> bool:
    """Create a PortProtonQt desktop shortcut for an executable."""
    from portprotonqt.config import create_desktop_file
    from portprotonqt.icon_extractor import generate_thumbnail
    from portprotonqt.logger import get_logger

    logger = get_logger(__name__)
    normalized_path = normalize_launch_path(exe_path)
    result = create_desktop_file(normalized_path, game_name)
    if not result:
        return False

    desktop_entry, desktop_path, icon_path = result

    if not generate_thumbnail(normalized_path, icon_path, size=128):
        logger.error("Failed to generate thumbnail from exe: %s", normalized_path)
        desktop_entry = desktop_entry.replace(f"Icon={icon_path}\n", "Icon=\n")

    try:
        Path(desktop_path).write_text(desktop_entry, encoding="utf-8")
        os.chmod(desktop_path, 0o755)
    except OSError as error:
        logger.error("Failed to save desktop file %s: %s", desktop_path, error)
        return False

    return True


def create_thumbnail(exe_path: str, output_path: str) -> bool:
    """Create a PNG thumbnail for an executable."""
    from portprotonqt.icon_extractor import generate_thumbnail
    from portprotonqt.logger import get_logger

    logger = get_logger(__name__)
    normalized_path = normalize_launch_path(exe_path)
    if not normalized_path or not output_path:
        return False

    try:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
    except OSError as error:
        logger.error("Failed to prepare thumbnail directory %s: %s", output_path, error)
        return False

    if not generate_thumbnail(normalized_path, output_path, size=128):
        logger.error("Failed to generate thumbnail: %s", normalized_path)
        return False

    return True


def parse_args():
    """Parse arguments for shortcut tools."""
    parser = argparse.ArgumentParser(description="PortProtonQt shortcut tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    shortcut_parser = subparsers.add_parser("shortcut", help="Create a desktop shortcut")
    shortcut_parser.add_argument("exe_path", help="Path to the executable")
    shortcut_parser.add_argument("game_name", help="Name of the game")

    thumbnail_parser = subparsers.add_parser("thumbnail", help="Create a PNG thumbnail")
    thumbnail_parser.add_argument("exe_path", help="Path to the executable")
    thumbnail_parser.add_argument("output_path", help="Path to the output PNG file")

    ppdb_parser = subparsers.add_parser("find-ppdb", help="Download PPDB for an executable")
    ppdb_parser.add_argument("exe_path", help="Path to the executable")

    return parser.parse_args()


def main() -> int:
    """Main entry point for shortcut tools."""
    args = parse_args()
    if args.command == "shortcut":
        return 0 if create_shortcut(args.exe_path, args.game_name) else 1
    if args.command == "thumbnail":
        return 0 if create_thumbnail(args.exe_path, args.output_path) else 1
    if args.command == "find-ppdb":
        return 0 if find_ext_ppdb(args.exe_path) else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
