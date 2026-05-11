"""Entry point for shortcut and thumbnail generation tools."""
import argparse
import os
import sys
from pathlib import Path
from portprotonqt.cli import normalize_launch_path


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

    return parser.parse_args()


def main() -> int:
    """Main entry point for shortcut tools."""
    args = parse_args()
    if args.command == "shortcut":
        return 0 if create_shortcut(args.exe_path, args.game_name) else 1
    if args.command == "thumbnail":
        return 0 if create_thumbnail(args.exe_path, args.output_path) else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
