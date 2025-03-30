# КОНСТАНТЫ
favoriteLabelSize = 48, 48 # Размер контейнера для звёздочки избранного
pixmapsScaledSize = 60, 60 # Уровень закругления обложек


# СТИЛЬ ШАПКИ ГЛАВНОГО ОКНА
MAIN_WINDOW_HEADER_STYLE = """
    QFrame {
        background: transparent;
        border: 10px solid rgba(255, 255, 255, 0.10);
        border-bottom: 0px solid rgba(255, 255, 255, 0.15);
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
        margin: 0 0 0 0;
        color: #007AFF;
    }
"""

# СТИЛЬ ОБЛАСТИ НАВИГАЦИИ (КНОПКИ ВКЛАДОК)
NAV_WIDGET_STYLE = """
    QWidget {
        background: none;
        border: 0px solid;
        border-radius: 0px;
    }
"""

# СТИЛЬ КНОПОК ВКЛАДОК НАВИГАЦИИ
NAV_BUTTON_STYLE = """
    QPushButton {
        background: rgba(0,122,255,0);
        padding: 12px 24px;
        margin: 10px 0 10px 10px;
        color: #7f7f7f;
        font-size: 18px;
        font-family: 'Play';
        text-transform: uppercase;
        border: none;
        border-radius: 15px;
    }
    QPushButton:checked {
        background: rgba(0,122,255,0);
        color: #09bec8;
        font-weight: normal;
        text-decoration: underline;
        border-radius: 15px;
    }
    QPushButton:hover {
        background: none;
        color: #09bec8;
    }
"""

# ГЛОБАЛЬНЫЙ СТИЛЬ ДЛЯ ОКНА (ФОН) И QLabel
MAIN_WINDOW_STYLE = """
    QMainWindow {
        background: none;
    }
    QLabel {
        color: #ffffff;
    }
"""

# СТИЛЬ ПОЛЯ ПОИСКА
SEARCH_EDIT_STYLE = """
    QLineEdit {
        background-color: rgba(30, 30, 30, 0.50);
        border: 0px solid rgba(255, 255, 255, 0.25);
        border-radius: 10px;
        padding: 7px 14px;
        font-family: 'Play';
        font-size: 16px;
        color: #ffffff;
    }
    QLineEdit:focus {
        border: 0px solid #007AFF;
    }
"""

# ОТКЛЮЧАЕМ РАМКУ У QScrollArea
SCROLL_AREA_STYLE = """
    QWidget {
        background: transparent;
    }
    QScrollBar:vertical {
        width: 10px;
        border: 0px solid;
        border-radius: 5px;
        background: rgba(20, 20, 20, 0.30);
    }
    QScrollBar::handle:vertical {
        background: #bebebe;
        border: 0px solid;
        border-radius: 5px;
    }
    QScrollBar::add-line:vertical {
        border: 0px solid;
        background: none;
    }
    QScrollBar::sub-line:vertical {
        border: 0px solid;
        background: none;
    }
    QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
        border: 0px solid;
        width: 3px;
        height: 3px;
        background: none;
    }

    QScrollBar:horizontal {
        height: 10px;
        border: 0px solid;
        border-radius: 5px;
        background: rgba(20, 20, 20, 0.30);
    }
    QScrollBar::handle:horizontal {
        background: #bebebe;
        border: 0px solid;
        border-radius: 5px;
    }
    QScrollBar::add-line:horizontal {
        border: 0px solid;
        background: none;
    }
    QScrollBar::sub-line:horizontal {
        border: 0px solid;
        background: none;
    }
    QScrollBar::up-arrow:horizontal, QScrollBar::down-arrow:horizontal {
        border: 0px solid;
        width: 3px;
        height: 3px;
        background: none;
    }

"""

# СТИЛЬ ОБЛАСТИ ДЛЯ КАРТОЧЕК ИГР (QWidget)
LIST_WIDGET_STYLE = """
    QWidget {
        background: none;
        border: 0px solid rgba(255, 255, 255, 0.10);
        border-radius: 25px;
    }
"""

# ЗАГОЛОВОК "БИБЛИОТЕКА" НА ВКЛАДКЕ
INSTALLED_TAB_TITLE_STYLE = "font-family: 'Play'; font-size: 24px; color: #ffffff;"

