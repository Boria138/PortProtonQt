from portprotonqt.theme_manager import ThemeManager
from portprotonqt.config import ui_config

# THEME_INHERITS = "standart"

theme_manager = ThemeManager()
current_theme_name = ui_config.get_theme()

autoSizeButtonPadding = 16

detailCompactCoverFrameSize = 128
detailCompactCoverImageSize = 108
detailCompactContentSpacing = 5
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

# VARS
font_family = "Play"
font_size_a = "16px"
font_size_b = "24px"
border_a = "0px solid"
border_b = "1px solid"
border_c = "2px solid"
border_radius_a = "10px"
border_radius_b = "15px"
color_a = "#70b8ff"
color_b = "#F8F9FC"
color_c = "#F0F2F5"
color_d = "#E9ECEF"
color_e = "#DEE2E6"
color_f = "#212529"
color_g = "rgba(0, 0, 0, 0)"
color_h = "transparent"
color_i = "rgba(40, 42, 51, 0.9)"

MAIN_WINDOW_STYLE = f"""
    QWidget {{
        background: #d2d3db;
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

# QMessageBox STYLES (MESSAGE BOXES)
MESSAGE_BOX_STYLE = f"""
    QMessageBox {{
        background: #d2d3db;
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

# OTHER_PAGES_WIDGET_STYLE
OTHER_PAGES_WIDGET_STYLE= f"""
    QWidget {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 #d2d3db,
            stop:1 #9394a5
    );
        border-radius: 0px;
    }}
"""

# CAROUSEL_WIDGET_STYLE
CAROUSEL_WIDGET_STYLE= f"""
    QWidget {{
        background: {color_e};
        border-radius: 0px;
    }}
"""

SETTINGS_FRAME_STYLE = f"""
    QFrame {{
        background: {color_h};
        border:  {border_b} {color_c};
        border-radius: {border_radius_b};
    }}
"""

SETTINGS_FRAME_TITLE_STYLE = f"""
    QLabel {{
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        color: {color_f};
        background: {color_h};
        border:  {border_a} {color_c};
    }}
"""

SETTINGS_TITLE_STYLE = f"""
    QLabel {{
        color: {color_f};
        height: 34px;
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        padding: 7px;
        background: {color_b};
        border-radius: {border_radius_a};
        border:  {border_a} {color_c};
        min-width: 320px;
    }}
"""

SETTINGS_TITLE_CHECKBOX_STYLE = f"""
    QLabel {{
        color: {color_f};
        height: 34px;
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        padding: 7px;
        background: {color_h};
        border-radius: {border_radius_a};
        border:  {border_a} {color_c};
        min-width: 180px;
    }}
"""

# QGroupBox STYLES
QGROUP_BOX_STYLE = f"""
    QGroupBox {{
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        color: {color_a};
        border: {border_b} {color_c};
        border-radius: {border_radius_a};
        margin-top: 10px;
        margin-right: 10px;
        padding-top: 5px;
        background: {color_h};
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
        border: {border_c} #ffffff;
    }}
"""

# GAME NAME LABEL IN CARD (QLabel)
GAME_CARD_NAME_LABEL_STYLE = f"""
    QLabel {{
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        background-color: {color_h};
        border: {border_a} {color_h};
        padding: 14px, 7px, 3px, 7px;
        qproperty-wordWrap: true;
    }}
"""

# MAIN FRAME FOR GAME DETAILS
DETAIL_CONTENT_FRAME_STYLE = f"""
    QFrame {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 #d2d3db,
            stop:1 #9394a5
        );
        border:  {border_a} {color_g};
        border-radius: {border_radius_b};
    }}
"""

# FRAME UNDER COVER
COVER_FRAME_STYLE = f"""
    QFrame {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 #E9ECEF,
            stop:1 #d2d3db
        );
        border-radius: {border_radius_b};
        border:  {border_a} {color_g};
    }}
"""

# COVER LABEL BORDER RADIUS
COVER_LABEL_STYLE = f"border-radius: {border_radius_b};"

# DETAILS WIDGET (TEXT, DESCRIPTION)
DETAILS_WIDGET_STYLE = f"background: rgba(20,20,20,0.40); border-radius: {border_radius_b}; padding: 10px;"
COMPACT_DETAILS_WIDGET_STYLE = f"""
        QFrame, QWidget {{
            background: qradialgradient(
            cx:0.5, cy:0.5, radius:0.8,
                stop:0 #E9ECEF,
                stop:1 #d2d3db
            );
            border-radius: {border_radius_b};
            padding: 10px;
        }}
"""

# TITLE (HEADER) ON DETAIL PAGE
DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 32px; color: {color_a};"
COMPACT_DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 32px; color: {color_f}; background: {color_h};"

# DIVIDER LINE
DETAIL_PAGE_LINE_STYLE = f"background: {color_h}; margin: 0 0;"

# DESCRIPTION TEXT
DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_a}; color: {color_f}; line-height: 1.5;"
COMPACT_DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_a}; color: {color_f}; line-height: 1.5; background: {color_h};"

