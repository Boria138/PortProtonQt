#!/usr/bin/env python3

import argparse
import sys
import re
import ast
from pathlib import Path
from babel.messages.frontend import CommandLineInterface

# ---------- Пути ----------
LOCALES_PATH = Path(__file__).parent.parent / "portprotonqt" / "locales"
THEMES_PATH  = Path(__file__).parent.parent / "portprotonqt" / "themes"
MESON_BUILD  = Path(__file__).parent.parent / "portprotonqt" / "meson.build"
POT_FILE     = LOCALES_PATH / "portprotonqt.pot"

# ---------- Версия проекта ----------
def _get_version() -> str:
    return "0.1.1"

# ---------- PyBabel команды ----------
def compile_locales() -> None:
    CommandLineInterface().run([
        "pybabel", "compile", "--use-fuzzy", "--directory",
        f"{LOCALES_PATH.resolve()}", "--domain=portprotonqt", "--statistics"
    ])

def extract_strings() -> None:
    input_dir = (Path(__file__).parent.parent / "portprotonqt").resolve()
    CommandLineInterface().run([
        "pybabel", "extract", "--project=PortProtonQt",
        f"--version={_get_version()}",
        "--strip-comment-tag",
        "--no-location",
        f"--input-dir={input_dir}",
        "--copyright-holder=boria138",
        f"--ignore-dirs={THEMES_PATH}",
        f"--output-file={POT_FILE.resolve()}"
    ])

def update_locales() -> None:
    saved_headers: dict[Path, list[str]] = {}
    saved_po_texts: dict[Path, str] = {}
    for po_file in LOCALES_PATH.glob("**/portprotonqt.po"):
        saved_po_texts[po_file] = po_file.read_text(encoding="utf-8")
        header_block = _get_po_header_block(po_file)
        if header_block:
            saved_headers[po_file] = header_block

    CommandLineInterface().run([
        "pybabel", "update",
        f"--input-file={POT_FILE.resolve()}",
        f"--output-dir={LOCALES_PATH.resolve()}",
        "--domain=portprotonqt",
        "--ignore-obsolete",
        "--ignore-pot-creation-date",
        "--update-header-comment",
    ])

    for po_file, header_block in saved_headers.items():
        _set_po_header_block(po_file, header_block)

    for po_file, original_text in saved_po_texts.items():
        _restore_unchanged_po_entries(po_file, original_text)

def _get_po_header_block(po_path: Path) -> list[str] | None:
    lines = po_path.read_text(encoding="utf-8").splitlines()
    in_header = False
    header_start = None
    header_end = None
    for i, line in enumerate(lines):
        if line == 'msgstr ""':
            in_header = True
            header_start = i + 1
            continue
        if not in_header:
            continue
        if not line.startswith('"'):
            header_end = i
            break
    if header_start is None or header_end is None or header_end <= header_start:
        return None
    return lines[header_start:header_end]

def _set_po_header_block(po_path: Path, block: list[str]) -> None:
    lines = po_path.read_text(encoding="utf-8").splitlines()
    in_header = False
    header_start = None
    header_end = None
    for i, line in enumerate(lines):
        if line == 'msgstr ""':
            in_header = True
            header_start = i + 1
            continue
        if not in_header:
            continue
        if not line.startswith('"'):
            header_end = i
            break
    if header_start is None or header_end is None:
        return
    lines[header_start:header_end] = block
    po_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def _parse_po_entry_signature(block: list[str]) -> tuple[str, tuple[tuple[str, str], ...]] | None:
    msgctxt = ""
    msgid = None
    msgstr_values: dict[str, str] = {}
    i = 0
    try:
        while i < len(block):
            line = block[i]
            if line.startswith("msgctxt "):
                msgctxt, i = _read_po_value(block, i, "msgctxt ")
                continue
            if line.startswith("msgid "):
                msgid, i = _read_po_value(block, i, "msgid ")
                continue
            if line.startswith("msgstr "):
                value, i = _read_po_value(block, i, "msgstr ")
                msgstr_values["msgstr"] = value
                continue
            if line.startswith("msgstr["):
                key = line.split(" ", maxsplit=1)[0]
                value, i = _read_po_value(block, i, f"{key} ")
                msgstr_values[key] = value
                continue
            i += 1
    except (SyntaxError, ValueError):
        return None
    if msgid is None or msgid == "":
        return None
    return f"{msgctxt}\x04{msgid}", tuple(sorted(msgstr_values.items()))

