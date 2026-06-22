from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config import ui_config

THEME_INHERITS = "standart-light"

theme_manager = ThemeManager()
current_theme_name = ui_config.get_theme()

# === Layout (differs from standart-light) ===
LIBRARY_LAYOUT_MODE = "list"
DETAIL_PAGE_LAYOUT_MODE = "compact"

portProtonPageMargins = (10, 7, 15, 10)
portProtonPageHorizontalSpacing = 5
portProtonPageVerticalSpacing = 2
portProtonPageSectionHeaderSpacing = 5
wineSettingsSetSpacing = 2

mangoHudSwitchesVerticalSpacing = 5
mangoHudFpsColumns = 6
mangoHudFpsVerticalSpacing = 5
mangoHudPresetsColumns = 4
exeSettingsGroupBoxBlockSpacing = 5
exeSettingsGroupBoxElementVerticalSpacing = 2
exeSettingsGroupBoxElementHorizontalSpacing = 5

# === Core Palette (light) ===
color_accent = "#70b8ff"
color_bg = "#F8F9FC"
color_surface = "#F0F2F5"
color_surface_elevated = "#E9ECEF"
color_surface_hover = "#DEE2E6"
color_text = "#ffffff"
color_surface_light = "#d2d3db"
color_surface_mid = "#9394a5"
color_text_dark = "#212529"
color_detail_overlay = "rgba(20,20,20,0.40)"
color_detail_line = "rgba(255,255,255,0.12)"

# === Card Animation (glow) ===
GAME_CARD_ANIMATION = {
    "detail_page_animation_type": "fade",
    "default_border_width": 1,
    "hover_border_width": 3,
    "focus_border_width": 4,
    "pulse_min_border_width": 2,
    "pulse_max_border_width": 3,
    "thickness_anim_duration": 300,
    "pulse_anim_duration": 800,
    "gradient_anim_duration": 3000,
    "gradient_start_angle": 360,
    "gradient_end_angle": 0,
    "card_animation_type": "glow",
    "fill_color": "#70b8ff",
    "fill_alpha": 90,
    "stripe_color": "#70b8ff",
    "stripe_alpha": 255,
    "default_scale": 1.0,
    "hover_scale": 1.08,
    "focus_scale": 1.05,
    "scale_anim_duration": 200,
    "thickness_easing_curve": "OutBack",
    "thickness_easing_curve_out": "InBack",
    "scale_easing_curve": "OutBack",
    "scale_easing_curve_out": "InBack",
    "gradient_colors": [
        {"position": 0, "color": "#d2d3db"},
        {"position": 0.5, "color": "#9394a5"},
        {"position": 1, "color": "#d2d3db"},
    ],
    "detail_page_fade_duration": 350,
    "detail_page_slide_duration": 500,
    "detail_page_bounce_duration": 400,
    "detail_page_fade_duration_exit": 350,
    "detail_page_slide_duration_exit": 500,
    "detail_page_bounce_duration_exit": 400,
    "detail_page_easing_curve": "OutCubic",
    "detail_page_easing_curve_exit": "InCubic",
}

# === QSS styles that differ from standart-light (hardcoded) ===
LIBRARY_WIDGET_STYLE = """
    QWidget {
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #d2d3db,
            stop:1 #9394a5
        );
        border-radius: 0px;
    }
"""

SETTINGS_TITLE_STYLE = """
    QLabel {
        color: #212529;
        height: 34px;
        font-family: 'Play';
        font-size: 16px;
        font-weight: bold;
        padding: 7px;
        background: #F8F9FC;
        border-radius: 10px;
        border: 0px solid #F0F2F5;
        min-width: 320px;
    }
"""

QGROUP_BOX_STYLE = """
    QGroupBox {
        font-family: 'Play';
        font-size: 16px;
        font-weight: bold;
        color: #212529;
        border: 1px solid #F0F2F5;
        border-radius: 10px;
        margin-top: 10px;
        margin-right: 10px;
        padding-top: 5px;
        background: transparent;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }
"""

