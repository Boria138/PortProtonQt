<div align="center">
  <img src="https://raw.githubusercontent.com/Castro-Fidel/PortWINE/master/data_from_portwine/img/gui/portproton.svg" width="64">
  <h1 align="center">PortProtonQt</h1>
  <p align="center">Проект нацеленный на переписывание PortProton(PortWINE) на PySide</p>
</div>

## В планах

- [X] Адаптировать структуру проекта для поддержки инструментов сборки (setuptools, poetry)
- [ ] Добавить возможность управление с геймпада, тачскрина, мыши и клавиатуры
- [X] Закончить перенос стилей в styles.py и задокументировать всё для поддержки системы тем
- [X] Добавить систему тем (тема находится в .local/share/PortProtonQT/имя темы) тема должна содержать styles.py и папку fonts в случае использования не стандартных шрифтов
- [ ] Продумать систему вкладок вместо той что есть сейчас
- [ ] Добавить Gamescope сессию на подобие той что есть в SteamOS
- [ ] Написать адаптивный дизайн
- [X] Брать описание и названия игр с базы данных Steam
- [X] Брать обложки для игр со SteamGridDB или CDN Steam
- [ ] Оптимизировать работу со SteamApi что бы ускорить время запуска
- [ ] Улучшить функцию поиска SteamApi что бы исправить некорректное определение ID (Graven определается как ENGRAVEN или GRAVENFALL, Spore определается как SporeBound или Spore Valley)
- [ ] Написать не обёртку над PortProton, а полноценную программу не зависящию от PortProton
- [ ] Избавится от любого вызова yad
- [ ] Написать свою реализацию запрета ухода в сон, а не использовать ту что в PortProton
- [ ] Написать свою реализацию трея, а не использовать ту что в PortProton
- [ ] Добавить в поиск экранную клавиатуру
- [ ] Добавить сортировку карточек по различным критериям (недавние или кол-во наиграного времени)
- [ ] Добавить индикацию запуска приложения
- [X] Достичь паритета функционала с Ingame (кроме поддержки нативных игр)
- [ ] Достичь паритета функционала с PortProton
- [ ] Если SteamApi вернул английское описание вместо русского переводить его самим
- [X] Добавить возможность изменения названия, описания и обложки через файлы .local/share/PortProtonQT/custom_data/exe_name/{desc,name,cover}
- [ ] Добавить интеграцию с HowLongToBeat для вывода в карточке игры время для прохождения игры [рефференс](https://github.com/hulkrelax/hltb-for-deck)
- [ ] Добавить в карточку игры сведения о поддержке геймадов 
- [ ] Добавить в карточки данные с ProtonDB и Are We Anti-Cheat Yet?

### Установка (debug)

```sh
python -m venv venv
source ./venv/bin/activate
pip install .
```

Запуск производится по команде portprotonqt

## Авторы

* [Boria138](https://github.com/Boria138) - Программист
* [BlackSnaker](https://github.com/BlackSnaker) - Дизайнер
* [Mikhail Tergoev(Castro-Fidel)](https://github.com/Castro-Fidel) - Автор оригинального проекта PortProton

> [!NOTE]
> Проект так же содержит части кода от [Ingame](https://github.com/Castro-Fidel/ingame)

> [!WARNING]  
> Проект находится на стадии WIP (work in progress) корректная работоспособность не гарантирована
