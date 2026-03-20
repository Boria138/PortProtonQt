📘 This documentation is also available in [English](README.md)

---

## 📋 Содержание
- [Обзор](#-обзор)
- [Перевод онлайн](#-перевод-онлайн)
- [Добавление нового перевода](#-добавление-нового-перевода)
- [Обновление существующих переводов](#-обновление-существующих-переводов)
- [Компиляция переводов](#-компиляция-переводов)
- [Проверка орфографии](#-проверка-орфографии)

---

## 📖 Обзор

Локализация в `PortProtonQT` осуществляется через систему `.po/.mo` файлов и управляется утилитой `Babel`. Все переводы находятся в подкаталогах вида `LC_MESSAGES/portprotonqt.po` для каждой поддерживаемой локали.

Текущий статус перевода:

<a href="https://translate.codeberg.org/engage/portprotonqt/">
<img src="https://translate.codeberg.org/widget/portprotonqt/multi-auto.svg" alt="Состояние перевода" />
</a>

---

## 🌐 Перевод онлайн

Вы можете помочь перевести PortProtonQt через нашу веб-платформу:

**[translate.codeberg.org/engage/portprotonqt](https://translate.codeberg.org/engage/portprotonqt)**

Преимущества веб-платформы:
- Не нужно настраивать окружение разработки
- Работа прямо в браузере
- Видно контекст и варианты от других переводчиков
- Совместная работа с сообществом

Переводы, отправленные через веб-платформу, периодически проверяются и объединяются с основным репозиторием.

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
