from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config import ui_config

THEME_INHERITS = "standart-light"

theme_manager = ThemeManager()
current_theme_name = ui_config.get_theme()

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

# QColor constants for programmatic use
color_shadow_card = "#00000096"  # rgba(0, 0, 0, 150)
color_shadow_detail = "#000000c8"  # rgba(0, 0, 0, 200)
color_placeholder_bg = "#333333"
color_default_fallback = "#1a1a1a"
color_disabled_bg = "#f0f0f0"
color_disabled_text = "#777a84"
color_text_muted = "#bbbbbb"
color_accent_blue = "#007AFF"
color_gamepad_supported = "#00ff00"
color_white = "#ffffff"
missing_exe_cover_opacity = 0.45

# Shadow constants
shadow_blur_radius = 20
shadow_offset = (0, 0)
settings_tooltip_offset_x = 28
settings_tooltip_offset_y = 4
virtual_keyboard_slide_animation_duration = 160
virtual_keyboard_fade_animation_duration = 140
virtual_keyboard_slide_fade_animation_duration = 180
virtual_keyboard_slide_bounce_animation_duration = 220
virtual_keyboard_animation_type = "slide"

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

# VARS
font_family = "Play"
font_size_normal = "16px"
font_size_header = "24px"
border_none = "0px solid"
border_thin = "1px solid"
border_medium = "2px solid"
border_radius_small = "10px"
border_radius_large = "15px"
border_radius_card = "20px"
border_radius_badge = "5px"
color_accent = "#70b8ff"
color_bg = "#F8F9FC"
color_surface = "#F0F2F5"
color_surface_elevated = "#E9ECEF"
color_surface_hover = "#DEE2E6"
color_text = "#ffffff"
color_transparent = "transparent"
color_overlay = "rgba(40, 42, 51, 0.9)"
color_surface_light = "#d2d3db"
color_surface_mid = "#9394a5"
color_text_dark = "#212529"
combo_disabled_bg = "#dee2e6"
combo_disabled_border = "#dee2e6"
combo_disabled_text = "#777a84"
color_nav_inactive = "#7f7f7f"
color_separator = "#7f7f7f"
color_scrollbar_bg = "rgba(20, 20, 20, 0.20)"
color_scrollbar_handle = "#bfbfbf"
color_border_subtle = "rgba(255, 255, 255, 0.01)"
color_border_input = "rgba(255, 255, 255, 0.5)"
color_border_light = "rgba(255, 255, 255, 0.2)"
color_border_faint = "rgba(255, 255, 255, 0.05)"
color_checkbox_unchecked_bg = "rgba(255, 255, 255, 0.1)"
color_checkbox_hover_bg = "rgba(255, 255, 255, 0.2)"
color_favorite_star = "gold"
color_badge_steam_bg = "rgba(0, 0, 0, 0.5)"
color_badge_steam_text = "white"
color_badge_default_bg = "rgba(0, 0, 0, 0.5)"
color_badge_default_text = "white"
color_detail_overlay = "rgba(220, 222, 226, 0.40)"
color_cover_frame_bg = "rgba(233, 236, 239, 0.80)"
color_no_cover_bg = "rgba(220,222,226,0.95)"
color_detail_line = "rgba(0,0,0,0.12)"
color_preview_btn_bg = "rgba(0, 0, 0, 0.5)"
color_preview_btn_text = "white"
SOURCE_CORNER = {
    "ribbon_color": color_surface,
    "ribbon_fold_color": "#00000096",
    "size_ratio": 0.28,
    "min_size": 54,
    "min_widget_size": 4,
    "peel_start_ratio": 0.32,
    "peel_mid_ratio": 0.58,
    "peel_end_ratio": 0.82,
    "peel_shadow_width": 3,
    "fold_start_ratio": 0.60,
    "fold_end_ratio": 0.92,
    "icon_center_ratio": 0.84,
    "icon_size_ratio": 0.25,
    "min_icon_size": 8,
    "gradient_start": 0.0,
    "gradient_end": 1.0,
    "gradient_lighter": 145,
    "gradient_darker": 112,
    "fold_darker": 132,
}


def get_source_corner_config() -> dict:
    return SOURCE_CORNER


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
        border:  {border_none} {color_surface};
        min-width: 320px;
    }}
"""

# QGroupBox STYLES
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

# GAME CARD STYLE (GAMECARD)
GAME_CARD_WINDOW_STYLE = f"""
    QFrame {{
        border-radius: 20px;
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,
        stop:0 rgba(255, 255, 255, 0.9),
        stop:0.3 rgba(233, 236, 239, 0.9),
        stop:0.7 rgba(210, 211, 219, 0.9),
        stop:1 rgba(180, 190, 200, 0.9));
        border: {border_medium} {color_text};
    }}
"""

# COVER LABEL BORDER RADIUS
COVER_LABEL_STYLE = f"border-radius: {border_radius_large};"

# DETAILS WIDGET (TEXT, DESCRIPTION)
DETAILS_WIDGET_STYLE = f"background: {color_detail_overlay}; border-radius: {border_radius_large}; padding: 10px;"
COMPACT_DETAILS_WIDGET_STYLE = f"""
        QFrame, QWidget {{
            background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
                stop:0 #E9ECEF,
                stop:1 {color_surface_light}
            );
            border-radius: {border_radius_large};
            padding: 10px;
        }}
