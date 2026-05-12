from .constants import *

# GLOBAL STYLE FOR WINDOW (BACKGROUND), LABELS, BUTTONS
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

# PROGRESS BAR STYLE
PROGRESS_BAR_STYLE = f"""
    QProgressBar {{
        color: {color_f};
        background-color: {color_c};
        text-align: center;
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
    QProgressBar::chunk {{
        background-color: {color_a};
    }}
"""

# STATUS BAR STYLE
STATUS_BAR_STYLE = f"""
    QStatusBar {{
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
    }}
"""

# HINT BAR STYLE
HINT_BAR_STYLE = f"""
    QWidget {{
        max-height: 36px;
    }}
"""

# HINT LABEL STYLE
HINTS_LABEL_STYLE = f"""
    QWidget {{
        background: {color_h};
        font-family: '{font_family}';
        font-size: 13px;
        color: {color_f};
        font-weight: 600;
        letter-spacing: 0.75px;
    }}
"""

# MAIN WINDOW HEADER STYLE
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

# NAVIGATION AREA STYLE (TAB BUTTONS)
NAV_WIDGET_STYLE = f"""
    QWidget {{
        background: {color_h};
        border:  {border_a};
    }}
"""

# NAVIGATION TAB BUTTON STYLE
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

# SEARCH FIELD STYLE
SEARCH_EDIT_STYLE = f"""
    QLineEdit {{
        background-color: rgba(30, 30, 30, 0.50);
        border: {border_b} rgba(255, 255, 255, 0.5);
        border-radius: {border_radius_a};
        padding: 7px 14px;
        font-family: '{font_family}';
        font-size: {font_size_a};
        color: {color_f};
        min-height: 24px;
    }}
    QLineEdit:focus {{
        border: {border_b} {color_a};
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

# GAME CARD AREA STYLE (QWidget)
LIST_WIDGET_STYLE = """
    QWidget {
        background: none;
        border:  {border_a} {color_g};
        border-radius: 25px;
    }
"""

# LIBRARY TAB TITLE
INSTALLED_TAB_TITLE_STYLE = f"""
    QLabel {{
        font-family: '{font_family}';
        font-size: {font_size_b};
        color: {color_f};
    }}
"""

# ACTION BUTTONS STYLE (SAVE, APPLY, ETC.)
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

# ACTION BUTTON ACTIVE STYLE (MANGOHUD, GAMESCOPE ETC.)
ACTION_BUTTON_ACTIVE_STYLE = f"""
    QPushButton {{
        background: {color_c};
        border: {border_c} {color_a};
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

# DRIVES BUTTONS STYLE (FILE MANAGER)
DRIVES_BUTTON_STYLE = f"""
    QPushButton {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        color: {color_f};
        font-size: {font_size_a};
        font-family: '{font_family}';
        min-width: 90px;
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

# OVERLAY STYLE
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

# TEXT STYLES: HEADINGS AND MAIN CONTENT
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

# MAIN PAGES STYLE
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

THEME_TAB_FOCUS_STYLE = f"""
    QComboBox#themeTabCombo:focus {{
        border: {border_b} {color_f};
        background-color: {color_a};
    }}
    QPushButton#themeApplyButton:focus {{
        border: {border_b} {color_f};
    }}
    QGraphicsView#themeScreenshotsCarousel {{
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
    }}
    QGraphicsView#themeScreenshotsCarousel:focus {{
        border: {border_b} {color_a};
    }}
"""

# PORTPROTON SETTINGS TAB STYLES
# PARAMS_TITLE_STYLE
PARAMS_TITLE_STYLE = f"""
    QLabel {{
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        height: 34px;
        padding: 7px;
        background: {color_d};
        border-radius: {border_radius_a};
        min-width: 150px;
    }}
"""

# QMessageBox STYLES (MESSAGE BOXES)
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

# Transparent background style
TRANSPARENT_BACKGROUND_STYLE = f"""
    QWidget {{
        background: {color_h};
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
        padding-top: 14px;
        background: {color_h};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }}
"""

# COMBOBOX
COMBOBOX_STYLE = f"""
    QComboBox {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        padding-left: 12px;
        height: 34px;
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
        background: #2a2c35;
        border: {border_c} #2a2c35;
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
        height: 12px;
        width: 12px;
    }}
    QComboBox::down-arrow:on {{
        image: url({theme_manager.get_icon("up", current_theme_name, as_path=True)});
        padding: 12px;
        height: 12px;
        width: 12px;
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
        padding: 7px 7px 7px 12px;
        margin: 3px;
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

SCROLL_STYLE = f"""
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
        border: {border_c} {color_g};
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
        background: {color_b};
        border: {border_c} {color_d};
    }}
    QCheckBox::indicator:checked:disabled {{
        image: url({theme_manager.get_icon("check", current_theme_name, as_path=True)});
        background: {color_b};
        border: {border_c} {color_d};
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

TOOLTIP_STYLE = f"""
    QLabel {{
        background-color: {color_b};
        border: {border_b} {color_c};
        border-radius: {border_radius_a};
        padding: 8px;
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
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
        padding: 8px 16px;
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
