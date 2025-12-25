from .constants import *

# ФОН ДЛЯ ДЕТАЛЬНОЙ СТРАНИЦЫ, ЕСЛИ ОБЛОЖКА НЕ ЗАГРУЖЕНА
DETAIL_PAGE_NO_COVER_STYLE = f"background: rgba(20,20,20,0.95); border-radius: {border_radius_b};"

# СТИЛЬ КНОПКИ "ДОБАВИТЬ ИГРУ" И "НАЗАД" НА ДЕТАЛЬНОЙ СТРАНИЦЕ И БИБЛИОТЕКИ
ADDGAME_BACK_BUTTON_STYLE = f"""
    QPushButton {{
        background: rgba(20, 20, 20, 0.40);
        border: {border_b} rgba(255, 255, 255, 0.5);
        border-radius: {border_radius_a};
        color: {color_f};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 8px 16px;
    }}
    QPushButton:hover {{
        background: {color_a};
    }}
    QPushButton:pressed {{
        background: {color_a};
    }}
"""

# ОСНОВНОЙ ФРЕЙМ ДЕТАЛЕЙ ИГРЫ
DETAIL_CONTENT_FRAME_STYLE = f"""
    QFrame {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(20, 20, 20, 0.40),
            stop:1 rgba(20, 20, 20, 0.35));
        border:  {border_a} {color_g};
        border-radius: {border_radius_b};
    }}
"""

# ФРЕЙМ ПОД ОБЛОЖКОЙ
COVER_FRAME_STYLE = f"""
    QFrame {{
        background: rgba(30, 30, 30, 0.80);
        border-radius: {border_radius_b};
        border:  {border_a} {color_g};
    }}
"""

# СКРУГЛЕНИЕ LABEL ПОД ОБЛОЖКУ
COVER_LABEL_STYLE = f"border-radius: {border_radius_b};"

# ВИДЖЕТ ДЕТАЛЕЙ (ТЕКСТ, ОПИСАНИЕ)
DETAILS_WIDGET_STYLE = f"background: rgba(20,20,20,0.40); border-radius: {border_radius_b}; padding: 10px;"

# НАЗВАНИЕ (ЗАГОЛОВОК) НА ДЕТАЛЬНОЙ СТРАНИЦЕ
DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 32px; color: #007AFF;"

# ЛИНИЯ-РАЗДЕЛИТЕЛЬ
DETAIL_PAGE_LINE_STYLE = "color: rgba(255,255,255,0.12); margin: 10px 0;"

# ТЕКСТ ОПИСАНИЯ
DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_a}; color: {color_f}; line-height: 1.5;"

# СТИЛЬ КНОПКИ "ИГРАТЬ"
PLAY_BUTTON_STYLE = f"""
    QPushButton {{
        background: rgba(20, 20, 20, 0.40);
        border: {border_b} rgba(255, 255, 255, 0.5);
        border-radius: {border_radius_a};
        font-size: 18px;
        color: {color_f};
        font-weight: bold;
        font-family: '{font_family}';
        padding: 8px 16px;
        min-width: 120px;
        min-height: 40px;
    }}
    QPushButton:hover {{
        background: {color_a};
    }}
    QPushButton:pressed {{
        background: {color_a};
    }}
    QPushButton:focus {{
        background: {color_a};
    }}
"""

ADDGAME_INPUT_STYLE = f"""
    QLineEdit {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        height: 34px;
        padding-left: 12px;
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QLineEdit:hover {{
        background: {color_c};
        border: {border_c} {color_a};
    }}
    QLineEdit:focus {{
        border: {border_c} {color_a};
        background-color: {color_e};
    }}
"""

# ФУНКЦИЯ ДЛЯ ДИНАМИЧЕСКОГО ГРАДИЕНТА (ДЕТАЛИ ИГР)
# Функции из этой темы срабатывает всегда вне зависимости от выбранной темы, функции из других тем работают только в этих темах
def detail_page_style(stops):
    return f"""
    QWidget {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    {stops});
                                    border-radius: {border_radius_b};
    }}
"""
