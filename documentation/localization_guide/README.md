📘 Эта документация также доступна на [русском.](README.ru.md)

---

## 📋 Contents
- [Overview](#-overview)
- [Translate Online](#-translate-online)
- [Adding a New Translation](#-adding-a-new-translation)
- [Updating Existing Translations](#-updating-existing-translations)
- [Compiling Translations](#-compiling-translations)
- [Spell Check](#-spell-check)

---

## 📖 Overview

Localization in `PortProtonQT` is powered by `Babel` using `.po/.mo` files stored under `LC_MESSAGES/portprotonqt.po` for each language.

Current translation status:

<a href="https://translate.codeberg.org/engage/portprotonqt/">
<img src="https://translate.codeberg.org/widget/portprotonqt/multi-auto.svg" alt="Translation status" />
</a>

---

## 🌐 Translate Online

You can help translate PortProtonQt using our web-based translation platform:

**[translate.codeberg.org/engage/portprotonqt](https://translate.codeberg.org/engage/portprotonqt)**

Benefits of using the web platform:
- No need to set up a development environment
- Work directly in your browser
- See context and suggestions from other translators
- Collaborate with the community

Translations submitted online are periodically reviewed and merged into the main repository.

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
python dev-scripts/l10n.py --compile-only
```

For a run directly from the Git working tree, compile translations locally before launch. Compiled `*.mo` files are not stored in the repository.


## 🔍 Spell Check

To check spelling, run the following commands:

```bash
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
python dev-scripts/l10n.py --spellcheck
```

The script performs parallel spellchecking of strings in `.po` and `.pot` files. For each file, it prints the list of strings being checked and highlights any spelling errors with suggestions. Words listed in `dev-scripts/.spellignore` are ignored and not treated as typos.