# СТИЛЬ КНОПКИ "ДОБАВИТЬ ИГРУ"
ADD_GAME_BUTTON_STYLE = """
    QPushButton {
        background: rgba(20, 20, 20, 0.40);
        border: 0px solid rgba(255, 255, 255, 0.20);
        border-radius: 10px;
        color: #ffffff;
        font-size: 16px;
        font-family: 'Play';
        padding: 8px 16px;
    }
    QPushButton:hover {
        background: #09bec8;
    }
    QPushButton:pressed {
        background: #09bec8;
    }
"""

# ТЕКСТОВЫЕ СТИЛИ: ЗАГОЛОВКИ И ОСНОВНОЙ КОНТЕНТ
TAB_TITLE_STYLE = "font-family: 'Play'; font-size: 24px; color: #ffffff; background-color: none;"
CONTENT_STYLE = "font-family: 'Play'; font-size: 16px; color: #ffffff;"

# ФОН ДЛЯ ДЕТАЛЬНОЙ СТРАНИЦЫ, ЕСЛИ ОБЛОЖКА НЕ ЗАГРУЖЕНА
DETAIL_PAGE_NO_COVER_STYLE = "background: rgba(20,20,20,0.95); border-radius: 15px;"

# СТИЛЬ КНОПКИ "НАЗАД" НА ДЕТАЛЬНОЙ СТРАНИЦЕ
BACK_BUTTON_STYLE = """
    QPushButton {
        background: rgba(20, 20, 20, 0.40);
        border: 0px solid rgba(255, 255, 255, 0.90);
        border-radius: 15px;
        color: #ffffff;
        font-size: 16px;
        font-family: 'Play';
        padding: 8px 16px;
    }
    QPushButton:hover {
        background: #09bec8;
    }
    QPushButton:pressed {
        background: #09bec8;
    }
"""

# ОСНОВНОЙ ФРЕЙМ ДЕТАЛЕЙ ИГРЫ
DETAIL_CONTENT_FRAME_STYLE = """
    QFrame {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(20, 20, 20, 0.40),
            stop:1 rgba(20, 20, 20, 0.35));
        border: 0px solid rgba(255, 255, 255, 0.10);
        border-radius: 15px;
    }
"""

# ФРЕЙМ ПОД ОБЛОЖКОЙ
COVER_FRAME_STYLE = """
    QFrame {
        background: rgba(30, 30, 30, 0.80);
        border-radius: 15px;
        border: 0px solid rgba(255, 255, 255, 0.15);
    }
"""

# СКРУГЛЕНИЕ LABEL ПОД ОБЛОЖКУ
COVER_LABEL_STYLE = "border-radius: 100px;"

# ВИДЖЕТ ДЕТАЛЕЙ (ТЕКСТ, ОПИСАНИЕ)
DETAILS_WIDGET_STYLE = "background: rgba(20,20,20,0.40); border-radius: 15px; padding: 10px;"

# НАЗВАНИЕ (ЗАГОЛОВОК) НА ДЕТАЛЬНОЙ СТРАНИЦЕ
DETAIL_PAGE_TITLE_STYLE = "font-family: 'Play'; font-size: 32px; color: #007AFF;"

# ЛИНИЯ-РАЗДЕЛИТЕЛЬ
DETAIL_PAGE_LINE_STYLE = "color: rgba(255,255,255,0.12); margin: 10px 0;"

# ТЕКСТ ОПИСАНИЯ
DETAIL_PAGE_DESC_STYLE = "font-family: 'Play'; font-size: 16px; color: #ffffff; line-height: 1.5;"

# Стиль списка тем
COMBO_BOX_STYLE = """
QComboBox {
    background-color: #2B2B2B;
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 0px solid;
    padding: 4px;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 20px;
    border-left: 1px solid #555555;
}
QComboBox QAbstractItemView {
    background-color: #333333;
    color: #ffffff;
    selection-background-color: #444444;
}
"""

# СТИЛЬ КНОПКИ "ИГРАТЬ"
PLAY_BUTTON_STYLE = """
    QPushButton {
        background: rgba(20, 20, 20, 0.40);
        border: 0px solid rgba(255, 255, 255, 0.20);
        border-radius: 15px;
        font-size: 18px;
        color: #ffffff;
        font-weight: bold;
        font-family: 'Play';
        padding: 8px 16px;
        min-width: 120px;
        min-height: 40px;
    }
    QPushButton:hover {
        background: #09bec8;
    }
    QPushButton:pressed {
        background: #09bec8;
    }
"""

