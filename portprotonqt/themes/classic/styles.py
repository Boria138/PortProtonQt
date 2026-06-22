from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config import ui_config

THEME_INHERITS = "standart"

theme_manager = ThemeManager()
current_theme_name = ui_config.get_theme()

autoSizeButtonPadding = 16

detailCompactCoverFrameSize = 128
detailCompactCoverImageSize = 108
detailCompactContentSpacing = 15
detailCompactHeaderSpacing = 16
detailCompactTitleMargins = (0, 0, 0, 0)
detailCompactDescriptionMargins = (3, 3, 3, 3)

portProtonPageMargins = (10, 7, 15, 10)
portProtonPageHorizontalSpacing = 5
portProtonPageVerticalSpacing = 2
portProtonPageSectionHeaderSpacing = 5
wineSettingsSetSpacing = 2

mangoHudSwitchesColumns = 4
mangoHudSwitchesVerticalSpacing = 5
mangoHudFpsColumns = 6
mangoHudFpsVerticalSpacing = 5
mangoHudPresetsColumns = 4
exeSettingsGroupBoxBlockSpacing = 5
exeSettingsGroupBoxElementVerticalSpacing = 2
exeSettingsGroupBoxElementHorizontalSpacing = 5

LIBRARY_LAYOUT_MODE = "list"
DETAIL_PAGE_LAYOUT_MODE = "compact"

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
        {"position": 0, "color": "#9ca3af"},
        {"position": 0.5, "color": "#6b7280"},
        {"position": 1, "color": "#9ca3af"},
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

# === Typography ===
font_family = "Play"
font_size_small = "11px"
font_size_normal = "16px"
font_size_value = "13px"
font_size_keyboard = "14px"
font_size_header = "24px"
font_size_play = "18px"
font_size_title = "32px"

# === Borders ===
border_none = "0px solid"
border_thin = "1px solid"
border_medium = "2px solid"
border_radius_small = "10px"
border_radius_large = "15px"
border_radius_card = "20px"
border_radius_badge = "5px"

# === Core Palette ===
color_accent = "#409EFF"
color_bg = "#282a33"
color_surface = "#3f424d"
color_surface_elevated = "#32343d"
color_surface_hover = "#404554"
color_text = "#ffffff"
color_transparent = "transparent"
color_overlay = "rgba(40, 42, 51, 0.9)"

# === Widget State Colors ===
color_combo_disabled_bg = "#2a2c35"
color_combo_disabled_border = "#2a2c35"
color_combo_disabled_text = "#777a84"

# === Navigation ===
color_nav_inactive = "#7f7f7f"
color_separator = "#7f7f7f"

# === Scrollbar ===
color_scrollbar_bg = "rgba(20, 20, 20, 0.30)"
color_scrollbar_handle = "#bebebe"

# === Border Variants ===
color_border_subtle = "rgba(255, 255, 255, 0.01)"
color_border_input = "rgba(255, 255, 255, 0.5)"
color_border_light = "rgba(255, 255, 255, 0.2)"
color_border_faint = "rgba(255, 255, 255, 0.05)"

# === Detail Page ===
color_detail_overlay = "rgba(20, 20, 20, 0.40)"
color_detail_line = "rgba(255,255,255,0.12)"

# === Preview Buttons ===
color_preview_btn_bg = "rgba(0, 0, 0, 0.5)"
color_preview_btn_text = "white"


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

# GAME CARD STYLE (GAMECARD)
GAME_CARD_WINDOW_STYLE = """
    QFrame {
        border-radius: 20px;
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #404554,
            stop:1 #30323d
        );
        border:  0px solid;
    }
"""

# COVER LABEL BORDER RADIUS
COVER_LABEL_STYLE = f"border-radius: {border_radius_large};"

# DETAILS WIDGET (TEXT, DESCRIPTION)
DETAILS_WIDGET_STYLE = f"background: {color_detail_overlay}; border-radius: {border_radius_large}; padding: 10px;"
COMPACT_DETAILS_WIDGET_STYLE = f"background: {color_detail_overlay}; border-radius: {border_radius_large}; padding: 10px;"

# TITLE (HEADER) ON DETAIL PAGE
DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: {font_size_title}; color: {color_accent};"
COMPACT_DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: {font_size_title}; color: {color_accent}; background: {color_transparent};"

