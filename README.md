<div align="center">
  <img src="https://raw.githubusercontent.com/Castro-Fidel/PortWINE/master/data_from_portwine/img/gui/portproton.svg" width="64">
  <h1 align="center">PortProtonQt</h1>
  <p align="center">Проект нацеленный на переписывание PortProton(PortWINE) на PySide</p>
</div>

## В планах

- [ ] Адаптировать структуру проекта для поддержки инструментов сборки (setuptools, poetry)
- [ ] Добавить поддержки геймпадов
- [ ] Добавить поддержку системы тем
- [ ] Добавить Gamescope сессию на подобие той что есть в SteamOS
- [ ] Написать адаптивный дизайн
- [X] Брать описание и названия игр с базы данных Steam
- [X] Брать обложки для игр со SteamGridDB или CDN Steam
- [X] Оптимизировать работу со SteamApi что бы ускорить время запуска
- [ ] Улучшить функцию поиска SteamApi что бы исправить некорректное определение ID (Graven определается как ENGRAVEN или GRAVENFALL, Spore определается как SporeBound или Spore Valley)
- [ ] Написать не обёртку над PortProton, а полноценную программу не зависящию от PortProton
- [ ] Избавится от любого вызова yad
- [ ] Написать свою реализацию запрета ухода в сон, а не использовать ту что в PortProton
- [ ] Написать свою реализацию трея, а не использовать ту что в PortProton
- [ ] Добавить в поиск экранную клавиатуру
- [ ] Добавить индикацию запуска приложения
- [ ] Достичь паритета функционала с Ingame
- [ ] Достичь паритета функционала с PortProton
- [ ] Переводить английское описание на русский язык
- [X] Добавить возможность изменения названия, описания и обложки через файлы custom_data/exe_name/{desc,name,cover}
- [ ] Добавить интеграцию с HowLongToBeat для вывода в карточке игры время для прохождения игры [рефференс](https://github.com/hulkrelax/hltb-for-deck)
- [ ] Добавить в карточку игры сведения о поддержке геймадов 
- [ ] Добавить в карточки данные с ProtonDB и Are We Anti-Cheat Yet?

## Авторы

* [Boria138](https://github.com/Boria138) - Программист
* [BlackSnaker](https://github.com/BlackSnaker) - Дизайнер
* [Mikhail Tergoev(Castro-Fidel)](https://github.com/Castro-Fidel) - Автор оригинального проекта PortProton

> [!NOTE]
> Проект так же содержит части кода от [Ingame](https://github.com/Castro-Fidel/ingame)

> [!WARNING]  
> Проект находится на стадии WIP (work in progress) корректная работоспособность не гарантирована
