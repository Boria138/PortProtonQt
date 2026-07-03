from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config import ui_config

THEME_INHERITS = "standart-light"

theme_manager = ThemeManager()
current_theme_name = ui_config.get_theme()

# === Layout (differs from standart-light) ===
LIBRARY_LAYOUT_MODE = "list"
DETAIL_PAGE_LAYOUT_MODE = "compact"

autoSizeButtonPadding = (0, 20)
portProtonPageMargins = (10, 7, 15, 10)
portProtonPageHorizontalSpacing = 5
portProtonPageVerticalSpacing = 2
portProtonPageSectionHeaderSpacing = 5
wineSettingsSetSpacing = 2
themeStorePageSpacing = 10
themeStoreCardDefaultWidth = 280
themeStoreDetailCarouselMinHeight = 300
mangoHudSwitchesColumns = 4
mangoHudSwitchesVerticalSpacing = 5
mangoHudFpsColumns = 6
mangoHudFpsVerticalSpacing = 5
mangoHudPresetsColumns = 4
exeSettingsGroupBoxBlockSpacing = 5
exeSettingsGroupBoxElementVerticalSpacing = 2
exeSettingsGroupBoxElementHorizontalSpacing = 5

# === Core Palette (light) ===
color_accent = "#409EFF"
color_bg = "#F8F9FC"
color_surface = "#F0F2F5"
color_surface_elevated = "#E9ECEF"
color_surface_hover = "#DEE2E6"
color_text = "#ffffff"
color_surface_light = "#d2d3db"
color_surface_mid = "#9394a5"
color_text_dark = "#212529"
color_detail_overlay = "rgba(220, 222, 226, 0.40)"
color_detail_line = "rgba(0,0,0,0.12)"

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
    "fill_color": color_accent,
    "fill_alpha": 90,
    "stripe_color": color_accent,
    "stripe_alpha": 255,
    "glow_base_alpha": 120,
    "glow_pulse_alpha": 80,
    "default_scale": 1.0,
    "hover_scale": 1.08,
    "focus_scale": 1.05,
    "scale_anim_duration": 200,
    "thickness_easing_curve": "OutBack",
    "thickness_easing_curve_out": "InBack",
    "scale_easing_curve": "OutBack",
    "scale_easing_curve_out": "InBack",
    "gradient_colors": [
        {"position": 0, "color": color_surface_light},
        {"position": 0.5, "color": color_surface_mid},
        {"position": 1, "color": color_surface_light},
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

# === QSS styles that differ from standart-light ===
LIBRARY_WIDGET_STYLE = f"""
    QWidget {{
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 {color_surface_light},
            stop:1 {color_surface_mid}
        );
        border-radius: 0px;
    }}
"""

SETTINGS_TITLE_STYLE = f"""
    QLabel {{
        color: {color_text_dark};
        height: 34px;
        font-family: '{font_family}';
        font-size: {font_size_normal};
        font-weight: bold;
        padding: 7px;
        background: {color_bg};
        border-radius: {border_radius_small};
        border: {border_none} {color_surface};
        min-width: 320px;
    }}
"""

QGROUP_BOX_STYLE = f"""
    QGroupBox {{
        font-family: '{font_family}';
        font-size: {font_size_normal};
        font-weight: bold;
        color: {color_text_dark};
        border: {border_thin} {color_surface};
        border-radius: {border_radius_small};
        margin-top: 10px;
        margin-right: 10px;
        padding-top: 5px;
        background: {color_transparent};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }}
"""

GAME_CARD_WINDOW_STYLE = f"""
    QFrame {{
        border-radius: {border_radius_card};
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,
        stop:0 rgba(255, 255, 255, 0.9),
        stop:0.3 rgba(233, 236, 239, 0.9),
        stop:0.7 rgba(210, 211, 219, 0.9),
        stop:1 rgba(180, 190, 200, 0.9));
        border: {border_medium} {color_text};
    }}
"""

COVER_LABEL_STYLE = f"border-radius: {border_radius_large};"

DETAILS_WIDGET_STYLE = f"background: {color_detail_overlay}; border-radius: {border_radius_large}; padding: 10px;"
COMPACT_DETAILS_WIDGET_STYLE = f"""
        QFrame, QWidget {{
            background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
                stop:0 {color_surface_elevated},
                stop:1 {color_surface_light}
            );
            border-radius: {border_radius_large};
            padding: 10px;
        }}
"""

DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 32px; color: {color_accent};"
COMPACT_DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 32px; color: {color_text_dark}; background: {color_transparent};"
DETAIL_PAGE_LINE_STYLE = f"background: {color_transparent}; margin: 0 0;"
DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_normal}; color: {color_text_dark}; line-height: 1.5;"
COMPACT_DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_normal}; color: {color_text_dark}; line-height: 1.5; background: {color_transparent};"
COMPACT_PLAYTIME_WIDGET_STYLE = f"background: {color_transparent}; border-radius: {border_radius_large}; padding: 10px;"

