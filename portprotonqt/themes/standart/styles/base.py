from .constants import *

# ГЛОБАЛЬНЫЙ СТИЛЬ ДЛЯ ОКНА (ФОН), ЛЭЙБЛОВ, КНОПОК
MAIN_WINDOW_STYLE = f"""
    QWidget {{
        background: {color_b};
    }}
    QLabel {{
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QPushButton {{
        background: {color_c};
        border: {border_c} rgba(255, 255, 255, 0.01);
        border-radius: {border_radius_a};
        color: {color_f};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 8px 16px;
    }}
    QPushButton:hover {{
        background: {color_a};
        border: {border_c} {color_a};
    }}
    QPushButton:pressed {{
        background: {color_b};
    }}
    QPushButton:focus {{
        border: {border_c} {color_a};
        background-color: {color_a};
    }}
"""

# СТИЛЬ ПРОГРЕСС-БАРА
PROGRESS_BAR_STYLE = f"""
    QProgressBar {{
        color: {color_f};
        background-color: {color_c};
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {color_a};
    }}
"""

# СТИЛЬ СТАТУС-БАРА
STATUS_BAR_STYLE = f"""
    QStatusBar {{
        color: {color_f};
    }}
"""

# СТИЛЬ ШАПКИ ГЛАВНОГО ОКНА
MAIN_WINDOW_HEADER_STYLE = f"""
    QFrame {{
        background: {color_h};
        border: 10px solid {color_g};
        border-bottom: 0px solid {color_g};
        border-top-left-radius: 30px;
        border-top-right-radius: 30px;
        border: none;
    }}
"""

# СТИЛЬ ОБЛАСТИ НАВИГАЦИИ (КНОПКИ ВКЛАДОК)
NAV_WIDGET_STYLE = f"""
    QWidget {{
        background: {color_h};
        border:  {border_a};
    }}
"""

# СТИЛЬ КНОПОК ВКЛАДОК НАВИГАЦИИ
NAV_BUTTON_STYLE = f"""
    NavLabel {{
        background: rgba(0,0,0,0);
        padding: 12px 3px;
        margin: 10px 0 10px 10px;
        color: #7f7f7f;
        font-family: '{font_family}';
        font-size: {font_size_a};
        text-transform: uppercase;
        border: {color_a};
        border-radius: {border_radius_b};
    }}
    NavLabel[checked = true] {{
        background: rgba(0,0,0,0);
        color: {color_a};
        font-weight: normal;
        text-decoration: underline;
        border-radius: {border_radius_b};
    }}
    NavLabel:hover {{
        background: none;
        color: {color_a};
    }}
"""

# СТИЛЬ ПОЛЯ ПОИСКА
SEARCH_EDIT_STYLE = f"""
    QLineEdit {{
        background-color: rgba(30, 30, 30, 0.50);
        border: {border_b} rgba(255, 255, 255, 0.5);
        border-radius: {border_radius_a};
        padding: 7px 14px;
        font-family: '{font_family}';
        font-size: {font_size_a};
        color: {color_f};
    }}
    QLineEdit:focus {{
        border: {border_b} {color_a};
    }}
"""

# ОТКЛЮЧАЕМ РАМКУ У QScrollArea
SCROLL_AREA_STYLE = f"""
    QWidget {{
        background: {color_h};
    }}
    QScrollBar:vertical {{
        width: 10px;
        border:  {border_a};
        border-radius: 5px;
        background: rgba(20, 20, 20, 0.30);
    }}
    QScrollBar::handle:vertical {{
        background: #bebebe;
        border:  {border_a};
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical {{
        border:  {border_a};
        background: none;
    }}
    QScrollBar::sub-line:vertical {{
        border:  {border_a};
        background: none;
    }}
    QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
        border:  {border_a};
        width: 3px;
        height: 3px;
        background: none;
    }}

    QScrollBar:horizontal {{
        height: 10px;
        border:  {border_a};
        border-radius: 5px;
        background: rgba(20, 20, 20, 0.30);
    }}
    QScrollBar::handle:horizontal {{
        background: #bebebe;
        border:  {border_a};
        border-radius: 5px;
    }}
    QScrollBar::add-line:horizontal {{
        border:  {border_a};
        background: none;
    }}
    QScrollBar::sub-line:horizontal {{
        border:  {border_a};
        background: none;
    }}
    QScrollBar::up-arrow:horizontal, QScrollBar::down-arrow:horizontal {{
        border:  {border_a};
        width: 3px;
        height: 3px;
        background: none;
    }}
"""

# SLIDER_SIZE_STYLE
SLIDER_SIZE_STYLE= f"""
    QWidget {{
        background: {color_h};
        height: 25px;
    }}
    QSlider::groove:horizontal {{
        border:  {border_a};
        border-radius: 3px;
        height: 6px; /* the groove expands to the size of the slider by default. by giving it a height, it has a fixed size */
        background: rgba(20, 20, 20, 0.30);
        margin: 6px 0;
    }}
    QSlider::handle:horizontal {{
        background: #bebebe;
        border:  {border_a};
        width: 18px;
        height: 18px;
        margin: -6px 0; /* handle is placed by default on the contents rect of the groove. Expand outside the groove */
        border-radius: 9px;
    }}
"""

