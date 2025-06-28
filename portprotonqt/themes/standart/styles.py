from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config_utils import read_theme_from_config

theme_manager = ThemeManager()
current_theme_name = read_theme_from_config()

# КОНСТАНТЫ
favoriteLabelSize = 48, 48
pixmapsScaledSize = 60, 60

# VARS
font_family = "Play"
font_size_a = "16px"
font_size_b = "24px"
border_a = "0px solid"
border_b = "1px solid"
border_c = "2px solid"
border_radius_a = "10px"
border_radius_b = "15px"
color_a = "#409EFF"
color_b = "#282a33"
color_c = "#3f424d"
color_d = "#32343d"
color_e = "#404554"
color_f = "#ffffff"
color_g = "rgba(0, 0, 0, 0)"
color_h = "transparent"

GAME_CARD_ANIMATION = {
    # Ширина обводки карточки в состоянии покоя (без наведения или фокуса).
    # Влияет на толщину рамки вокруг карточки, когда она не выделена.
    # Значение в пикселях.
    "default_border_width": 2,

    # Ширина обводки при наведении курсора.
    # Увеличивает толщину рамки, когда курсор находится над карточкой.
    # Значение в пикселях.
    "hover_border_width": 8,

    # Ширина обводки при фокусе (например, при выборе с клавиатуры).
    # Увеличивает толщину рамки, когда карточка в фокусе.
    # Значение в пикселях.
    "focus_border_width": 12,

    # Минимальная ширина обводки во время пульсирующей анимации.
    # Определяет минимальную толщину рамки при пульсации (анимация "дыхания").
    # Значение в пикселях.
    "pulse_min_border_width": 8,

    # Максимальная ширина обводки во время пульсирующей анимации.
    # Определяет максимальную толщину рамки при пульсации.
    # Значение в пикселях.
    "pulse_max_border_width": 10,

    # Длительность анимации изменения толщины обводки (например, при наведении или фокусе).
    # Влияет на скорость перехода от одной ширины обводки к другой.
    # Значение в миллисекундах.
    "thickness_anim_duration": 300,

    # Длительность одного цикла пульсирующей анимации.
    # Определяет, как быстро рамка "пульсирует" между min и max значениями.
    # Значение в миллисекундах.
    "pulse_anim_duration": 800,

    # Длительность анимации вращения градиента.
    # Влияет на скорость, с которой градиентная обводка вращается вокруг карточки.
    # Значение в миллисекундах.
    "gradient_anim_duration": 3000,

    # Начальный угол градиента (в градусах).
    # Определяет начальную точку вращения градиента при старте анимации.
    "gradient_start_angle": 360,

    # Конечный угол градиента (в градусах).
    # Определяет конечную точку вращения градиента.
    # Значение 0 означает полный поворот на 360 градусов.
    "gradient_end_angle": 0,

    # Тип кривой сглаживания для анимации увеличения обводки (при наведении/фокусе).
    # Влияет на "чувство" анимации (например, плавное ускорение или замедление).
    # Возможные значения: строки, соответствующие QEasingCurve.Type (например, "OutBack", "InOutQuad").
    "thickness_easing_curve": "OutBack",

    # Тип кривой сглаживания для анимации уменьшения обводки (при уходе курсора/потере фокуса).
    # Влияет на "чувство" возврата к исходной ширине обводки.
    "thickness_easing_curve_out": "InBack",

    # Цвета градиента для анимированной обводки.
    # Список словарей, где каждый словарь задает позицию (0.0–1.0) и цвет в формате hex.
    # Влияет на внешний вид обводки при наведении или фокусе.
    "gradient_colors": [
        {"position": 0, "color": "#00fff5"},    # Начальный цвет (циан)
        {"position": 0.33, "color": "#FF5733"}, # Цвет на 33% (оранжевый)
        {"position": 0.66, "color": "#9B59B6"}, # Цвет на 66% (пурпурный)
        {"position": 1, "color": "#00fff5"}     # Конечный цвет (возвращение к циану)
    ]
}

