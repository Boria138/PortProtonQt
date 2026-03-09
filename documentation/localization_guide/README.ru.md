📘 This documentation is also available in [English](README.md)

---

## 📋 Содержание
- [Обзор](#-обзор)
- [Добавление нового перевода](#-добавление-нового-перевода)
- [Обновление существующих переводов](#-обновление-существующих-переводов)
- [Компиляция переводов](#-компиляция-переводов)
- [Проверка орфографии](#-проверка-орфографии)

---

## 📖 Обзор

Локализация в `PortProtonQT` осуществляется через систему `.po/.mo` файлов и управляется утилитой `Babel`. Все переводы находятся в подкаталогах вида `LC_MESSAGES/portprotonqt.po` для каждой поддерживаемой локали.

Текущий статус перевода:

<!-- Сгенерировано автоматически! -->

| Локаль | Прогресс | Переведено |
| :----- | -------: | ---------: |
| [de](../../portprotonqt/locales/de/LC_MESSAGES/portprotonqt.po) | 0% | 0 из 528 |
| [es](../../portprotonqt/locales/es/LC_MESSAGES/portprotonqt.po) | 0% | 0 из 528 |
| [pt](../../portprotonqt/locales/pt/LC_MESSAGES/portprotonqt.po) | 0% | 0 из 528 |
| [ru](../../portprotonqt/locales/ru/LC_MESSAGES/portprotonqt.po) | 83% | 440 из 528 |

---


## 🏁 Добавление нового перевода

1. Выполните:

```bash
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
python dev-scripts/l10n.py --create-new <код_локали>
```

2. Отредактируйте файл `portprotonqt/locales/<локаль>/LC_MESSAGES/portprotonqt.po` в Poedit или GTranslator.

---

## 🔄 Обновление существующих переводов

Если вы добавили новые строки в код:

```bash
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
python dev-scripts/l10n.py --update-all
```

---

## 🧵 Компиляция переводов

```bash
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
python dev-scripts/l10n.py
```

## 🔍 Проверка орфографии

Для проверки орфографии используйте команду:

```bash
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
python dev-scripts/l10n.py --spellcheck
```

Скрипт выполняет параллельную проверку строк в `.po` и `.pot` файлах, выводит для каждого файла список проверяемых строк и ошибки с предложениями исправлений. Игнорирует слова, указанные в файле `dev-scripts/.spellignore`, чтобы не считать их опечатками.
