"""Read PE version metadata for PortProton shell scripts."""

import re
import sys
from pathlib import Path

import pefile

from portprotonqt.logger import get_logger

logger = get_logger(__name__)


def read_metadata(path: str) -> dict[str, str] | None:
    """Read version strings without starting an external metadata tool."""
    try:
        with pefile.PE(path, fast_load=True) as pe:
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
            return {
                key.decode("utf-8", errors="replace"): value.decode("utf-8", errors="replace")
                for block in getattr(pe, "FileInfo", []) for info in block
                for table in getattr(info, "StringTable", []) for key, value in table.entries.items()
            }
    except pefile.PEFormatError as error:
        logger.debug("Unsupported PE file %s: %s", path, error)
    except OSError as error:
        logger.warning("Failed to read executable metadata %s: %s", path, error)
    return None


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: python -m portprotonqt.scripts_utils.exe_metadata FILE\n")
        return 2
    metadata = read_metadata(sys.argv[1])
    if metadata is None:
        return 1
    sys.stdout.write(f"File Name: {Path(sys.argv[1]).name}\n")
    for key, value in metadata.items():
        label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", key)
        sys.stdout.write(f"{label}: {' '.join(value.splitlines())}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
