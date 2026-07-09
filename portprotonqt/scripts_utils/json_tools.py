"""JSON helpers for PortProton shell scripts."""
import argparse
import sys
from pathlib import Path
from typing import Any

import orjson


def _load_json_file(path: str) -> Any:
    with Path(path).open("rb") as f:
        return orjson.loads(f.read())


def _wine_url(metadata: dict[str, Any], version: str) -> str:
    version_lower = version.lower()
    for items in metadata.values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("name", "")).lower() == version_lower:
                return str(item.get("url", ""))
    return ""


def _epic_manifest_fields(manifest: dict[str, Any]) -> tuple[str, str, str]:
    install_location = str(manifest.get("InstallLocation", ""))
    launch_executable = str(manifest.get("LaunchExecutable", ""))
    exe_path = f"{install_location}\\{launch_executable}"
    return exe_path, str(manifest.get("DisplayName", "")), str(manifest.get("AppName", ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PortProton JSON tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    wine_parser = subparsers.add_parser("wine-url")
    wine_parser.add_argument("version")

    epic_parser = subparsers.add_parser("epic-manifest")
    epic_parser.add_argument("manifest_path")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "wine-url":
            metadata = orjson.loads(sys.stdin.buffer.read())
            sys.stdout.write(_wine_url(metadata, args.version))
            return 0
        if args.command == "epic-manifest":
            fields = _epic_manifest_fields(_load_json_file(args.manifest_path))
            sys.stdout.write("\t".join(fields))
            return 0
    except (OSError, orjson.JSONDecodeError) as error:
        sys.stderr.write(f"Failed to parse JSON: {error}\n")
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
