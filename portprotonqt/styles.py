# styles.py
# В этом файле содержатся все константы стилей.
# Каждый блок CSS описывает оформление конкретных элементов интерфейса:
#   - основного окна и его шапки
#   - вкладок (табов)
#   - кнопок (как в шапке, так и во вкладках)
#   - полей ввода (поиска, диалог добавления и т.д.)
#   - элементов детальной страницы (фреймов, лейблов)
#   - карточек игр (GameCard)
#   - виртуальной клавиатуры (VirtualKeyboard)
#
# Дополнительно, к каждому свойству добавлен комментарий, поясняющий, за что оно отвечает.

# ----- СТИЛИ ДЛЯ ОСНОВНОГО ОКНА И ШАПКИ -----

MAIN_WINDOW_HEADER_STYLE = """
    QFrame {  /* Используется для QFrame в шапке (header) главного окна MainWindow */

        background: rgba(0, 0, 0, 0.6);               
        border-bottom: 1px solid rgba(255,255,255,0.1); 
    }
"""

MAIN_WINDOW_STYLE = """
    QMainWindow {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                     stop:0 #1a1a1a, stop:1 #333333);
    }

    QLabel {
        color: #ffffff;
    }
"""

TITLE_LABEL_STYLE = """
    /* Применяется к QLabel с логотипом / заголовком "PortProton" в верхней части главного окна */

    font-family: 'RASKHAL';                           
    font-size: 32px;                                  
    color: #00fff5;                                   /* Бирюзовый цвет текста */
    text-shadow: 0 0 5px #00fff5, 0 0 7px #9B59B6;    
"""

KEYBOARD_BUTTON_STYLE = """
    /* Используется для кнопки "Клавиатура" в шапке главного окна */

    QPushButton {
        background: rgba(255, 255, 255, 0.15);        /* Светлый фон с прозрачностью */
        border: 1px solid rgba(255, 255, 255, 0.3);   
        border-radius: 10px;                          
        color: white;                                 
        font-size: 16px;                              
        padding: 10px 20px;                           
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);        /* При наведении - чуть ярче */
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);        /* При нажатии - ещё ярче */
        border: 1px solid rgba(255, 255, 255, 0.5);   /* Граница становится более заметной */
    }
"""

NAV_WIDGET_STYLE = """
    /* Стиль для контейнера кнопок вкладок (navWidget) в главном окне */

    background: rgba(255, 255, 255, 0.1);             /* Слегка светлый фон с прозрачностью */
    border: 1px solid rgba(255, 255, 255, 0.2);       /* Тонкая белая полупрозрачная граница */
    border-radius: 10px;                              
"""

NAV_BUTTON_STYLE = """
    /* Используется для кнопок вкладок: "Библиотека", "Автоустановка", "Эмуляторы", "Настройки wine", "Настройки PortProton" */

    QPushButton {
        background: transparent;                      /* Прозрачный фон */
        padding: 12px 20px;                           /* Отступы внутри кнопок вкладок */
        color: #fff;                                  /* Белый цвет текста */
        font-family: 'Poppins';                       /* Шрифт Poppins */
        text-transform: uppercase;                    /* Текст вкладки в верхнем регистре */
        border: none;                                 /* Без явной рамки */
    }
    QPushButton:checked {
        background: linear-gradient(45deg, rgba(0,255,255,0.15), rgba(155,89,182,0.25));

        /* При активной вкладке появляется лёгкий градиент (бирюзовый -> фиолетовый) */

        color: #00fff5;                               /* Цвет текста при активном состоянии */
        font-weight: bold;                            /* Жирное начертание, чтобы выделяться */
        border-radius: 5px;                           /* Слегка скруглённые углы */
    }
    QPushButton:hover {
        color: #00fff5;                               /* При наведении меняем цвет текста на бирюзовый */
    }
"""

GLOBAL_MAIN_WINDOW_STYLE = """
    /* Применяется ко всему QMainWindow (фон и общий стиль) */

    QMainWindow {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                     stop:0 #1a1a1a, stop:1 #333333);
        /* Вертикальный градиент от #1a1a1a (почти чёрный) к #333333 (тёмно-серый) */
    }
    QLabel {
        color: #fff;  /* Все QLabel по умолчанию будут белого цвета текста */
    }
"""

