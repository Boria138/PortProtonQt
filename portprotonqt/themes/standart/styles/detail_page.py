from .constants import *

# BACKGROUND FOR DETAIL PAGE IF COVER NOT LOADED
DETAIL_PAGE_NO_COVER_STYLE = f"background: rgba(20,20,20,0.95); border-radius: {border_radius_b};"

# STYLE FOR "ADD GAME" AND "BACK" BUTTONS ON DETAIL PAGE AND LIBRARY
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
    QPushButton:focus {{
        background: {color_a};
        border: {border_b} {color_a};
    }}
"""

LIBRARY_CONTROLS_BUTTON_STYLE = f"""
    QPushButton {{
        background: rgba(20, 20, 20, 0.40);
        border: {border_b} rgba(255, 255, 255, 0.5);
        border-radius: {border_radius_a};
        color: {color_f};
        font-size: {font_size_a};
        font-family: '{font_family}';
        padding: 8px 12px;
        min-width: 24px;
    }}
    QPushButton:hover,
    QPushButton:pressed,
    QPushButton:focus,
    QPushButton:checked {{
        background: rgba(20, 20, 20, 0.40);
        border: {border_b} {color_a};
    }}
"""

LIBRARY_FILTER_COMBOBOX_STYLE = f"""
    QComboBox {{
        background: rgba(20, 20, 20, 0.40);
        border: {border_b} rgba(255, 255, 255, 0.5);
        border-radius: {border_radius_a};
        padding-left: 12px;
        height: 34px;
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
        min-width: 120px;
        combobox-popup: 0;
    }}
    QComboBox:hover,
    QComboBox:focus,
    QComboBox:on {{
        background: rgba(20, 20, 20, 0.40);
        border: {border_b} {color_a};
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
    QComboBox QAbstractItemView {{
        outline: none;
        background: {color_c};
        border: {border_b} {color_a};
        border-radius: {border_radius_a};
        color: {color_f};
        selection-background-color: {color_a};
        selection-color: {color_f};
    }}
    QComboBox QAbstractItemView::item {{
        background: {color_c};
        color: {color_f};
        padding: 6px 10px;
        min-height: 24px;
    }}
    QComboBox QAbstractItemView::item:hover,
    QComboBox QAbstractItemView::item:selected {{
        background: {color_a};
        color: {color_f};
    }}
"""

# MAIN FRAME FOR GAME DETAILS
DETAIL_CONTENT_FRAME_STYLE = f"""
    QFrame {{
        background: {color_b};
        border:  {border_a} {color_g};
        border-radius: {border_radius_b};
    }}
"""

# FRAME UNDER COVER
COVER_FRAME_STYLE = f"""
    QFrame {{
        background: rgba(30, 30, 30, 0.80);
        border-radius: {border_radius_b};
        border:  {border_a} {color_g};
    }}
"""

# COVER WIDGET
COVER_WIDGET_STYLE = f"""
    QWidget {{
        background: {color_h};
        border:  {border_a} {color_h};
    }}
"""

# COVER LABEL BORDER RADIUS
COVER_LABEL_STYLE = f"border-radius: {border_radius_b};"

# DETAILS WIDGET (TEXT, DESCRIPTION)
DETAILS_WIDGET_STYLE = f"""
        QFrame {{
            background: rgba(20,20,20,0.40);
            border-radius: {border_radius_b};
            padding: 10px;
        }}
        QWidget#child {{
            background: rgba(20,20,20,0.40);
            border-radius: {border_radius_b};
            padding: 10px;
        }}
"""


COMPACT_DETAILS_WIDGET_STYLE = f"background: rgba(20,20,20,0.40); border-radius: {border_radius_b}; padding: 10px;"

# TITLE (HEADER) ON DETAIL PAGE
DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 32px; color: {color_a}; background: {color_h};"
COMPACT_DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: 32px; color: {color_a}; background: {color_h};"

# DIVIDER LINE
DETAIL_PAGE_LINE_STYLE = "color: rgba(255,255,255,0.12); margin: 0 0;"

# DESCRIPTION TEXT
DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_a}; color: {color_f}; line-height: 1.5;"
COMPACT_DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_a}; color: {color_f}; line-height: 1.5; background: {color_h};"

# PLAYTIME WIDGET (PLAYTIME)
COMPACT_PLAYTIME_WIDGET_STYLE = f"background: {color_h}; border-radius: {border_radius_b}; padding: 10px;"

# PLAY BUTTON STYLE
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
        margin-top: 15px;
        min-width: 120px;
        min-height: 40px;
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
"""

# FUNCTION FOR DYNAMIC GRADIENT (GAME DETAILS)
# Functions from this theme always work regardless of selected theme, functions from other themes work only in those themes
def detail_page_style(stops):
    return f"""
    QWidget {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                    {stops});
                                    border-radius: 0px;
    }}
"""
