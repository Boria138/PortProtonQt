from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config import ui_config

THEME_INHERITS = "standart"

theme_manager = ThemeManager()
current_theme_name = ui_config.get_theme()

# === Layout (differs from standart) ===
LIBRARY_LAYOUT_MODE = "list"
DETAIL_PAGE_LAYOUT_MODE = "compact"

portProtonPageMargins = (10, 7, 15, 10)
portProtonPageHorizontalSpacing = 5
portProtonPageVerticalSpacing = 2
portProtonPageSectionHeaderSpacing = 5
wineSettingsSetSpacing = 2
themeStorePageSpacing = 10
themeStoreGridOuterMargin = 14
themeStoreGridSpacing = 16
themeStoreGridMinColumnWidth = 260
themeStoreCardMinWidth = 220
themeStoreCardHeight = 280
themeStorePreviewHeight = 160
themeStoreDetailCarouselMinHeight = 300

mangoHudSwitchesVerticalSpacing = 5
mangoHudFpsColumns = 6
mangoHudFpsVerticalSpacing = 5
mangoHudPresetsColumns = 4
exeSettingsGroupBoxBlockSpacing = 5
exeSettingsGroupBoxElementVerticalSpacing = 2
exeSettingsGroupBoxElementHorizontalSpacing = 5

# === Gradients (unique to classic) ===
color_library_gradient_start = "#22242b"
color_library_gradient_end = "#1a1b21"
color_card_gradient_start = "#404554"
color_card_gradient_end = "#30323d"

# === Card Animation (glow instead of gradient) ===
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
    "fill_color": "#409EFF",
    "fill_alpha": 90,
    "stripe_color": "#409EFF",
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
        {"position": 0, "color": "#32343d"},
        {"position": 0.5, "color": "#404554"},
        {"position": 1, "color": "#32343d"},
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

# === QSS styles that differ from standart (hardcoded values) ===
LIBRARY_WIDGET_STYLE = """
    QWidget {
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #22242b,
            stop:1 #1a1b21
        );
        border-radius: 0px;
    }
"""

GAME_CARD_WINDOW_STYLE = """
    QFrame {
        border-radius: 20px;
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #404554,
            stop:1 #30323d
        );
        border: 0px solid transparent;
    }
"""

COVER_LABEL_STYLE = "border-radius: 15px;"

DETAILS_WIDGET_STYLE = "background: rgba(20,20,20,0.40); border-radius: 15px; padding: 10px;"
COMPACT_DETAILS_WIDGET_STYLE = "background: rgba(20,20,20,0.40); border-radius: 15px; padding: 10px;"

DETAIL_PAGE_TITLE_STYLE = "font-family: 'Play'; font-size: 32px; color: #409EFF;"
COMPACT_DETAIL_PAGE_TITLE_STYLE = "font-family: 'Play'; font-size: 32px; color: #409EFF; background: transparent;"
DETAIL_PAGE_LINE_STYLE = "color: rgba(255,255,255,0.12); margin: 0 0;"
DETAIL_PAGE_DESC_STYLE = "font-family: 'Play'; font-size: 16px; color: #ffffff; line-height: 1.5;"
COMPACT_DETAIL_PAGE_DESC_STYLE = "font-family: 'Play'; font-size: 16px; color: #ffffff; line-height: 1.5; background: transparent;"
COMPACT_PLAYTIME_WIDGET_STYLE = "background: transparent; border-radius: 15px; padding: 10px;"

LAST_LAUNCH_TITLE_STYLE = "max-height: 16px; background: rgba(20,20,20,0.40);font-family: 'Play'; font-size: 11px; color: #ffffff; text-transform: uppercase; letter-spacing: 0.75px;"
LAST_LAUNCH_VALUE_STYLE = "height: 16px; background: rgba(20,20,20,0.40);font-family: 'Play'; font-size: 13px; color: #ffffff; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = "max-height: 16px; background: rgba(20,20,20,0.40);font-family: 'Play'; font-size: 11px; color: #ffffff; text-transform: uppercase; letter-spacing: 0.75px;"
PLAY_TIME_VALUE_STYLE = "height: 16px; background: rgba(20,20,20,0.40);font-family: 'Play'; font-size: 13px; color: #ffffff; font-weight: 600; letter-spacing: 0.75px;"

PLAY_BUTTON_STYLE = """
    QPushButton {
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, stop:0 #404554, stop:1 #30323d);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        font-size: 16px;
        margin-top: 15px;
        color: #ffffff;
        font-weight: bold;
        font-family: 'Play';
        padding: 5px 10px;
        min-width: 120px;
        min-height: 30px;
    }
    QPushButton:hover, QPushButton:pressed, QPushButton:focus {
        background: #409EFF;
    }
"""

