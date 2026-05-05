#!/usr/bin/env python3

import argparse
import sys
import re
import ast
import subprocess
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from babel.messages.frontend import CommandLineInterface
from pyaspeller import YandexSpeller

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

# ---------- Игнорируемые префиксы для spellcheck ----------
IGNORED_PREFIXES = ()

def load_ignored_prefixes(ignore_file=".spellignore"):
    path = Path(__file__).parent / ignore_file
    try:
        return tuple(path.read_text(encoding='utf-8').splitlines())
    except FileNotFoundError:
        return ()

IGNORED_PREFIXES = load_ignored_prefixes() + ("PortProton", "flatpak")

# ---------- Проверка fuzzy строк ----------
def find_fuzzy_entries(filepath: Path) -> list[tuple[int, str, str]]:
    """Находит fuzzy записи в .po файле. Возвращает список (номер_строки, msgid, флаги)."""
    fuzzy_entries = []
    lines = filepath.read_text(encoding='utf-8').splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Ищем комментарий с флагами, содержащий fuzzy
        if line.startswith('#,') and 'fuzzy' in line:
            flags = line[2:].strip()
            line_num = i + 1
            # Ищем следующий msgid
            msgid = ""
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line.startswith('msgid '):
                    match = re.match(r'^msgid\s+"(.*)"', next_line)
                    if match:
                        msgid = match.group(1)
                    i += 1
                    # Собираем многострочный msgid
                    while i < len(lines) and lines[i].strip().startswith('"'):
                        msgid += lines[i].strip()[1:-1]
                        i += 1
                    break
                i += 1
            # Пропускаем пустой msgid (заголовок PO файла)
            if msgid:
                fuzzy_entries.append((line_num, msgid, flags))
        else:
            i += 1
    return fuzzy_entries

# ---------- Проверка орфографии с параллелизмом ----------
speller = YandexSpeller()
MSGID_RE = re.compile(r'^msgid\s+"(.*)"')
MSGSTR_RE = re.compile(r'^msgstr\s+"(.*)"')

def extract_po_strings(filepath: Path) -> list[str]:
    # Collect all strings, then filter by ignore list
    texts, current_key, buffer = [], None, ""
    def flush():
        nonlocal buffer
        if buffer.strip():
            texts.append(buffer)
        buffer = ""
    for line in filepath.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if stripped.startswith("msgid ") and filepath.suffix == '.pot':
            flush(); current_key = 'msgid'; buffer = MSGID_RE.match(stripped).group(1) or ''
        elif stripped.startswith("msgstr "):
            flush(); current_key = 'msgstr'; buffer = MSGSTR_RE.match(stripped).group(1) or ''
        elif stripped.startswith('"') and stripped.endswith('"') and current_key:
            buffer += stripped[1:-1]
        else:
            flush(); current_key = None
    flush()
    # Final filter: remove ignored and multi-line
    return [
        t for t in texts
        if t.strip() and all(pref not in t for pref in IGNORED_PREFIXES) and "\n" not in t
    ]

def _check_text(text: str) -> tuple[str, list[dict]]:
    result = speller.spell(text)
    errors = [r for r in result if r.get('word') and r.get('s')]
    return text, errors

def check_file(filepath: Path, issues_summary: dict) -> bool:
    print(f"Checking file: {filepath}")
    texts = extract_po_strings(filepath)
    has_errors = False
    printed_err = False
    with ThreadPoolExecutor(max_workers=8) as pool:
        for text, errors in pool.map(_check_text, texts):
            print(f'  In string: "{text}"')
            if errors:
                if not printed_err:
                    print(f"❌ Errors in file: {filepath}")
                    printed_err = True
                has_errors = True
                for err in errors:
                    print(f"    - typo: {err['word']}, suggestions: {', '.join(err['s'])}")
                issues_summary[filepath].extend([(text, err) for err in errors])
    return has_errors

def get_spellcheck_files(paths: list[str]) -> list[Path]:
    if not paths:
        return list(LOCALES_PATH.glob("**/portprotonqt.po")) + [POT_FILE]

    files = []
    for path in paths:
        file_path = Path(path)
        if file_path.suffix not in {'.po', '.pot'}:
            continue
        files.append(file_path)
    return files