LAST_LAUNCH_TITLE_STYLE = f"max-height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 {color_surface_elevated},stop:1 {color_surface_light}); font-family: '{font_family}'; font-size: {font_size_small}; color: {color_text_dark}; text-transform: uppercase; letter-spacing: 0.75px;"
LAST_LAUNCH_VALUE_STYLE = f"height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 {color_surface_elevated},stop:1 {color_surface_light}); font-family: '{font_family}'; font-size: {font_size_value}; color: {color_text_dark}; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = f"max-height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 {color_surface_elevated},stop:1 {color_surface_light}); font-family: '{font_family}'; font-size: {font_size_small}; color: {color_text_dark}; text-transform: uppercase; letter-spacing: 0.75px;"
PLAY_TIME_VALUE_STYLE = f"height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 {color_surface_elevated},stop:1 {color_surface_light}); font-family: '{font_family}'; font-size: {font_size_value}; color: {color_text_dark}; font-weight: 600; letter-spacing: 0.75px;"

PLAY_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, stop:0 {color_surface_elevated}, stop:1 {color_surface_light});
        border: {border_thin} {color_text};
        border-radius: {border_radius_small};
        font-size: {font_size_normal};
        margin-top: 15px;
        color: {color_text_dark};
        font-weight: bold;
        font-family: '{font_family}';
        padding: 5px 10px;
        min-width: 120px;
        min-height: 30px;
    }}
    QPushButton:hover, QPushButton:pressed, QPushButton:focus {{
        background: {color_accent};
    }}
"""

ADDGAME_BACK_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, stop:0 {color_surface_elevated}, stop:1 {color_surface_light});
        border: {border_thin} {color_text};
        border-radius: {border_radius_small};
        color: {color_text_dark};
        font-size: {font_size_normal};
        font-family: '{font_family}';
        padding: 5px 10px;
        min-width: 120px;
        min-height: 25px;
    }}
    QPushButton:hover, QPushButton:pressed {{
        background: {color_accent};
    }}
    QPushButton:focus {{
        background: {color_accent};
        border: {border_thin} {color_accent};
    }}
"""

LIBRARY_CONTROLS_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, stop:0 {color_surface_elevated}, stop:1 {color_surface_light});
        border: {border_thin} {color_text};
        border-radius: {border_radius_small};
        color: {color_text_dark};
        font-size: {font_size_normal};
        font-family: '{font_family}';
        padding: 5px 10px;
        min-width: 24px;
        min-height: 25px;
    }}
    QPushButton:hover, QPushButton:pressed, QPushButton:focus, QPushButton:checked {{
        background: {color_accent};
        border: {border_thin} {color_accent};
    }}
"""

SEARCH_EDIT_STYLE = f"""
    QLineEdit {{
        background: {color_bg};
        border: {border_none};
        border-radius: {border_radius_small};
        padding: 5px 10px;
        font-family: '{font_family}';
        font-size: {font_size_normal};
        color: {color_text_dark};
        min-height: 25px;
    }}
    QLineEdit:hover, QLineEdit:focus {{
        border: {border_thin} {color_accent};
    }}
"""

NAV_BUTTON_STYLE = f"""
    NavLabel {{
        background: {color_transparent};
        padding: 6px 3px;
        margin: 10px 0 10px 10px;
        color: {color_overlay};
        font-family: '{font_family}';
        font-size: {font_size_normal};
        text-transform: uppercase;
        border: {color_accent};
        border-radius: 0px;
    }}
    NavLabel[checked = true] {{
        background: {color_transparent};
        color: {color_text_dark};
        font-weight: normal;
        text-decoration: none;
        border-bottom: {border_medium} {color_accent};
        border-radius: 0px;
    }}
    NavLabel:hover {{
        background: {color_transparent};
        color: {color_text_dark};
        border-bottom: {border_medium} {color_nav_inactive};
    }}
    NavLabel[checked = true]:hover {{
        background: {color_transparent};
        color: {color_text_dark};
        border-bottom: {border_medium} {color_accent};
    }}
