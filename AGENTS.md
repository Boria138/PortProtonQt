# PortProtonQt — Инструкция для AI-агентов

**Проект:** PortProtonQt — GUI для управления играми из PortProton, Steam и Epic Games Store
**Язык:** Python 3.10+
**Платформа:** Linux (POSIX)
**Лицензия:** GPL-3.0
**Сборка:** Meson + uv

---

## 🎯 Core Principles (ALWAYS apply)

| Principle | ✅ Do | ❌ Never |
|-----------|------|---------|
| KISS | ≤30 lines functions | Nested if hell |
| YAGNI | Concrete code | Future abstractions |
| DRY | Extract methods | Copy-paste |
| SRP | 1 task per method | God functions |
| Linux | /usr/bin/env, #!/bin/bash | .bat, cmd.exe |

---

## 📏 Linux Metrics

| Check | Target |
|-------|--------|
| Shebang | `#!/usr/bin/env python3` |
| Paths | `/tmp/`, `$HOME/`, `~` |
| EOL | LF only |
| Commit | English, ≤72 chars |
| Functions | ≤30 lines, ≤4 params |
| Files | ≤800 lines |
| Nesting | ≤4 levels |

---

## 🚫 Forbidden Patterns

```python
# ❌ NEVER — 6+ parameters
def process_game(user, ctx, log, val, map, cache):
    ...

# ✅ ALWAYS — ≤4 parameters
def process_game(game_id: str, config: dict) -> Game:
    """Краткое описание."""
    ...
```

```python
# ❌ NEVER — Deep nesting
if condition1:
    if condition2:
        if condition3:
            if condition4:
                ...

# ✅ ALWAYS — Early returns
if not condition1:
    return
if not condition2:
    return
...
```

```python
# ❌ NEVER — print statements
print(f"Game {name} started")

# ✅ ALWAYS — logging
from portprotonqt.logger import get_logger
logger = get_logger(__name__)
logger.info("Game %s started", name)
```

---

## 🏗️ Project Structure

```
PortProtonQt/
├── portprotonqt/          # Main Python package
│   ├── app.py            # Entry point
│   ├── main_window.py    # Main window
│   ├── game_card.py      # Game card widget
│   ├── steam_api.py      # Steam integration
│   ├── egs_api.py        # Epic Games integration
│   ├── theme_manager.py  # Theme management
│   ├── logger.py         # Logging module
│   └── themes/           # Theme files (styles.py)
├── build-aux/            # Build resources (icons, desktop, udev)
├── dev-scripts/          # Development scripts
├── documentation/        # Documentation
├── meson.build          # Meson configuration
├── pyproject.toml       # Python/uv configuration
└── .pre-commit-config.yaml
```

---

## 🛠️ Development Workflow

### Setup (development)

```bash
uv python install 3.10
uv sync
source .venv/bin/activate
pre-commit install
```

### Run

```bash
portprotonqt
```

### Pre-commit checks

```bash
# Automatic on commit
pre-commit run --all-files

# Manual
pre-commit run ruff-check --all-files
pre-commit run pyright --all-files
pre-commit run uv-lock --all-files
```

### Build (release)

```bash
meson setup builddir
meson compile -C builddir
meson install -C builddir
```

---

## 📋 AI Agent Checklist

### When writing code

- [ ] Functions ≤30 lines
- [ ] Parameters ≤4
- [ ] Nesting ≤4 levels
- [ ] LF line endings
- [ ] Type hints
- [ ] Logging via `portprotonqt.logger`, not `print`
- [ ] Error handling (try/except)

### When refactoring

- [ ] No code duplicates
- [ ] No unused imports
- [ ] No commented-out code
- [ ] No TODO without tickets
- [ ] Clear variable names (not `x`, `tmp`, `data`)

### When adding dependencies

- [ ] Check license (GPL-3.0 compatible)
- [ ] Add to `pyproject.toml`
- [ ] Run `uv lock`

---

## 🔒 Security (CRITICAL)

```python
# ❌ NEVER — Hardcoded credentials
API_KEY = "sk-abc123..."

# ✅ ALWAYS — Environment variables
API_KEY = os.getenv("API_KEY")
```

```python
# ❌ NEVER — Path traversal
file_path = f"/data/{user_filename}"

# ✅ ALWAYS — Sanitize paths
file_path = os.path.join(BASE_DIR, os.path.basename(user_filename))
```

---

## 📝 Code Style

### Imports

```python
# Standard library
import os
from pathlib import Path

# Third-party
from PySide6.QtWidgets import QApplication
import requests

# Local (absolute imports)
from portprotonqt.steam_api import SteamAPI
from portprotonqt.game_card import GameCard
from portprotonqt.logger import get_logger
```

### Type hints

```python
def get_game(game_id: str, cache: dict | None = None) -> Game | None:
    ...

class Game:
    name: str
    playtime: int
    cover_url: str | None
```

### Logging

```python
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

logger.debug("Debug message")
logger.info("Game %s started", name)
logger.warning("Low disk space")
logger.error("Failed to load: %s", error)
```

### Exceptions

```python
try:
    risky_operation()
except SpecificError as e:
    logger.error("Operation failed: %s", e)
    raise
```

---

