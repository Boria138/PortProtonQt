from .constants import *

CONTEXT_MENU_STYLE = f"""
    QMenu {{
        background: {color_b};
        color: {color_f};
        font-family: '{font_family}';
        font-size: {font_size_a};
        padding: 5px;
        min-width: 150px;
        border: {border_b} {color_a};
        border-radius: {border_radius_a};
    }}
    QMenu::icon {{
        margin-left: 15px;
    }}
    QMenu::item {{
        padding: 10px 20px 10px 10px;
        background: {color_h};
        border-radius: {border_radius_a};
        color: {color_f};
    }}
    QMenu::item:selected {{
        background: {color_a};
        color: {color_f};
    }}
    QMenu::item:disabled {{
            color: #7f7f7f;
        }}
    QMenu::item:hover {{
        background: {color_a};
        color: {color_f};
    }}
    QMenu::item:focus {{
        background: {color_a};
        color: {color_f};
        border: {border_b} rgba(255, 255, 255, 0.3);
        border-radius: {border_radius_a};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: #7f7f7f;
        margin: 3px 6px;
    }}
"""

VIRTUAL_KEYBOARD_STYLE = f"""
QWidget {{
    background: {color_i};
}}
QPushButton {{
    font-size: 14px;
    border: {border_a} {color_h};
    border-radius: {border_radius_a};
    min-width: 30px;
    min-height: 30px;
    padding: 5px;
    background-color: {color_c};
    color: {color_f};
}}
QPushButton:hover {{
    background-color: {color_a};
    border: {border_b} {color_a};
}}
QPushButton:focus {{
    border: {border_b} {color_a};
    background-color: {color_a};
}}
QPushButton[vk_selected="true"] {{
    border: {border_b} {color_a};
    background-color: {color_a};
}}
QPushButton:pressed {{
    background-color: {color_c};
    border: {border_a} {color_h};
}}
QPushButton[checked="true"] {{
    background-color: {color_a};
    color: {color_f};
    border: {border_a} {color_h};
}}
QPushButton[checked="true"]:focus {{
    border: {border_b} {color_f};
}}
"""

# FULLSCREEN THEME SCREENSHOT PREVIEW STYLES
PREV_BUTTON_STYLE="background-color: rgba(0, 0, 0, 0.5); color: white; border: none;"
NEXT_BUTTON_STYLE="background-color: rgba(0, 0, 0, 0.5); color: white; border: none;"