# DIVIDER LINE
DETAIL_PAGE_LINE_STYLE = f"color: {color_detail_line}; margin: 0 0;"

# DESCRIPTION TEXT
DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_normal}; color: {color_text}; line-height: 1.5;"
COMPACT_DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_normal}; color: {color_text}; line-height: 1.5; background: {color_transparent};"

# PLAYTIME WIDGET (PLAYTIME)
COMPACT_PLAYTIME_WIDGET_STYLE = f"background: {color_transparent}; border-radius: {border_radius_large}; padding: 10px;"

# ADDITIONAL INFO STYLES ON GAMES PAGE
LAST_LAUNCH_TITLE_STYLE = f"max-height: 16px; background: {color_detail_overlay};font-family: '{font_family}'; font-size: {font_size_small}; color: {color_text}; text-transform: uppercase; letter-spacing: 0.75px;"
LAST_LAUNCH_VALUE_STYLE = f"height: 16px; background: {color_detail_overlay};font-family: '{font_family}'; font-size: {font_size_value}; color: {color_text}; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = f"max-height: 16px; background: {color_detail_overlay};font-family: '{font_family}'; font-size: {font_size_small}; color: {color_text}; text-transform: uppercase; letter-spacing: 0.75px;"
PLAY_TIME_VALUE_STYLE = f"height: 16px; background: {color_detail_overlay};font-family: '{font_family}'; font-size: {font_size_value}; color: {color_text}; font-weight: 600; letter-spacing: 0.75px;"

# PLAY BUTTON STYLE
PLAY_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #404554,
            stop:1 #30323d
        );
        border: {border_thin} {color_border_light};
        border-radius: {border_radius_small};
        font-size: {font_size_normal};
        margin-top: 15px;
        color: {color_text};
        font-weight: bold;
        font-family: '{font_family}';
        padding: 5px 10px;
        min-width: 120px;
        min-height: 30px;
    }}
    QPushButton:hover {{
        background: {color_accent};
    }}
    QPushButton:pressed {{
        background: {color_accent};
    }}
    QPushButton:focus {{
        background: {color_accent};
    }}
"""
# STYLE FOR "ADD GAME" AND "BACK" BUTTONS ON DETAIL PAGE AND LIBRARY
ADDGAME_BACK_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #404554,
            stop:1 #30323d
        );
        border: {border_none};
        border-radius: {border_radius_small};
        color: {color_text};
        font-size: {font_size_normal};
        font-family: '{font_family}';
        padding: 5px 10px;
        min-width: 120px;
        min-height: 25px;
    }}
    QPushButton:hover {{
        background: {color_accent};
    }}
    QPushButton:pressed {{
        background: {color_accent};
    }}
    QPushButton:focus {{
        background: {color_accent};
        border: {border_thin} {color_accent};
    }}
"""

LIBRARY_CONTROLS_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #404554,
            stop:1 #30323d
        );
        border: {border_none};
        border-radius: {border_radius_small};
        color: {color_text};
        font-size: {font_size_normal};
        font-family: '{font_family}';
        padding: 5px 10px;
        min-width: 24px;
        min-height: 25px;
    }}
    QPushButton:hover,
    QPushButton:pressed,
    QPushButton:focus,
    QPushButton:checked {{
        background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
            stop:0 #404554,
            stop:1 #30323d
        );
        border: {border_thin} {color_accent};
    }}
