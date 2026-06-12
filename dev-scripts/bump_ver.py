#!/usr/bin/env python3

import argparse
import re
import subprocess
from pathlib import Path
from datetime import date

# Base directory of the project
BASE_DIR = Path(__file__).parent.parent
# Specific project files
APPIMAGE_RECIPE = BASE_DIR / "build-aux" / "AppImageBuilder.yml"
ARCH_PKGBUILD = BASE_DIR / "build-aux" / "PKGBUILD"
FEDORA_SPEC = BASE_DIR / "build-aux" / "fedora.spec"
FEDORA_GIT_SPEC = BASE_DIR / "build-aux" / "fedora-git.spec"
PYPROJECT = BASE_DIR / "pyproject.toml"
MESON_BUILD = BASE_DIR / "meson.build"
APP_PY = BASE_DIR / "portprotonqt" / "app.py"
GITEA_WORKFLOW = BASE_DIR / ".gitea" / "workflows" / "build.yml"
CHANGELOG = BASE_DIR / "CHANGELOG.md"
METAINFO = BASE_DIR / "build-aux" / "share" / "metainfo" / "ru.linux_gaming.PortProtonQt.metainfo.xml"

def bump_appimage(path: Path, old: str, new: str) -> bool:
    """
    Update only the 'version' field under app_info in AppImageBuilder.yml
    """
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r"(?m)^(\s*version:\s*)" + re.escape(old) + r"$")
    new_text, count = pattern.subn(lambda m: m.group(1) + new, text)
    if count:
        path.write_text(new_text, encoding='utf-8')
    return bool(count)

def bump_arch(path: Path, old: str, new: str) -> bool:
    """
    Update pkgver in PKGBUILD
    """
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r"(?m)^(pkgver=)" + re.escape(old) + r"$")
    new_text, count = pattern.subn(lambda m: m.group(1) + new, text)
    if count:
        path.write_text(new_text, encoding='utf-8')
    return bool(count)

def bump_fedora(path: Path, old: str, new: str) -> bool:
    """
    Update only the '%global pypi_version' line in fedora.spec
    """
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r"(?m)^(%global\s+pypi_version\s+)" + re.escape(old) + r"$")
    new_text, count = pattern.subn(lambda m: m.group(1) + new, text)
    if count:
        path.write_text(new_text, encoding='utf-8')
    return bool(count)


def bump_pyproject(path: Path, old: str, new: str) -> bool:
    """
    Update version in pyproject.toml under [project]
    """
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r"(?m)^(version\s*=\s*)\"" + re.escape(old) + r"\"$")
    new_text, count = pattern.subn(lambda m: m.group(1) + f'"{new}"', text)
    if count:
        path.write_text(new_text, encoding='utf-8')
    return bool(count)

def bump_meson(path: Path, old: str, new: str) -> bool:
    """
    Update version in meson.build
    """
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r"(version:\s*)'" + re.escape(old) + r"'")
    new_text, count = pattern.subn(lambda m: m.group(1) + f"'{new}'", text)
    if count:
        path.write_text(new_text, encoding='utf-8')
    return bool(count)

def bump_app_py(path: Path, old: str, new: str) -> bool:
    """
    Update APP_VERSION fallback in app.py
    """
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r"(?m)^(\s*APP_VERSION\s*=\s*)\"" + re.escape(old) + r"\"$")
    new_text, count = pattern.subn(lambda m: m.group(1) + f'"{new}"', text)
    if count:
        path.write_text(new_text, encoding='utf-8')
    return bool(count)

def bump_workflow(path: Path, old: str, new: str) -> bool:
    """
    Update VERSION in Gitea Actions workflow
    """
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r"(?m)^(\s*VERSION:\s*)" + re.escape(old) + r"$")
    new_text, count = pattern.subn(lambda m: m.group(1) + new, text)
    if count:
        path.write_text(new_text, encoding='utf-8')
    return bool(count)

def bump_changelog(path: Path, old: str, new: str) -> bool:
    """
    Update [Unreleased] to [new] - YYYY-MM-DD in CHANGELOG.md
    """
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r"(?m)^##\s*\[Unreleased\]$")
    current_date = date.today().strftime('%Y-%m-%d')
    new_text, count = pattern.subn(f"## [{new}] - {current_date}", text)
    if count:
        path.write_text(new_text, encoding='utf-8')
    return bool(count)

def bump_metainfo(path: Path, old: str, new: str) -> bool:
    """
    Update releases in metainfo:
    1. Change old version's <description></description> to <description/>
    2. Prepend new version with <description></description>
    """
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')

    # 1. Update the old version entry to use self-closing description
    # Match tag starting with <release version="OLD" and ending with >
    old_pattern = re.compile(
        r'(<release version="' + re.escape(old) + r'"[^>]*>)\s*<description></description>\s*(</release>)',
        re.DOTALL
    )

    current_date = date.today().strftime('%Y-%m-%d')
    type_attr = ' type="development"' if new.startswith('0.') else ''
    new_entry = (
        f'    <release version="{new}" date="{current_date}"{type_attr}>\n'
        f'      <description></description>\n'
        f'    </release>'
    )

    # Replace old entry's description with self-closing
    new_text, count = old_pattern.subn(r'\1\n      <description/>\n    \2', text, count=1)

    if count:
        # 2. Insert the new entry at the beginning of the <releases> tag
        new_text = new_text.replace('<releases>', f'<releases>\n{new_entry}')
        path.write_text(new_text, encoding='utf-8')
        return True

    # Fallback if old version wasn't found with expected pattern
    if f'version="{new}"' not in text:
         new_text = text.replace('<releases>', f'<releases>\n{new_entry}')
         path.write_text(new_text, encoding='utf-8')
         return True

    return False

def main():
    parser = argparse.ArgumentParser(description='Bump project version in specific files')
    parser.add_argument('old', help='Old version string')
    parser.add_argument('new', help='New version string')
    args = parser.parse_args()
    old, new = args.old, args.new

    tasks = [
        (APPIMAGE_RECIPE, bump_appimage),
        (ARCH_PKGBUILD, bump_arch),
        (FEDORA_SPEC, bump_fedora),
        (FEDORA_GIT_SPEC, bump_fedora),
        (PYPROJECT, bump_pyproject),
        (MESON_BUILD, bump_meson),
        (APP_PY, bump_app_py),
        (GITEA_WORKFLOW, bump_workflow),
        (CHANGELOG, bump_changelog),
        (METAINFO, bump_metainfo)
    ]

    updated = []
    for path, func in tasks:
        if func(path, old, new):
            updated.append(path.relative_to(BASE_DIR))

    if updated:
        print(f"Updated version from {old} to {new} in {len(updated)} files:")
        for p in sorted(updated):
            print(f" - {p}")

        try:
            subprocess.run(["uv", "lock"], check=True)
            print("Regenerated uv.lock")
        except subprocess.CalledProcessError as e:
            print(f"Failed to regenerate uv.lock: {e}")
    else:
        print(f"No occurrences of version {old} found in specified files.")

if __name__ == '__main__':
    main()