ADDGAME_BACK_BUTTON_STYLE = """
    QPushButton {
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, stop:0 #404554, stop:1 #30323d);
        border: 0px solid;
        border-radius: 10px;
        color: #ffffff;
        font-size: 16px;
        font-family: 'Play';
        padding: 5px 10px;
        min-width: 120px;
        min-height: 25px;
    }
    QPushButton:hover, QPushButton:pressed {
        background: #409EFF;
    }
    QPushButton:focus {
        background: #409EFF;
        border: 1px solid #409EFF;
    }
"""

LIBRARY_CONTROLS_BUTTON_STYLE = """
    QPushButton {
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, stop:0 #404554, stop:1 #30323d);
        border: 0px solid;
        border-radius: 10px;
        color: #ffffff;
        font-size: 16px;
        font-family: 'Play';
        padding: 5px 10px;
        min-width: 24px;
        min-height: 25px;
    }
    QPushButton:hover, QPushButton:pressed, QPushButton:focus, QPushButton:checked {
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8, stop:0 #404554, stop:1 #30323d);
        border: 1px solid #409EFF;
    }
"""

LIBRARY_FILTER_COMBOBOX_STYLE = """
    QComboBox {
        background: #32343d;
        border: 1px solid transparent;
        border-radius: 10px;
        padding-left: 12px;
        height: 30px;
        color: #ffffff;
        font-family: 'Play';
        font-size: 16px;
        min-width: 120px;
        combobox-popup: 0;
    }
    QComboBox:hover, QComboBox:focus {
        background: #409EFF;
        border: 1px solid #409EFF;
    }
    QComboBox:on {
        background: #32343d;
        border: 1px solid #409EFF;
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
        background: #3f424d;
        border: 1px solid #409EFF;
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
        color: #ffffff;
    }
    QComboBox QAbstractItemView::item:hover,
    QComboBox QAbstractItemView::item:selected {
        background: #409EFF;
        color: #ffffff;
    }
""" % (
    theme_manager.get_icon("down", current_theme_name, as_path=True),
    theme_manager.get_icon("up", current_theme_name, as_path=True),
)

SEARCH_EDIT_STYLE = """
    QLineEdit {
        background: #282a33;
        border: 0px solid;
        border-radius: 10px;
        padding: 5px 10px;
        font-family: 'Play';
        font-size: 16px;
        color: #ffffff;
        min-height: 25px;
    }
    QLineEdit:hover, QLineEdit:focus {
        border: 1px solid #409EFF;
    }
"""

SETTINGS_TITLE_STYLE = """
    QLabel {
        color: #ffffff;
        margin-top: 1px;
        font-family: 'Play';
        font-size: 16px;
        font-weight: bold;
        padding: 6px;
        height: 30px;
        background: #32343d;
        border-radius: 10px;
        min-width: 320px;
    }
"""

ACTION_BUTTON_STYLE = """
    QPushButton {
        background: #3f424d;
        border: 2px solid transparent;
        border-radius: 10px;
        color: #ffffff;
        font-size: 16px;
        font-family: 'Play';
        padding: 5px 16px;
        min-height: 20px;
    }
    QPushButton:hover {
        background: #409EFF;
        border: 2px solid #409EFF;
    }
    QPushButton:pressed {
        background: #282a33;
    }
    QPushButton:focus {
        border: 2px solid #409EFF;
        background-color: #409EFF;
    }
"""

ACTION_BUTTON_ACTIVE_STYLE = """
    QPushButton {
        background: #3f424d;
        border: 2px solid #409EFF;
        border-radius: 10px;
        color: #ffffff;
        font-size: 16px;
        font-family: 'Play';
        padding: 5px 16px;
        min-height: 20px;
    }
    QPushButton:hover {
        background: #409EFF;
        border: 2px solid #409EFF;
    }
    QPushButton:pressed {
        background: #282a33;
    }
    QPushButton:focus {
        border: 2px solid #409EFF;
        background-color: #409EFF;
    }
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
        color: {color_text};
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
        color: #bbbbbb;
        background: {color_transparent};
        border: {border_none} {color_transparent};
        font-family: '{font_family}';
        font-size: {font_size_value};
        padding: 2px 12px;
    }}
"""

THEME_STORE_DETAIL_TITLE_STYLE = f"""
    QLabel {{
        color: {color_text};
        background: {color_transparent};
        border: {border_none} {color_transparent};
        font-family: '{font_family}';
        font-size: {font_size_header};
        font-weight: bold;
    }}
"""

THEME_STORE_DESCRIPTION_STYLE = f"""
    QTextBrowser {{
        color: {color_text};
        background: {color_surface};
        border: {border_thin} rgba(255, 255, 255, 0.2);
        border-radius: {border_radius_small};
        font-family: '{font_family}';
        font-size: {font_size_normal};
        padding: 12px;
    }}
"""
