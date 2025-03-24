# СТИЛЬ ШАПКИ ГЛАВНОГО ОКНА
MAIN_WINDOW_HEADER_STYLE = """
    QFrame {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(255, 255, 255, 1.0),
            stop:0.5 rgba(248, 248, 248, 1.0),
            stop:1 rgba(238, 238, 238, 1.0));
        border: 1px solid rgba(0, 0, 0, 0.10);
        border-bottom: 1px solid rgba(0, 0, 0, 0.15);
        border-top-left-radius: 30px;
        border-top-right-radius: 30px;
        border: none;
    }
"""

# СТИЛЬ ЗАГОЛОВКА (ЛОГО) В ШАПКЕ
TITLE_LABEL_STYLE = """
    QLabel {
        font-family: 'RASKHAL';
        font-size: 38px;
        color: #002244;
    }
"""

# СТИЛЬ ОБЛАСТИ НАВИГАЦИИ (КНОПКИ ВКЛАДОК)
NAV_WIDGET_STYLE = """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(255, 255, 255, 1),
            stop:1 rgba(250, 250, 250, 1));
        border: 1px solid rgba(0, 0, 0, 0.10);
        border-radius: 25px;
    }
"""

# СТИЛЬ КНОПОК ВКЛАДОК НАВИГАЦИИ
NAV_BUTTON_STYLE = """
    QPushButton {
        background: transparent;
        padding: 14px 24px;
        color: #333333;
        font-family: 'Poppins';
        text-transform: uppercase;
        border: none;
        border-radius: 15px;
    }
    QPushButton:checked {
        background: rgba(0,122,255,0.25);
        color: #002244;
        font-weight: bold;
        border-radius: 15px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(0,122,255,0.12),
            stop:1 rgba(0,122,255,0.08));
        color: #002244;
    }
"""

# ГЛОБАЛЬНЫЙ СТИЛЬ ДЛЯ ОКНА (ФОН) И QLabel
MAIN_WINDOW_STYLE = """
    QMainWindow {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #ffffff,
            stop:1 #f2f2f2);
    }
    QLabel {
        color: #333333;
    }
"""

# СТИЛЬ ПОЛЯ ПОИСКА
SEARCH_EDIT_STYLE = """
    QLineEdit {
        background-color: #ffffff;
        border: 1px solid rgba(0, 0, 0, 0.15);
        border-radius: 30px;
        padding-left: 35px;
        padding-right: 10px;
        font-family: 'Poppins';
        font-size: 16px;
        color: #333333;
    }
    QLineEdit:focus {
        border: 1px solid #003366;
    }
"""

# ОТКЛЮЧАЕМ РАМКУ У QScrollArea
SCROLL_AREA_STYLE = "border: none;"

# СТИЛЬ ОБЛАСТИ ДЛЯ КАРТОЧЕК ИГР (QWidget)
LIST_WIDGET_STYLE = """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(255, 255, 255, 1),
            stop:1 rgba(250, 250, 250, 1));
        border: 1px solid rgba(0, 0, 0, 0.10);
        border-radius: 25px;
    }
"""

# ЗАГОЛОВОК "БИБЛИОТЕКА" НА ВКЛАДКЕ
INSTALLED_TAB_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 28px; color: #002244;"

# СТИЛЬ КНОПКИ "ДОБАВИТЬ ИГРУ"
ADD_GAME_BUTTON_STYLE = """
    QPushButton {
        background: #ffffff;
        border: 1px solid rgba(0, 0, 0, 0.20);
        border-radius: 20px;
        color: #333333;
        font-size: 16px;
        padding: 12px 24px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(0,122,255,0.10),
            stop:1 rgba(0,122,255,0.05));
    }
    QPushButton:pressed {
        background: #f0f0f0;
        border: 1px solid rgba(0, 0, 0, 0.25);
    }
"""

# ТЕКСТОВЫЕ СТИЛИ: ЗАГОЛОВКИ И ОСНОВНОЙ КОНТЕНТ
TAB_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 24px; color: #333333;"
CONTENT_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #333333;"

# ФОН ДЛЯ ДЕТАЛЬНОЙ СТРАНИЦЫ, ЕСЛИ ОБЛОЖКА НЕ ЗАГРУЖЕНА (Glassmorphism)
DETAIL_PAGE_NO_COVER_STYLE = "background: rgba(255, 255, 255, 0.15);"

# СТИЛЬ КНОПКИ "НАЗАД" НА ДЕТАЛЬНОЙ СТРАНИЦЕ (Glassmorphism)
BACK_BUTTON_STYLE = """
    QPushButton {
        background: rgba(255, 255, 255, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.4);
        border-radius: 15px;
        color: #333333;
        font-size: 16px;
        padding: 8px 16px;
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.4);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
"""

# ОСНОВНОЙ ФРЕЙМ ДЕТАЛЕЙ ИГРЫ (Glassmorphism style)
DETAIL_CONTENT_FRAME_STYLE = """
    QFrame {
        background: rgba(255, 255, 255, 0.25);
        border: 1px solid rgba(255, 255, 255, 0.4);
        border-radius: 15px;
    }
"""

# ФРЕЙМ ПОД ОБЛОЖКОЙ (Glassmorphism style)
COVER_FRAME_STYLE = """
    QFrame {
        background: rgba(255, 255, 255, 0.2);
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
"""

# СКРУГЛЕНИЕ LABEL ПОД ОБЛОЖКУ
COVER_LABEL_STYLE = "border-radius: 20px;"

# ВИДЖЕТ ДЕТАЛЕЙ (ТЕКСТ, ОПИСАНИЕ) (Glassmorphism style)
DETAILS_WIDGET_STYLE = "background: rgba(255, 255, 255, 0.2); border: 1px solid rgba(255, 255, 255, 0.3); border-radius: 15px; padding: 10px;"

