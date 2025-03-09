# СТИЛЬ ШАПКИ ГЛАВНОГО ОКНА
MAIN_WINDOW_HEADER_STYLE = """
    QFrame {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 rgba(20, 20, 20, 0.9),
            stop:1 rgba(40, 40, 45, 0.9)
        );
        border-bottom: 1px solid rgba(255,255,255,0.1);
        border-top-left-radius: 15px;
        border-top-right-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
"""

# СТИЛЬ ЗАГОЛОВКА (ЛОГО) В ШАПКЕ
TITLE_LABEL_STYLE = """
    font-family: 'RASKHAL';
    font-size: 32px;
    color: #00fff5;
    text-shadow:
        0 0 8px  #00fff5,
        0 0 10px #9B59B6;
"""

# СТИЛЬ КНОПОК ВИРТУАЛЬНОЙ КЛАВИАТУРЫ (ПОЛУПРОЗРАЧНЫЙ ФОН)
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

# СТИЛЬ КНОПОК ВИРТУАЛЬНОЙ КЛАВИАТУРЫ (БЕЛЫЙ ФОН)
VIRTUAL_KEYBORD_AREA_KEYS_STYLE = """
    QPushButton {
        background: #ffffff;
        border: 2px solid #cccccc;
        border-radius: 12px;
        color: #333333;
        font-size: 22px;
        font-family: 'Arial';
    }
    QPushButton:hover {
        background: #f2f2f2;
    }
    QPushButton:pressed {
        background: #e6e6e6;
        border: 2px solid #aaaaaa;
    }
"""

# СТИЛЬ ШАПКИ ВИРТУАЛЬНОЙ КЛАВИАТУРЫ
VIRTUAL_KEYBOARD_HEADER_STYLE = """
    background: rgba(0, 0, 0, 0.2);
    border-top-left-radius: 15px;
    border-top-right-radius: 15px;
"""

# СТИЛЬ ТЕКСТА В ШАПКЕ ВИРТУАЛЬНОЙ КЛАВИАТУРЫ
VIRTUAL_KEYBOARD_HEADER_LABEL_STYLE = "color: white; font-size: 18px;"

# СТИЛЬ ОБЛАСТИ С КНОПКАМИ В ВИРТУАЛЬНОЙ КЛАВИАТУРЕ
VIRTUAL_KEYBOARD_AREA_STYLE = """
    background: rgba(255, 255, 255, 0.95);
    border-bottom-left-radius: 15px;
    border-bottom-right-radius: 15px;
"""

# СТИЛЬ ОБЛАСТИ НАВИГАЦИИ (КНОПКИ ВКЛАДОК)
NAV_WIDGET_STYLE = """
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 10px;
"""

# СТИЛЬ КНОПОК ВКЛАДОК НАВИГАЦИИ
NAV_BUTTON_STYLE = """
    QPushButton {
        background: transparent;
        padding: 12px 20px;
        color: #fff;
        font-family: 'Poppins';
        text-transform: uppercase;
        border: none;
    }
    QPushButton:checked {
        background: linear-gradient(45deg, rgba(0,255,255,0.15), rgba(155,89,182,0.25));
        color: #00fff5;
        font-weight: bold;
        border-radius: 5px;
    }
    QPushButton:hover {
        color: #00fff5;
    }
"""

# ГЛОБАЛЬНЫЙ СТИЛЬ ДЛЯ ОКНА (ФОН) И QLabel
MAIN_WINDOW_STYLE = """
    QMainWindow {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                     stop:0 #1a1a1a, stop:1 #333333);
    }
    QLabel {
        color: #ffffff;
    }
"""

# ПОЛЕ ПОИСКА
SEARCH_EDIT_STYLE = """
    QLineEdit {
        background-color: #222;
        border: 2px solid #444;
        border-radius: 15px;
        padding-left: 35px;
        padding-right: 10px;
        font-family: 'Poppins';
        font-size: 16px;
        color: white;
    }
    QLineEdit:focus {
        border: 2px solid #00fff5;
    }
"""

# ОТКЛЮЧАЕМ РАМКУ У QScrollArea
SCROLL_AREA_STYLE = "border: none;"

# ОБЛАСТЬ ДЛЯ КАРТОЧЕК ИГР (QWidget)
LIST_WIDGET_STYLE= """
    background-color: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 15px;
"""