# PLAYTIME WIDGET (PLAYTIME)
COMPACT_PLAYTIME_WIDGET_STYLE = f"background: {color_h}; border-radius: {border_radius_b}; padding: 10px; margin: 10px 0 0 0;"

# ADDITIONAL INFO STYLES ON GAMES PAGE
LAST_LAUNCH_TITLE_STYLE = f"max-height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 #d2d3db); font-family: '{font_family}'; font-size: 11px; color: {color_f}; text-transform: uppercase; letter-spacing: 0.75px;"
LAST_LAUNCH_VALUE_STYLE = f"height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 #d2d3db); font-family: '{font_family}'; font-size: 13px; color: {color_f}; font-weight: 600; letter-spacing: 0.75px;"
PLAY_TIME_TITLE_STYLE = f"max-height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 #d2d3db); font-family: '{font_family}'; font-size: 11px; color: {color_f}; text-transform: uppercase; letter-spacing: 0.75px;"
PLAY_TIME_VALUE_STYLE = f"height: 16px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,stop:0 #E9ECEF,stop:1 #d2d3db); font-family: '{font_family}'; font-size: 13px; color: {color_f}; font-weight: 600; letter-spacing: 0.75px;"

# PLAY BUTTON STYLE
PLAY_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 #E9ECEF,
            stop:1 #d2d3db
        );
        border: {border_b} #ffffff;
        border-radius: {border_radius_a};
        font-size: {font_size_a};
        margin-top: 15px;
        color: {color_f};
        font-weight: bold;
        font-family: '{font_family}';
        padding: 5px 10px;
        min-width: 120px;
        min-height: 30px;
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
# STYLE FOR "ADD GAME" AND "BACK" BUTTONS ON DETAIL PAGE AND LIBRARY
ADDGAME_BACK_BUTTON_STYLE = f"""
    QPushButton {{
        background: qradialgradient(
        cx:0.5, cy:0.5, radius:0.8,
            stop:0 #E9ECEF,
            stop:1 #d2d3db
        );
        border: {border_b} #ffffff;
        border-radius: {border_radius_a};
        color: {color_f};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 5px 10px;
        min-width: 120px;
        min-height: 25px;
    }}
    QPushButton:hover {{
        background: {color_a};
    }}
    QPushButton:pressed {{
        background: {color_a};
    }}
"""

# SEARCH FIELD STYLE
SEARCH_EDIT_STYLE = f"""
    QLineEdit {{
        background: {color_b};
        border: {border_a};
        border-radius: {border_radius_a};
        padding: 5px 10px;
        font-family: '{font_family}';
        font-size: {font_size_a};
        color: {color_f};
        min-height: 25px;
    }}
    QLineEdit:hover {{
        border: {border_b} {color_a};
    }}
    QLineEdit:focus {{
        border: {border_b} {color_a};
    }}
"""

# NAVIGATION TAB BUTTON STYLE
NAV_BUTTON_STYLE = f"""
    NavLabel {{
        background: {color_h};
        padding: 6px 3px;
        margin: 10px 0 10px 10px;
        color: {color_i};
        font-family: '{font_family}';
        font-size: {font_size_a};
        text-transform: uppercase;
        border: {color_a};
        border-radius: 0px;
    }}
    NavLabel[checked = true] {{
        background: {color_h};
        color: {color_f};
        font-weight: normal;
        text-decoration: none;
        border-bottom: {border_c} {color_a};
        border-radius: 0px;
    }}
    NavLabel:hover {{
        background: {color_h};
        color: {color_f};
        border-bottom: {border_c} #7f7f7f;
    }}
    NavLabel[checked = true]:hover {{
        background: {color_h};
        color: {color_f};
        border-bottom: {border_c} {color_a};
    }}
"""
WINETRICKS_TABBLE_STYLE = f"""
QTableWidget {{
    background: {color_h};
    color: {color_f};
    gridline-color: {color_h};
    alternate-background-color: {color_e};
    border: {border_a};
    border-radius: {border_radius_a};
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QHeaderView::section {{
    background: {color_d};
    color: {color_f};
    padding: 2px;
    border: {border_a};
    font-weight: bold;
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QTableWidget::item {{
    padding: 3px;
    border-bottom: {border_a } {color_c};
    height: 32px;
}}
QTableWidget::item:selected,
QTableWidget::item:focus,
QTableWidget::item:selected:focus {{
    background: {color_a};
    color: {color_f};
    selection-background-color: {color_a};
}}
QTableWidget::item:hover {{
    background: {color_h};
}}
"""

