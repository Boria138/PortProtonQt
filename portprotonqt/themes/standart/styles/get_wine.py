from .constants import *

GETWINE_WINDOW_STYLE = f"""
/* TabWidget */
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
}}
QTabBar::tab:selected {{
    background: {color_a};
    color: {color_f};
}}
QTabBar::tab:hover {{
    background: {color_a};
}}
/* Table */
QHeaderView::section {{
    background: {color_d};
    color: {color_f};
    border: {border_a};
    font-weight: bold;
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
QTableWidget::item:focus {{
    background: {color_a};
}}
/* CheckBox */
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
/* ScrollBar */
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
/* LogArea */
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
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {color_a};
}}
"""
