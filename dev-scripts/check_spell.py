#!/usr/bin/env python3
import re
import sys
import os
import glob
from pyaspeller import YandexSpeller

speller = YandexSpeller()

MSGID_RE = re.compile(r'^msgid\s+"(.*)"')
MSGSTR_RE = re.compile(r'^msgstr\s+"(.*)"')

def load_ignored_prefixes(ignore_file=".spellignore"):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ignore_path = os.path.join(script_dir, ignore_file)
    try:
        with open(ignore_path, encoding='utf-8') as f:
            return tuple(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        print(f"Ignore file {ignore_path} not found. Using empty ignore list.")
        return ()

IGNORED_PREFIXES = load_ignored_prefixes()

def extract_po_strings(filepath):
    with open(filepath, encoding='utf-8') as f:
        lines = f.readlines()

    texts = []
    current_key = None
    buffer = ""

    def flush():
        nonlocal buffer
        if buffer.strip():
            texts.append(buffer)
        buffer = ""

    for line in lines:
        line = line.strip()
        if line.startswith("msgid ") and filepath.endswith('.pot'):
            flush()
            current_key = "msgid"
            buffer = MSGID_RE.match(line).group(1) if MSGID_RE.match(line) else ""
        elif line.startswith("msgstr "):
            flush()
            current_key = "msgstr"
            buffer = MSGSTR_RE.match(line).group(1) if MSGSTR_RE.match(line) else ""
        elif line.startswith('"') and line.endswith('"') and current_key:
            buffer += line[1:-1]
        else:
            flush()
            current_key = None

    flush()
    return [
        t for t in texts
        if t.strip() and not any(prefix in t for prefix in IGNORED_PREFIXES) and "\n" not in t
    ]

def check_file(filepath):
    texts = extract_po_strings(filepath)
    issues = []  # For summary (only strings with errors)
    has_errors = False
    header_printed = False

    for text in texts:
        results = speller.spell(text)
        valid_results = [r for r in results if r.get('word') and r.get('s')]
        if valid_results:
            if not header_printed:
                print(f"\n❌ Errors in file: {filepath}")
                header_printed = True
            has_errors = True
            print(f'  In string: "{text}"')
            for err in valid_results:
                word = err.get('word')
                suggestions = ', '.join(err.get('s', []))
                print(f"    - typo: {word}, suggestions: {suggestions}")
            issues.append((text, valid_results))
        else:
            if not header_printed:
                print(f"\nChecking file: {filepath}")
                header_printed = True
            print(f'  In string: "{text}"')

    return issues, has_errors

def print_help():
    print("Usage:")
    print("  ./check-spell.py [files or glob patterns]")
    print("Examples:")
    print("  ./check-spell.py portprotonqt/locales/**/*.po")
    print("  ./check-spell.py translations.pot")
    print("Description:")
    print("  Checks spelling of msgid/msgstr strings in .po/.pot files using YandexSpeller.")
    print("  You can use a .spellignore file to exclude strings containing known words/phrases.")

def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print_help()
        return 0

    files = []
    for arg in sys.argv[1:]:
        if arg.endswith(('.po', '.pot')):
            files.extend(glob.glob(arg, recursive=True))

    files = sorted(set(files))
    if not files:
        print("No .po or .pot files found.")
        return 0

    has_errors = False
    all_issues = []  # Store only issues with spelling errors for summary

    for file in files:
        issues, file_has_errors = check_file(file)
        if file_has_errors:
            has_errors = True
            all_issues.extend([(file, text, errors) for text, errors in issues])
        else:
            print(f"✅ {file} — no errors found.")

    # Print summary of spelling errors only
    if has_errors:
        print("\n📋 Summary of Spelling Errors:")
        # Group issues by file
        from collections import defaultdict
        issues_by_file = defaultdict(list)
        for file, text, errors in all_issues:
            issues_by_file[file].append((text, errors))

        for file, file_issues in issues_by_file.items():
            print(f"\n✗ {file}")
            print("-----")
            typo_count = sum(len(errors) for _, errors in file_issues)
            print(f"Typos: {typo_count}")
            typo_index = 1
            for text, errors in file_issues:
                for err in errors:
                    word = err.get('word')
                    suggestions = ', '.join(err.get('s', []))
                    print(f"{typo_index}. {word} (suggest: {suggestions})")
                    typo_index += 1
            print("-----")

    return 1 if has_errors else 0

if __name__ == "__main__":
    sys.exit(main())
