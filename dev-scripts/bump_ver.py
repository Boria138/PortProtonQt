#!/usr/bin/env python3

import argparse
import re
from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).parent.parent
# Specific project files
APPIMAGE_RECIPE = BASE_DIR / "build-aux" / "AppImageBuilder.yml"
ARCH_PKGBUILD = BASE_DIR / "build-aux" / "PKGBUILD"
FEDORA_SPEC = BASE_DIR / "build-aux" / "fedora.spec"
PYPROJECT = BASE_DIR / "pyproject.toml"
APP_PY = BASE_DIR / "portprotonqt" / "app.py"
GITHUB_WORKFLOW = BASE_DIR / ".github" / "workflows" / "build.yml"
GITEA_WORKFLOW = BASE_DIR / ".gitea" / "workflows" / "build.yml"

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


def bump_app_py(path: Path, old: str, new: str) -> bool:
    """
    Update __app_version__ in app.py
    """
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r"(?m)^(\s*__app_version__\s*=\s*)\"" + re.escape(old) + r"\"$")
    new_text, count = pattern.subn(lambda m: m.group(1) + f'"{new}"', text)
    if count:
        path.write_text(new_text, encoding='utf-8')
    return bool(count)


def bump_workflow(path: Path, old: str, new: str) -> bool:
    """
    Update VERSION in GitHub or Gitea Actions workflow
    """
    if not path.exists():
        return False
    text = path.read_text(encoding='utf-8')
    pattern = re.compile(r"(?m)^(\s*VERSION:\s*)" + re.escape(old) + r"$")
    new_text, count = pattern.subn(lambda m: m.group(1) + new, text)
    if count:
        path.write_text(new_text, encoding='utf-8')
    return bool(count)


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
        (PYPROJECT, bump_pyproject),
        (APP_PY, bump_app_py),
        (GITHUB_WORKFLOW, bump_workflow),
        (GITEA_WORKFLOW, bump_workflow)
    ]

    updated = []
    for path, func in tasks:
        if func(path, old, new):
            updated.append(path.relative_to(BASE_DIR))

    if updated:
        print(f"Updated version from {old} to {new} in {len(updated)} files:")
        for p in sorted(updated):
            print(f" - {p}")
    else:
        print(f"No occurrences of version {old} found in specified files.")


if __name__ == '__main__':
    main()
