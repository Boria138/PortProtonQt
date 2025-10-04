<div align="center">
  <img src="build-aux/share/icons/hicolor/scalable/apps/ru.linux_gaming.PortProtonQt.svg" width="64">
  <h1 align="center">PortProtonQt</h1>
  <p align="center">Удобный графический интерфейс для управления и запуска игр из PortProton, Steam и Epic Games Store. Оно объединяет библиотеки игр в единый центр для лёгкой навигации и организации. Лёгкая структура и кроссплатформенная поддержка обеспечивают цельный игровой опыт без необходимости использования нескольких лаунчеров. Интеграция с PortProton упрощает запуск Windows-игр на Linux с минимальной настройкой.</p>
</div>

### Установка (devel)

```sh
uv python install 3.10
uv sync
source .venv/bin/activate
```

Запуск производится по команде portprotonqt

### Установка (release)

Выберите подходящий пакет для вашей системы или AppImage.

Запуск производится по команде portprotonqt или по ярлыку в меню

### Разработка

В проект встроен линтер (ruff), статический анализатор (pyright) и проверка lock файла, если эти проверки не пройдут PR не будет принят, поэтому перед коммитом введите такую команду

```sh
uv python install 3.10
uv sync --all-extras --dev
source .venv/bin/activate
pre-commit install
```

pre-commit сам запустится при коммите, если вы хотите запустить его вручную введите команду

```sh
pre-commit run --all-files
```

## Авторы

* [Boria138](https://git.linux-gaming.ru/Boria138) - Основной разработчик
* [BlackSnaker](https://git.linux-gaming.ru/BlackSnaker) - Автор идеи, а так же начальной реализации проекта
* [Mikhail Tergoev (Castro-Fidel)](https://git.linux-gaming.ru/CastroFidel) - Автор оригинального проекта PortProton

### Контрибьюторы

Мы благодарим всех, кто внёс вклад в развитие PortProtonQt, включая тех, кто участвует через коммиты, а также тех, кто помогает другими способами (тестирование, идеи, переводы, документация и т.д.). Полный список участников, можно найти в [списке активности репозитория](https://git.linux-gaming.ru/Boria138/PortProtonQt/activity/contributors). Дополнительные участники также перечислены в файле [CHANGELOG.md](CHANGELOG.md). Если вы внесли вклад, но не указаны, свяжитесь с основными разработчиками, чтобы мы могли вас отметить!

## Зависимости и лицензии

PortProtonQt использует код и зависимости от следующих проектов:

- [Legendary](https://github.com/derrod/legendary) — инструмент для работы с Epic Games Store, лицензия [GPL-3.0](https://github.com/derrod/legendary/blob/master/LICENSE).
- [Icoextract](https://github.com/jlu5/icoextract) — библиотека для извлечения иконок, лицензия [MIT](https://github.com/jlu5/icoextract/blob/master/LICENSE).
- [HowLongToBeat Python API](https://github.com/ScrappyCocco/HowLongToBeat-PythonAPI) — библиотека для взаимодействия с HowLongToBeat, лицензия [MIT](https://github.com/ScrappyCocco/HowLongToBeat-PythonAPI/blob/master/LICENSE.md).
Полный текст лицензий см. в файле [LICENSE](LICENSE).

> [!WARNING]
> Проект находится на стадии WIP (work in progress) корректная работоспособность не гарантирована

> [!WARNING]
> **Будьте осторожны!** Если вы берёте тему не из официального репозитория или надёжного источника, убедитесь, что в её файле `styles.py` нет вредоносного или нежелательного кода. Поскольку `styles.py` — это обычный Python-файл, он может содержать любые инструкции. Всегда проверяйте содержимое чужих тем перед использованием.
