📘 Эта документация также доступна на [русском.](README.ru.md)

---

## 📋 Contents
- [Overview](#-overview)
- [Adding a New Translation](#-adding-a-new-translation)
- [Updating Existing Translations](#-updating-existing-translations)
- [Compiling Translations](#-compiling-translations)
- [Spell Check](#-spell-check)

---

## 📖 Overview

Localization in `PortProtonQT` is powered by `Babel` using `.po/.mo` files stored under `LC_MESSAGES/portprotonqt.po` for each language.

Current translation status:

<!-- Auto-generated coverage table -->

| Locale | Progress | Translated |
| :----- | -------: | ---------: |
| [de](./de/LC_MESSAGES/portprotonqt.po) | 0% | 0 of 397 |
| [es](./es/LC_MESSAGES/portprotonqt.po) | 0% | 0 of 397 |
| [pt](./pt/LC_MESSAGES/portprotonqt.po) | 0% | 0 of 397 |
| [ru](./ru/LC_MESSAGES/portprotonqt.po) | 100% | 397 of 397 |

---


## 🏁 Adding a New Translation

1. Run:

```bash
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
python dev-scripts/l10n.py --create-new <locale_code>
```

2. Edit the file `portprotonqt/locales/<locale>/LC_MESSAGES/portprotonqt.po` in Poedit or GTranslator.

---

## 🔄 Updating Existing Translations

If you’ve added new strings to the code:

```bash
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
python dev-scripts/l10n.py --update-all
```

---

## 🧵 Compiling Translations

```bash
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
python dev-scripts/l10n.py
```


## 🔍 Spell Check

To check spelling, run the following commands:

```bash
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
python dev-scripts/l10n.py --spellcheck
```

The script performs parallel spellchecking of strings in `.po` and `.pot` files. For each file, it prints the list of strings being checked and highlights any spelling errors with suggestions. Words listed in `dev-scripts/.spellignore` are ignored and not treated as typos.
