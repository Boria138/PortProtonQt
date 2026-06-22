from .constants import *

GETWINE_WINDOW_STYLE = f"""
/* Table */
QHeaderView::section {{
    background: {color_surface_elevated};
    color: {color_text};
    border: {border_none};
    font-weight: bold;
    font-family: '{font_family}';
    font-size: {font_size_normal};
}}
QTableWidget {{
    background: {color_transparent};
    gridline-color: {color_transparent};
    color: {color_text};
    alternate-background-color: {color_surface_elevated};
    border: {border_none};
    border-radius: {border_radius_small};
    font-family: '{font_family}';
    font-size: {font_size_normal};
}}
QTableWidget::item:!enabled {{
    color: {color_disabled_text};
}}
QTableWidget::item:selected,
QTableWidget::item:selected:!active,
QTableWidget::item:hover {{
    background: {color_accent};
}}
/* LogArea */
QFrame {{
    background: {color_transparent};
}}
QTextEdit {{
    background: {color_surface};
    border: {border_none};
    border-radius: {border_radius_small};
    color: {color_text};
    font-family: '{font_family}';
    font-size: {font_size_normal};
    padding: 5px;
}}
QProgressBar {{
    color: {color_text};
    background-color: {color_surface};
    height: 34px;
    text-align: center;
    font-family: '{font_family}';
    font-size: {font_size_normal};
}}
QProgressBar::chunk {{
    background-color: {color_accent};
}}
"""

# Empty state label style
GETWINE_EMPTY_LABEL_STYLE = f"font-size: {font_size_normal}; padding: 50px;"
