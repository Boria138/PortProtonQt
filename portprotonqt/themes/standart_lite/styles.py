# Улучшенный тёмный glassmorphism-стиль с более гладкими формами

# ШАПКА ГЛАВНОГО ОКНА
MAIN_WINDOW_HEADER_STYLE = """
    QFrame {
        /* Мягкий тёмный полупрозрачный градиент */
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(25, 25, 25, 0.30),
            stop:1 rgba(35, 35, 35, 0.30));
        /* «Стеклянная» окантовка с усиленными скруглениями */
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-top-left-radius: 35px;
        border-top-right-radius: 35px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.18);
        /* Более мягкая, расширенная тень для эффекта стекла */
        box-shadow: 0 25px 70px rgba(0, 0, 0, 0.7);
    }
"""

# ЛОГО/ЗАГОЛОВОК В ШАПКЕ
TITLE_LABEL_STYLE = """
    QLabel {
        font-family: 'RASKHAL';
        font-size: 42px;
        color: #007AFF;
        /* Усиленное свечение вокруг текста */
        text-shadow: 0 0 15px rgba(0,122,255,0.7), 0 3px 6px rgba(0, 0, 0, 0.6);
    }
"""

# ОБЛАСТЬ НАВИГАЦИИ
NAV_WIDGET_STYLE = """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(25, 25, 25, 0.40),
            stop:1 rgba(40, 40, 40, 0.35));
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 30px;
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.5);
    }
"""

# КНОПКИ ВКЛАДОК НАВИГАЦИИ
NAV_BUTTON_STYLE = """
    QPushButton {
        background: transparent;
        padding: 16px 28px;
        color: #ffffff;
        font-family: 'Poppins';
        text-transform: uppercase;
        border: none;
        border-radius: 20px;
        font-weight: 500;
    }
    QPushButton:checked {
        background: rgba(0,122,255,0.30);
        color: #007AFF;
        font-weight: bold;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(0,122,255,0.20),
            stop:1 rgba(0,122,255,0.15));
        color: #007AFF;
        cursor: pointer;
    }
"""

# ГЛОБАЛЬНЫЙ ФОН ОКНА И СТИЛЬ QLabel
MAIN_WINDOW_STYLE = """
    QMainWindow {
        /* Тёмный фон с плавным, слегка размытой текстурой */
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #121212,
            stop:1 #1a1a1a);
    }
    QLabel {
        color: #ffffff;
    }
"""

# ПОЛЕ ПОИСКА
SEARCH_EDIT_STYLE = """
    QLineEdit {
        background-color: rgba(30, 30, 30, 0.50);
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 40px;
        padding-left: 40px;
        padding-right: 15px;
        font-family: 'Poppins';
        font-size: 16px;
        color: #ffffff;
    }
    QLineEdit:focus {
        border: 1px solid #007AFF;
    }
"""

# ОТКЛЮЧАЕМ РАМКУ У QScrollArea
SCROLL_AREA_STYLE = "border: none;"

# ОБЛАСТЬ ДЛЯ КАРТОЧЕК ИГР
LIST_WIDGET_STYLE = """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(25, 25, 25, 0.45),
            stop:1 rgba(25, 25, 25, 0.35));
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 30px;
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.5);
    }
"""

# ЗАГОЛОВОК "БИБЛИОТЕКА" НА ВКЛАДКЕ
INSTALLED_TAB_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 28px; color: #007AFF;"

# КНОПКА "ДОБАВИТЬ ИГРУ"
ADD_GAME_BUTTON_STYLE = """
    QPushButton {
        background: rgba(25, 25, 25, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 25px;
        color: #ffffff;
        font-size: 16px;
        padding: 14px 26px;
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.5);
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(0,122,255,0.25),
            stop:1 rgba(0,122,255,0.20));
        cursor: pointer;
    }
    QPushButton:pressed {
        background: rgba(25, 25, 25, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.35);
    }
"""

# ТЕКСТОВЫЕ СТИЛИ
TAB_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 24px; color: #ffffff;"
CONTENT_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #ffffff;"

# ДОПОЛНИТЕЛЬНЫЕ СТИЛИ ИНФОРМАЦИИ НА СТРАНИЦЕ ИГР
LAST_LAUNCH_TITLE_STYLE = "font-family: 'Poppins'; font-size: 11px; color: #bbbbbb; text-transform: uppercase; letter-spacing: 0.75px; margin-bottom: 2px;"
LAST_LAUNCH_VALUE_STYLE = "font-family: 'Poppins'; font-size: 13px; color: #ffffff; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = "font-family: 'Poppins'; font-size: 11px; color: #bbbbbb; text-transform: uppercase; letter-spacing: 0.75px; margin-bottom: 2px;"
PLAY_TIME_VALUE_STYLE = "font-family: 'Poppins'; font-size: 13px; color: #ffffff; font-weight: 600; letter-spacing: 0.75px;"
GAMEPAD_SUPPORT_VALUE_STYLE = """
    font-family: 'Poppins'; font-size: 12px; color: #00ff00;
    font-weight: bold; background: rgba(0, 0, 0, 0.3);
    border-radius: 5px; padding: 4px 8px;
"""

# ФОН ДЕТАЛЬНОЙ СТРАНИЦЫ, ЕСЛИ НЕТ ОБЛОЖКИ
DETAIL_PAGE_NO_COVER_STYLE = "background: rgba(20,20,20,0.90);"

