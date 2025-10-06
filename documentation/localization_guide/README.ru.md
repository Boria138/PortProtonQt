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

Локализация в `PortProtonQT` осуществляется через систему `.po/.mo` файлов и управляется утилитой `Babel`. Все переводы находятся в подкаталогах вида `LC_MESSAGES/messages.po` для каждой поддерживаемой локали.

Текущий статус перевода:

<!-- Сгенерировано автоматически! -->

| Локаль | Прогресс | Переведено |
| :----- | -------: | ---------: |
| [de_DE](./de_DE/LC_MESSAGES/messages.po) | 0% | 0 из 213 |
| [es_ES](./es_ES/LC_MESSAGES/messages.po) | 0% | 0 из 213 |
| [ru_RU](./ru_RU/LC_MESSAGES/messages.po) | 100% | 213 из 213 |

---


## 🏁 Добавление нового перевода

1. Выполните:

```bash
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
python dev-scripts/l10n.py --create-new <код_локали>
```

2. Отредактируйте файл `portprotonqt/locales/<локаль>/LC_MESSAGES/messages.po` в Poedit или любом текстовом редакторе.

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
