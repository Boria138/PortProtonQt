from .constants import *

SETTINGS_FRAME_STYLE = f"""
    QFrame {{
        background: {color_b};
        border:  {border_a} {color_g};
        border-radius: {border_radius_b};
        margin-right: 10px;
    }}
"""

SETTINGS_FRAME_TITLE_STYLE = f"""
    QLabel {{
        font-family: '{font_family}';
        font-size: {font_size_a};
        font-weight: bold;
        color: {color_a};
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
        background: {color_d};
        border-radius: {border_radius_a};
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
        min-width: 180px;
    }}
"""

# Disabled line edit style
SETTINGS_DISABLED_INPUT_STYLE = f"background-color: {color_disabled_bg};"