def _read_po_value(block: list[str], idx: int, prefix: str) -> tuple[str, int]:
    value = _unquote_po_string(block[idx][len(prefix):])
    idx += 1
    while idx < len(block) and block[idx].startswith('"'):
        value += _unquote_po_string(block[idx])
        idx += 1
    return value, idx

def _unquote_po_string(value: str) -> str:
    value = value.strip()
    if not value.startswith('"'):
        return ""
    return ast.literal_eval(value)

def _split_po_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line == "":
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks

def _restore_unchanged_po_entries(po_path: Path, original_text: str) -> None:
    original_blocks = _split_po_blocks(original_text)
    original_entries: dict[str, tuple[tuple[tuple[str, str], ...], list[str]]] = {}
    for block in original_blocks:
        signature = _parse_po_entry_signature(block)
        if signature is None:
            continue
        key, values = signature
        original_entries[key] = (values, block)

    current_blocks = _split_po_blocks(po_path.read_text(encoding="utf-8"))
    changed = False
    for i, block in enumerate(current_blocks):
        signature = _parse_po_entry_signature(block)
        if signature is None:
            continue
        key, values = signature
        if key not in original_entries:
            continue
        original_values, original_block = original_entries[key]
        if values != original_values:
            continue
        if block == original_block:
            continue
        current_blocks[i] = original_block
        changed = True

    if not changed:
        return
    rebuilt = "\n\n".join("\n".join(block) for block in current_blocks)
    po_path.write_text(rebuilt + "\n", encoding="utf-8")

def _update_meson_locales(new_locales: list[str]) -> None:
    """Обновляет список языков в meson.build."""
    if not MESON_BUILD.exists():
        return

    text = MESON_BUILD.read_text(encoding="utf-8")

    # Ищем foreach lang : ['de', 'es', 'pt', 'ru']
    pattern = r"(foreach\s+lang\s*:\s*\[)([^\]]+)(\])"
    match = re.search(pattern, text)
    if not match:
        return

    # Парсим текущий список языков
    current_langs_str = match.group(2)
    current_langs = re.findall(r"'([^']+)'", current_langs_str)

    # Добавляем новые языки и сортируем
    all_langs = sorted(set(current_langs) | set(new_locales))

    # Формируем новый список
    new_langs_str = ", ".join(f"'{lang}'" for lang in all_langs)
    new_text = text[:match.start()] + match.group(1) + new_langs_str + match.group(3) + text[match.end():]

    if new_text != text:
        MESON_BUILD.write_text(new_text, encoding="utf-8")
        print(f"Updated meson.build with locales: {all_langs}")

def create_new(locales: list[str]) -> None:
    if not POT_FILE.exists():
        extract_strings()
    for locale in locales:
        CommandLineInterface().run([
            "pybabel", "init",
            f"--input-file={POT_FILE.resolve()}",
            f"--output-dir={LOCALES_PATH.resolve()}",
            "--domain=portprotonqt",
            "--no-wrap",
            f"--locale={locale}"
        ])
    # Обновляем meson.build с новыми локалями
    _update_meson_locales(locales)

# ---------- Основной обработчик ----------
def main(args) -> int:
    if args.update_all:
        extract_strings(); update_locales()
    if args.create_new:
        create_new(args.create_new)
    compile_locales()
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="l10n", description="Localization utility for PortProtonQt.")
    parser.add_argument("--create-new", nargs='+', type=str, default=False, help="Create .po for new locales")
    parser.add_argument("--update-all", action='store_true', help="Extract/update locales")
    args = parser.parse_args()
    sys.exit(main(args))