## 🎨 Themes

### Theme structure

```
portprotonqt/themes/
└── theme_name/
    ├── styles.py      # QSS styles
    ├── metadata.json  # Theme metadata
    └── icons/         # Theme icons
```

### Validate themes

```bash
python dev-scripts/check_qss_properties.py
```

> [!WARNING]
> `styles.py` is a regular Python file. Check third-party themes for malicious code.

---

## 🌐 Localization

### Usage

```python
from portprotonqt.localization import get_translation
_ = get_translation()

label = _("Game")
```

### Update translations

```bash
uv sync --all-extras --dev
source .venv/bin/activate

# Update all .po files
python dev-scripts/l10n.py --update-all

# Compile .mo files
python dev-scripts/l10n.py

# Spell check
python dev-scripts/l10n.py --spellcheck
```

### Add new language

```bash
python dev-scripts/l10n.py --create-new <locale_code>
```

---

## 🧹 Dead Code Removal

```bash
# Find unused imports
ruff check --select=F401 portprotonqt/

# Find unused variables
ruff check --select=F841 portprotonqt/

# Type check
pyright portprotonqt/
```

---

## 📦 Dependencies

### Core

- **PySide6** — GUI framework
- **Legendary** — Epic Games integration (GPL-3.0)
- **Icoextract** — Icon extraction (MIT)
- **HowLongToBeat API** — Playtime data (MIT)
- **Requests** — HTTP requests
- **Pillow** — Image handling

### License compatibility

- ✅ MIT, Apache-2.0, BSD — compatible with GPL-3.0
- ⚠️ LGPL — requires dynamic linking
- ❌ Proprietary — incompatible

---

## 🚀 Release Process

```bash
# Update version in pyproject.toml and meson.build
# Update CHANGELOG.md

git commit -m "chore: bump version to 0.1.12"
```

### Changelog format

```markdown
## [0.1.12] - 2026-02-19

### Added
- New feature X

### Fixed
- Bug Y

### Changed
- Improved performance Z
```

---

## 🔍 Code Review Guidelines

### When invoked for review:

1. Run `git diff` to see recent changes
2. Focus on modified files
3. Begin review immediately

### Review Checklist

- [ ] Code is simple and readable
- [ ] Functions and variables are well-named
- [ ] No duplicated code
- [ ] Proper error handling
- [ ] No exposed secrets or API keys
- [ ] Input validation implemented
- [ ] Performance considerations addressed
- [ ] Time complexity analyzed
- [ ] Licenses of integrated libraries checked

### Security Checks (CRITICAL)

- Hardcoded credentials (API keys, passwords, tokens)
- SQL injection risks (string concatenation in queries)
- Missing input validation
- Insecure dependencies (outdated, vulnerable)
- Path traversal risks (user-controlled file paths)
- Authentication bypasses

### Code Quality (HIGH)

- Large functions (>50 lines)
- Large files (>800 lines)
- Deep nesting (>4 levels)
- Missing error handling (try/except)
- Missing tests for new code

### Performance (MEDIUM)

- Inefficient algorithms (O(n²) when O(n log n) possible)
- Missing caching
- N+1 queries

### Best Practices (MEDIUM)

- Emoji usage in code/comments
- TODO/FIXME without tickets
- Accessibility issues (missing ARIA labels, poor contrast)
- Poor variable naming (x, tmp, data)
- Magic numbers without explanation
- Inconsistent formatting

### Review Output Format

For each issue:

```
[CRITICAL] Hardcoded API key
File: portprotonqt/steam_api.py:42
Issue: API key exposed in source code
Fix: Move to environment variable

API_KEY = "sk-abc123"  # ❌ Bad
API_KEY = os.getenv("API_KEY")  # ✓ Good
```

### Approval Criteria

- ✅ **Approve:** No CRITICAL or HIGH issues
- ⚠️ **Warning:** MEDIUM issues only (can merge with caution)
- ❌ **Block:** CRITICAL or HIGH issues found

### Project-Specific Guidelines

- Follow MANY SMALL FILES principle (200-400 lines typical)
- No emojis in codebase
- Verify theme security (check `styles.py` for malicious code)
- Check Steam/EGS API integration error handling
- Validate cache fallback behavior

---

## 🆘 Troubleshooting

```bash
# Pre-commit not running
pre-commit install --install-hooks

# Check specific file
pyright portprotonqt/game_card.py

# Ruff checks
ruff check portprotonqt/
```

---

## 📚 Resources

- [Theme documentation](documentation/theme_guide)
- [Localization guide](documentation/localization_guide)
- [Metadata override guide](documentation/metadata_override)
- [TODO list](TODO.md)
- [Changelog](CHANGELOG.md)

---

## ⚡ Quick Reference

```bash
# Setup
uv sync && source .venv/bin/activate

# Run
portprotonqt

# Checks
ruff check && pyright && pre-commit run --all-files

# Build
meson setup builddir && meson compile -C builddir

# Localization
python dev-scripts/l10n.py --update-all
python dev-scripts/l10n.py

# Commit
git commit -m "feat: description in English ≤72 chars"
```

---

**Last updated:** 2026-02-19
**Version:** 0.1.11
**Status:** Work in Progress (Beta)