def get_changed_translation_files(base: str, head: str) -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base, head, "--", "portprotonqt/locales"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return []

    files = []
    for path in result.stdout.splitlines():
        file_path = Path(path)
        if file_path.suffix != ".po":
            continue
        if _has_changed_translations(file_path, base, head):
            files.append(file_path)
    return files

def _has_changed_translations(po_path: Path, base: str, head: str) -> bool:
    old_text = _read_git_file(base, po_path)
    if old_text is None:
        old_entries = {}
    else:
        old_entries = _po_translation_map(old_text)
    current_text = _read_git_file(head, po_path)
    if current_text is None:
        return False
    current_entries = _po_translation_map(current_text)

    for key, values in current_entries.items():
        if not _has_translation(values):
            continue
        if old_entries.get(key) != values:
            return True
    return False

def _read_git_file(ref: str, path: Path) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path.as_posix()}"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout

def _po_translation_map(text: str) -> dict[str, tuple[tuple[str, str], ...]]:
    entries = {}
    for block in _split_po_blocks(text):
        signature = _parse_po_entry_signature(block)
        if signature is None:
            continue
        key, values = signature
        entries[key] = values
    return entries

def _has_translation(values: tuple[tuple[str, str], ...]) -> bool:
    return any(value.strip() for _, value in values)

# ---------- Основной обработчик ----------
def main(args) -> int:
    if args.update_all:
        extract_strings(); update_locales()
    if args.create_new:
        create_new(args.create_new)
    if args.spellcheck:
        if args.changed_since:
            files = get_changed_translation_files(args.changed_since, args.changed_to)
        else:
            files = get_spellcheck_files(args.files)
        if not files:
            print("No changed translations to check.")
            return 0
        seen = set(); has_err = False
        issues_summary = defaultdict(list)
        fuzzy_summary = defaultdict(list)
        for f in files:
            if not f.exists() or f in seen: continue
            seen.add(f)
            # Проверка fuzzy строк (только для .po файлов)
            if f.suffix == '.po':
                fuzzy_entries = find_fuzzy_entries(f)
                if fuzzy_entries:
                    fuzzy_summary[f] = fuzzy_entries
                    has_err = True
            if check_file(f, issues_summary):
                has_err = True
            else:
                if f not in fuzzy_summary:
                    print(f"✅ {f} — no errors found.")
        # Вывод fuzzy строк
        if fuzzy_summary:
            print("\n⚠️  Fuzzy Entries (require review before release):")
            for file, entries in fuzzy_summary.items():
                print(f"\n⚠ {file}")
                print("-----")
                for idx, (line_num, msgid, flags) in enumerate(entries, 1):
                    print(f"{idx}. Line {line_num}: [{flags}]")
                    print(f"   msgid: \"{msgid[:80]}{'...' if len(msgid) > 80 else ''}\"")
                print("-----")
        # Вывод орфографических ошибок
        if issues_summary:
            print("\n📋 Summary of Spelling Errors:")
            for file, errs in issues_summary.items():
                print(f"\n✗ {file}")
                print("-----")
                for idx, (text, err) in enumerate(errs, 1):
                    print(f"{idx}. In '{text}': typo '{err['word']}', suggestions: {', '.join(err['s'])}")
                print("-----")
        return 1 if has_err else 0
    extract_strings(); compile_locales()
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="l10n", description="Localization utility for PortProtonQt.")
    parser.add_argument("--create-new", nargs='+', type=str, default=False, help="Create .po for new locales")
    parser.add_argument("--update-all", action='store_true', help="Extract/update locales")
    parser.add_argument("--spellcheck", action='store_true', help="Run spellcheck on POT and PO files")
    parser.add_argument("--changed-since", type=str, default="", help="Check only PO files with changed translations")
    parser.add_argument("--changed-to", type=str, default="HEAD", help="Target ref for --changed-since")
    parser.add_argument("files", nargs='*', help="Files to check with --spellcheck")
    args = parser.parse_args()
    sys.exit(main(args))