"""

COMBOBOX_STYLE = f"""
    QComboBox {{
        background: {color_surface};
        border: {border_medium} transparent;
        border-radius: {border_radius_small};
        padding-left: 12px;
        height: 30px;
        color: {color_text_dark};
        font-family: '{font_family}';
        font-size: {font_size_normal};
        min-width: 120px;
        combobox-popup: 0;
    }}
    QComboBox:on {{
        background: {color_bg};
        border: {border_medium} {color_accent};
        border-bottom-style: none;
        border-top-left-radius: {border_radius_small};
        border-top-right-radius: {border_radius_small};
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
    }}
    QComboBox:hover {{
        border: {border_medium} {color_accent};
        background: {color_accent};
        color: {color_text};
    }}
    QComboBox:focus {{
        border: {border_medium} {color_accent};
        background-color: {color_accent};
        color: {color_text};
    }}
    QComboBox:disabled {{
        background: {color_surface_hover};
        border: {border_medium} {color_surface_hover};
        color: {color_disabled_text};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        border-left: {border_thin} {color_border_faint};
        padding: 12px;
        height: 12px;
        width: 12px;
    }}
    QComboBox::down-arrow {{
        image: url(%s);
        padding: 12px;
        height: 10px;
        width: 10px;
    }}
    QComboBox::down-arrow:on {{
        image: url(%s);
        padding: 12px;
        height: 10px;
        width: 10px;
    }}
    QComboBox QAbstractItemView {{
        outline: none;
        background: {color_surface};
        border: {border_medium} {color_accent};
        border-top-style: none;
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        border-bottom-left-radius: {border_radius_small};
        border-bottom-right-radius: {border_radius_small};
    }}
    QComboBox:editable {{
        background: {color_surface};
        color: {color_text_dark};
    }}
    QComboBox::drop-down:editable:focus {{
        background: {color_accent};
        border-top-left-radius: 0px;
        border-top-right-radius: {border_radius_small};
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: {border_radius_small};
    }}
    QListView {{
        background: {color_surface};
    }}
    QListView::item {{
        padding: 3px 3px 3px 6px;
        margin: 1px;
        min-height: 24px;
        border-radius: {border_radius_small};
        color: {color_text_dark};
    }}
    QListView::item:hover {{
        background: {color_bg};
    }}
    QListView::item:selected {{
        background: {color_bg};
    }}
    QListView::item:focus {{
        background: {color_accent};
        color: {color_text};
    }}
""" % (
    theme_manager.get_icon("down", current_theme_name, as_path=True),
    theme_manager.get_icon("up", current_theme_name, as_path=True),
)

SETTINGS_TABLE_COMBOBOX_STYLE = f"""
    QComboBox#settingsTableCombo:hover,
    QComboBox#settingsTableCombo:focus {{
        background: {color_surface};
        border: {border_medium} {color_accent};
        color: {color_text_dark};
    }}
"""

LINE_EDIT_STYLE = f"""
    QLineEdit {{
        background: {color_surface};
        border: {border_medium} {color_border_subtle};
        border-radius: {border_radius_small};
        height: 30px;
        padding-left: 12px;
        color: {color_text_dark};
        font-family: '{font_family}';
        font-size: {font_size_normal};
    }}
    QLineEdit:hover {{
        background: {color_surface};
        border: {border_medium} {color_accent};
    }}
    QLineEdit:focus {{
        border: {border_medium} {color_accent};
        background-color: {color_surface_hover};
    }}
"""

ADDGAME_INPUT_STYLE = f"""
    QLineEdit {{
        background: {color_surface};
        border: {border_medium} transparent;
        border-radius: {border_radius_small};
        height: 30px;
        padding-left: 12px;
        color: {color_text_dark};
        font-family: '{font_family}';
        font-size: {font_size_normal};
    }}
    QLineEdit:hover {{
        background: {color_surface};
        border: {border_medium} {color_accent};
    }}
    QLineEdit:focus {{
        border: {border_medium} {color_accent};
        background-color: {color_surface_hover};
    }}
