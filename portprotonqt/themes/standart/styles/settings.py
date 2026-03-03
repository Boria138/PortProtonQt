from .constants import *

SETTINGS_COMBO_STYLE = f"""
    QComboBox {{
        background: {color_c};
        border: {border_c} {color_g};
        border-radius: {border_radius_a};
        height: 34px;
        padding-left: 12px;
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
        border: {border_c} {color_a};
        border-top-style: none;
        border-top-left-radius: 0px;
        border-top-right-radius: 0px;
        border-bottom-left-radius: 10px;
        border-bottom-right-radius: 10px;
    }}
    QListView {{
        background: {color_c};
    }}
    QListView::item {{
        padding: 7px 7px 7px 12px;
        margin: 3px;
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

SETTINGS_CHECKBOX_STYLE = f"""
    QCheckBox {{
        color: {color_f};
        font-family: '{font_family}';
        font-size: 14px;
    }}
    QCheckBox::indicator {{
        width: 20px;
        height: 20px;
        border: 2px solid {color_f};
        border-radius: 4px;
        background: {color_b};
    }}
    QCheckBox::indicator:hover {{
        background: {color_c};
        border-color: {color_a};
    }}
    QCheckBox::indicator:focus {{
        border-color: {color_a};
    }}
    QCheckBox::indicator:checked {{
        image: url({theme_manager.get_icon("check", current_theme_name, as_path=True)});
        background: {color_a};
        border-color: {color_a};
    }}
"""