# СТИЛЬ КНОПКИ "ОБЗОР..." В ДИАЛОГЕ "ДОБАВИТЬ ИГРУ"
DIALOG_BROWSE_BUTTON_STYLE = """
    QPushButton {
        background: rgba(20, 20, 20, 0.40);
        border: 0px solid rgba(255, 255, 255, 0.20);
        border-radius: 15px;
        color: #ffffff;
        font-size: 16px;
        padding: 5px 10px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(0,122,255,0.20),
            stop:1 rgba(0,122,255,0.15));
    }
    QPushButton:pressed {
        background: rgba(20, 20, 20, 0.60);
        border: 0px solid rgba(255, 255, 255, 0.25);
    }
"""

# СТИЛЬ КАРТОЧКИ ИГРЫ (GAMECARD)
GAME_CARD_WINDOW_STYLE = """
    QFrame {
        border-radius: 20px;
        background: rgba(20, 20, 20, 0.40);
        border: 0px solid rgba(255, 255, 255, 0.20);
    }
"""

# НАЗВАНИЕ В КАРТОЧКЕ (QLabel)
GAME_CARD_NAME_LABEL_STYLE = """
    QLabel {
        color: #ffffff;
        font-family: 'Play';
        font-size: 16px;
        font-weight: bold;
        background-color: rgba(20, 20, 20, 0);
        border-bottom-left-radius: 20px;
        border-bottom-right-radius: 20px;
        padding: 14px, 7px, 3px, 7px;
        qproperty-wordWrap: true;
    }
"""

# ДОПОЛНИТЕЛЬНЫЕ СТИЛИ ИНФОРМАЦИИ НА СТРАНИЦЕ ИГР
LAST_LAUNCH_TITLE_STYLE = "font-family: 'Play'; font-size: 11px; color: #bbbbbb; text-transform: uppercase; letter-spacing: 0.75px; margin-bottom: 2px;"
LAST_LAUNCH_VALUE_STYLE = "font-family: 'Play'; font-size: 13px; color: #ffffff; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = "font-family: 'Play'; font-size: 11px; color: #bbbbbb; text-transform: uppercase; letter-spacing: 0.75px; margin-bottom: 2px;"
PLAY_TIME_VALUE_STYLE = "font-family: 'Play'; font-size: 13px; color: #ffffff; font-weight: 600; letter-spacing: 0.75px;"
GAMEPAD_SUPPORT_VALUE_STYLE = """
    font-family: 'Play'; font-size: 12px; color: #00ff00;
    font-weight: bold; background: rgba(0, 0, 0, 0.3);
    border-radius: 5px; padding: 4px 8px;
"""

# СТИЛИ ПОЛНОЭКРАНОГО ПРЕВЬЮ СКРИНШОТОВ ТЕМЫ
PREV_BUTTON_STYLE="background-color: rgba(0, 0, 0, 0.5); color: white; border: none;"
NEXT_BUTTON_STYLE="background-color: rgba(0, 0, 0, 0.5); color: white; border: none;"
CAPTION_LABEL_STYLE="color: white; font-size: 16px;"

# СТИЛИ БЕЙДЖА PROTONDB НА КАРТОЧКЕ
def get_protondb_badge_style(tier):
    tier = tier.lower()
    tier_colors = {
        "platinum": {"background": "rgba(255,255,255,0.9)", "color": "black"},
        "gold": {"background": "rgba(253,185,49,0.7)", "color": "black"},
        "silver": {"background": "rgba(169,169,169,0.8)", "color": "black"},
        "bronze": {"background": "rgba(205,133,63,0.7)", "color": "black"},
        "borked": {"background": "rgba(255,0,0,0.7)", "color": "black"},
        "pending": {"background": "rgba(160,82,45,0.7)", "color": "black"}
    }
    colors = tier_colors.get(tier, {"background": "rgba(0, 0, 0, 0.5)", "color": "white"})
    return f"""
        qproperty-alignment: AlignCenter;
        background-color: {colors["background"]};
        color: {colors["color"]};
        font-size: 16px;
        border-radius: 5px;
        font-family: 'Play';
        font-weight: bold;
    """

# СТИЛИ БЕЙДЖА STEAM
STEAM_BADGE_STYLE= """
    qproperty-alignment: AlignCenter;
    background: rgba(0, 0, 0, 0.5);
    color: white;
    font-size: 16px;
    border-radius: 5px;
    font-family: 'Play';
    font-weight: bold;
"""

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

# AUTOINSTALL_WIDGET_STYLE
AUTOINSTALL_WIDGET_STYLE= """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(55,55,55,1),
            stop:1 rgba(24,24,24,1));
        border-radius: 0px;
    }
"""