GAME_CARD_WINDOW_STYLE = """
    QFrame {
        border-radius: 20px;
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,
        stop:0 rgba(255, 255, 255, 0.9),
        stop:0.3 rgba(233, 236, 239, 0.9),
        stop:0.7 rgba(210, 211, 219, 0.9),
        stop:1 rgba(180, 190, 200, 0.9));
        border: 2px solid #ffffff;
    }
"""

COVER_LABEL_STYLE = "border-radius: 15px;"

DETAILS_WIDGET_STYLE = "background: rgba(20,20,20,0.40); border-radius: 15px; padding: 10px;"
COMPACT_DETAILS_WIDGET_STYLE = """
        QFrame, QWidget {
            background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
                stop:0 #E9ECEF,
                stop:1 #d2d3db
            );
            border-radius: 15px;
            padding: 10px;
        }
"""

DETAIL_PAGE_TITLE_STYLE = "font-family: 'Play'; font-size: 32px; color: #70b8ff;"
COMPACT_DETAIL_PAGE_TITLE_STYLE = "font-family: 'Play'; font-size: 32px; color: #212529; background: transparent;"
DETAIL_PAGE_LINE_STYLE = "background: transparent; margin: 0 0;"
DETAIL_PAGE_DESC_STYLE = "font-family: 'Play'; font-size: 16px; color: #212529; line-height: 1.5;"
COMPACT_DETAIL_PAGE_DESC_STYLE = "font-family: 'Play'; font-size: 16px; color: #212529; line-height: 1.5; background: transparent;"
COMPACT_PLAYTIME_WIDGET_STYLE = "background: transparent; border-radius: 15px; padding: 10px;"

LAST_LAUNCH_TITLE_STYLE = "max-height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 #d2d3db); font-family: 'Play'; font-size: 11px; color: #212529; text-transform: uppercase; letter-spacing: 0.75px;"
LAST_LAUNCH_VALUE_STYLE = "height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 #d2d3db); font-family: 'Play'; font-size: 13px; color: #212529; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = "max-height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 #d2d3db); font-family: 'Play'; font-size: 11px; color: #212529; text-transform: uppercase; letter-spacing: 0.75px;"
PLAY_TIME_VALUE_STYLE = "height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 #d2d3db); font-family: 'Play'; font-size: 13px; color: #212529; font-weight: 600; letter-spacing: 0.75px;"

PLAY_BUTTON_STYLE = """
    QPushButton {
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, stop:0 #E9ECEF, stop:1 #d2d3db);
        border: 1px solid #ffffff;
        border-radius: 10px;
        font-size: 16px;
        margin-top: 15px;
        color: #212529;
        font-weight: bold;
        font-family: 'Play';
        padding: 5px 10px;
        min-width: 120px;
        min-height: 30px;
    }
    QPushButton:hover, QPushButton:pressed, QPushButton:focus {
        background: #70b8ff;
    }
"""

ADDGAME_BACK_BUTTON_STYLE = """
    QPushButton {
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, stop:0 #E9ECEF, stop:1 #d2d3db);
        border: 1px solid #ffffff;
        border-radius: 10px;
        color: #212529;
        font-size: 16px;
        font-family: 'Play';
        padding: 5px 10px;
        min-width: 120px;
        min-height: 25px;
    }
    QPushButton:hover, QPushButton:pressed {
        background: #70b8ff;
    }
    QPushButton:focus {
        background: #70b8ff;
        border: 1px solid #70b8ff;
    }
"""

LIBRARY_CONTROLS_BUTTON_STYLE = """
    QPushButton {
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, stop:0 #E9ECEF, stop:1 #d2d3db);
        border: 1px solid #ffffff;
        border-radius: 10px;
        color: #212529;
        font-size: 16px;
        font-family: 'Play';
        padding: 5px 10px;
        min-width: 24px;
        min-height: 25px;
    }
    QPushButton:hover, QPushButton:pressed, QPushButton:focus, QPushButton:checked {
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, stop:0 #E9ECEF, stop:1 #d2d3db);
        border: 1px solid #70b8ff;
    }
"""

