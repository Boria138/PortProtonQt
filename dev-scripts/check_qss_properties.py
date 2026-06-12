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

def check_css_comments(content: str, file_path: Path) -> list[str]:
    """
    Проверка синтаксиса CSS-комментариев.
    Возвращает список ошибок.
    """
    errors = []
    # Ищем незавершённые комментарии: /* без закрывающего */
    # Исключаем корректные комментарии /* ... */
    in_comment = False
    comment_start = 0
    i = 0
    while i < len(content) - 1:
        if content[i:i+2] == '/*':
            if in_comment:
                errors.append(f"Nested comment start at position {i}")
            in_comment = True
            comment_start = i
            i += 2
        elif content[i:i+2] == '*/':
            if not in_comment:
                errors.append(f"Unexpected comment end '*/' without matching '/*' at position {i}")
            in_comment = False
            i += 2
        else:
            i += 1

    if in_comment:
        errors.append(f"Unclosed comment starting at position {comment_start}")

    # Ищем опечатки: * ... */ без открывающего /*
    # Паттерн: пробел/символ, затем *, затем текст, затем */
    pattern = r'(?<!/)\*\s+[^*]*\*/'
    for match in re.finditer(pattern, content):
        # Проверяем, не часть строки ли это (внутри f-строки)
        line_start = content.rfind('\n', 0, match.start()) + 1
        line_prefix = content[line_start:match.start()]
        # Пропускаем, если это внутри строки (после кавычки)
        if '"' in line_prefix or "'" in line_prefix:
            continue
        errors.append(f"Invalid comment '{match.group()}' - missing opening '/*'")

    return errors


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

        # Check CSS comment syntax
        comment_errors = check_css_comments(content, qss_file)
        for error in comment_errors:
            print(f"ERROR: CSS comment syntax error in {qss_file}: {error}")
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