# ----- СТИЛИ ДЛЯ БИБЛИОТЕКИ (ВКЛАДКА "Библиотека") И ЕЁ ЭЛЕМЕНТОВ -----

SEARCH_EDIT_STYLE = """
    /* Применяется к QLineEdit поиска в "Библиотека" */

    QLineEdit {
        background-color: #222;                       /* Тёмно-серый фон поля ввода */
        border: 2px solid #444;                       /* Тёмно-серая рамка */
        border-radius: 15px;                          /* Закруглённые углы */
        padding-left: 35px;                           /* Отступ слева (под иконку лупы) */
        padding-right: 10px;                          /* Отступ справа */
        font-family: 'Poppins';                       /* Шрифт для текста */
        font-size: 16px;                              /* Размер шрифта */
        color: white;                                 /* Цвет вводимого текста */
    }
    QLineEdit:focus {
        border: 2px solid #00fff5;                    /* При фокусе - бирюзовая рамка */
    }
"""

SCROLL_AREA_STYLE = "border: none;"
# Применяется к QScrollArea (со списком игр). Отключает рамку вокруг области скролла.

LIST_WIDGET_STYLE = """
    /* Фон виджета (QWidget) внутри QScrollArea, в котором располагаются карточки игр */

    background-color: rgba(255, 255, 255, 0.1);       /* Слегка светлый, полупрозрачный фон */
    border: 1px solid rgba(255, 255, 255, 0.3);       /* Тонкая полупрозрачная граница */
    border-radius: 15px;                              /* Скруглённые углы для контейнера */
"""

INSTALLED_TAB_TITLE_STYLE = """
    /* Стиль для QLabel заголовка вкладки "Библиотека игр" */

    font-family: 'Orbitron';                          /* Шрифт Orbitron */
    font-size: 28px;                                  /* Крупный текст */
    color: #f5f5f5;                                   /* Светлый цвет шрифта */
"""

ADD_GAME_BUTTON_STYLE = """
    /* Применяется к кнопке "Добавить игру" */

    QPushButton {
        background: rgba(255, 255, 255, 0.15);        /* Прозрачный белый фон */
        border: 1px solid rgba(255, 255, 255, 0.3);   /* Тонкая белая граница */
        border-radius: 10px;                          /* Скруглённые углы */
        color: white;                                 /* Белый цвет текста */
        font-size: 16px;                              /* Размер текста */
        padding: 10px 20px;                           /* Отступы внутри кнопки */
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);        /* При наведении - фон ярче */
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);        /* При нажатии - ещё ярче */
        border: 1px solid rgba(255, 255, 255, 0.5);   /* Граница более заметная */
    }
"""

# ----- ОБЩИЕ СТИЛИ ДЛЯ ТАБОВ И ТЕКСТА -----

TAB_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 12px; color: #f5f5f5;"
# Дополнительный стиль может использоваться для внутренних заголовков вкладок (если нужно).

CONTENT_STYLE = "font-family: 'Orbition'; font-size: 16px;"
# Общий стиль для текстового содержимого (если где-то необходимо).

# ----- СТИЛИ ДЕТАЛЬНОЙ СТРАНИЦЫ (Когда открываем отдельную страницу игры) -----

BACK_BUTTON_STYLE = """
    /* Кнопка "Назад" на детальной странице игры */

    QPushButton {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 5px;
        color: white;
        font-size: 16px;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
"""

DETAIL_CONTENT_FRAME_STYLE = """
    /* Основной фрейм справа, в котором находится описание, кнопка "Играть" и т.д. */

    QFrame {
        background: rgba(255, 255, 255, 0.05);        /* Лёгкая подсветка фона */
        border: 1px solid rgba(255,255,255,0.1);      /* Тонкая белая полупрозрачная рамка */
        border-radius: 10px;                        
    }
"""

