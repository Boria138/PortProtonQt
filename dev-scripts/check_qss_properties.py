#!/usr/bin/env python3

import sys
from pathlib import Path
import re

# Запрещенные свойства
FORBIDDEN_PROPERTIES = {
    "box-shadow",
    "backdrop-filter",
    "cursor",
    "text-shadow",
}

def check_qss_files():
    has_errors = False
    for qss_file in Path("portprotonqt/themes").glob("**/*.py"):
        with open(qss_file, "r") as f:
            content = f.read()
            for prop in FORBIDDEN_PROPERTIES:
                if re.search(rf"{prop}\s*:", content, re.IGNORECASE):
                    print(f"ERROR: Unknown qss property found '{prop}' on file {qss_file}")
                    has_errors = True
    return has_errors

if __name__ == "__main__":
    if check_qss_files():
        sys.exit(1)