# СТИЛЬ ОБЛАСТИ ДЛЯ КАРТОЧЕК ИГР (QWidget)
LIST_WIDGET_STYLE = """
    QWidget {
        background: none;
        border:  {border_a} {color_g};
        border-radius: 25px;
    }
"""

# ЗАГОЛОВОК "БИБЛИОТЕКА" НА ВКЛАДКЕ
INSTALLED_TAB_TITLE_STYLE = f"""
    QLabel {{
        font-family: '{font_family}';
        font-size: {font_size_b};
        color: {color_f};
    }}
"""

# СТИЛЬ КНОПОК "СОХРАНЕНИЯ, ПРИМЕНЕНИЯ И Т.Д."
ACTION_BUTTON_STYLE = f"""
    QPushButton {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        color: {color_f};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 8px 16px;
    }}
    QPushButton:hover {{
        background: {color_a};
        border: {border_c} {color_a};
    }}
    QPushButton:pressed {{
        background: {color_b};
    }}
    QPushButton:focus {{
        border: {border_c} {color_a};
        background-color: {color_a};
    }}
"""

# СТИЛЬ ОВЕРЛЕЯ
OVERLAY_WINDOW_STYLE = f"background: {color_b};"
OVERLAY_BUTTON_STYLE = f"""
    QPushButton {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        color: {color_f};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 8px 16px;
    }}
    QPushButton:hover {{
        background: {color_a};
        border: {border_c} {color_a};
    }}
    QPushButton:pressed {{
        background: {color_b};
    }}
    QPushButton:focus {{
        border: {border_c} {color_a};
        background-color: {color_a};
    }}
"""

# ТЕКСТОВЫЕ СТИЛИ: ЗАГОЛОВКИ И ОСНОВНОЙ КОНТЕНТ
TAB_TITLE_STYLE = f"font-family: '{font_family}'; font-size: {font_size_b}; color: {color_f}; background-color: none;"
CONTENT_STYLE = f"""
    QLabel {{
        font-family: '{font_family}';
        font-size: {font_size_a};
        color: {color_f};
        background-color: none;
        border-bottom: {border_b} rgba(255, 255, 255, 0.2);
        padding-bottom: 15px;
    }}
"""

PREVIEW_WIDGET_STYLE = f"""
    QWidget {{
        margin-top: 3px;
        background-color: {color_c};
        border-radius: {border_radius_a};
    }}
"""

# СТИЛЬ ОСНОВНЫХ СТРАНИЦ
# LIBRARY_WIDGET_STYLE
LIBRARY_WIDGET_STYLE= """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(112,20,132,1),
            stop:1 rgba(50,134,182,1));
        border-radius: 0px;
    }
"""

# CONTAINER_STYLE
CONTAINER_STYLE= """
    QWidget {
        background-color: none;
    }
"""

# OTHER_PAGES_WIDGET_STYLE
OTHER_PAGES_WIDGET_STYLE= f"""
    QWidget {{
        background: {color_d};
        border-radius: 0px;
    }}
"""

# CAROUSEL_WIDGET_STYLE
CAROUSEL_WIDGET_STYLE= f"""
    QWidget {{
        background: {color_c};
        border-radius: 0px;
    }}
"""

# СТИЛИ ДЛЯ ВКЛАДКИ НАСТРОЕК PORTPROTON
# PARAMS_TITLE_STYLE
PARAMS_TITLE_STYLE = f"color: {color_f}; font-family: '{font_family}'; font-size: {font_size_a}; padding: 10px; background: {color_h};"

PROXY_INPUT_STYLE = f"""
    QLineEdit {{
        background: {color_b};
        border: {border_c} rgba(255, 255, 255, 0.01);
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

# СТИЛИ ДЛЯ QMessageBox (ОКНА СООБЩЕНИЙ)
MESSAGE_BOX_STYLE = f"""
    QMessageBox {{
        background: {color_b};
        border: {border_a};
    }}
    QMessageBox QLabel {{
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QMessageBox QPushButton {{
        background: {color_c};
        border: {border_a} {color_h};
        border-radius: {border_radius_a};
        color: {color_f};
        font-family: '{font_family}';
        padding: 8px 20px;
        min-width: 80px;
    }}
    QMessageBox QPushButton:hover {{
        background: {color_a};
        border-color: border: {border_b} {color_a};
    }}
    QMessageBox QPushButton:focus {{
        border: {border_c} {color_a};
        background: {color_a};
    }}
"""

# Favorite Star
FAVORITE_LABEL_STYLE = f"color: gold; font-size: 32px; background: {color_h};"
