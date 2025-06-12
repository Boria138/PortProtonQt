#!/usr/bin/env python3

import argparse
import sys
import io
import contextlib
import re
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from babel.messages.frontend import CommandLineInterface
from pyaspeller import YandexSpeller

# ---------- Пути ----------
GUIDE_DIR    = Path(__file__).parent.parent / "documentation" / "localization_guide"
README_EN    = GUIDE_DIR / "README.md"
README_RU    = GUIDE_DIR / "README.ru.md"
LOCALES_PATH = Path(__file__).parent.parent / "portprotonqt" / "locales"
THEMES_PATH  = Path(__file__).parent.parent / "portprotonqt" / "themes"
README_FILES = [README_EN, README_RU]
POT_FILE     = LOCALES_PATH / "messages.pot"

# ---------- Версия проекта ----------
def _get_version() -> str:
    return "0.1.1"

# ---------- Обновление README ----------
def _update_coverage(lines: list[str]) -> None:
    # Парсим статистику из вывода pybabel --statistics
    locales_stats = [line for line in lines if line.endswith(".po")]
    # Извлекаем (count, pct, locale) и сортируем
    rows = sorted(
        (m := re.search(
            r"""(\d+\ of\ \d+).*         # message counts
            \((\d+\%)\).*                # message percentage
            locales\/(.*)\/LC_MESSAGES  # locale name""",
            stat, re.VERBOSE
        )) and m.groups()
        for stat in locales_stats
    )

    for md_file in README_FILES:
        if not md_file.exists():
            continue

        text = md_file.read_text(encoding="utf-8")
        is_ru = (md_file == README_RU)

        # Выбираем заголовок раздела
        status_header = (
            "Current translation status:" if not is_ru
            else "Текущий статус перевода:"
        )

        # Формируем шапку и строки таблицы
        if is_ru:
            table_header = (
                "<!-- Сгенерировано автоматически! -->\n\n"
                "| Локаль | Прогресс | Переведено |\n"
                "| :----- | -------: | ---------: |\n"
            )
            fmt = lambda count, pct, loc: f"| [{loc}](./{loc}/LC_MESSAGES/messages.po) | {pct} | {count.replace(' of ', ' из ')} |"
        else:
            table_header = (
                "<!-- Auto-generated coverage table -->\n\n"
                "| Locale | Progress | Translated |\n"
                "| :----- | -------: | ---------: |\n"
            )
            fmt = lambda count, pct, loc: f"| [{loc}](./{loc}/LC_MESSAGES/messages.po) | {pct} | {count} |"

        # Собираем строки и добавляем '---' в конце
        coverage_table = (
            table_header
            + "\n".join(fmt(c, p, l) for c, p, l in rows)
            + "\n\n---"
        )

        # Удаляем старую автоматически сгенерированную таблицу
        old_block = (
            r"<!--\s*(?:Сгенерировано автоматически!|Auto-generated coverage table)\s*-->"
            r".*?(?=\n(?:##|\Z))"
        )
        cleaned = re.sub(old_block, "", text, flags=re.DOTALL)

        # Вставляем новую таблицу сразу после строки с заголовком
        insert_pattern = rf"(^.*{re.escape(status_header)}.*$)"
        new_text = re.sub(
            insert_pattern,
            lambda m: m.group(1) + "\n\n" + coverage_table,
            cleaned,
            count=1,
            flags=re.MULTILINE
        )

        # Записываем файл, если были изменения
        if new_text != text:
            md_file.write_text(new_text, encoding="utf-8")

# ---------- PyBabel команды ----------
def compile_locales() -> None:
    CommandLineInterface().run([
        "pybabel", "compile", "--use-fuzzy", "--directory",
        f"{LOCALES_PATH.resolve()}", "--statistics"
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
    CommandLineInterface().run([
        "pybabel", "update",
        f"--input-file={POT_FILE.resolve()}",
        f"--output-dir={LOCALES_PATH.resolve()}",
        "--ignore-obsolete",
        "--update-header-comment",
    ])

def create_new(locales: list[str]) -> None:
    if not POT_FILE.exists():
        extract_strings()
    for locale in locales:
        CommandLineInterface().run([
            "pybabel", "init",
            f"--input-file={POT_FILE.resolve()}",
            f"--output-dir={LOCALES_PATH.resolve()}",
            f"--locale={locale}"
        ])

# ---------- Игнорируемые префиксы для spellcheck ----------
IGNORED_PREFIXES = ()

def load_ignored_prefixes(ignore_file=".spellignore"):
    path = Path(__file__).parent / ignore_file
    try:
        return tuple(path.read_text(encoding='utf-8').splitlines())
    except FileNotFoundError:
        return ()

IGNORED_PREFIXES = load_ignored_prefixes() + ("PortProton", "flatpak")

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

# ---------- Основной обработчик ----------
def main(args) -> int:
    if args.update_all:
        extract_strings(); update_locales()
    if args.create_new:
        create_new(args.create_new)
    if args.spellcheck:
        files = list(LOCALES_PATH.glob("**/*.po")) + [POT_FILE]
        seen = set(); has_err = False
        issues_summary = defaultdict(list)
        for f in files:
            if not f.exists() or f in seen: continue
            seen.add(f)
            if check_file(f, issues_summary):
                has_err = True
            else:
                print(f"✅ {f} — no errors found.")
        if has_err:
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
    parser.add_argument("--update-all", action='store_true', help="Extract/update locales and update README coverage")
    parser.add_argument("--spellcheck", action='store_true', help="Run spellcheck on POT and PO files")
    args = parser.parse_args()
    if args.spellcheck:
        sys.exit(main(args))
    f = io.StringIO()
    with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        main(args)
    output = f.getvalue().splitlines()
    _update_coverage(output)
    sys.exit(0)