# КНОПКА "НАЗАД" НА ДЕТАЛЬНОЙ СТРАНИЦЕ
BACK_BUTTON_STYLE = """
    QPushButton {
        background: rgba(25, 25, 25, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 20px;
        color: #ffffff;
        font-size: 16px;
        padding: 10px 20px;
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.5);
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(0,122,255,0.25),
            stop:1 rgba(0,122,255,0.20));
        cursor: pointer;
    }
    QPushButton:pressed {
        background: rgba(25, 25, 25, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.35);
    }
"""

# ОСНОВНОЙ ФРЕЙМ ДЕТАЛЕЙ ИГРЫ
DETAIL_CONTENT_FRAME_STYLE = """
    QFrame {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(25, 25, 25, 0.45),
            stop:1 rgba(25, 25, 25, 0.40));
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 20px;
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.5);
    }
"""

# ФРЕЙМ ПОД ОБЛОЖКОЙ
COVER_FRAME_STYLE = """
    QFrame {
        background: rgba(30, 30, 30, 0.80);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.20);
    }
"""

# СКРУГЛЕНИЕ ДЛЯ LABEL ПОД ОБЛОЖКУ
COVER_LABEL_STYLE = "border-radius: 20px;"

# ВИДЖЕТ ДЕТАЛЕЙ (ТЕКСТ, ОПИСАНИЕ)
DETAILS_WIDGET_STYLE = "background: rgba(20,20,20,0.45); border-radius: 20px; padding: 12px;"

# НАЗВАНИЕ (ЗАГОЛОВОК) НА ДЕТАЛЬНОЙ СТРАНИЦЕ
DETAIL_PAGE_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 32px; color: #007AFF;"

# ЛИНИЯ-РАЗДЕЛИТЕЛЬ
DETAIL_PAGE_LINE_STYLE = "color: rgba(255,255,255,0.12); margin: 10px 0;"

# ТЕКСТ ОПИСАНИЯ
DETAIL_PAGE_DESC_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #ffffff; line-height: 1.5;"

# СПИСОК ТЕМ (QComboBox)
COMBO_BOX_STYLE = """
QComboBox {
    background-color: rgba(40, 40, 40, 0.75);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.25);
    border-radius: 12px;
    padding: 4px 8px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border-left: 1px solid rgba(255, 255, 255, 0.25);
}
QComboBox QAbstractItemView {
    background-color: rgba(40, 40, 40, 0.95);
    color: #ffffff;
    selection-background-color: rgba(0, 122, 255, 0.35);
    border-radius: 12px;
}
"""

# КНОПКА "ИГРАТЬ"
PLAY_BUTTON_STYLE = """
    QPushButton {
        background: rgba(25, 25, 25, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 20px;
        font-size: 16px;
        color: #ffffff;
        font-weight: bold;
        padding: 10px 20px;
        min-width: 130px;
        min-height: 45px;
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.5);
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(0,122,255,0.25),
            stop:1 rgba(0,122,255,0.20));
        cursor: pointer;
    }
    QPushButton:pressed {
        background: rgba(25, 25, 25, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.35);
    }
"""

# КНОПКА "ОБЗОР..." В ДИАЛОГЕ "ДОБАВИТЬ ИГРУ"
DIALOG_BROWSE_BUTTON_STYLE = """
    QPushButton {
        background: rgba(25, 25, 25, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 20px;
        color: #ffffff;
        font-size: 16px;
        padding: 8px 18px;
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.5);
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(0,122,255,0.25),
            stop:1 rgba(0,122,255,0.20));
        cursor: pointer;
    }
    QPushButton:pressed {
        background: rgba(25, 25, 25, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.35);
    }
"""

# КАРТОЧКА ИГРЫ
GAME_CARD_WINDOW_STYLE = """
    QFrame {
        border-radius: 25px;
        background: rgba(25, 25, 25, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.25);
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.5);
    }
"""

# НАЗВАНИЕ В КАРТОЧКЕ
GAME_CARD_NAME_LABEL_STYLE = """
    QLabel {
        color: #ffffff;
        font-family: 'Orbitron';
        font-size: 18px;
        font-weight: bold;
        background-color: rgba(20, 20, 20, 0.80);
        border-bottom-left-radius: 25px;
        border-bottom-right-radius: 25px;
        padding: 14px;
        qproperty-wordWrap: true;
    }
"""

# СТИЛИ ПРЕВЬЮ СКРИНШОТОВ (стрелки карусели)
PREV_BUTTON_STYLE = """
    QPushButton {
        background-color: rgba(0, 0, 0, 0.55);
        color: white;
        border: none;
        border-radius: 20px;
        padding: 10px;
    }
    QPushButton:hover {
        background-color: rgba(0, 0, 0, 0.75);
    }
"""

NEXT_BUTTON_STYLE = """
    QPushButton {
        background-color: rgba(0, 0, 0, 0.55);
        color: white;
        border: none;
        border-radius: 20px;
        padding: 10px;
    }
    QPushButton:hover {
        background-color: rgba(0, 0, 0, 0.75);
    }
"""

# СТИЛЬ БЕЙДЖА PROTONDB
PROTONDB_BADGE_STYLE = """
    background-color: rgba(0, 0, 0, 0.55);
    color: white;
    padding: 3px 6px;
    border-radius: 8px;
    font-weight: bold;
"""

# ФУНКЦИЯ ДЛЯ ДИНАМИЧЕСКОГО ГРАДИЕНТА (ДЕТАЛИ ИГР)
def detail_page_style(stops):
    return f"""
    QWidget {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    {stops});
    }}
"""