SCROLL_STYLE = f"""
    QScrollBar:vertical {{
        width: 10px;
        border:  {border_a};
        border-radius: 5px;
        background: rgba(20, 20, 20, 0.20);
    }}
    QScrollBar::handle:vertical {{
        background: {color_c};
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
        background: rgba(20, 20, 20, 0.20);
    }}
    QScrollBar::handle:horizontal {{
        background: {color_c};
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

# COMBOBOX
COMBOBOX_STYLE = f"""
    QComboBox {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        padding-left: 12px;
        height: 30px;
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
    /* Focus state */
    QComboBox:focus {{
        border: {border_c} {color_a};
        background-color: {color_a};
    }}
    QComboBox:disabled {{
        background: {color_e};
        border: {border_c} {color_e};
        color: #777a84;
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
        background: {color_c};
        border: {border_c} {color_a};
        border-top-style: none;
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        border-bottom-left-radius: 10px;
        border-bottom-right-radius: 10px;
    }}
    QComboBox:editable {{
        background: {color_c};
    }}
    QComboBox::drop-down:editable:focus {{
        background: {color_a};
        border-top-left-radius: 0px;
        border-top-right-radius: 10px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 10px;
    }}
    QListView {{
        background: {color_c};
    }}
    QListView::item {{
        padding: 3px 3px 3px 6px;
        margin: 1px;
        min-height: 24px;
        border-radius: {border_radius_a};
        color: {color_f};
    }}
    QListView::item:hover {{
        background: {color_b};
    }}
    QListView::item:selected {{
        background: {color_b};
    }}
    /* Selection in list when item is focused */
    QListView::item:focus {{
        background: {color_a};
        color: {color_f};
    }}
"""

CHECKBOX_STYLE = f"""
    QCheckBox {{
        height: 34px;
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QCheckBox::indicator {{
        width: 24px;
        height: 24px;
        border: {border_c} #bfbfbf;
        border-radius: {border_radius_a};
        background: {color_c};
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
    QCheckBox::indicator:disabled {{
        background: {color_e};
        border: {border_c} {color_e};
    }}
    QCheckBox::indicator:checked:disabled {{
        image: url({theme_manager.get_icon("check", current_theme_name, as_path=True)});
        background: {color_e};
        border: {border_c} {color_e};
    }}

    QTableWidget::indicator {{
        width: 24px;
        height: 24px;
        border: {border_c} {color_h};
        border-radius: {border_radius_a};
        background: {color_b};
    }}
    QTableWidget::indicator:unchecked {{
        background: rgba(255, 255, 255, 0.1);
        image: none;
    }}
    QTableWidget::indicator:checked {{
        background: {color_b};
        image: url({theme_manager.get_icon("check", current_theme_name, as_path=True)});
        border: {border_c} {color_a};
    }}
    QTableWidget::indicator:hover {{
        background: rgba(255, 255, 255, 0.2);
        border: {border_c} {color_a};
    }}
    QTableWidget::indicator:focus {{
        background: rgba(255, 255, 255, 0.2);
        border: {border_c} {color_a};
    }}
    QTableWidget::indicator:disabled {{
        background: {color_b};
        border: {border_c} {color_d};
    }}
    QTableWidget::indicator:checked:disabled {{
        image: url({theme_manager.get_icon("check", current_theme_name, as_path=True)});
        background: {color_b};
        border: {border_c} {color_d};
    }}
"""

LINE_EDIT_STYLE = f"""
    QLineEdit {{
        background: {color_c};
        border: {border_c} rgba(255, 255, 255, 0.01);
        border-radius: {border_radius_a};
        height: 30px;
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

ADDGAME_INPUT_STYLE = f"""
    QLineEdit {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        height: 30px;
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

TAB_STYLE = f"""
    QTabWidget::pane {{
        border-top: 1px solid {color_c};
        background: {color_h};
    }}
    QTabBar::tab {{
        background: {color_c};
        color: {color_f};
        padding: 6px 12px;
        border-top-left-radius: {border_radius_a};
        border-top-right-radius: {border_radius_a};
        margin-right: 2px;
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QTabBar::tab:selected {{
        background: {color_a};
        color: {color_f};
    }}
    QTabBar::tab:hover {{
        background: {color_a};
    }}
"""

# HINT BAR STYLE
HINT_BAR_STYLE = f"""
    QWidget {{
        max-height: 36px;
    }}
"""

# QGroupBox STYLES
QGROUP_BOX_STYLE = f"""
    QGroupBox {{
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        color: {color_a};
        border: {border_b} {color_c};
        border-radius: {border_radius_a};
        margin-top: 10px;
        margin-right: 10px;
        padding-top: 5px;
        background: {color_h};
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
        background: {color_b};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        color: {color_f};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 5px 16px;
        min-height: 20px;
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

# ACTION BUTTON ACTIVE STYLE (MANGOHUD, GAMESCOPE ETC.)
ACTION_BUTTON_ACTIVE_STYLE = f"""
    QPushButton {{
        background: {color_c};
        border: {border_c} {color_a};
        border-radius: {border_radius_a};
        color: {color_f};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 5px 16px;
        min-height: 20px;
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