# ЗАГОЛОВОК "БИБЛИОТЕКА" НА ВКЛАДКЕ
INSTALLED_TAB_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 28px; color: #f5f5f5;"

# КНОПКА "ДОБАВИТЬ ИГРУ"
ADD_GAME_BUTTON_STYLE = """
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

# ТЕКСТОВЫЕ СТИЛИ: ЗАГОЛОВКИ И КОНТЕНТ
TAB_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 24px; color: #f5f5f5;"
CONTENT_STYLE = "font-family: 'Poppins'; font-size: 16px;"

# ФОН ДЕТАЛЬНОЙ СТРАНИЦЫ, ЕСЛИ ОБЛОЖКА НЕ ЗАГРУЖЕНА
DETAIL_PAGE_NO_COVER_STYLE = "background: #1a1a1a;"

# КНОПКА "НАЗАД" НА ДЕТАЛЬНОЙ СТРАНИЦЕ
BACK_BUTTON_STYLE = """
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

# ОСНОВНОЙ ФРЕЙМ ДЕТАЛЕЙ ИГРЫ
DETAIL_CONTENT_FRAME_STYLE = """
    QFrame {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
    }
"""

# ФРЕЙМ ПОД ОБЛОЖКОЙ
COVER_FRAME_STYLE = """
    QFrame {
        background: #222222;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.1);
    }
"""

# СКРУГЛЕНИЕ УКАЗАНОЙ QLABEL ПОД ОБЛОЖКУ
COVER_LABEL_STYLE = "border-radius: 15px;"

# ВИДЖЕТ ДЕТАЛЕЙ (ТЕКСТ, ОПИСАНИЕ)
DETAILS_WIDGET_STYLE = "background: rgba(255,255,255,0.05); border-radius: 10px;"

# НАЗВАНИЕ (ЗАГОЛОВОК) НА ДЕТАЛЬНОЙ СТРАНИЦЕ
DETAIL_PAGE_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 32px; color: #00fff5;"

# ЛИНИЯ-РАЗДЕЛИТЕЛЬ
DETAIL_PAGE_LINE_STYLE = "color: rgba(255,255,255,0.2);"

# ТЕКСТ ОПИСАНИЯ
DETAIL_PAGE_DESC_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #ffffff;"

# ЛЕЙБЛ "STEAM APPID"
STEAM_APPID_LABEL_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #ffffff;"

# КНОПКА "ИГРАТЬ"
PLAY_BUTTON_STYLE = """
    QPushButton {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 5px;
        font-size: 16px;
        color: white;
        font-weight: bold;
        padding: 8px 16px;
        min-width: 120px;
        min-height: 40px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.25);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
"""

# КНОПКА "ОБЗОР..." В ДИАЛОГЕ "ДОБАВИТЬ ИГРУ"
DIALOG_BROWSE_BUTTON_STYLE = """
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

# ОФОРМЛЕНИЕ КАРТОЧКИ ИГРЫ (GAMECARD)
GAME_CARD_WINDOW_STYLE = """
    QFrame {
        border-radius: 15px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #141414, stop:1 #2a2a2a);
    }
"""

# НАЗВАНИЕ В КАРТОЧКЕ (QLabel), ГДЕ ДОЛЖЕН ПОМЕЩАТЬСЯ ТЕКСТ ЛЮБОЙ ДЛИНЫ
GAME_CARD_NAME_LABEL_STYLE= """
    QLabel {
        color: white;
        font-family: 'Orbitron';
        font-size: 18px;
        font-weight: bold;
        background-color: #111;
        border-bottom-left-radius: 15px;
        border-bottom-right-radius: 15px;
        padding: 14px;
        /* Включаем перенос текста на новую строку, 
           чтобы длинные названия тоже умещались */
        qproperty-wordWrap: true;
    }
"""

# ФУНКЦИЯ ДЛЯ ДИНАМИЧЕСКОГО ГРАДИЕНТА (ДЕТАЛИ ИГРЫ)
# Функции из этой темы срабатывают всегда вне зависимости от выбранной темы функции с кастомных тем вызываются только при использовании кастомной темы
def detail_page_style(stops):
    return f"""
    QWidget {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    {stops});
    }}
"""
