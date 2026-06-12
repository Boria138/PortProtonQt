from .constants import *

GETWINE_WINDOW_STYLE = f"""
/* Table */
QHeaderView::section {{
    background: {color_d};
    color: {color_f};
    border: {border_a};
    font-weight: bold;
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QTableWidget {{
    background: {color_h};
    gridline-color: {color_h};
    color: {color_f};
    alternate-background-color: {color_d};
    border: {border_a};
    border-radius: {border_radius_a};
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QTableWidget::item:!enabled {{
    color: #7a7a7a;
}}
QTableWidget::item:selected,
QTableWidget::item:selected:!active,
QTableWidget::item:hover {{
    background: {color_a};
}}
/* LogArea */
QFrame {{
    background: {color_h};
}}
QTextEdit {{
    background: {color_c};
    border: {border_a};
    border-radius: {border_radius_a};
    color: {color_f};
    font-family: '{font_family}';
    font-size: {font_size_a};
    padding: 5px;
}}
QProgressBar {{
    color: {color_f};
    background-color: {color_c};
    height: 34px;
    text-align: center;
    font-family: '{font_family}';
    font-size: {font_size_a};
}}
QProgressBar::chunk {{
    background-color: {color_a};
}}
"""

# Empty state label style
GETWINE_EMPTY_LABEL_STYLE = f"font-size: {font_size_a}; padding: 50px;"