# EMULATORS_WIDGET_STYLE
EMULATORS_WIDGET_STYLE= """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(55,55,55,1),
            stop:1 rgba(24,24,24,1));
        border-radius: 0px;
    }
"""

# WINE_SETTINGS_WIDGET_STYLE
WINE_SETTINGS_WIDGET_STYLE= """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(55,55,55,1),
            stop:1 rgba(24,24,24,1));
        border-radius: 0px;
    }
"""

# PORTPROTON_SETTINGS_WIDGET_STYLE
PORTPROTON_SETTINGS_WIDGET_STYLE= """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(55,55,55,1),
            stop:1 rgba(24,24,24,1));
        border-radius: 0px;
    }
"""

# THEMES_WIDGET_STYLE
THEMES_WIDGET_STYLE= """
    QWidget {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(55,55,55,1),
            stop:1 rgba(24,24,24,1));
        border-radius: 0px;
    }
"""

# SLIDER_SIZE_STYLE
SLIDER_SIZE_STYLE= """
    QWidget {
        background: transparent;
    }
    QSlider::groove:horizontal {
        border: 0px solid;
        border-radius: 3px;
        height: 6px; /* the groove expands to the size of the slider by default. by giving it a height, it has a fixed size */
        background: rgba(20, 20, 20, 0.30);
        margin: 6px 0;
    }
    QSlider::handle:horizontal {
        background: #bebebe;
        border: 0px solid;
        width: 18px;
        height: 18px;
        margin: -6px 0; /* handle is placed by default on the contents rect of the groove. Expand outside the groove */
        border-radius: 9px;
    }
"""

# Favorite Star
FAVORITE_LABEL_STYLE = "color: gold; font-size: 32px; background: transparent;"

# СТИЛИ ДЛЯ QMessageBox (ОКНА СООБЩЕНИЙ)
MESSAGE_BOX_STYLE = """
    QMessageBox {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(40, 40, 40, 0.95),
            stop:1 rgba(25, 25, 25, 0.95));
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 12px;
    }
    QMessageBox QLabel {
        color: #ffffff;
        font-family: 'Play';
        font-size: 16px;
    }
    QMessageBox QPushButton {
        background: rgba(30, 30, 30, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 8px;
        color: #ffffff;
        font-family: 'Play';
        padding: 8px 20px;
        min-width: 80px;
    }
    QMessageBox QPushButton:hover {
        background: #09bec8;
        border-color: rgba(255, 255, 255, 0.3);
    }
"""

# СТИЛИ ДЛЯ ВКЛАДКИ НАСТРОЕК PORTPROTON
FORM_LABEL_STYLE = """
    QLabel {
        color: #bbbbbb;
        font-family: 'Play';
        font-size: 14px;
        padding: 4px 0;
    }
"""

PROXY_INPUT_STYLE = """
    QLineEdit {
        background: rgba(30, 30, 30, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 8px;
        padding: 8px;
        color: #ffffff;
        font-family: 'Play';
        font-size: 14px;
    }
    QLineEdit:focus {
        border-color: #09bec8;
    }
"""

SETTINGS_COMBO_STYLE = """
    QComboBox {
        background: rgba(30, 30, 30, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 8px;
        padding: 6px;
        color: #ffffff;
        font-family: 'Play';
        font-size: 14px;
        min-width: 120px;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: center right;
        width: 20px;
        border-left: 1px solid rgba(255, 255, 255, 0.2);
    }
    QComboBox QAbstractItemView {
        background: rgba(40, 40, 40, 0.95);
        color: #ffffff;
        selection-background-color: #09bec8;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }
"""

SETTINGS_SAVE_BUTTON_STYLE = """
    QPushButton {
        background: rgba(0, 158, 188, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 8px;
        color: #ffffff;
        font-family: 'Play';
        font-size: 16px;
        padding: 10px 25px;
    }
    QPushButton:hover {
        background: rgba(0, 158, 188, 0.9);
    }
    QPushButton:pressed {
        background: #09bec8;
    }
"""

# ФУНКЦИЯ ДЛЯ ДИНАМИЧЕСКОГО ГРАДИЕНТА (ДЕТАЛИ ИГР)
# Функции из этой темы срабатывает всегда вне зависимости от выбранной темы, функции из других тем работают только в этих темах
def detail_page_style(stops):
    return f"""
    QWidget {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    {stops});
                                    border-radius: 15px;
    }}
"""