"""

# TITLE (HEADER) ON DETAIL PAGE
DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 32px; color: {color_accent};"
COMPACT_DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 32px; color: {color_text_dark}; background: {color_transparent};"

# DIVIDER LINE
DETAIL_PAGE_LINE_STYLE = f"background: {color_transparent}; margin: 0 0;"

# DESCRIPTION TEXT
DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_normal}; color: {color_text_dark}; line-height: 1.5;"
COMPACT_DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_normal}; color: {color_text_dark}; line-height: 1.5; background: {color_transparent};"

# PLAYTIME WIDGET (PLAYTIME)
COMPACT_PLAYTIME_WIDGET_STYLE = f"background: {color_transparent}; border-radius: {border_radius_large}; padding: 10px;"

# ADDITIONAL INFO STYLES ON GAMES PAGE
LAST_LAUNCH_TITLE_STYLE = f"max-height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 {color_surface_light}); font-family: '{font_family}'; font-size: 11px; color: {color_text_dark}; text-transform: uppercase; letter-spacing: 0.75px;"
LAST_LAUNCH_VALUE_STYLE = f"height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 {color_surface_light}); font-family: '{font_family}'; font-size: 13px; color: {color_text_dark}; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = f"max-height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 {color_surface_light}); font-family: '{font_family}'; font-size: 11px; color: {color_text_dark}; text-transform: uppercase; letter-spacing: 0.75px;"
PLAY_TIME_VALUE_STYLE = f"height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 {color_surface_light}); font-family: '{font_family}'; font-size: 13px; color: {color_text_dark}; font-weight: 600; letter-spacing: 0.75px;"

# PLAY BUTTON STYLE
PLAY_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 #E9ECEF,
            stop:1 {color_surface_light}
        );
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
            stop:0 #E9ECEF,
            stop:1 {color_surface_light}
        );
        border: {border_thin} {color_text};
        border-radius: {border_radius_small};
        color: {color_text_dark};
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
            stop:0 #E9ECEF,
            stop:1 {color_surface_light}
        );
        border: {border_thin} {color_text};
        border-radius: {border_radius_small};
        color: {color_text_dark};
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
            stop:0 #E9ECEF,
            stop:1 {color_surface_light}
        );
        border: {border_thin} {color_accent};
    }}
"""

LIBRARY_FILTER_COMBOBOX_STYLE = f"""
    QComboBox {{
        background: {color_bg};
        border: {border_thin} {color_text};
        border-radius: {border_radius_small};
        padding-left: 12px;
        height: 30px;
        color: {color_text_dark};
        font-family: '{font_family}';
        font-size: {font_size_normal};
        min-width: 120px;
        combobox-popup: 0;
    }}
    QComboBox:hover,
    QComboBox:focus{{
        background: {color_bg};
        border: {border_thin} {color_accent};
    }}
    QComboBox:on {{
        background: {color_bg};
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
        border-left: {border_thin} rgba(255, 255, 255, 0.05);
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
        color: {color_text_dark};
    }}
    QComboBox QAbstractItemView::item:hover,
    QComboBox QAbstractItemView::item:selected {{
        background: {color_accent};
        color: {color_text_dark};
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
        color: {color_text_dark};
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
        border-bottom: {border_medium} #7f7f7f;
    }}
    NavLabel[checked = true]:hover {{
        background: {color_transparent};
        color: {color_text_dark};
        border-bottom: {border_medium} {color_accent};
    }}
"""

WINETRICKS_TABBLE_STYLE = f"""
QTableWidget {{
    background: {color_transparent};
    color: {color_text_dark};
    gridline-color: {color_transparent};
    alternate-background-color: {color_surface_hover};
    border: {border_none};
    border-radius: {border_radius_small};
    font-family: '{font_family}';
    font-size: {font_size_normal};
}}
QHeaderView::section {{
    background: {color_surface_elevated};
    color: {color_text_dark};
    padding: 2px;
    border: {border_none};
    font-weight: bold;
    font-family: '{font_family}';
    font-size: {font_size_normal};
}}
QTableWidget::item {{
    padding: 3px;
    border-bottom: {border_none } {color_surface};
    height: 32px;
}}
QTableWidget::item:selected,
QTableWidget::item:focus,
QTableWidget::item:selected:focus {{
    background: {color_accent};
    color: {color_text_dark};
    selection-background-color: {color_accent};
}}
QTableWidget::item:hover {{
    background: {color_transparent};
}}
QTableWidget::item:selected:hover {{
    background: {color_accent};
    color: {color_text_dark};
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
        background: {color_surface_hover};
        border: {border_medium} {color_surface_hover};
        color: {combo_disabled_text};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: center right;
        border-left: {border_thin} rgba(255, 255, 255, 0.05);
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
        color: {color_text_dark};
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
        color: {color_text_dark};
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
        border: {border_medium} rgba(255, 255, 255, 0.01);
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
        border-top: 1px solid {color_surface};
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

# ACTION BUTTONS STYLE (SAVE, APPLY, ETC.)
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
        background: {color_bg};
    }}
    QPushButton:focus {{
        border: {border_medium} {color_accent};
        background-color: {color_accent};
    }}
"""
