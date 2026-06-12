from .constants import *

WINETRICKS_TABBLE_STYLE = f"""
QTableWidget {{
    background: {color_h};
    color: {color_f};
    gridline-color: {color_h};
    alternate-background-color: {color_d};
    border: {border_a};
    border-radius: {border_radius_a};
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QHeaderView::section {{
    background: {color_d};
    color: {color_f};
    padding: 5px;
    border: {border_a};
    font-weight: bold;
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QTableWidget::item {{
    padding: 8px;
    border-bottom: {border_a } {color_c};
    height: 36px;
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
QTableWidget::item:selected:hover {{
    background: {color_a};
    color: {color_f};
}}
"""