CONTEXT_MENU_STYLE = f"""
    QMenu {{
        background: {color_b};
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
        padding: 5px;
    }}
    QMenu::item {{
        padding: 8px 20px;
        background: {color_h};
        border-radius: {border_radius_a};
        color: {color_f};
    }}
    QMenu::item:selected {{
        background: {color_a};
        color: {color_f};
    }}
    QMenu::item:hover {{
        background: {color_a};
        color: {color_f};
    }}
    QMenu::item:focus {{
        background: {color_a};
        color: {color_f};
        border: {border_b} rgba(255, 255, 255, 0.3);
        border-radius: {border_radius_a};
    }}
"""

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
COVER_LABEL_STYLE = "border-radius: 100px;"

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
"""

# СТИЛЬ КНОПКИ "ОБЗОР..." В ДИАЛОГЕ "ДОБАВИТЬ ИГРУ"
DIALOG_BROWSE_BUTTON_STYLE = f"""
    QPushButton {{
        background: rgba(20, 20, 20, 0.40);
        border:  {border_a} rgba(255, 255, 255, 0.20);
        border-radius: {border_radius_b};
        color: {color_f};
        font-size: {font_size_a};
        padding: 5px 10px;
    }}
    QPushButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(0,122,255,0.20),
            stop:1 rgba(0,122,255,0.15));
    }}
    QPushButton:pressed {{
        background: rgba(20, 20, 20, 0.60);
        border:  {border_a} rgba(255, 255, 255, 0.25);
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
    QMenu {{
        border: {border_b} {color_g};
        padding: 5px 10px;
        background: {color_d};
    }}
    QMenu::item {{
        padding: 0px 10px;
        border: 10px solid {color_h}; /* reserve space for selection border */
    }}
    QMenu::item:selected {{
        background: {color_c};
        border-radius: {border_radius_a};
    }}
"""

# СТИЛЬ КАРТОЧКИ ИГРЫ (GAMECARD)
GAME_CARD_WINDOW_STYLE = f"""
    QFrame {{
        border-radius: 20px;
        background: rgba(20, 20, 20, 0.40);
        border:  {border_a} {color_g};
    }}
"""

# НАЗВАНИЕ В КАРТОЧКЕ (QLabel)
GAME_CARD_NAME_LABEL_STYLE = f"""
    QLabel {{
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        background-color: {color_g};
        border-bottom-left-radius: 20px;
        border-bottom-right-radius: 20px;
        padding: 14px, 7px, 3px, 7px;
        qproperty-wordWrap: true;
    }}
"""

# ДОПОЛНИТЕЛЬНЫЕ СТИЛИ ИНФОРМАЦИИ НА СТРАНИЦЕ ИГР
LAST_LAUNCH_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 11px; color: #bbbbbb; text-transform: uppercase; letter-spacing: 0.75px; margin-bottom: 2px;"
LAST_LAUNCH_VALUE_STYLE = f"font-family: '{font_family}'; font-size: 13px; color: {color_f}; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 11px; color: #bbbbbb; text-transform: uppercase; letter-spacing: 0.75px; margin-bottom: 2px;"
PLAY_TIME_VALUE_STYLE = f"font-family: '{font_family}'; font-size: 13px; color: {color_f}; font-weight: 600; letter-spacing: 0.75px;"
GAMEPAD_SUPPORT_VALUE_STYLE = f"""
    font-family: '{font_family}'; font-size: {font_size_a}; color: #00ff00;
    font-weight: bold; background: {color_g};
    border-radius: 5px; padding: 4px 8px;
"""

# СТИЛИ ПОЛНОЭКРАНОГО ПРЕВЬЮ СКРИНШОТОВ ТЕМЫ
PREV_BUTTON_STYLE="background-color: rgba(0, 0, 0, 0.5); color: white; border: none;"
NEXT_BUTTON_STYLE="background-color: rgba(0, 0, 0, 0.5); color: white; border: none;"
CAPTION_LABEL_STYLE=f"color: white; font-size: {font_size_a};"

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
        font-size: {font_size_a};
        border-radius: 5px;
        font-family: '{font_family}';
        font-weight: bold;
    """

# СТИЛИ БЕЙДЖА WEANTICHEATYET
def get_anticheat_badge_style(status):
    status = status.lower()
    status_colors = {
        "supported": {"background": "rgba(102, 168, 15, 0.7)", "color": "black"},
        "running": {"background": "rgba(25, 113, 194, 0.7)", "color": "black"},
        "planned": {"background": "rgba(156, 54, 181, 0.7)", "color": "black"},
        "broken": {"background": "rgba(232, 89, 12, 0.7)", "color": "black"},
        "denied": {"background": "rgba(224, 49, 49, 0.7)", "color": "black"}
    }
    colors = status_colors.get(status, {"background": "rgba(0, 0, 0, 0.5)", "color": "white"})
    return f"""
        qproperty-alignment: AlignCenter;
        background-color: {colors["background"]};
        color: {colors["color"]};
        font-size: {font_size_a};
        border-radius: 5px;
        font-family: '{font_family}';
        font-weight: bold;
    """

# СТИЛИ БЕЙДЖА STEAM
STEAM_BADGE_STYLE= f"""
    qproperty-alignment: AlignCenter;
    background: rgba(0, 0, 0, 0.5);
    color: white;
    font-size: {font_size_a};
    border-radius: 5px;
    font-family: '{font_family}';
    font-weight: bold;
"""

# Favorite Star
FAVORITE_LABEL_STYLE = f"color: gold; font-size: 32px; background: {color_h};"

# СТИЛИ ДЛЯ QMessageBox (ОКНА СООБЩЕНИЙ)
MESSAGE_BOX_STYLE = f"""
    QMessageBox {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 rgba(40, 40, 40, 0.95),
            stop:1 rgba(25, 25, 25, 0.95));
        border: {border_b} rgba(255, 255, 255, 0.15);
        border-radius: 12px;
    }}
    QMessageBox QLabel {{
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QMessageBox QPushButton {{
        background: rgba(30, 30, 30, 0.6);
        border: {border_b} rgba(255, 255, 255, 0.2);
        border-radius: {border_radius_a};
        color: {color_f};
        font-family: '{font_family}';
        padding: 8px 20px;
        min-width: 80px;
    }}
    QMessageBox QPushButton:hover {{
        background: #09bec8;
        border-color: rgba(255, 255, 255, 0.3);
    }}
    QMessageBox QPushButton:focus {{
        border: {border_c} {color_a};
        background: {color_e};
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
    QMenu {{
        border: {border_b} rgba(255, 255, 255, 0.2);
        padding: 5px 10px;
        background: {color_d};
    }}
    QMenu::item {{
        padding: 0px 10px;
        border: 10px solid {color_h}; /* reserve space for selection border */
    }}
    QMenu::item:selected {{
        background: {color_c};
        border-radius: {border_radius_a};
    }}
"""

SETTINGS_COMBO_STYLE = f"""
    QComboBox {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        height: 34px;
        padding-left: 12px;
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
        min-width: 120px;
        combobox-popup: 0;
    }}
    QComboBox:on {{
        background: {color_b};
        border: {border_c} {color_a};
        border-bottom-style: none;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
    }}
    QComboBox:hover {{
        border: {border_c} {color_a};
        background: {color_a};
    }}
    /* Состояние фокуса */
    QComboBox:focus {{
        border: {border_c} {color_a};
        background-color: {color_a};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        border-left: {border_b} rgba(255, 255, 255, 0.05);
        padding: 12px;
        height: 12px;
        width: 12px;
    }}
    QComboBox::down-arrow {{
        image: url({theme_manager.get_icon("down", current_theme_name, as_path=True)});
        padding: 12px;
        height: 12px;
        width: 12px;
    }}
    QComboBox::down-arrow:on {{
        image: url({theme_manager.get_icon("up", current_theme_name, as_path=True)});
        padding: 12px;
        height: 12px;
        width: 12px;
    }}
    /* Список при открытом комбобоксе */
    QComboBox QAbstractItemView {{
        outline: none;
        border: {border_c} {color_a};
        border-top-style: none;
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        border-bottom-left-radius: 10px;
        border-bottom-right-radius: 10px;
    }}
    QListView {{
        background: {color_c};
    }}
    QListView::item {{
        padding: 7px 7px 7px 12px;
        margin: 3px;
        border-radius: {border_radius_a};
        color: {color_f};
    }}
    QListView::item:hover {{
        background: {color_b};
    }}
    QListView::item:selected {{
        background: {color_b};
    }}
    /* Выделение в списке при фокусе на элементе */
    QListView::item:focus {{
        background: {color_a};
        color: {color_f};
    }}
"""

SETTINGS_CHECKBOX_STYLE = f"""
    QCheckBox {{
        height: 34px;
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QCheckBox::indicator {{
        width: 24px;
        height: 24px;
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        background: {color_b};
    }}
    QCheckBox::indicator:hover {{
        background: {color_c};
        border: {border_c} {color_a};
    }}
    QCheckBox::indicator:focus {{
        border: {border_c} {color_a};
    }}
    QCheckBox::indicator:checked {{
        image: url({theme_manager.get_icon("check", current_theme_name, as_path=True)});
        border: {border_c} {color_a};
    }}
"""

FILE_EXPLORER_STYLE = f"""
    QListView {{
        font-size: {font_size_a};
        font-family: {font_family};
        background: {color_c};
        color: {color_f};
        border-top-left-radius: 5px;
        border-bottom-left-radius: 5px;
    }}
    QListView::item {{
        padding: 8px;
        margin: 0px 5px;
    }}
    QListView::item:alternate {{
        margin: 0px 5px;
        background: {color_d};
    }}
    QListView::item:selected {{
        background: {color_a};
        color: {color_f};
        border-radius: {border_radius_a};
    }}
    QListView::item:hover {{
        background: {color_a};
        color: {color_f};
        border-radius: {border_radius_a};
    }}
    QListView::item:focus {{
        background: {color_a};
        color: {color_f};
        border-radius: {border_radius_a};
    }}
    QScrollBar:vertical {{
        width: 10px;
        border:  {border_a};
        border-radius: 5px;
        background: {color_c};
    }}
    QScrollBar::handle:vertical {{
        background: #bebebe;
        border:  {border_a};
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical {{
        border:  {border_a};
        background: {color_c};
        border-bottom-right-radius: 5px;
    }}
    QScrollBar::sub-line:vertical {{
        border:  {border_a};
        background: {color_c};
        border-top-right-radius: 5px;
    }}
    QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
        border:  {border_a};
        width: 3px;
        height: 3px;
        background: none;
    }}
"""

FILE_EXPLORER_PATH_LABEL_STYLE = f"""
    QLabel {{
        color: {color_a};
        font-size: {font_size_a};
        font-family: {font_family};
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