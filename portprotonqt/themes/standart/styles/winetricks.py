from .constants import *

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
    padding: 5px;
    border: {border_none};
    font-weight: bold;
    font-family: '{font_family}';
    font-size: {font_size_normal};
}}
QTableWidget::item {{
    padding: 8px;
    border-bottom: {border_none} {color_surface};
    height: 36px;
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