LIBRARY_FILTER_COMBOBOX_STYLE = """
    QComboBox {
        background: #F8F9FC;
        border: 1px solid #ffffff;
        border-radius: 10px;
        padding-left: 12px;
        height: 30px;
        color: #212529;
        font-family: 'Play';
        font-size: 16px;
        min-width: 120px;
        combobox-popup: 0;
    }
    QComboBox:hover, QComboBox:focus {
        background: #F8F9FC;
        border: 1px solid #70b8ff;
    }
    QComboBox:on {
        background: #F8F9FC;
        border: 1px solid #70b8ff;
        border-bottom-style: none;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: center right;
        border-left: 1px solid rgba(255, 255, 255, 0.05);
        padding: 12px;
        height: 12px;
        width: 12px;
    }
    QComboBox::down-arrow {
        image: url(%s);
        padding: 12px;
        height: 10px;
        width: 10px;
    }
    QComboBox::down-arrow:on {
        image: url(%s);
        padding: 12px;
        height: 10px;
        width: 10px;
    }
    QComboBox QAbstractItemView {
        outline: none;
        background: #F0F2F5;
        border: 1px solid #70b8ff;
        border-top-style: none;
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        border-bottom-left-radius: 10px;
        border-bottom-right-radius: 10px;
    }
    QComboBox QAbstractItemView::item {
        padding: 3px 3px 3px 6px;
        margin: 1px;
        min-height: 24px;
        border-radius: 10px;
        color: #212529;
    }
    QComboBox QAbstractItemView::item:hover,
    QComboBox QAbstractItemView::item:selected {
        background: #70b8ff;
        color: #212529;
    }
""" % (
    theme_manager.get_icon("down", current_theme_name, as_path=True),
    theme_manager.get_icon("up", current_theme_name, as_path=True),
)

SEARCH_EDIT_STYLE = """
    QLineEdit {
        background: #F8F9FC;
        border: 0px solid;
        border-radius: 10px;
        padding: 5px 10px;
        font-family: 'Play';
        font-size: 16px;
        color: #212529;
        min-height: 25px;
    }
    QLineEdit:hover, QLineEdit:focus {
        border: 1px solid #70b8ff;
    }
"""

NAV_BUTTON_STYLE = """
    NavLabel {
        background: transparent;
        padding: 6px 3px;
        margin: 10px 0 10px 10px;
        color: rgba(40, 42, 51, 0.9);
        font-family: 'Play';
        font-size: 16px;
        text-transform: uppercase;
        border: #70b8ff;
        border-radius: 0px;
    }
    NavLabel[checked = true] {
        background: transparent;
        color: #212529;
        font-weight: normal;
        text-decoration: none;
        border-bottom: 2px solid #70b8ff;
        border-radius: 0px;
    }
    NavLabel:hover {
        background: transparent;
        color: #212529;
        border-bottom: 2px solid #7f7f7f;
    }
    NavLabel[checked = true]:hover {
        background: transparent;
        color: #212529;
        border-bottom: 2px solid #70b8ff;
    }
"""