COVER_FRAME_STYLE = """
    /* Фрейм слева под обложкой игры */

    QFrame {
        background: #222222;                          /* Тёмно-серый цвет фона */
        border-radius: 10px;                         
        border: 1px solid rgba(255,255,255,0.1);      /* Тонкая прозрачная рамка */
    }
"""

COVER_LABEL_STYLE = "border-radius: 10px;"
# Используется для QLabel, где отображается обложка (картинка); те же скруглённые углы.

DETAILS_WIDGET_STYLE = "background: rgba(255,255,255,0.05); border-radius: 10px;"
# Виджет, где располагаются тайтл, описание, AppID и кнопка "Играть".

DETAIL_PAGE_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 32px; color: #00fff5;"
# Большой заголовок на детальной странице (имя игры).

DETAIL_PAGE_LINE_STYLE = "color: rgba(255,255,255,0.2);"
# Стиль для QFrame.HLine (горизонтальной линии-разделителя) на детальной странице.

DETAIL_PAGE_DESC_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #fff;"
# Основной текст описания игры (короткий обзор).

STEAM_APPID_LABEL_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #fff;"
# Стиль для подписи "Steam AppID" (если игра найдена в Steam).

PLAY_BUTTON_STYLE = """
    /* Кнопка "Играть" на детальной странице */

    QPushButton {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 5px;
        font-size: 16px;
        color: white;
        font-weight: bold;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
"""

# ----- СТИЛИ ОКНА "Добавить игру" (Диалог AddGameDialog) -----

DIALOG_BROWSE_BUTTON_STYLE = """
    /* Применяется к кнопке "Обзор..." в диалоговом окне добавления игры (AddGameDialog) */

    QPushButton {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 10px;
        color: white;
        font-size: 16px;
        padding: 5px 10px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
"""

# ----- СТИЛИ КАРТОЧЕК (GameCard) -----

GAME_CARD_WINDOW_STYLE = """
    /* Основная стилизация QFrame в карточке игры (GameCard) */

    QFrame {
        border-radius: 15px;                          /* Сильно скруглённые углы */
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    stop:0 #141414, stop:1 #2a2a2a);
        /* Вертикальный градиент от #141414 (очень тёмный серый) к #2a2a2a (темноватый серый) */
    }
"""

GAME_CARD_NAME_LABEL_STYLE = """
    /* Текстовое поле с названием игры внутри карточки GameCard */
    color: white;                                     /* Белый цвет шрифта */
    font-family: 'Orbitron';                          
    font-size: 18px;                                  
    font-weight: bold;                                
    background-color: #111;                           /* Тёмный фон */
    border-bottom-left-radius: 15px;                  
    border-bottom-right-radius: 15px;                 /* Скругление нижнего правого угла */
    padding: 8px;                                     /* Внутренние отступы вокруг текста */
"""

# ----- СТИЛИ ВИРТУАЛЬНОЙ КЛАВИАТУРЫ (VirtualKeyboard) -----

VIRTUAL_KEYBOARD_HEADER_STYLE = """
    /* Верхняя панель клавиатуры (QFrame с заголовком "Виртуальная клавиатура") */

    background: rgba(0, 0, 0, 0.2);                   /* Тёмный прозрачный фон */
    border-top-left-radius: 15px;                    
    border-top-right-radius: 15px;                   
"""

VIRTUAL_KEYBOARD_HEADER_LABEL_STYLE = """
    /* Надпись "Виртуальная клавиатура" в шапке клавиатуры */
    color: white;                                     /* Белый цвет текста */
    font-size: 18px;                                 
    font-family: 'Poppins';                          
"""

VIRTUAL_KEYBOARD_AREA_STYLE = """
    /* Основная область, где располагаются кнопки клавиатуры */
    background: rgba(255, 255, 255, 0.95);            /* Почти белый фон */
    border-bottom-left-radius: 15px;                 
    border-bottom-right-radius: 15px;              
"""

VIRTUAL_KEYBOARD_KEYS_STYLE = """
    QPushButton {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 10px;
        color: white;
        font-size: 16px;
        padding: 10px 20px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
"""