# НАЗВАНИЕ (ЗАГОЛОВОК) НА ДЕТАЛЬНОЙ СТРАНИЦЕ
DETAIL_PAGE_TITLE_STYLE = "font-family: 'Orbitron'; font-size: 32px; color: #002244;"

# ЛИНИЯ-РАЗДЕЛИТЕЛЬ
DETAIL_PAGE_LINE_STYLE = "color: rgba(0,0,0,0.12); margin: 10px 0;"

# ТЕКСТ ОПИСАНИЯ
DETAIL_PAGE_DESC_STYLE = "font-family: 'Poppins'; font-size: 16px; color: #333333; line-height: 1.5;"

# Стиль списка тем
COMBO_BOX_STYLE = """
QComboBox {
    background-color: rgba(255, 255, 255, 0.3);
    color: #333333;
    border: 1px solid rgba(255, 255, 255, 0.4);
    padding: 4px;
    border-radius: 5px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid rgba(255, 255, 255, 0.4);
}
QComboBox QAbstractItemView {
    background-color: rgba(255, 255, 255, 0.2);
    color: #333333;
    selection-background-color: rgba(255, 255, 255, 0.3);
}
"""

# СТИЛЬ КНОПКИ "ИГРАТЬ" (Glassmorphism style)
PLAY_BUTTON_STYLE = """
    QPushButton {
        background: rgba(255, 255, 255, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.4);
        border-radius: 15px;
        font-size: 16px;
        color: #333333;
        font-weight: bold;
        padding: 8px 16px;
        min-width: 120px;
        min-height: 40px;
      
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.4);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
"""

# СТИЛЬ КНОПКИ "ОБЗОР..." В ДИАЛОГЕ "ДОБАВИТЬ ИГРУ" (Glassmorphism style)
DIALOG_BROWSE_BUTTON_STYLE = """
    QPushButton {
        background: rgba(255, 255, 255, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.4);
        border-radius: 15px;
        color: #333333;
        font-size: 16px;
        padding: 5px 10px;
       
    }
    QPushButton:hover {
        background: rgba(255, 255, 255, 0.4);
    }
    QPushButton:pressed {
        background: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
"""

# СТИЛЬ КАРТОЧКИ ИГРЫ (GAMECARD) с элементами glassmorphism
GAME_CARD_WINDOW_STYLE = """
    QFrame {
        border-radius: 20px;
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 rgba(255, 255, 255, 0.3),
            stop:1 rgba(249, 249, 249, 0.3));
        border: 1px solid rgba(255, 255, 255, 0.4);
       
    }
"""

# НАЗВАНИЕ В КАРТОЧКЕ (QLabel) с эффектом прозрачности
GAME_CARD_NAME_LABEL_STYLE = """
    QLabel {
        color: #333333;
        font-family: 'Orbitron';
        font-size: 18px;
        font-weight: bold;
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(242, 242, 242, 0.5),
            stop:1 rgba(232, 232, 232, 0.5));
        border-bottom-left-radius: 20px;
        border-bottom-right-radius: 20px;
        padding: 14px;
        qproperty-wordWrap: true;
    }
"""

# ДОПОЛНИТЕЛЬНЫЕ СТИЛИ ИНФОРМАЦИИ НА СТРАНИЦЕ ИГР
LAST_LAUNCH_TITLE_STYLE = "font-family: 'Poppins'; font-size: 11px; color: #666666; text-transform: uppercase; letter-spacing: 0.75px; margin-bottom: 2px;"
LAST_LAUNCH_VALUE_STYLE = "font-family: 'Poppins'; font-size: 13px; color: #333333; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = "font-family: 'Poppins'; font-size: 11px; color: #666666; text-transform: uppercase; letter-spacing: 0.75px; margin-bottom: 2px;"
PLAY_TIME_VALUE_STYLE = "font-family: 'Poppins'; font-size: 13px; color: #333333; font-weight: 600; letter-spacing: 0.75px;"
GAMEPAD_SUPPORT_VALUE_STYLE = """
    font-family: 'Poppins'; font-size: 12px; color: #008000;
    font-weight: bold; background: rgba(240,240,240,1);
    border-radius: 5px; padding: 4px 8px;
"""

# СТИЛИ ПОЛНОЭКРАНОГО ПРЕВЬЮ СКРИНШОТОВ ТЕМЫ
PREV_BUTTON_STYLE = "background-color: rgba(255, 255, 255, 0.8); color: #333333; border: none;"
NEXT_BUTTON_STYLE = "background-color: rgba(255, 255, 255, 0.8); color: #333333; border: none;"
CAPTION_LABEL_STYLE = "color: #333333; font-size: 16px;"

# СТИЛИ БЕЙДЖА PROTONDB НА КАРТОЧКЕ
PROTONDB_BADGE_STYLE = """
    background-color: rgba(240, 240, 240, 1);
    color: #333333;
    padding: 2px 4px;
    border-radius: 5px;
    font-weight: bold;
"""
# СТИЛИ БЕЙДЖА STEAM
STEAM_BADGE_STYLE= """
    background-color: rgba(240, 240, 240, 1);
    color: #333333;
    font-size: 12px;
    padding: 6px 12px;
    border-radius: 5px;
    font-weight: bold;
"""

# ФУНКЦИЯ ДЛЯ ДИНАМИЧЕСКОГО ГРАДИЕНТА (ДЕТАЛИ ИГР)
# Функции из этой темы срабатывают всегда вне зависимости от выбранной темы, функции из других тем работают только в этих темах
def detail_page_style(stops):
    return f"""
    QWidget {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    {stops});
    }}
"""