COMBOBOX_STYLE = """
    QComboBox {
        background: #F0F2F5;
        border: 2px solid transparent;
        border-radius: 10px;
        padding-left: 12px;
        height: 30px;
        color: #212529;
        font-family: 'Play';
        font-size: 16px;
        min-width: 120px;
        combobox-popup: 0;
    }
    QComboBox:on {
        background: #F8F9FC;
        border: 2px solid #70b8ff;
        border-bottom-style: none;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
    }
    QComboBox:hover {
        border: 2px solid #70b8ff;
        background: #70b8ff;
    }
    QComboBox:focus {
        border: 2px solid #70b8ff;
        background-color: #70b8ff;
    }
    QComboBox:disabled {
        background: #dee2e6;
        border: 2px solid #dee2e6;
        color: #777a84;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: center right;
        border-left: 1px solid rgba(255, 255, 255, 0.05);
        padding: 12px;
        height: 12px;
        width: 12px;
    }
    QComboBox::down-arrow {
        image: url(%s);
        padding: 12px;
        height: 10px;
        width: 10px;
    }
    QComboBox::down-arrow:on {
        image: url(%s);
        padding: 12px;
        height: 10px;
        width: 10px;
    }
    QComboBox QAbstractItemView {
        outline: none;
        background: #F0F2F5;
        border: 2px solid #70b8ff;
        border-top-style: none;
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        border-bottom-left-radius: 10px;
        border-bottom-right-radius: 10px;
    }
    QComboBox QAbstractItemView::item {
        padding: 3px 3px 3px 6px;
        margin: 1px;
        min-height: 24px;
        border-radius: 10px;
        color: #212529;
    }
    QComboBox QAbstractItemView::item:hover,
    QComboBox QAbstractItemView::item:selected {
        background: #70b8ff;
        color: #212529;
    }
""" % (
    theme_manager.get_icon("down", current_theme_name, as_path=True),
    theme_manager.get_icon("up", current_theme_name, as_path=True),
)

LINE_EDIT_STYLE = """
    QLineEdit {
        background: #F0F2F5;
        border: 2px solid rgba(255, 255, 255, 0.01);
        border-radius: 10px;
        height: 30px;
        padding-left: 12px;
        color: #212529;
        font-family: 'Play';
        font-size: 16px;
    }
    QLineEdit:hover {
        background: #F0F2F5;
        border: 2px solid #70b8ff;
    }
    QLineEdit:focus {
        border: 2px solid #70b8ff;
        background-color: #DEE2E6;
    }
"""

ADDGAME_INPUT_STYLE = """
    QLineEdit {
        background: #F0F2F5;
        border: 2px solid transparent;
        border-radius: 10px;
        height: 30px;
        padding-left: 12px;
        color: #212529;
        font-family: 'Play';
        font-size: 16px;
    }
    QLineEdit:hover {
        background: #F0F2F5;
        border: 2px solid #70b8ff;
    }
    QLineEdit:focus {
        border: 2px solid #70b8ff;
        background-color: #DEE2E6;
    }
"""

TAB_STYLE = """
    QTabWidget::pane {
        border-top: 1px solid #F0F2F5;
        background: transparent;
    }
    QTabBar::tab {
        background: #F0F2F5;
        color: #212529;
        padding: 6px 12px;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        margin-right: 2px;
        font-family: 'Play';
        font-size: 16px;
    }
    QTabBar::tab:selected {
        background: #70b8ff;
        color: #212529;
    }
    QTabBar::tab:hover {
        background: #70b8ff;
    }
"""

ACTION_BUTTON_STYLE = """
    QPushButton {
        background: #F8F9FC;
        border: 2px solid transparent;
        border-radius: 10px;
        color: #212529;
        font-size: 16px;
        font-family: 'Play';
        padding: 5px 16px;
        min-height: 20px;
    }
    QPushButton:hover {
        background: #70b8ff;
        border: 2px solid #70b8ff;
    }
    QPushButton:pressed {
        background: #F8F9FC;
    }
    QPushButton:focus {
        border: 2px solid #70b8ff;
        background-color: #70b8ff;
    }
"""

ACTION_BUTTON_ACTIVE_STYLE = """
    QPushButton {
        background: #F0F2F5;
        border: 2px solid #70b8ff;
        border-radius: 10px;
        color: #212529;
        font-size: 16px;
        font-family: 'Play';
        padding: 5px 16px;
        min-height: 20px;
    }
    QPushButton:hover {
        background: #70b8ff;
        border: 2px solid #70b8ff;
    }
    QPushButton:pressed {
        background: #F8F9FC;
    }
    QPushButton:focus {
        border: 2px solid #70b8ff;
        background-color: #70b8ff;
    }
"""
