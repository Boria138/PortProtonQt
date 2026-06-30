from .constants import *

# BACKGROUND FOR DETAIL PAGE IF COVER NOT LOADED
DETAIL_PAGE_NO_COVER_STYLE = f"background: {color_no_cover_bg}; border-radius: {border_radius_large};"

# STYLE FOR "ADD GAME" AND "BACK" BUTTONS ON DETAIL PAGE AND LIBRARY
ADDGAME_BACK_BUTTON_STYLE = f"""
    QPushButton {{
        background: {color_detail_overlay};
        border: {border_thin} {color_border_input};
        border-radius: {border_radius_small};
        color: {color_text};
        font-size: {font_size_normal};
        font-family: '{font_family}';
        padding: 8px 16px;
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
        background: {color_detail_overlay};
        border: {border_thin} {color_border_input};
        border-radius: {border_radius_small};
        color: {color_text};
        font-size: {font_size_normal};
        font-family: '{font_family}';
        padding: 8px 12px;
        min-width: 24px;
    }}
    QPushButton:hover,
    QPushButton:pressed,
    QPushButton:focus,
    QPushButton:checked {{
        background: {color_detail_overlay};
        border: {border_thin} {color_accent};
    }}
"""

# MAIN FRAME FOR GAME DETAILS
DETAIL_CONTENT_FRAME_STYLE = f"""
    QFrame {{
        background: {color_bg};
        border:  {border_none} transparent;
        border-radius: {border_radius_large};
    }}
"""

# FRAME UNDER COVER
COVER_FRAME_STYLE = f"""
    QFrame {{
        background: {color_cover_frame_bg};
        border-radius: {border_radius_large};
        border:  {border_none} transparent;
    }}
"""

# COVER WIDGET
COVER_WIDGET_STYLE = f"""
    QWidget {{
        background: {color_transparent};
        border:  {border_none} {color_transparent};
    }}
"""

# COVER LABEL BORDER RADIUS
COVER_LABEL_STYLE = f"border-radius: {border_radius_large};"

# DETAILS WIDGET (TEXT, DESCRIPTION)
DETAILS_WIDGET_STYLE = f"""
        QFrame {{
            background: {color_detail_overlay};
            border-radius: {border_radius_large};
            padding: 10px;
        }}
        QWidget#child {{
            background: {color_detail_overlay};
            border-radius: {border_radius_large};
            padding: 10px;
        }}
"""


COMPACT_DETAILS_WIDGET_STYLE = f"background: {color_detail_overlay}; border-radius: {border_radius_large}; padding: 10px;"

# TITLE (HEADER) ON DETAIL PAGE
DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: {font_size_title}; color: {color_accent}; background: {color_transparent};"
COMPACT_DETAIL_PAGE_TITLE_STYLE = f"font-family: '{font_family}'; font-size: {font_size_title}; color: {color_accent}; background: {color_transparent};"

# DIVIDER LINE
DETAIL_PAGE_LINE_STYLE = f"color: {color_detail_line}; margin: 0 0;"

# DESCRIPTION TEXT
DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_normal}; color: {color_text}; line-height: 1.5;"
COMPACT_DETAIL_PAGE_DESC_STYLE = f"font-family: '{font_family}'; font-size: {font_size_normal}; color: {color_text}; line-height: 1.5; background: {color_transparent};"

# PLAYTIME WIDGET (PLAYTIME)
COMPACT_PLAYTIME_WIDGET_STYLE = f"background: {color_transparent}; border-radius: {border_radius_large}; padding: 10px;"

# PLAY BUTTON STYLE
PLAY_BUTTON_STYLE = f"""
    QPushButton {{
        background: {color_detail_overlay};
        border: {border_thin} {color_border_input};
        border-radius: {border_radius_small};
        font-size: {font_size_play};
        color: {color_text};
        font-weight: bold;
        font-family: '{font_family}';
        padding: 8px 16px;
        margin-top: 15px;
        min-width: 120px;
        min-height: 40px;
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

ADDGAME_INPUT_STYLE = f"""
    QLineEdit {{
        background: {color_surface};
        border: {border_medium} transparent;
        border-radius: {border_radius_small};
        height: 34px;
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
