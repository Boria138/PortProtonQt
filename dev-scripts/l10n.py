#!/usr/bin/env python3

import argparse
import contextlib
import io
import re
import subprocess
from pathlib import Path
from babel.messages.frontend import CommandLineInterface

GUIDE_DIR    = Path(__file__).parent.parent / "documentation" / "localization_guide"
README_EN    = GUIDE_DIR / "README.md"
README_RU    = GUIDE_DIR / "README.ru.md"
LOCALES_PATH = Path(__file__).parent.parent / "portprotonqt" / "locales"
THEMES_PATH = Path(__file__).parent.parent / "portprotonqt" / "themes"
README_FILES = [README_EN, README_RU]


def _get_version() -> str:
    version = "0.1.0"
    return version


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


def compile_locales() -> None:
    CommandLineInterface().run(
        [
            "pybabel",
            "compile",
            "--use-fuzzy",
            "--directory",
            f"{LOCALES_PATH.resolve()}",
            "--statistics",
        ]
    )


def extract_strings() -> None:
    input_dir = (Path(__file__).parent.parent / "portprotonqt").resolve()
    CommandLineInterface().run(
        [
            "pybabel",
            "extract",
            "--project=PortProtonQT",
            f"--version={_get_version()}",
            "--width=79",
            "--strip-comment-tag",
            "--no-location",
            f"--input-dir={input_dir}",
            f"--ignore-dirs={THEMES_PATH}",
            f"--output-file={(LOCALES_PATH / 'messages.pot').resolve()}",
        ]
    )


def update_locales() -> None:
    CommandLineInterface().run(
        [
            "pybabel",
            "update",
            f"--input-file={(LOCALES_PATH / 'messages.pot').resolve()}",
            f"--output-dir={LOCALES_PATH.resolve()}",
            "--width=79",
            "--ignore-obsolete",
        ]
    )


def create_new(locales: list[str]) -> None:
    for locale in locales:
        CommandLineInterface().run(
            [
                "pybabel",
                "init",
                f"--input-file={(LOCALES_PATH / 'messages.pot').resolve()}",
                f"--output-dir={LOCALES_PATH.resolve()}",
                f"--locale={locale}",
            ]
        )


def main(args: argparse.Namespace) -> None:
    if args.update_all:
        extract_strings()
        update_locales()
    if args.create_new:
        pot_file = LOCALES_PATH / "messages.pot"
        if not pot_file.exists():
            extract_strings()
        create_new(locales=args.create_new)
    compile_locales()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="l10n",
        description="Compile NormCap localizations to .mo-files.",
    )
    parser.add_argument(
        "--create-new",
        action="store",
        type=str,
        default=False,
        help="Create locales (.po) for one or more new locales (e.g. de_DE).",
        nargs="+",
    )
    parser.add_argument(
        "--update-all",
        action="store_true",
        default=False,
        help="Also extract strings (.pot) and update locales (.po).",
    )
    args = parser.parse_args()

    try:
        # Run commands while capturing output to generate stats.
        f = io.StringIO()
        with contextlib.redirect_stderr(f), contextlib.redirect_stdout(f):
            main(args)
        output = f.getvalue()
        print(output, flush=True)  # noqa: T201
        _update_coverage(lines=output.splitlines())
    except Exception:
        # In case of error, run again without output capturing
        main(args)