"""

LIBRARY_FILTER_COMBOBOX_STYLE = f"""
    QComboBox {{
        background: {color_surface_elevated};
        border: {border_thin} {color_transparent};
        border-radius: {border_radius_small};
        padding-left: 12px;
        height: 30px;
        color: {color_text};
        font-family: '{font_family}';
        font-size: {font_size_normal};
        min-width: 120px;
        combobox-popup: 0;
    }}
    QComboBox:hover,
    QComboBox:focus {{
        background: {color_accent};
        border: {border_thin} {color_accent};
    }}
    QComboBox:on {{
        background: {color_surface_elevated};
        border: {border_thin} {color_accent};
        border-bottom-style: none;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
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
        image: url({theme_manager.get_icon("down", current_theme_name, as_path=True)});
        padding: 12px;
        height: 10px;
        width: 10px;
    }}
    QComboBox::down-arrow:on {{
        image: url({theme_manager.get_icon("up", current_theme_name, as_path=True)});
        padding: 12px;
        height: 10px;
        width: 10px;
    }}
    QComboBox QAbstractItemView {{
        outline: none;
        background: {color_surface};
        border: {border_thin} {color_accent};
        border-top-style: none;
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        border-bottom-left-radius: 10px;
        border-bottom-right-radius: 10px;
    }}
    QComboBox QAbstractItemView::item {{
        padding: 3px 3px 3px 6px;
        margin: 1px;
        min-height: 24px;
        border-radius: {border_radius_small};
        color: {color_text};
    }}
    QComboBox QAbstractItemView::item:hover,
    QComboBox QAbstractItemView::item:selected {{
        background: {color_accent};
        color: {color_text};
    }}
"""

# SEARCH FIELD STYLE
SEARCH_EDIT_STYLE = f"""
    QLineEdit {{
        background: {color_bg};
        border: {border_none};
        border-radius: {border_radius_small};
        padding: 5px 10px;
        font-family: '{font_family}';
        font-size: {font_size_normal};
        color: {color_text};
        min-height: 25px;
    }}
    QLineEdit:hover {{
        border: {border_thin} {color_accent};
    }}
    QLineEdit:focus {{
        border: {border_thin} {color_accent};
    }}
"""

# NAVIGATION TAB BUTTON STYLE
NAV_BUTTON_STYLE = f"""
    NavLabel {{
        background: {color_transparent};
        padding: 6px 3px;
        margin: 10px 0 10px 10px;
        color: {color_nav_inactive};
        font-family: '{font_family}';
        font-size: {font_size_normal};
        text-transform: uppercase;
        border: {color_accent};
        border-radius: 0px;
    }}
    NavLabel[checked = true] {{
        background: {color_transparent};
        color: {color_text};
        font-weight: normal;
        text-decoration: none;
        border-bottom: {border_thin} {color_accent};
        border-radius: 0px;
    }}
    NavLabel:hover {{
        background: {color_transparent};
        color: {color_text};
        border-bottom: {border_thin} {color_nav_inactive};
    }}
    NavLabel[checked = true]:hover {{
        background: {color_transparent};
        color: {color_text};
        border-bottom: {border_thin} {color_accent};
    }}
"""
WINETRICKS_TABBLE_STYLE = f"""
QTableWidget {{
    background: {color_transparent};
    color: {color_text};
    gridline-color: {color_transparent};
    alternate-background-color: {color_surface_elevated};
    border: {border_none};
    border-radius: {border_radius_small};
    font-family: '{font_family}';
    font-size: {font_size_normal};
}}
QHeaderView::section {{
    background: {color_surface_elevated};
    color: {color_text};
    padding: 2px;
    border: {border_none};
    font-weight: bold;
    font-family: '{font_family}';
    font-size: {font_size_normal};
}}
QTableWidget::item {{
    padding: 3px;
    border-bottom: {border_none} {color_surface};
    height: 32px;
}}
QTableWidget::item:selected,
QTableWidget::item:focus,
QTableWidget::item:selected:focus {{
    background: {color_accent};
    color: {color_text};
    selection-background-color: {color_accent};
}}
QTableWidget::item:hover {{
    background: {color_transparent};
}}
QTableWidget::item:selected:hover {{
    background: {color_accent};
    color: {color_text};
}}
"""

# COMBOBOX
COMBOBOX_STYLE = f"""
    QComboBox {{
        background: {color_surface};
        border: {border_medium} transparent;
        border-radius: {border_radius_small};
        padding-left: 12px;
        height: 30px;
        color: {color_text};
        font-family: '{font_family}';
        font-size: {font_size_normal};
        min-width: 120px;
        combobox-popup: 0;
    }}
    QComboBox:on {{
        background: {color_bg};
        border: {border_medium} {color_accent};
        border-bottom-style: none;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
    }}
    QComboBox:hover {{
        border: {border_medium} {color_accent};
        background: {color_accent};
    }}
    /* Focus state */
    QComboBox:focus {{
        border: {border_medium} {color_accent};
        background-color: {color_accent};
    }}
    QComboBox:disabled {{
        background: {color_combo_disabled_bg};
        border: {border_medium} {color_combo_disabled_border};
        color: {color_combo_disabled_text};
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
        image: url({theme_manager.get_icon("down", current_theme_name, as_path=True)});
        padding: 12px;
        height: 10px;
        width: 10px;
    }}
    QComboBox::down-arrow:on {{
        image: url({theme_manager.get_icon("up", current_theme_name, as_path=True)});
        padding: 12px;
        height: 10px;
        width: 10px;
    }}