"""

TAB_STYLE = f"""
    QTabWidget::pane {{
        border-top: {border_thin} {color_surface};
        background: {color_transparent};
    }}
    QTabBar::tab {{
        background: {color_surface};
        color: {color_text_dark};
        padding: 6px 12px;
        border-top-left-radius: {border_radius_small};
        border-top-right-radius: {border_radius_small};
        margin-right: 2px;
        font-family: '{font_family}';
        font-size: {font_size_normal};
    }}
    QTabBar::tab:selected {{
        background: {color_accent};
        color: {color_text_dark};
        color: {color_text};
    }}
    QTabBar::tab:hover {{
        background: {color_accent};
        color: {color_text};
    }}
"""

HINT_BAR_STYLE = f"""
    QWidget {{
        max-height: 40px;
    }}
"""

ACTION_BUTTON_STYLE = f"""
    QPushButton {{
        background: {color_bg};
        border: {border_medium} transparent;
        border-radius: {border_radius_small};
        color: {color_text_dark};
        font-size: {font_size_normal};
        font-family: '{font_family}';
        padding: 5px 16px;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background: {color_accent};
        border: {border_medium} {color_accent};
    }}
    QPushButton:pressed {{
        background: {color_accent};
        color: {color_text};
    }}
    QPushButton:focus {{
        border: {border_medium} {color_accent};
        background-color: {color_accent};
        color: {color_text};
    }}
"""

ACTION_BUTTON_ACTIVE_STYLE = f"""
    QPushButton {{
        background: {color_surface};
        border: {border_medium} {color_accent};
        border-radius: {border_radius_small};
        color: {color_text_dark};
        font-size: {font_size_normal};
        font-family: '{font_family}';
        padding: 5px 16px;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background: {color_accent};
        border: {border_medium} {color_accent};
        color: {color_text};
    }}
    QPushButton:pressed {{
        background: {color_bg};
    }}
    QPushButton:focus {{
        border: {border_medium} {color_accent};
        background-color: {color_accent};
        color: {color_text};
    }}
"""

THEME_STORE_SCROLL_STYLE = f"""
    QScrollArea {{
        background: {color_surface_elevated};
        border: {border_none} {color_transparent};
    }}
"""

THEME_STORE_CARD_STYLE = f"""
    QFrame#themeStoreCard {{
        background: {color_surface};
        border: {border_thin} rgba(255, 255, 255, 0.2);
        border-radius: {border_radius_small};
    }}
    QFrame#themeStoreCard:hover {{
        background: {color_surface_hover};
        border: {border_thin} {color_accent};
    }}
    QFrame#themeStoreCard:focus {{
        background: {color_surface_hover};
        border: {border_medium} {color_accent};
    }}
"""

THEME_STORE_PREVIEW_STYLE = f"""
    QLabel {{
        background: {color_bg};
        border: {border_none} {color_transparent};
        border-top-left-radius: {border_radius_small};
        border-top-right-radius: {border_radius_small};
    }}
"""

THEME_STORE_CARD_TITLE_STYLE = f"""
    QLabel {{
        color: {color_text_dark};
        background: {color_transparent};
        border: {border_none} {color_transparent};
        font-family: '{font_family}';
        font-size: {font_size_normal};
        font-weight: bold;
        padding: 10px 12px 4px 12px;
    }}
"""

THEME_STORE_CARD_META_STYLE = f"""
    QLabel {{
        color: {color_text_muted};
        background: {color_transparent};
        border: {border_none} {color_transparent};
        font-family: '{font_family}';
        font-size: {font_size_normal};
        padding: 2px 12px;
    }}
"""

THEME_STORE_DETAIL_TITLE_STYLE = f"""
    QLabel {{
        color: {color_text_dark};
        background: {color_transparent};
        border: {border_none} {color_transparent};
        font-family: '{font_family}';
        font-size: {font_size_header};
        font-weight: bold;
    }}
"""

THEME_STORE_DESCRIPTION_STYLE = f"""
    QTextBrowser {{
        color: {color_text_dark};
        background: {color_surface};
        border: {border_thin} rgba(255, 255, 255, 0.2);
        border-radius: {border_radius_small};
        font-family: '{font_family}';
        font-size: {font_size_normal};
        padding: 12px;
    }}
"""
