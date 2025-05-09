📘 Эта документация также доступна на [русском.](README.ru.md)

---

## 📋 Contents
- [Overview](#overview)
- [Adding a New Translation](#adding-a-new-translation)
- [Updating Existing Translations](#updating-existing-translations)
- [Compiling Translations](#compiling-translations)

---

## 📖 Overview

Localization in `PortProtonQT` is powered by `Babel` using `.po/.mo` files stored under `LC_MESSAGES/messages.po` for each language.

Current translation status:

<!-- Auto-generated coverage table -->

| Locale | Progress | Translated |
| :----- | -------: | ---------: |
| [de_DE](./de_DE/LC_MESSAGES/messages.po) | 0% | 0 of 108 |
| [es_ES](./es_ES/LC_MESSAGES/messages.po) | 0% | 0 of 108 |
| [ru_RU](./ru_RU/LC_MESSAGES/messages.po) | 100% | 108 of 108 |

---


## 🏁 Adding a New Translation

1. Run:

```bash
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
python dev-scripts/l10n.py --create-new <locale_code>
```

2. Edit the file `portprotonqt/locales/<locale>/LC_MESSAGES/messages.po` in Poedit or any text editor.

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
