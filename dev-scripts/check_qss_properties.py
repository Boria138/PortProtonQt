#!/usr/bin/env python3

import sys
from pathlib import Path
import re
import ast

# Запрещенные QSS-свойства
FORBIDDEN_PROPERTIES = {
    "box-shadow",
    "backdrop-filter",
    "cursor",
    "text-shadow",
}

# Запрещенные модули и функции
FORBIDDEN_MODULES = {
    "os",
    "subprocess",
    "shutil",
    "sys",
    "socket",
    "ctypes",
    "pathlib",
    "glob",
}
FORBIDDEN_FUNCTIONS = {
    "exec",
    "eval",
    "open",
    "__import__",
}

def check_qss_files():
    has_errors = False
    for qss_file in Path("portprotonqt/themes").glob("**/*.py"):
        with open(qss_file, "r") as f:
            content = f.read()

            # Проверка на запрещённые QSS-свойства
            for prop in FORBIDDEN_PROPERTIES:
                if re.search(rf"{prop}\s*:", content, re.IGNORECASE):
                    print(f"ERROR: Unknown QSS property found '{prop}' in file {qss_file}")
                    has_errors = True

            # Проверка на опасные импорты и функции
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    # Проверка импортов
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        for name in node.names:
                            if name.name in FORBIDDEN_MODULES:
                                print(f"ERROR: Forbidden module '{name.name}' found in file {qss_file}")
                                has_errors = True
                    # Проверка вызовов функций
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_FUNCTIONS:
                            print(f"ERROR: Forbidden function '{node.func.id}' found in file {qss_file}")
                            has_errors = True
            except SyntaxError as e:
                print(f"ERROR: Syntax error in file {qss_file}: {e}")
                has_errors = True

    return has_errors

if __name__ == "__main__":
    if check_qss_files():
        sys.exit(1)
