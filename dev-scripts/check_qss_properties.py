#!/usr/bin/env python3

import sys
from pathlib import Path
import re

# Import the security checker from the main module
sys.path.insert(0, str(Path(__file__).parent.parent))  # Add project root to path
from portprotonqt.theme_security import ThemeSecurityChecker

# Запрещенные QSS-свойства
FORBIDDEN_PROPERTIES = {
    "box-shadow",
    "backdrop-filter",
    "cursor",
    "text-shadow",
}

def check_qss_files():
    has_errors = False
    for qss_file in Path("portprotonqt/themes").glob("**/*.py"):
        # Check for forbidden QSS properties first
        with open(qss_file, "r", encoding='utf-8') as f:
            content = f.read()

        for prop in FORBIDDEN_PROPERTIES:
            if re.search(rf"{prop}\s*:", content, re.IGNORECASE):
                print(f"ERROR: Unknown QSS property found '{prop}' in file {qss_file}")
                has_errors = True

        # Use the imported ThemeSecurityChecker to check for dangerous imports and functions
        checker = ThemeSecurityChecker()
        is_safe, errors = checker.check_theme_safety(str(qss_file))
        
        if not is_safe:
            for error in errors:
                print(error)
            has_errors = True

    return has_errors

if __name__ == "__main__":
    if check_qss_files():
        sys.exit(1)