/* List when combobox is open */
    QComboBox QAbstractItemView {{
        outline: none;
        background: {color_surface};
        border: {border_medium} {color_accent};
        border-top-style: none;
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        border-bottom-left-radius: 10px;
        border-bottom-right-radius: 10px;
    }}
    QComboBox:editable {{
        background: {color_surface};
    }}
    QComboBox::drop-down:editable:focus {{
        background: {color_accent};
        border-top-left-radius: 0px;
        border-top-right-radius: 10px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 10px;
    }}
    QListView {{
        background: {color_surface};
    }}
    QListView::item {{
        padding: 3px 3px 3px 6px;
        margin: 1px;
        min-height: 24px;
        border-radius: {border_radius_small};
        color: {color_text};
    }}
    QListView::item:hover {{
        background: {color_bg};
    }}
    QListView::item:selected {{
        background: {color_bg};
    }}
    /* Selection in list when item is focused */
    QListView::item:focus {{
        background: {color_accent};
        color: {color_text};
    }}
"""

SETTINGS_TABLE_COMBOBOX_STYLE = f"""
    QComboBox#settingsTableCombo:hover,
    QComboBox#settingsTableCombo:focus {{
        background: {color_surface};
        border: {border_medium} {color_accent};
    }}
"""

LINE_EDIT_STYLE = f"""
    QLineEdit {{
        background: {color_surface};
        border: {border_medium} {color_border_subtle};
        border-radius: {border_radius_small};
        height: 30px;
        padding-left: 12px;
        color: {color_text};
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
        color: {color_text};
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
        border-top: 1px solid {color_surface};
        background: {color_transparent};
    }}
    QTabBar::tab {{
        background: {color_surface};
        color: {color_text};
        padding: 6px 12px;
        border-top-left-radius: {border_radius_small};
        border-top-right-radius: {border_radius_small};
        margin-right: 2px;
        font-family: '{font_family}';
        font-size: {font_size_normal};
    }}
    QTabBar::tab:selected {{
        background: {color_accent};
        color: {color_text};
    }}
    QTabBar::tab:hover {{
        background: {color_accent};
    }}
"""

# HINT BAR STYLE
HINT_BAR_STYLE = f"""
    QWidget {{
        max-height: 40px;
    }}
"""

SETTINGS_TITLE_STYLE = f"""
    QLabel {{
        color: {color_text};
        margin-top: 1px;
        font-family: '{font_family}';
        font-size: {font_size_normal};
        font-weight: bold;
        padding: 6px;
        height: 30px;
        background: {color_surface_elevated};
        border-radius: {border_radius_small};
        min-width: 320px;
    }}
"""

# QGroupBox STYLES
QGROUP_BOX_STYLE = f"""
    QGroupBox {{
        font-family: '{font_family}';
        font-size: {font_size_normal};
        font-weight: bold;
        color: {color_accent};
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

# ACTION BUTTONS STYLE (SAVE, APPLY, ETC.)
ACTION_BUTTON_STYLE = f"""
    QPushButton {{
        background: {color_surface};
        border: {border_medium} transparent;
        border-radius: {border_radius_small};
        color: {color_text};
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
        background: {color_bg};
    }}
    QPushButton:focus {{
        border: {border_medium} {color_accent};
        background-color: {color_accent};
    }}
"""

# ACTION BUTTON ACTIVE STYLE (MANGOHUD, GAMESCOPE ETC.)
ACTION_BUTTON_ACTIVE_STYLE = f"""
    QPushButton {{
        background: {color_surface};
        border: {border_medium} {color_accent};
        border-radius: {border_radius_small};
        color: {color_text};
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
        background: {color_bg};
    }}
    QPushButton:focus {{
        border: {border_medium} {color_accent};
        background-color: {color_accent};
    }}
"""
